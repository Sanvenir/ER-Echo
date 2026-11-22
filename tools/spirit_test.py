#!/usr/bin/env python3
"""召唤限制 / 灵体外观 的实测脚本。

一条连接里发一串命令（DLL 每帧处理队列），然后读回盘上的 json 做断言：
  1. anywhere / multi_summon  —— 把「区域 + 已有召唤物 + 冷却」限制全关掉
  2. request_summon --trigger —— 直接写 SummonBuddyManager 的请求 spEffect
     （232000 = 我们改写的离群野狼三行 → 3 个克隆体；207000 = 拟态泪滴本体一行）
  3. clone_info               —— 克隆体是否真的出来了（等级/血量/距离/npc id）
  4. probe_spirit             —— 克隆体身上还有没有 295000/295200（骨灰外观）

用法：
  python tools/spirit_test.py                  # 默认 trigger 232000
  python tools/spirit_test.py --trigger 207000
  python tools/spirit_test.py --no-summon      # 只看现状
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

GAME = pathlib.Path.cwd()
BRIDGE = pathlib.Path(__file__).resolve().parent.parent / "bridge"
sys.path.insert(0, str(BRIDGE))

from protocol import dumps, listen  # noqa: E402

GLOW_IDS = {295000, 295200}


def read_json(name: str):
    path = GAME / name
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


class Ipc:
    def __init__(self, sock, reader, token: str):
        self.sock = sock
        self.reader = reader
        self.token = token
        self.pending: list[dict] = []

    def send(self, cmd: str, args: dict | None = None, wait: float = 10.0) -> dict | None:
        self.sock.sendall(dumps({"type": "command", "cmd": cmd, "args": args or {}, "token": self.token}))
        deadline = time.monotonic() + wait
        while time.monotonic() < deadline:
            ack = None
            for i, msg in enumerate(self.pending):
                if msg.get("cmd") == cmd:
                    ack = self.pending.pop(i)
                    break
            if ack is not None:
                ok = ack.get("ok")
                print(f"[{'ok' if ok else 'fail'}] {cmd}: {ack.get('msg') or ack.get('error') or ''}")
                return ack
            for msg in self._drain(0.25):
                if msg.get("type") == "ack":
                    self.pending.append(msg)
                elif msg.get("type") == "state":
                    pass
        print(f"[timeout] {cmd}", file=sys.stderr)
        return None

    def _drain(self, timeout: float):
        try:
            msg = self.reader.read_line(timeout=timeout)
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] {exc}", file=sys.stderr)
            return
        if msg is not None:
            yield msg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7811)
    ap.add_argument("--token", default="change-me")
    ap.add_argument("--no-summon", action="store_true")
    ap.add_argument("--trigger", type=int, default=232000, help="召唤请求用的 spEffect id")
    ap.add_argument("--wait", type=float, default=10.0, help="召唤后等克隆体出现的秒数")
    args = ap.parse_args()

    sock, reader = listen(args.host, args.port, args.token, timeout=180)
    ipc = Ipc(sock, reader, args.token)
    failures = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        if not ok:
            failures += 1
        print(f"{'PASS' if ok else 'FAIL'}  {name}{('  ' + detail) if detail else ''}")

    try:
        if not args.no_summon:
            ipc.send("anywhere", {"on": True})
            ipc.send("multi_summon", {"on": True})
            ipc.send("summon_state")
            ipc.send("request_summon", {"id": args.trigger})
            time.sleep(args.wait)

        ipc.send("clone_info", wait=20.0)
        clones = read_json("er_echo_clone_info.json") or {}
        rows = [r for r in clones.get("rows", []) if r.get("is_player_ins")]
        check("clones present", len(rows) >= 1, f"{len(rows)} PlayerIns clone(s)")
        for i, row in enumerate(rows):
            print(
                f"      clone[{i}] npc={row.get('npc_param_id')} name={row.get('name')} lv={row.get('level')} "
                f"hp={row.get('hp')} dist={row.get('distance')}"
            )

        ipc.send("probe_spirit", wait=25.0)
        spirit = read_json("er_echo_spirit.json") or {}
        for i, c in enumerate(spirit.get("clones", [])):
            ids = sorted({int(e["id"]) for e in c.get("speffects", [])})
            glow = sorted(set(ids) & GLOW_IDS)
            check(f"clone[{i}] npc={c.get('npc_param_id')} no ash-glow", not glow, f"speffects={ids}")
            print(
                f"      clone[{i}] phantom_override={c.get('phantom_param_override')} "
                f"base_transparency={c.get('base_transparency')} tint={c.get('tint_alpha_multiplier')}"
            )
        state = spirit.get("summon") or {}
        if state:
            print(
                "      manager: "
                f"req={state.get('request_summon_speffect_id')} "
                f"active={state.get('active_summon_speffect_id')} "
                f"range={state.get('is_within_activation_range')} "
                f"alive={state.get('player_has_alive_summon')} "
                f"cooldown={state.get('item_use_cooldown_timer')}"
            )
        stones = (spirit.get("stones") or {}).get("activate_range_max")
        check("buddy stone range widened", (stones or 0) >= 1000, f"max activate_range={stones}")
    finally:
        sock.close()

    print("ALL PASS" if failures == 0 else f"{failures} FAILED")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
