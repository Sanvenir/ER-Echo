#!/usr/bin/env python3
"""从现有 profile 派生一份新档案（改装备槽/等级/属性），用于做「明显不同的外观」测试。

用法：
  # 把防具换成其他套装（id 从 er_echo_equip.json 的 protectors 里挑）
  python tools/make_profile.py --base tools/profile.live_test.json -o tools/profile.knight.json \
      --name Knight --slot 12=690000 --slot 13=690100 --slot 14=690200 --slot 15=690300

  # 只改等级
  python tools/make_profile.py --base tools/profile.live_test.json -o tools/profile.lv50.json --level 50

槽位编号（ChrAsm 22 槽）：
  0/1 左手/右手主武器   2/3 副武器   4/5 第三武器
  6..11 箭/弩矢          12 头 13 身 14 手 15 腿
  17..21 护符
空槽写 -1；0 也会被当成空（引擎里 -1 才是真正的空）。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

SLOT_COUNT = 22
STAT_KEYS = ["vigor", "mind", "endurance", "strength",
             "dexterity", "intelligence", "faith", "arcane"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--name", default=None)
    ap.add_argument("--level", type=int, default=None)
    ap.add_argument("--slot", action="append", default=[], metavar="IDX=PARAM_ID",
                    help="改某个装备槽，可重复")
    for key in STAT_KEYS:
        ap.add_argument(f"--{key}", type=int, default=None)
    args = ap.parse_args()

    profile = json.loads(pathlib.Path(args.base).read_text(encoding="utf-8"))
    equip = [int(x) for x in profile["equipment_param_ids"]]
    if len(equip) != SLOT_COUNT:
        raise SystemExit(f"base profile equipment_param_ids must have {SLOT_COUNT} entries")

    for pair in args.slot:
        idx_s, _, val_s = pair.partition("=")
        idx = int(idx_s)
        if not 0 <= idx < SLOT_COUNT:
            raise SystemExit(f"slot index out of range: {idx}")
        equip[idx] = int(val_s)

    profile["equipment_param_ids"] = equip
    if args.name:
        profile["name"] = args.name
        profile.setdefault("notes", "")
        profile["notes"] += f" | derived by make_profile.py from {pathlib.Path(args.base).name}"
    if args.level is not None:
        profile["level"] = args.level
    for key in STAT_KEYS:
        v = getattr(args, key)
        if v is not None:
            profile.setdefault("stats", {})[key] = v

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[ok] {out}: {profile['name']} lv{profile['level']}")
    print("     equip:", " ".join(f"{i}:{v}" for i, v in enumerate(equip) if v))


if __name__ == "__main__":
    try:
        main()
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
