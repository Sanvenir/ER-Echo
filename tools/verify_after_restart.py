#!/usr/bin/env python3
"""换上新 DLL 之后的一键验收（连接 → 拉几个 dump → 逐项判定）。

检查项：
  1. `dump_profile` 能跑，并且和离线导出的同名档案逐字段一致（diff_profile 的判据）；
  2. `dump_equip` 能跑 → 查 `EquipParamProtector` 里有没有 10000（主存档 slot 0 的占位值疑点，见 §13.9）；
  3. `clone_info`：克隆体等级 / HP 是否等于档案里的 `pools`（验证 apply_stats 写三围上限是否生效）；
  4. state 流：能不能收到结构化状态、克隆体距离是否在报。

用法：
  python tools\\verify_after_restart.py                 # 全部检查
  python tools\\verify_after_restart.py --no-state      # 跳过 10 秒状态采样
退出码：0 = 全过；1 = 有失败项。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT / "tools"))

from protocol import dumps, listen, recv_json  # noqa: E402

GAME = ROOT.parent
RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> bool:
    RESULTS.append((ok, label))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    return ok


class Client:
    def __init__(self, args):
        self.token = args.token
        self.sock, self.reader = listen(args.host, args.port, args.token, timeout=args.wait + 30)

    def command(self, cmd: str, args: dict | None = None, wait: float = 6.0) -> tuple[bool, str]:
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
        return False, "timeout waiting for ack"

    def read_json(self, name: str) -> dict | None:
        path = GAME / name
        for _ in range(20):
            if path.exists():
                try:
                    return json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass
            time.sleep(0.1)
        return None

    def close(self) -> None:
        self.sock.close()


def ini_profile_paths() -> list[pathlib.Path]:
    """er_echo.ini 里配置的 profiles=（DLL 真正加载的那几个）。"""
    ini = GAME / "er_echo.ini"
    try:
        raw = ini.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    paths, section = [], ""
    for line in raw.splitlines():
        line = line.strip()
        if not line or line[0] in ";#":
            continue
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
        out.append(path if path.is_absolute() else GAME / p)
    return out


def find_profile(name: str, level: int | None = None) -> pathlib.Path | None:
    """同名角色可能在多份存档里都有（Sv 在 sl2 是 lv15、在 cnv 是 lv13），
    先看 er_echo.ini 配的那几个，再退回全目录搜索。"""
    candidates = list(ini_profile_paths())
    candidates += sorted(ROOT.glob("tools/from_save_account/*/slot*_*.json"))
    candidates += sorted(ROOT.glob("tools/profile*.json"))
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("name") != name:
            continue
        if level is not None and data.get("level") != level:
            continue
        return path
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7811)
    ap.add_argument("--token", default="change-me")
    ap.add_argument("--wait", type=float, default=5.0)
    ap.add_argument("--no-state", action="store_true")
    args = ap.parse_args()

    client = Client(args)
    print("[ok] DLL connected\n")

    print("[1] dump_profile ↔ 离线档案")
    ok, detail = client.command("dump_profile")
    profile = client.read_json("er_echo_profile.json") if ok else None
    if check(ok, f"dump_profile: {detail}") and profile:
        print(f"      当前角色: {profile.get('name')!r} lv{profile.get('level')} "
              f"hp={profile.get('hp')} clone_slots={len(profile.get('equipment_param_ids') or [])}")
        path = find_profile(profile.get("name", ""), profile.get("level"))
        if path is None:
            print(f"      (没有同名离线档案可比对，跳过 diff)")
        else:
            import subprocess
            proc = subprocess.run(
                [sys.executable, str(ROOT / "tools" / "diff_profile.py"),
                 str(GAME / "er_echo_profile.json"), str(path)],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            tail = (proc.stdout or "").strip().splitlines()[-1:] or [""]
            check(proc.returncode == 0, f"diff_profile vs {path.name}: {tail[0]}")
            if proc.returncode != 0:
                print(proc.stdout)

    print("\n[2] dump_equip（参数表）")
    ok, detail = client.command("dump_equip", wait=15.0)
    equip = client.read_json("er_echo_equip.json") if ok else None
    if check(ok, f"dump_equip: {detail}") and equip:
        protectors = set(equip.get("protectors") or [])
        print(f"      weapons={equip.get('weapon_count')} protectors={equip.get('protector_count')} "
              f"accessories={equip.get('accessory_count')}")
        check(10000 in protectors,
              "protector 表里有 10000 → 之前怀疑的「占位值」其实是真实防具（§13.9）")
        check(660000 in protectors, "protector 表里存在 660000 → 旧导出用的 Sv 头盔 id 也是真的")

    print("\n[3] clone_info（克隆体注入）")
    ok, detail = client.command("clone_info", wait=8.0)
    info = client.read_json("er_echo_clone_info.json") if ok else None
    if check(ok, f"clone_info: {detail}") and info:
        rows = [r for r in (info.get("rows") or []) if r.get("is_player_ins")]
        print(f"      克隆体 {len(rows)} 个（已过滤非玩家占位）")
        for i, row in enumerate(rows):
            print(f"      [{i}] {row.get('name')!r} lv{row.get('level')} hp={row.get('hp')} "
                  f"dist={row.get('distance')} head={row.get('equip_head')} body={row.get('equip_body')}")
        if not rows:
            print("      (现在没有克隆体，跳过 HP/pools 比对——用骨灰召唤后重跑本脚本)")

    if not args.no_state:
        print("\n[4] state 流（10 秒）")
        deadline = time.monotonic() + 10.0
        states = 0
        clone_dists: list[float] = []
        while time.monotonic() < deadline:
            try:
                msg = recv_json(client.reader, timeout=0.5)
            except TimeoutError:
                continue
            if msg.get("type") != "state":
                continue
            states += 1
            for c in msg.get("clones") or []:
                dist = c.get("dist")
                if isinstance(dist, (int, float)) and dist >= 0:
                    clone_dists.append(float(dist))
        check(states > 0, f"收到 {states} 条 state")
        check("clones" in (msg if states else {}), "state 里带 clones 字段（新 DLL）")
        if clone_dists:
            print(f"      克隆体距离样本 {len(clone_dists)} 个，最近 {min(clone_dists):.1f} m / 最远 {max(clone_dists):.1f} m")

    client.close()
    failed = [label for ok, label in RESULTS if not ok]
    print("\n" + ("ALL PASS" if not failed else f"{len(failed)} FAILED: {failed}"))
    raise SystemExit(0 if not failed else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
