#!/usr/bin/env python3
"""等玩家用骨灰召唤（state 里 clones>0），然后自动 dump 一次 clone_info。

用法：
  python tools/wait_for_summon.py --seconds 240
退出码：0 = 看到克隆体并 dump 成功；1 = 超时。
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7811)
    ap.add_argument("--token", default="change-me")
    ap.add_argument("--seconds", type=float, default=240.0)
    args = ap.parse_args()

    sock, reader = listen(args.host, args.port, args.token, timeout=args.seconds + 30)
    print("[ok] DLL connected; waiting for clones in state…", flush=True)
    deadline = time.monotonic() + args.seconds
    seen = 0
    while time.monotonic() < deadline:
        try:
            msg = recv_json(reader, timeout=0.5)
        except TimeoutError:
            continue
        if msg.get("type") != "state":
            continue
        clones = msg.get("clones") or []
        seen += 1
        if seen % 10 == 1:
            print(f"[state] clones={len(clones)} hp={msg.get('player', {}).get('hp', 0):.2f} "
                  f"{[round(c.get('dist', -1), 1) for c in clones]}", flush=True)
        if len(clones) > 0:
            print(f"[ok] {len(clones)} clone(s) in state; dumping clone_info…", flush=True)
            sock.sendall(dumps({"type": "command", "cmd": "clone_info", "args": {},
                                "token": args.token}))
            ack_deadline = time.monotonic() + 8
            while time.monotonic() < ack_deadline:
                try:
                    reply = recv_json(reader, timeout=0.5)
                except TimeoutError:
                    continue
                if reply.get("type") == "ack" and reply.get("cmd") == "clone_info":
                    print(f"[ack] clone_info ok={reply.get('ok')} {reply.get('detail', '')}")
                    break
            path = GAME / "er_echo_clone_info.json"
            for _ in range(20):
                if path.exists():
                    break
                time.sleep(0.1)
            if path.exists():
                info = json.loads(path.read_text(encoding="utf-8"))
                print(json.dumps(info, ensure_ascii=False, indent=2))
            sock.close()
            raise SystemExit(0)
    sock.close()
    print("[timeout] 没等到克隆体")
    raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
