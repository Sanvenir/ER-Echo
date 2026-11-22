#!/usr/bin/env python3
"""通用 IPC 命令发送器（不依赖 shell 引号）。

`ipc_client.py` 的 `--args` 在 PowerShell 下会被剥掉内层双引号，传 JSON 很痛苦；
这个脚本用 `--arg k=v` 组装参数，值先按 JSON 解析，失败就当字符串。

用法：
  python tools/ipc_send.py ping
  python tools/ipc_send.py rebuild_clone --arg mode=model
  python tools/ipc_send.py rebuild_clone --arg mode=both
  python tools/ipc_send.py set_equipment --args-file tools\args.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

BRIDGE = pathlib.Path(__file__).resolve().parent.parent / "bridge"
sys.path.insert(0, str(BRIDGE))

from protocol import dumps, listen  # noqa: E402


def parse_value(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7811)
    ap.add_argument("--token", default="change-me")
    ap.add_argument("--wait", type=float, default=3.0)
    ap.add_argument("--arg", action="append", default=[], metavar="k=v")
    ap.add_argument("--args-file", default=None)
    args = ap.parse_args()

    payload: dict = {}
    if args.args_file:
        payload.update(json.loads(pathlib.Path(args.args_file).read_text(encoding="utf-8")))
    for item in args.arg:
        if "=" not in item:
            print(f"error: --arg needs k=v, got {item!r}", file=sys.stderr)
            raise SystemExit(2)
        key, raw = item.split("=", 1)
        payload[key] = parse_value(raw)

    sock, reader = listen(args.host, args.port, args.token, timeout=args.wait + 30)
    print("[ok] connected")
    sock.sendall(dumps({"type": "command", "cmd": args.cmd, "args": payload,
                        "token": args.token}))
    print(f"[sent] {args.cmd} {payload}")

    deadline = time.monotonic() + args.wait
    while time.monotonic() < deadline:
        try:
            msg = reader.read_line(timeout=0.25)
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] {exc}", file=sys.stderr)
            break
        if msg is None:
            continue
        print(json.dumps(msg, ensure_ascii=False, indent=2))
        if msg.get("type") == "ack":
            break
    sock.close()


if __name__ == "__main__":
    main()
