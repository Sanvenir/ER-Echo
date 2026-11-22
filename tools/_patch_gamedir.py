#!/usr/bin/env python3
"""一次性补丁：把各脚本里「从 PSScriptRoot 猜游戏目录」改成用 tools/gamedir.ps1。

源码 2026-11-21 从 <Game>\\er-echo 搬到 D:\\Projects\\ER-Echo，原来的
`Split-Path -Parent (Split-Path -Parent $PSScriptRoot)` / `Split-Path -Parent $repo`
全部失效，这里逐文件替换并校验，改完保留原有 UTF-8 BOM 状态。
"""

from __future__ import annotations

import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent

HELPER_CALL = (". (Join-Path $PSScriptRoot 'gamedir.ps1')\n"
               "$game = Get-ErEchoGameDir   # 源码已搬出游戏目录，统一走探测（见 gamedir.ps1）")

# 直接换成「dot-source + 探测」的老写法：$game = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
SIMPLE = {
    "tools/auto_start.ps1",
    "tools/enter_game.ps1",
    "tools/install_plugin.ps1",
    "tools/reset_to_vanilla.ps1",
}

# $game = Split-Path -Parent $repo   （打包脚本）
FROM_REPO = {
    "tools/package_plugin.ps1",
    "tools/package_release.ps1",
    "tools/package_nexus.ps1",
    "tools/package_payload.ps1",
}


def patch(path: pathlib.Path, pairs: list[tuple[str, str]], must: int = 1) -> str:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    total = 0
    for old, new in pairs:
        n = text.count(old)
        if n == 0:
            return f"SKIP {path}: pattern not found: {old.splitlines()[0][:60]!r}"
        total += n
        text = text.replace(old, new)
    if total < must:
        return f"SKIP {path}: {total} < {must}"
    data = text.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)
    return f"OK   {path}: {total} replacement(s)"


def main() -> int:
    results: list[str] = []

    for rel in sorted(SIMPLE):
        p = REPO / rel
        text = p.read_text(encoding="utf-8-sig")
        m = re.search(r"(?m)^\$game = Split-Path -Parent \(Split-Path -Parent \$PSScriptRoot\).*$", text)
        if not m:
            results.append(f"SKIP {rel}: no simple pattern")
            continue
        results.append(patch(p, [(m.group(0), HELPER_CALL)]))

    for rel in sorted(FROM_REPO):
        p = REPO / rel
        text = p.read_text(encoding="utf-8-sig")
        m = re.search(r"(?m)^\$game = Split-Path -Parent \$repo.*$", text)
        if not m:
            results.append(f"SKIP {rel}: no repo pattern")
            continue
        results.append(patch(p, [(m.group(0), HELPER_CALL)]))

    # doctor.ps1：默认目标
    p = REPO / "tools/doctor.ps1"
    old = "    $Target = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)"
    new = ("    . (Join-Path $PSScriptRoot 'gamedir.ps1')\n"
           "    $Target = Get-ErEchoGameDir")
    results.append(patch(p, [(old, new)]))

    # switch_menu_mode.ps1：整块改成 repo + 插件布局
    p = REPO / "tools/switch_menu_mode.ps1"
    old = """$game = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$ini = Join-Path $game 'er_echo.ini'
$talk = Join-Path $game 'mod\\script\\talk\\m00_00_00_00.talkesdbnd.dcx'

$source = if ($Mode -eq 'nested') {
    Join-Path $game 'er-echo\\ui\\out_vanilla\\m00_00_00_00.talkesdbnd.dcx'
} else {
    Join-Path $game 'er-echo\\ui\\out_rootmenu\\m00_00_00_00.talkesdbnd.dcx'
}"""
    new = """. (Join-Path $PSScriptRoot 'gamedir.ps1')
$repo = Split-Path -Parent $PSScriptRoot      # 源码根（ESD 构建产物在这里）
$game = Get-ErEchoGameDir

# 插件布局（mods\\ER-Echo\\）优先，老平铺布局兜底
$ini = Join-Path $game 'mods\\ER-Echo\\er_echo.ini'
if (-not (Test-Path -LiteralPath $ini)) { $ini = Join-Path $game 'er_echo.ini' }
$talk = Join-Path $game 'mods\\ER-Echo\\mod\\script\\talk\\m00_00_00_00.talkesdbnd.dcx'
if (-not (Test-Path -LiteralPath (Split-Path -Parent $talk))) {
    $talk = Join-Path $game 'mod\\script\\talk\\m00_00_00_00.talkesdbnd.dcx'
}

$source = if ($Mode -eq 'nested') {
    Join-Path $repo 'ui\\out_vanilla\\m00_00_00_00.talkesdbnd.dcx'
} else {
    Join-Path $repo 'ui\\out_rootmenu\\m00_00_00_00.talkesdbnd.dcx'
}"""
    results.append(patch(p, [(old, new)]))

    # mod/build.ps1：游戏目录探测 + 优先插件布局
    p = REPO / "mod/build.ps1"
    old = "$game = Split-Path -Parent $root                   # ELDEN RING/Game"
    new = (". (Join-Path $root 'tools\\gamedir.ps1')\n"
           "try { $game = Get-ErEchoGameDir } catch { $game = $null }   # 只用于顺手拷 DLL，找不到就跳过")
    results.append(patch(p, [(old, new)]))

    old = """    $live = Join-Path $game 'er_echo.dll'
    $staged = Join-Path $game 'er_echo.new.dll'
    try {
        Copy-Item $dll $live -Force -ErrorAction Stop"""
    new = """    if (-not $game) {
        Write-Host '[i] 没找到游戏目录，跳过拷贝（只编译）'
        return
    }
    # 插件布局优先：mods\\ER-Echo\\；没有就退回游戏根目录的平铺布局
    $pluginDir = Join-Path $game 'mods\\ER-Echo'
    $live = if (Test-Path -LiteralPath $pluginDir) { Join-Path $pluginDir 'er_echo.dll' } else { Join-Path $game 'er_echo.dll' }
    $staged = Join-Path (Split-Path -Parent $live) 'er_echo.new.dll'
    try {
        Copy-Item $dll $live -Force -ErrorAction Stop"""
    results.append(patch(p, [(old, new)]))

    for line in results:
        print(line)
    bad = [r for r in results if r.startswith("SKIP")]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
