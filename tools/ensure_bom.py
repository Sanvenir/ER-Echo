#!/usr/bin/env python3
"""给含非 ASCII 的 .ps1 补 UTF-8 BOM。

Windows PowerShell 5.1 在没有 BOM 时按系统 ANSI（GBK）读脚本，中文注释/字符串里的
字节会被拆坏，直接报 `UnexpectedToken` / `Missing closing '}'`。
（2026-11 反复踩过：编辑工具存盘会把 BOM 丢掉。）

用法：
    python tools/ensure_bom.py            # 修整个仓库的 .ps1
    python tools/ensure_bom.py a.ps1 b.ps1
"""

from __future__ import annotations

import pathlib
import sys

BOM = b"\xef\xbb\xbf"


def fix(path: pathlib.Path) -> str:
    data = path.read_bytes()
    has = data.startswith(BOM)
    text = data.decode("utf-8-sig")
    needs = any(ord(c) > 127 for c in text)
    if needs and not has:
        path.write_bytes(BOM + text.encode("utf-8"))
        return f"BOM added  {path}"
    if not needs and has:
        path.write_bytes(text.encode("utf-8"))
        return f"BOM removed {path}"
    return f"ok         {path}"


def main(argv: list[str]) -> int:
    repo = pathlib.Path(__file__).resolve().parent.parent
    targets = [pathlib.Path(a) for a in argv] if argv else sorted(repo.rglob("*.ps1"))
    changed = 0
    for p in targets:
        if not p.is_file():
            continue
        print(fix(p))
        changed += 1
    print(f"[done] checked {changed} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
