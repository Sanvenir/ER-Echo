#!/usr/bin/env python3
"""分析 DLL 自动 dump 出来的 JSON，给出下一步要用的行 id。

用法：
  python tools/analyze_dump.py                 # 读游戏根目录三个 json
  python tools/analyze_dump.py --dir <game>

输出：
  - 骨灰行（BuddyParam）：按 trigger_sp_effect_id 分组；标出「玩家型/骑乘型」
  - 骑乘行（RideParam）：atk_chr_id=0（c0000）或 def_chr_id 是马/ Torrent 的行
  - 玩家 profile 摘要
  - 建议的 `set_rows` 命令
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

GAME = pathlib.Path(r"D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game")
MIMIC_NPC_PARAM = 133201000  # 社区值，仅作提示


def load(path: pathlib.Path):
    if not path.exists():
        print(f"[missing] {path.name}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"[bad] {path.name}: {exc}")
        return None


def analyze_buddies(data) -> list[dict]:
    rows = (data or {}).get("rows", [])
    if not rows:
        return []
    groups: dict[int, list[dict]] = {}
    for row in rows:
        groups.setdefault(row.get("trigger_sp_effect_id", -1), []).append(row)

    print(f"\n== BuddyParam: {len(rows)} rows, {len(groups)} trigger spEffects ==")
    interesting = []
    for sp, group in groups.items():
        # 只打印「多体」或「有 ridden / playerInit」的组，避免刷屏
        multi = len(group) > 1
        flags = []
        for r in group:
            if r.get("npc_param_id_ridden", -1) >= 0:
                flags.append("ridden")
            if r.get("npc_player_init_param_id", -1) >= 0:
                flags.append("playerInit")
            if r.get("pc_follow_type", 0):
                flags.append("follow")
        if multi or flags or any(r.get("npc_param_id") == MIMIC_NPC_PARAM for r in group):
            tag = ",".join(sorted(set(flags))) or "-"
            print(f"  sp={sp:<10} rows={len(group):<2} [{tag}]")
            for r in group:
                print("    " + json.dumps(r, ensure_ascii=False))
            interesting.extend(group)
    return interesting


def analyze_ride(data) -> list[dict]:
    rows = (data or {}).get("rows", [])
    if not rows:
        return []
    print(f"\n== RideParam: {len(rows)} rows ==")
    hits = []
    for r in rows:
        atk, dfn = r.get("atk_chr_id"), r.get("def_chr_id")
        if atk == 0 or dfn in (0, 8000, 80000000, 2600, 2500, 4360, 4361, 4362, 4363, 4364, 4365, 4366, 3160):
            hits.append(r)
            print("  " + json.dumps(r, ensure_ascii=False))
    if not hits:
        print("  (no c0000/mount rows matched; dumping all)")
        for r in rows[:20]:
            print("  " + json.dumps(r, ensure_ascii=False))
    return hits


def analyze_profile(data) -> None:
    if not data:
        return
    print("\n== player profile ==")
    print(f"  level={data.get('level')} hp={data.get('hp')} runes={data.get('rune_count')}")
    print(f"  stats={data.get('stats')}")
    eq = data.get("equipment_param_ids") or []
    used = [(i, v) for i, v in enumerate(eq) if v]
    print(f"  equipment: {used}")
    face = data.get("face") or {}
    print(f"  face: magic={face.get('magic')} size={face.get('buffer_size')} hex_len={len(face.get('hex',''))}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(GAME))
    args = ap.parse_args()
    root = pathlib.Path(args.dir)

    buddies = load(root / "er_echo_buddies.json")
    ride = load(root / "er_echo_ride.json")
    prof = load(root / "er_echo_profile.json")

    interesting = analyze_buddies(buddies)
    analyze_ride(ride)
    analyze_profile(prof)

    if interesting:
        # 建议：找 npc_param_id 属于 c0000 玩家模型的行（这里用 heuristics：有 playerInit 或 npc_param_id 是 8 位）
        print("\n== next ==")
        print("  挑一行作为克隆槽位，例如：")
        for r in interesting[:3]:
            print(f"  # buddy row {r.get('id')} -> npc={r.get('npc_param_id')} think={r.get('npc_think_param_id')}")
        print("  python tools/ipc_client.py set_rows --think <think行> --npc <npc行> --behavior <行为表行>")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
