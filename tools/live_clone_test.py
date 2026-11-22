#!/usr/bin/env python3
"""克隆体注入 + LLM 工具的实机验证。

档案列表从 `er_echo.ini` 的 `[clone] profiles=` 读（那才是 DLL 真正加载的），
克隆体只统计 `is_player_ins == true` 的行（召唤物集合里还有个非玩家的占位史莱姆）。

用法：
  python tools\\live_clone_test.py            # 只读检查
  python tools\\live_clone_test.py --tools    # 额外做换装/加点/回滚（会真的改克隆体）
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
GAME = ROOT.parent
sys.path.insert(0, str(ROOT / "bridge"))

from protocol import dumps, listen, recv_json  # noqa: E402

FAILS: list[str] = []


def check(ok: bool, label: str) -> bool:
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    if not ok:
        FAILS.append(label)
    return ok


def ini_profiles() -> list[dict]:
    """读 er_echo.ini 里配置的 profiles=，返回 profile dict 列表。"""
    ini = GAME / "er_echo.ini"
    raw = ini.read_text(encoding="utf-8", errors="replace")
    section = ""
    paths = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line[0] in ";#[":
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip()
            continue
        if section != "clone":
            continue
        key, _, value = line.partition("=")
        if key.strip() == "profiles":
            paths = [p.strip() for p in value.split(",") if p.strip()]
    out = []
    for p in paths:
        path = pathlib.Path(p)
        if not path.is_absolute():
            path = GAME / p
        try:
            out.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[warn] profile {path}: {exc}")
    return out


class Client:
    def __init__(self, args):
        self.token = args.token
        self.sock, self.reader = listen(args.host, args.port, args.token, timeout=30)

    def command(self, cmd: str, args: dict | None = None, wait: float = 8.0) -> tuple[bool, str]:
        self.sock.sendall(dumps({"type": "command", "cmd": cmd, "args": args or {},
                                 "token": self.token}))
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            try:
                msg = recv_json(self.reader, timeout=0.5)
            except TimeoutError:
                continue
            if msg.get("type") == "ack" and msg.get("cmd") == cmd:
                return bool(msg.get("ok")), str(msg.get("detail", ""))
        return False, "ack timeout"

    def clones(self) -> list[dict]:
        ok, detail = self.command("clone_info")
        if not ok:
            print(f"  (clone_info 失败: {detail})")
            return []
        path = GAME / "er_echo_clone_info.json"
        for _ in range(20):
            if path.exists():
                break
            time.sleep(0.1)
        try:
            rows = json.loads(path.read_text(encoding="utf-8")).get("rows") or []
        except (OSError, json.JSONDecodeError):
            return []
        return [r for r in rows if r.get("is_player_ins")]

    def close(self) -> None:
        self.sock.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7811)
    ap.add_argument("--token", default="change-me")
    ap.add_argument("--tools", action="store_true", help="额外测试换装/加点/回滚")
    args = ap.parse_args()

    profiles = ini_profiles()
    if not profiles:
        print("[!] er_echo.ini 里没有 profiles=")
        raise SystemExit(2)
    print("loaded profiles (from er_echo.ini):")
    for path, prof in profiles:
        pools = prof.get("pools") or {}
        print(f"  - {prof.get('name')} lv{prof.get('level')} hp{pools.get('hp')} "
              f"({path.name})")

    client = Client(args)
    print("[ok] DLL connected\n")

    rows = client.clones()
    if not check(bool(rows), f"clone_info: {len(rows)} PlayerIns clone(s)"):
        client.close()
        raise SystemExit(1)

    print("\n[1] 等级 / 血量 vs 档案 pools")
    for i, row in enumerate(rows):
        prof = profiles[i % len(profiles)][1]
        hp = row.get("hp") or [0, 0]
        pools = prof.get("pools") or {}
        ok = row.get("level") == prof.get("level")
        if pools.get("hp"):
            ok = ok and hp[1] == pools["hp"]
        check(ok, f"clone[{i}] lv{row.get('level')} hp{hp} "
                  f"(profile {prof.get('name')} lv{prof.get('level')} hp{pools.get('hp')})")

    print("\n[2] 装备 22 槽 vs 档案")
    for i, row in enumerate(rows):
        prof = profiles[i % len(profiles)][1]
        got = row.get("equip") or []
        want = prof.get("equipment_param_ids") or []
        diff = {k: (a, b) for k, (a, b) in enumerate(zip(got, want)) if a != b}
        check(not diff, f"clone[{i}] equip 22/22" + (f" diff={diff}" if diff else ""))

    print("\n[3] state 流里的克隆体距离")
    deadline = time.monotonic() + 6
    dists: list[float] = []
    while time.monotonic() < deadline:
        try:
            msg = recv_json(client.reader, timeout=0.5)
        except TimeoutError:
            continue
        if msg.get("type") != "state":
            continue
        for c in msg.get("clones") or []:
            d = c.get("dist")
            if isinstance(d, (int, float)) and d >= 0:
                dists.append(float(d))
    check(bool(dists), f"state 距离样本 {len(dists)} 个"
                       + (f"，{min(dists):.1f}~{max(dists):.1f} m" if dists else ""))

    if args.tools:
        head_now = (rows[0].get("equip") or [None] * 22)[12]
        candidate = 660000 if head_now != 660000 else 630000
        print(f"\n[4] set_equipment head {head_now} -> {candidate}")
        ok, detail = client.command("set_equipment",
                                    {"who": "all", "loadout": {"head": candidate}})
        check(ok, f"set_equipment: {detail}")
        time.sleep(0.8)
        after = client.clones()
        got = (after[0].get("equip") or [None] * 22)[12] if after else None
        check(got == candidate, f"克隆体 head = {got}（期望 {candidate}）")

        ok, detail = client.command("rollback_equipment")
        check(ok, f"rollback_equipment: {detail}")
        time.sleep(0.8)
        back = client.clones()
        got = (back[0].get("equip") or [None] * 22)[12] if back else None
        check(got == head_now, f"回滚后 head = {got}（期望 {head_now}）")

        prof = profiles[0][1]
        vigor_now = (prof.get("stats") or {}).get("vigor") or 10
        want = min(99, vigor_now + 2)
        print(f"\n[5] set_stats vigor {vigor_now} -> {want}（±20% 内）")
        ok, detail = client.command("set_stats", {"who": 0, "vigor": want})
        check(ok, f"set_stats: {detail}")
        time.sleep(1.0)
        after = client.clones()
        if after:
            print(f"      clone[0] lv{after[0].get('level')} hp{after[0].get('hp')} "
                  f"vigor={after[0].get('vigor')} effective_vigor={after[0].get('effective_vigor')}")
            check(after[0].get("effective_vigor") == want,
                  f"effective_vigor = {after[0].get('effective_vigor')}（期望 {want}）")

    client.close()
    print("\n" + ("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
    raise SystemExit(0 if not FAILS else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
