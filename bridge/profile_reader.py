#!/usr/bin/env python3
"""角色档案（profile.json）读写与校验。

profile.json 由离线工具生成（见 tools/export_profile.md），格式：

{
  "v": 1,
  "source": {"slot": 3, "steam_id": "7656...", "exported_by": "ER Save Manager"},
  "name": "Tarnished",
  "level": 150,
  "stats": {"vigor": 60, "mind": 20, "endurance": 30, "strength": 50,
             "dexterity": 40, "intelligence": 10, "faith": 25, "arcane": 10},
  "equipment_param_ids": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  "face_hex": "ffffffff...",       // 0x12F 字节，FaceData 原块
  "body_type": 0,
  "summon_spirit_level": 10,
  "scadutree_blessing": 20,
  "ai": {"preset": "caster", "aggression": 0.5, "spell_rate": 1.0,
         "guard_rate": 0.2, "target_switch": 0.6},   // 可选：赐福菜单「队友 AI」写入
  "notes": ""
}

用法：
  python profile_reader.py profile.json          # 打印摘要 + 校验
  python profile_reader.py profile.json --json   # 输出规范化 JSON（给 DLL 用）
"""

from __future__ import annotations

import argparse
import base64
import json
import sys

FACE_SIZE = 0x12F
SLOT_COUNT = 22
STAT_KEYS = ["vigor", "mind", "endurance", "strength",
             "dexterity", "intelligence", "faith", "arcane"]

# ChrAsm / 存档 PGD+0x58 的槽位顺序
SLOT_NAMES = [
    "left_hand_1", "right_hand_1", "left_hand_2", "right_hand_2",
    "left_hand_3", "right_hand_3", "arrow_1", "bolt_1", "arrow_2", "bolt_2",
    "arrow_3", "bolt_3", "head", "body", "hands", "legs", "hair",
    "talisman_1", "talisman_2", "talisman_3", "talisman_4", "talisman_5",
]


class ProfileError(ValueError):
    pass


def load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return validate(data)


def validate(data: dict) -> dict:
    if data.get("v") != 1:
        raise ProfileError("profile.v must be 1")
    if not isinstance(data.get("name"), str) or not data["name"]:
        raise ProfileError("name is required")
    if not 1 <= int(data.get("level", 0)) <= 713:
        raise ProfileError("level out of range")
    stats = data.get("stats") or {}
    for key in STAT_KEYS:
        if not 1 <= int(stats.get(key, 0)) <= 99:
            raise ProfileError(f"stat {key} out of range (1..99)")
    equip = data.get("equipment_param_ids")
    if not isinstance(equip, list) or len(equip) != SLOT_COUNT:
        raise ProfileError(f"equipment_param_ids must be {SLOT_COUNT} entries")
    if any(int(x) < 0 for x in equip):
        raise ProfileError("equipment ids must be >= 0")

    face_hex = data.get("face_hex")
    face_b64 = data.get("face_b64")
    if face_hex:
        face = bytes.fromhex(face_hex)
    elif face_b64:
        face = base64.b64decode(face_b64)
    else:
        raise ProfileError("face_hex or face_b64 required")
    if len(face) != FACE_SIZE:
        raise ProfileError(f"face data must be 0x{FACE_SIZE:X} bytes, got {len(face)}")
    if not face.startswith(b"\xff\xff\xff\xffFACE"):
        raise ProfileError("face data missing FACE magic")
    data["face"] = face
    return data


def describe(data: dict) -> str:
    eq = data["equipment_param_ids"]
    lines = [
        f"name        : {data['name']}",
        f"level       : {data['level']}",
        f"stats       : " + " ".join(f"{k}={data['stats'][k]}" for k in STAT_KEYS),
        f"body_type   : {data.get('body_type', 0)}",
        f"spirit lvl  : {data.get('summon_spirit_level', 0)}",
        f"face bytes  : {len(data['face'])}",
        f"source      : {data.get('source', {})}",
    ]
    ai = data.get("ai")
    if isinstance(ai, dict):
        lines.append(
            "ai          : "
            f"{ai.get('preset', 'custom')} aggr={ai.get('aggression')} "
            f"spell={ai.get('spell_rate')} guard={ai.get('guard_rate')} "
            f"target={ai.get('target_switch')}"
        )
    lines.append("equipment   :")
    for name, item in zip(SLOT_NAMES, eq):
        if item:
            lines.append(f"  {name:14s} {item}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--json", action="store_true", help="输出规范化 JSON（不含 face 原始字节）")
    args = ap.parse_args()
    data = load(args.path)
    if args.json:
        out = {k: v for k, v in data.items() if k != "face"}
        out["face_hex"] = data["face"].hex()
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(describe(data))


if __name__ == "__main__":
    try:
        main()
    except (ProfileError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
