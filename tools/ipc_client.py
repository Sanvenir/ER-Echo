#!/usr/bin/env python3
"""ER Echo 手动 IPC 客户端：不跑 LLM，直接给游戏内 DLL 发命令。

用法（游戏已加载 er_echo.dll 且 sidecar 未占用端口时）：
  python tools/ipc_client.py dump_buddies
  python tools/ipc_client.py dump_ride
  python tools/ipc_client.py dump_profile
  python tools/ipc_client.py set_weights --aggression 0.7 --dodge_rate 0.3
  python tools/ipc_client.py ping

注意：DLL 是 TCP **server**（127.0.0.1:7811），同一时间只接受一个客户端；
运行本工具前先停掉 bridge/director.py。
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


WEIGHT_KEYS = [
    "aggression", "dodge_rate", "guard_rate", "combo_rate", "heal_priority",
    "spell_rate", "item_rate", "spacing", "target_switch",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7811)
    ap.add_argument("--token", default="change-me")
    ap.add_argument("--wait", type=float, default=3.0, help="等待回执秒数")
    ap.add_argument("--behavior", type=int, default=None, help="set_rows: NpcAiBehaviorProbability 行 id")
    ap.add_argument("--think", type=int, default=None, help="set_rows: NpcThinkParam 行 id")
    ap.add_argument("--npc", type=int, default=None, help="set_rows: NpcParam 行 id")
    ap.add_argument("--id", type=int, default=None, help="request_summon: spEffect id")
    ap.add_argument("--on", type=str, default=None, choices=["true", "false"], help="keep_summons: on/off")
    ap.add_argument("--path", type=str, default=None, help="load_profile: json path")
    ap.add_argument("--chara", type=int, default=None, help="spawn_debug: CharaInitParam id")
    ap.add_argument("--dy", type=float, default=None, help="spawn_debug: vertical offset (default 1.5)")
    ap.add_argument("--init", type=int, default=None, help="set_buddy_row: npc_player_init_param_id")
    ap.add_argument("--follow", type=int, default=None, help="set_buddy_row: pc_follow_type")
    ap.add_argument("--stats", type=str, default=None, choices=["true", "false"], help="apply_to_clone: write level/stats too")
    ap.add_argument("--paths", type=str, default=None, help="set_clone_profiles: comma-separated profile json paths")
    ap.add_argument("--dist", type=float, default=None, help="set_follow: follow distance (m)")
    ap.add_argument("--args", dest="args_json", default=None,
                    help="通用：直接给 args 的 JSON（如 set_equipment 的 loadout / set_stats 的加点）")
    ap.add_argument("--repeat", type=int, default=1,
                    help="set_weights: 重复次数（DLL 每次只混合 15%%，要多次才逼近目标）")
    ap.add_argument("--seq-start", type=int, default=1, help="set_weights: 起始 seq（必须递增 DLL 才会再收）")
    for slot in ("head", "body", "hands", "legs", "weapon_left", "weapon_right"):
        ap.add_argument(f"--{slot}", type=int, default=None, help=f"set_player_equipment: {slot} id")
    for key in WEIGHT_KEYS:
        ap.add_argument(f"--{key}", type=float, default=None)
    args = ap.parse_args()

    sock, reader = listen(args.host, args.port, args.token, timeout=args.wait + 30)
    print("[ok] connected")

    if args.args_json:
        # 通用入口：echos 只做形状校验，语义校验全在 DLL 里（白名单/存在性/clamp）
        payload = json.loads(args.args_json)
        sock.sendall(dumps({"type": "command", "cmd": args.cmd, "args": payload,
                            "token": args.token}))
        print(f"[sent] {args.cmd} {payload}")
    elif args.cmd == "set_weights":
        weights = {k: getattr(args, k) for k in WEIGHT_KEYS if getattr(args, k) is not None}
        if not weights:
            print("error: no weight given", file=sys.stderr)
            raise SystemExit(2)
        for i in range(max(1, args.repeat)):
            sock.sendall(dumps({"type": "weights", "seq": args.seq_start + i, "token": args.token,
                                "weights": weights, "strategy": "observe"}))
            if i + 1 < args.repeat:
                time.sleep(0.25)
        print(f"[sent] weights x{args.repeat} seq {args.seq_start}..{args.seq_start + args.repeat - 1} {weights}")
    elif args.cmd == "set_buddy_row":
        payload = {k: v for k, v in
                   (("id", args.id), ("npc", args.npc), ("think", args.think),
                    ("init", args.init), ("follow", args.follow))
                   if v is not None}
        sock.sendall(dumps({"type": "command", "cmd": args.cmd, "args": payload,
                            "token": args.token}))
        print(f"[sent] set_buddy_row {payload}")
    elif args.cmd == "spawn_debug":
        payload = {k: v for k, v in
                   (("npc", args.npc), ("think", args.think), ("chara", args.chara), ("dy", args.dy))
                   if v is not None}
        sock.sendall(dumps({"type": "command", "cmd": args.cmd, "args": payload,
                            "token": args.token}))
        print(f"[sent] spawn_debug {payload}")
    elif args.cmd == "set_rows":
        payload = {k: v for k, v in
                   (("behavior", args.behavior), ("think", args.think), ("npc", args.npc))
                   if v is not None}
        if not payload:
            print("error: give --behavior/--think/--npc", file=sys.stderr)
            raise SystemExit(2)
        sock.sendall(dumps({"type": "command", "cmd": args.cmd, "args": payload,
                            "token": args.token}))
        print(f"[sent] set_rows {payload}")
    elif args.cmd == "load_profile":
        payload = {"path": str(pathlib.Path(args.path).resolve())} if args.path else {}
        sock.sendall(dumps({"type": "command", "cmd": args.cmd, "args": payload,
                            "token": args.token}))
        print(f"[sent] load_profile {payload}")
    elif args.cmd == "set_player_equipment":
        payload = {k: getattr(args, k) for k in
                   ("head", "body", "hands", "legs", "weapon_left", "weapon_right")
                   if getattr(args, k) is not None}
        sock.sendall(dumps({"type": "command", "cmd": args.cmd, "args": payload,
                            "token": args.token}))
        print(f"[sent] set_player_equipment {payload}")
    elif args.cmd == "keep_summons":
        payload = {"on": (args.on or "true") == "true"}
        sock.sendall(dumps({"type": "command", "cmd": args.cmd, "args": payload,
                            "token": args.token}))
        print(f"[sent] keep_summons {payload}")
    elif args.cmd == "request_summon":
        payload = {"id": args.id} if args.id is not None else {}
        sock.sendall(dumps({"type": "command", "cmd": args.cmd, "args": payload,
                            "token": args.token}))
        print(f"[sent] request_summon {payload}")
    elif args.cmd == "set_clone_profiles":
        paths = [str(pathlib.Path(p.strip()).resolve())
                 for p in (args.paths or "").split(",") if p.strip()]
        if not paths:
            print("error: give --paths a,b,c", file=sys.stderr)
            raise SystemExit(2)
        sock.sendall(dumps({"type": "command", "cmd": args.cmd, "args": {"paths": paths},
                            "token": args.token}))
        print(f"[sent] set_clone_profiles {paths}")
    elif args.cmd == "apply_to_clone":
        payload = {"stats": (args.stats or "false") == "true"}
        sock.sendall(dumps({"type": "command", "cmd": args.cmd, "args": payload,
                            "token": args.token}))
        print(f"[sent] apply_to_clone {payload}")
    elif args.cmd in ("auto_apply", "apply_stats"):
        payload = {"on": (args.on or "true") == "true"}
        sock.sendall(dumps({"type": "command", "cmd": args.cmd, "args": payload,
                            "token": args.token}))
        print(f"[sent] {args.cmd} {payload}")
    elif args.cmd == "set_follow":
        payload = {"dist": args.dist} if args.dist is not None else {}
        sock.sendall(dumps({"type": "command", "cmd": args.cmd, "args": payload,
                            "token": args.token}))
        print(f"[sent] set_follow {payload}")
    else:
        sock.sendall(dumps({"type": "command", "cmd": args.cmd, "args": {},
                            "token": args.token}))
        print(f"[sent] {args.cmd}")

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
