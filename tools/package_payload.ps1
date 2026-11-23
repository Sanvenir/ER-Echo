#requires -Version 5.1
<#
.SYNOPSIS
  生成安装器 payload（随 setup exe 一起发布的文件），输出到 er-echo\build\payload。

.DESCRIPTION
  布局：
      build\payload\
        shared\            装到插件目录的公共文件
          er_echo.dll
          profiles\profile.example.json
          docs\*.md
          LICENSES\*
          README-PLUGIN.txt
        me2\               原版 / Mod Engine 2 目标
          config-er-echo.toml      -> <Game>\config-er-echo.toml
          plugin\                  -> <Game>\mods\ER-Echo\
            launch-er-echo.bat
            launch-er-echo-admin.bat
            mod\script\talk\m00_00_00_00.talkesdbnd.dcx   （赐福菜单必需）
        me3\               原版之外，Convergence 目标才用
          （默认留空：不覆盖 Convergence 自己的 talk ESD）

  tools\build_gui_exe.ps1 会用 --add-data 把它塞进 exe（onedir 的 _internal\payload）。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\package_payload.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [string]$OutDir,
    [string]$Version = '0.1.0'
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot          # er-echo/
. (Join-Path $PSScriptRoot 'gamedir.ps1')
$game = Get-ErEchoGameDir   # 源码已搬出游戏目录，统一走探测（见 gamedir.ps1）
if (-not $OutDir) { $OutDir = Join-Path $repo 'build\payload' }

function Say([string]$Text, [string]$Color = 'Gray') { Write-Host $Text -ForegroundColor $Color }

function Copy-One([string]$Source, [string]$DestDir) {
    if (-not (Test-Path -LiteralPath $Source)) { throw "缺少文件: $Source" }
    New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
    Copy-Item -LiteralPath $Source -Destination $DestDir -Force
}

function Copy-Tree([string]$SourceDir, [string]$DestDir, [string[]]$Exclude = @()) {
    if (-not (Test-Path -LiteralPath $SourceDir)) { return }
    New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
    foreach ($item in Get-ChildItem -LiteralPath $SourceDir -Force) {
        $skip = $false
        foreach ($pattern in $Exclude) { if ($item.Name -like $pattern) { $skip = $true; break } }
        if ($skip) { continue }
        if ($item.PSIsContainer) {
            Copy-Tree $item.FullName (Join-Path $DestDir $item.Name) $Exclude
        } else {
            Copy-Item -LiteralPath $item.FullName -Destination $DestDir -Force
        }
    }
}

function Write-Crlf([string]$Path, [string]$Text) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Path) | Out-Null
    $normalized = ($Text -split "`r?`n") -join "`r`n"
    [IO.File]::WriteAllText($Path, $normalized, [Text.UTF8Encoding]::new($false))
}

# ---------------------------------------------------------------- 0) DLL
$builtDll = Join-Path $repo 'mod\target\release\er_echo.dll'
if (-not $SkipBuild) {
    Say '[1/4] cargo build --release ...' 'Cyan'
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'mod\build.ps1')
    if ($LASTEXITCODE -ne 0) { throw "构建失败（exit $LASTEXITCODE）" }
}
if (-not (Test-Path -LiteralPath $builtDll)) { throw "找不到 $builtDll" }
$dllHash = (Get-FileHash -LiteralPath $builtDll -Algorithm SHA256).Hash

# ---------------------------------------------------------------- 1) 清空
Say '[2/4] 准备 payload 目录 ...' 'Cyan'
if (Test-Path -LiteralPath $OutDir) {
    $full = [IO.Path]::GetFullPath($OutDir)
    $buildRoot = [IO.Path]::GetFullPath((Join-Path $repo 'build'))
    if (-not $full.StartsWith($buildRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "拒绝删除不在 build\ 里的路径: $full"
    }
    Remove-Item -LiteralPath $OutDir -Recurse -Force
}
$shared = Join-Path $OutDir 'shared'
$me2 = Join-Path $OutDir 'me2'
$me3 = Join-Path $OutDir 'me3'
New-Item -ItemType Directory -Force -Path $shared, (Join-Path $me2 'plugin'), $me3 | Out-Null

# ---------------------------------------------------------------- 2) shared
Say '[3/4] 拷贝公共文件 ...' 'Cyan'
Copy-One $builtDll $shared
New-Item -ItemType Directory -Force -Path (Join-Path $shared 'profiles') | Out-Null
Copy-One (Join-Path $repo 'tools\profile.example.json') (Join-Path $shared 'profiles')
# 菜单文案覆盖模板：docs/i18n.md 让用户复制这个文件；手动包和安装器都要带
Copy-One (Join-Path $repo 'install\er_echo_i18n.example.ini') $shared

# CLI 工具 / bridge：安装器布局（mods\ER-Echo\）下也要有 doctor.ps1、导出工具和 IPC，
# 和插件包保持一致（否则 docs 里的自检 / 导出命令在安装器用户那里找不到文件）。
# 注意工具落在 mods\ER-Echo\tools\，gamedir.ps1 的「老布局」候选是 mods\ER-Echo 的上一级，
# 不是游戏根目录；自动探测仍会走 Steam 注册表，也可以用 -Target / ER_ECHO_GAME_DIR 显式指定。
$toolExclude = @(
    'live_*.ps1', 'restart_and_test*.ps1', 'restart_and_probe.ps1', 'restart_with_new_dll.ps1',
    '_probe_magic*.py', 'analyze_dump.py', 'profile.*.json', '_inspect_regulation.mjs',
    'package_release.ps1', 'package_nexus.ps1', 'package_payload.ps1', 'package_plugin.ps1',
    'from_save', 'from_save_account', '__pycache__', '*.pyc', 'Setup',
    # 开发/自动化脚本：不随发布包分发（换 DLL、模拟按键、抓图、ESD 构建、打包脚本）。
    'auto_start.ps1', 'enter_game.ps1', 'focus_game.ps1', 'press_key.ps1', 'sit_grace.ps1',
    'shot.ps1', 'swap_dll_on_exit.ps1', 'watch_state.py', 'verify_after_restart.py',
    'probe_face_memory.py', 'patch_grace_esd.py', 'pack_talk_esd.py', 'extract_game_file.py',
    'make_gui_icon.py', 'install_plugin.ps1', 'ensure_bom.py', 'build_gui_exe.ps1'
)
Copy-Tree (Join-Path $repo 'tools') (Join-Path $shared 'tools') $toolExclude
Copy-One (Join-Path $repo 'tools\profile.example.json') (Join-Path $shared 'tools')
Copy-Tree (Join-Path $repo 'bridge') (Join-Path $shared 'bridge') @('__pycache__', '*.pyc')

# 内置档案（彩蛋 / 备用角色）：install\profiles\builtin_*.json -> payload\shared\profiles\
# 安装器每次都用这份覆盖到 <plugin>\profiles\，并固定追加在 profiles= 名单末尾；
# 导出工具只写 slot<N>_*.json，所以用户导出不会覆盖它。
$builtinDir = Join-Path $repo 'install\profiles'
if (Test-Path -LiteralPath $builtinDir) {
    Get-ChildItem -LiteralPath $builtinDir -Filter 'builtin_*.json' -File | ForEach-Object {
        Copy-One $_.FullName (Join-Path $shared 'profiles')
        Write-Host ("[i] builtin profile: {0}" -f $_.Name)
    }
}

# 参数 id 表（游戏内 dump_equip / dump_magic 导出，按 regulation 分套）：
#   tables\vanilla      原版 / Mod Engine 2 安装用
#   tables\convergence  Convergence（me3）安装用
# 有表时导出器才能硬校验装备 id，混搭套装的角色也不会被误判成「缺装备」。
foreach ($set in @('vanilla', 'convergence')) {
    $tblSrc = Join-Path $repo ('install\tables\' + $set)
    if (Test-Path -LiteralPath $tblSrc) {
        Copy-Tree $tblSrc (Join-Path $OutDir ('tables\' + $set))
        Write-Host ("[i] id tables: {0} ({1} 文件)" -f $set, (Get-ChildItem -LiteralPath $tblSrc -File).Count)
    }
}

New-Item -ItemType Directory -Force -Path (Join-Path $shared 'docs') | Out-Null
foreach ($doc in @('INSTALL.md', 'INSTALL.en.md', 'i18n.md', 'usage.md', 'PLUGIN.md', 'CONVERGENCE.md')) {
    $src = Join-Path $repo ('docs\' + $doc)
    if (Test-Path -LiteralPath $src) { Copy-One $src (Join-Path $shared 'docs') }
}
$licDir = Join-Path $shared 'LICENSES'
New-Item -ItemType Directory -Force -Path $licDir | Out-Null
Copy-One (Join-Path $repo 'vendor\fromsoftware-rs-main\LICENSE-MIT-NON-AI') $licDir
Copy-One (Join-Path $repo 'vendor\fromsoftware-rs-main\LICENSE-ASL2-NON-AI') $licDir
# 安装器运行时（Qt6/PySide6/Python/OpenSSL/libffi/PyInstaller）的许可全文与 LGPL 声明
$thirdParty = Join-Path $repo 'nexus\third-party'
if (Test-Path -LiteralPath $thirdParty) {
    Copy-Item -Path (Join-Path $thirdParty '*') -Destination $licDir -Force
}
Copy-One (Join-Path $repo 'nexus\THIRD-PARTY-LICENSES.txt') $shared

$readme = @'
ER Echo 0.1.0
=============

安装（不用手动放文件、不用改 ini）
  ER-Echo-Setup.exe -> 「安装 / Setup」页 -> 游戏路径 填或选：
    原版 + Mod Engine 2： ...\steamapps\common\ELDEN RING\Game
    Convergence 3.x    ： ...\Games\Convergence3\ConvergenceER
  -> 自动检测 -> 一键安装。装完同一页点「一键启动游戏」：
     原版跑 launch-er-echo.bat（可勾管理员），Convergence 跑 me3 + convergence*.me3；
     安装完成的弹窗也会问「现在启动游戏？」。

  加载器（ME2 / me3）不随包分发：没装时安装器会给出官方发布页和详细安装步骤
  （ME2: github.com/soulsmods/ModEngine2/releases；me3: github.com/garyttierney/me3/releases）。
  原版也能用 me3：加载器选「me3（独立安装）」，安装器会生成 er-echo.me3 并一键启动。

Install (nothing to copy by hand, no ini editing)
  Run ER-Echo-Setup.exe -> "Setup" tab -> Game path:
    vanilla + Mod Engine 2: ...\steamapps\common\ELDEN RING\Game
    Convergence 3.x       : ...\Games\Convergence3\ConvergenceER
  -> Detect -> Install. Then click "Launch game" on the same tab: vanilla starts
     launch-er-echo.bat (optional admin), Convergence starts me3 + convergence*.me3.
     The install dialog also offers "Launch the game now?".

  Mod loaders are NOT bundled: if ME2/me3 is missing, the installer links to the official
  release pages and shows detailed steps (ME2: github.com/soulsmods/ModEngine2/releases;
  me3: github.com/garyttierney/me3/releases). Vanilla + me3 is supported too: pick
  "me3 (standalone)"; the installer writes er-echo.me3 and launches it.

本目录内容 / what is here
  er_echo.dll                mod 本体
  profiles\profile.example.json   示例档案（安装器会用你自己的角色覆盖 profiles=）
  profiles\builtin_sanvenir.json  内置角色 Sanvenir（彩蛋 / 备用）：固定在 profiles= 末尾，
                                  导出自己的角色时不会被覆盖；重装会恢复成发布版
  er_echo_i18n.example.ini   菜单文案覆盖模板（复制成 er_echo_i18n.ini 再改）
  tools\                     doctor.ps1 自检、导出工具、IPC 客户端
  bridge\                    可选 LLM 战斗导演（默认 mock 离线）
  docs\                      安装 / 插件 / Convergence / 使用说明
  LICENSES\ THIRD-PARTY-LICENSES.txt

注意 / notes
  * 只支持 ELDEN RING 1.17.2（exe 2.7.2.0 / 2.7.2.1），离线模式。
  * 原版需要先装 Mod Engine 2；Convergence 自带 me3，不用另装。
  * 卸载：setup exe -> 「卸载 / Uninstall」，会自动恢复改过的配置。
'@
# 版本号只从 -Version 参数来（build_gui_exe.ps1 会把它传下来）
$readme = $readme -replace '(?m)^ER Echo \d+\.\d+\.\d+', ("ER Echo " + $Version)
Write-Crlf (Join-Path $shared 'README-PLUGIN.txt') $readme

# ---------------------------------------------------------------- 3) ME2
Say '[4/4] 生成 ME2 配置和启动器 ...' 'Cyan'
Write-Crlf (Join-Path $me2 'config-er-echo.toml') @'
# ============================================================
# ER Echo - 自带的 Mod Engine 2 配置（可插拔）
# 用法：双击 mods\ER-Echo\launch-er-echo.bat
# 不修改游戏根目录的 config_eldenring.toml / launchmod_eldenring.bat。
# 卸载：删掉 mods\ER-Echo\ 和本文件。
# ============================================================
[modengine]
debug = false
external_dlls = ["mods/ER-Echo/er_echo.dll"]

[extension.mod_loader]
enabled = true
loose_params = false
mods = [ { enabled = true, name = "er-echo", path = "mods/ER-Echo/mod" } ]
'@

$plugin = Join-Path $me2 'plugin'
Write-Crlf (Join-Path $plugin 'launch-er-echo.bat') @'
@echo off
chcp 65001 >nul
:: ER Echo launcher (non-elevated).
:: cd to the game root (this file lives in mods\ER-Echo\);
:: -c points at our own config so config_eldenring.toml stays untouched;
:: -p skips ME2 2.1.0's Steam path detection (0xC0000409 in ucrtbase.dll).
:: If the game closes after ~10 s (WER: eldenring.exe / 0xc0000005 /
:: offset 0x1EBCEF9), use launch-er-echo-admin.bat instead.

cd /d "%~dp0..\.."

.\modengine2_launcher.exe -t er -c ".\config-er-echo.toml" -p ".\eldenring.exe"
set "ME2RC=%ERRORLEVEL%"
if not "%ME2RC%"=="0" (
    echo.
    echo [ERROR] Mod Engine 2 launcher failed, exit code %ME2RC%.
    echo         See modengine2\logs and er_echo.log for details.
    pause
)
'@

Write-Crlf (Join-Path $plugin 'launch-er-echo-admin.bat') @'
@echo off
chcp 65001 >nul
:: ER Echo launcher (self-elevating).
:: Use this if the normal launcher makes the game core-dump after ~10 s
:: (Steam overlay vs ModEngine2 hooks). Cost: no Steam overlay in game.

cd /d "%~dp0..\.."

whoami /groups 2>nul | findstr /C:"S-1-16-12288" >nul
if errorlevel 1 (
    echo Requesting administrator privileges ...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    if errorlevel 1 (
        echo.
        echo [ERROR] Elevation was cancelled.
        pause
    )
    exit /b
)

.\modengine2_launcher.exe -t er -c ".\config-er-echo.toml" -p ".\eldenring.exe"
set "ME2RC=%ERRORLEVEL%"
if not "%ME2RC%"=="0" (
    echo.
    echo [ERROR] Mod Engine 2 launcher failed, exit code %ME2RC%.
    pause
)
'@

# 赐福菜单需要挂载这份 ESD（实测：不挂载 ezstate 注入会报
# "cannot find grace root list start state"，菜单不出现）
Copy-One (Join-Path $repo 'ui\out_vanilla\m00_00_00_00.talkesdbnd.dcx') (Join-Path $plugin 'mod\script\talk')

# ---------------------------------------------------------------- 4) 汇总
$files = @(Get-ChildItem -LiteralPath $OutDir -Recurse -File)
$size = ($files | Measure-Object Length -Sum).Sum
Say ("[ok] payload: {0}  ({1} 个文件, {2} KB)" -f $OutDir, $files.Count, [math]::Round($size / 1KB, 1)) 'Green'
Say ("DLL SHA256: {0}" -f $dllHash)
exit 0
