#!/usr/bin/env python3
"""把 DLL 的运行时 dump（er_echo_profile.json）转成可直接加载的 profile.json。

用法：
  python tools/dump_to_profile.py er_echo_profile.json -o profiles/slot2.json --name "Slot 2"

来源是「当前游戏里正在玩的那个角色」——同一台机器上切换存档（读另一个槽）再 dump 一次，
就能得到第二份档案；`set_clone_profiles --paths a.json,b.json` 即可一次召唤多个不同角色。

注意：equipment_param_ids 里空槽在 dump 里是 -1，profile 规范要求 >= 0，这里统一写成 0。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

FACE_SIZE = 0x12F
SLOT_COUNT = 22
STAT_KEYS = ["vigor", "mind", "endurance", "strength",
             "dexterity", "intelligence", "faith", "arcane"]


def convert(dump: dict, name: str, notes: str) -> dict:
    stats = dump.get("stats") or {}
    equip = [int(x) for x in dump.get("equipment_param_ids") or []]
    if len(equip) != SLOT_COUNT:
        raise SystemExit(f"equipment_param_ids must have {SLOT_COUNT} entries, got {len(equip)}")
    equip = [0 if x < 0 else x for x in equip]

    face = dump.get("face") or {}
    face_hex = face.get("hex") or ""
    if len(face_hex) // 2 != FACE_SIZE:
        # 旧 DLL 只导出 276 字节运行时缓冲：补回 0x12F 块头 + 11 字节尾。
        payload_hex = face.get("payload_hex") or face_hex
        if len(payload_hex) // 2 not in (276, 288):
            raise SystemExit("dump has no usable face data (old DLL?)")
        payload = bytes.fromhex(payload_hex)
        size = int(face.get("buffer_size", 288))
        block = (b"\xff\xff\xff\xff" + b"FACE"
                 + int(face.get("version", 0)).to_bytes(4, "little")
                 + size.to_bytes(4, "little")
                 + payload)
        face_hex = block.ljust(FACE_SIZE, b"\x00")[:FACE_SIZE].hex()
    if len(face_hex) // 2 != FACE_SIZE:
        raise SystemExit(f"face must be 0x{FACE_SIZE:X} bytes, got {len(face_hex)//2}")

    profile = {
        "v": 1,
        "source": {
            "slot": 0,
            "steam_id": "",
            "exported_by": "er-echo tools/dump_to_profile.py (live dump)",
        },
        "name": name,
        "level": int(dump["level"]),
        "stats": {k: int(stats.get(k, 1)) for k in STAT_KEYS},
        "equipment_param_ids": equip,
        "face_hex": face_hex,
        "body_type": 0,
        "scadutree_blessing": int(dump.get("scadutree_blessing", 0) or 0),
        "notes": notes,
    }
    # 新 DLL 的 dump 直接给了三围上限（引擎算好的最终值），一起带上
    pools = {}
    for key in ("hp", "fp", "stamina"):
        part = dump.get(key) or {}
        max_v = part.get("max") or part.get("base_max")
        if max_v:
            pools[key] = int(max_v)
    if len(pools) == 3:
        profile["pools"] = pools
    return profile


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dump", nargs="?", default="er_echo_profile.json")
    ap.add_argument("-o", "--out", default="profiles/from_dump.json")
    ap.add_argument("--name", default="Live Tarnished")
    ap.add_argument("--notes", default="exported from a live er_echo_profile.json dump")
    args = ap.parse_args()

    with open(args.dump, "r", encoding="utf-8") as fh:
        dump = json.load(fh)
    profile = convert(dump, args.name, args.notes)

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"[ok] wrote {out} ({out.stat().st_size} bytes): {profile['name']} lv{profile['level']}")
    print("     equip:", [x for x in profile["equipment_param_ids"] if x][:8], "...")


if __name__ == "__main__":
    try:
        main()
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
