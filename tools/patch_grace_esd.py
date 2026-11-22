#!/usr/bin/env python3
"""Add ER Echo companion controls to the site-of-grace talk script.

Fallback after the nested-menu experiments: put the controls directly in the
**root** grace list. This is the same mechanism as vanilla options and is the
only variant confirmed working in-game (2026-11-16).

    AddTalkListData(61, 69100001, -1)   # 队伍人数（点击 0→1→2→3→0）
    AddTalkListData(62, 69100002, -1)   # 1 号位（点击循环档案）
    AddTalkListData(63, 69100003, -1)   # 2 号位
    AddTalkListData(64, 69100004, -1)   # 3 号位
    AddTalkListData(65, 69100005, -1)   # 立即重新召唤

The nested version (x900 + ShowShopMessage) kept either opening a blank menu
(ESDLang moved the menu events to an `Unused` state) or returning to the root
list immediately. Reference mods (erdGameTools / elden-ring-transmog) get
nested menus by injecting `er::ezstate` states into the live talk machine in
C++, not by recompiling the ESD file. Porting that is a separate project; until
then the root options are the reliable UI.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(ROOT, "er-echo", "ui", "esd", "py", "t000001000.py")
DST = os.path.join(ROOT, "er-echo", "ui", "esd", "edit", "t000001000.py")

ROOT_OPTIONS = '''        AddTalkListData(61, 69100001, -1)
        AddTalkListData(62, 69100002, -1)
        AddTalkListData(63, 69100003, -1)
        AddTalkListData(64, 69100004, -1)
        AddTalkListData(65, 69100005, -1)
'''

HANDLERS = '''        elif GetTalkListEntryResult() == 61:
            """State 60"""
            SetEventFlag(6728, FlagState.On)
        elif GetTalkListEntryResult() == 62:
            """State 61"""
            SetEventFlag(6724, FlagState.On)
        elif GetTalkListEntryResult() == 63:
            """State 62"""
            SetEventFlag(6725, FlagState.On)
        elif GetTalkListEntryResult() == 64:
            """State 63"""
            SetEventFlag(6726, FlagState.On)
        elif GetTalkListEntryResult() == 65:
            """State 64"""
            SetEventFlag(6727, FlagState.On)
'''


def main() -> int:
    with open(SRC, "r", encoding="utf-8") as f:
        text = f.read()

    if "AddTalkListData(61, 69100001" in text:
        print("already patched")
        return 0

    needle = '''        ClearTalkListData()
        """State 2"""
        AddTalkListDataIf(not GetEventFlag(9411) or GetEventFlag(9412), 1, 15000420, -1)'''
    if needle not in text:
        print("ERROR: could not find grace list start", file=sys.stderr)
        return 1
    text = text.replace(
        needle,
        '''        ClearTalkListData()
        """State 2"""
''' + ROOT_OPTIONS + '''        AddTalkListDataIf(not GetEventFlag(9411) or GetEventFlag(9412), 1, 15000420, -1)''',
        1,
    )

    needle = "        elif GetTalkListEntryResult() == 75:\n"
    if needle not in text:
        print("ERROR: could not find result 75 branch", file=sys.stderr)
        return 1
    text = text.replace(needle, HANDLERS + needle, 1)

    os.makedirs(os.path.dirname(DST), exist_ok=True)
    with open(DST, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"wrote {DST} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
