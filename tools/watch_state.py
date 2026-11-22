#!/usr/bin/env python3
"""监听 DLL 的 state 流（只读，不发权重/命令）。

用途：
  * 确认 DLL 真的在上报战斗状态（LLM 能不能看见）；
  * 看克隆体的真实距离 / 血量比例（跟随、注入是否生效）；
  * 看事件是否在正确时机触发（player_low_hp / enemy_engaged / clone_summoned …）。

用法：
  python tools/watch_state.py --seconds 30
  python tools/watch_state.py --seconds 30 --raw      # 打印原始 NDJSON
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

BRIDGE = pathlib.Path(__file__).resolve().parent.parent / "bridge"
sys.path.insert(0, str(BRIDGE))

from protocol import listen, recv_json  # noqa: E402


def summarize(msg: dict) -> str:
    player = msg.get("player") or {}
    clones = msg.get("clones") or []
    enemy = msg.get("enemy")
    events = msg.get("events") or []
    parts = [
        f"hp={player.get('hp', 0):.2f}",
        f"fp={player.get('fp', 0):.2f}",
        f"lv={player.get('level', 0)}",
        f"clones={len(clones)}",
    ]
    for c in clones:
        parts.append(
            f"[{c.get('name') or c.get('npc')} lv{c.get('level', '?')} "
            f"hp{c.get('hp', 0):.2f} d{c.get('dist', -1):.1f}]"
        )
    if enemy:
        parts.append(f"enemy_dist={enemy.get('dist', -1):.1f}")
    if events:
        parts.append("events=" + ",".join(events))
    return " ".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7811)
    ap.add_argument("--token", default="change-me")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--raw", action="store_true")
    args = ap.parse_args()

    sock, reader = listen(args.host, args.port, args.token, timeout=args.seconds + 30)
    print(f"[ok] DLL connected; listening for state ({args.seconds:.0f}s)")
    deadline = time.monotonic() + args.seconds
    count = 0
    try:
        while time.monotonic() < deadline:
            try:
                msg = recv_json(reader, timeout=0.5)
            except TimeoutError:
                continue
            kind = msg.get("type")
            if kind == "state":
                count += 1
                if args.raw:
                    print(json.dumps(msg, ensure_ascii=False))
                else:
                    print(f"[state {count:03d}] {summarize(msg)}")
            elif kind == "ack":
                print(f"[ack] {msg.get('cmd')}: ok={msg.get('ok')} {msg.get('detail', '')}")
    finally:
        sock.close()
    print(f"[done] {count} state(s) in {args.seconds:.0f}s")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
