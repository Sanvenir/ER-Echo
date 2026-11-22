#requires -Version 5.1
<#
.SYNOPSIS
  打「可插拔插件包」：整个 mod 只占一个 mods\ER-Echo\ 目录 + 一个自带配置，不改 ME2 的任何文件。

.DESCRIPTION
  布局（相对游戏根目录）：

    config-er-echo.toml          ← 自己的 ME2 配置（不动 config_eldenring.toml）
    mods\ER-Echo\                ← 插件本体，删掉即卸载
      er_echo.dll  er_echo.ini  launch-er-echo.bat  ...
      还有 launch-er-echo-admin.bat / profiles\ / tools\ / docs\ / LICENSES\

  DLL 的配置查找已改成「优先 DLL 同目录」，所以 er_echo.ini 可以待在插件目录里。
  启动方式：双击 mods\ER-Echo\launch-er-echo.bat（它会 cd 到游戏根目录再调 ME2）。

.PARAMETER Version
  版本号，默认 0.1.0。

.PARAMETER SkipBuild
  不重新编译，直接用 mod\target\release\er_echo.dll。

.PARAMETER OutDir
  输出目录，默认 er-echo\dist\plugin。
#>
[CmdletBinding()]
param(
    [string]$Version = '0.1.0',
    [switch]$SkipBuild,
    [string]$OutDir
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot          # er-echo/
. (Join-Path $PSScriptRoot 'gamedir.ps1')
$game = Get-ErEchoGameDir   # 源码已搬出游戏目录，统一走探测（见 gamedir.ps1）
if (-not $OutDir) { $OutDir = Join-Path $repo 'dist\plugin' }

$stage = Join-Path $OutDir ("ER-Echo-Plugin-" + $Version)
$plugin = Join-Path $stage 'mods\ER-Echo'
$zip = $stage + '.zip'

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
        foreach ($pattern in $Exclude) {
            if ($item.Name -like $pattern) { $skip = $true; break }
        }
        if ($skip) { continue }
        if ($item.PSIsContainer) {
            Copy-Tree $item.FullName (Join-Path $DestDir $item.Name) $Exclude
        } else {
            Copy-Item -LiteralPath $item.FullName -Destination $DestDir -Force
        }
    }
}

function Write-Crlf([string]$Path, [string]$Text) {
    $normalized = ($Text -split "`r?`n") -join "`r`n"
    [IO.File]::WriteAllText($Path, $normalized, [Text.UTF8Encoding]::new($false))
}

# ---------------------------------------------------------------- 0) 构建
$builtDll = Join-Path $repo 'mod\target\release\er_echo.dll'
if (-not $SkipBuild) {
    Say '[1/5] cargo build --release ...' 'Cyan'
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'mod\build.ps1')
    if ($LASTEXITCODE -ne 0) { throw "构建失败（exit $LASTEXITCODE）" }
}
if (-not (Test-Path -LiteralPath $builtDll)) { throw "找不到 $builtDll" }
$dllHash = (Get-FileHash -LiteralPath $builtDll -Algorithm SHA256).Hash

# ---------------------------------------------------------------- 1) 目录
Say '[2/5] 准备插件目录 ...' 'Cyan'
if (Test-Path -LiteralPath $stage) {
    $full = [IO.Path]::GetFullPath($stage)
    $root = [IO.Path]::GetFullPath($OutDir)
    if (-not $full.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
        throw "拒绝删除不在输出目录里的路径: $full"
    }
    Remove-Item -LiteralPath $stage -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $plugin | Out-Null

# ---------------------------------------------------------------- 2) 插件本体
Say '[3/5] 拷贝插件文件 ...' 'Cyan'
Copy-One $builtDll $plugin
Copy-One (Join-Path $repo 'install\er_echo_i18n.example.ini') $plugin
Copy-One (Join-Path $repo 'nexus\THIRD-PARTY-LICENSES.txt') $plugin
Copy-Tree (Join-Path $repo 'install') (Join-Path $plugin 'install')

$licDir = Join-Path $plugin 'LICENSES'
New-Item -ItemType Directory -Force -Path $licDir | Out-Null
Copy-One (Join-Path $repo 'vendor\fromsoftware-rs-main\LICENSE-MIT-NON-AI') $licDir
Copy-One (Join-Path $repo 'vendor\fromsoftware-rs-main\LICENSE-ASL2-NON-AI') $licDir

# er_echo.ini：profiles 默认指向内置的 Sanvenir（相对游戏根目录），去掉作者存档相关注释
$iniSource = Join-Path $game 'er_echo.ini'
if (-not (Test-Path -LiteralPath $iniSource)) {
    $iniSource = Join-Path $repo 'install\er_echo.ini.template'
}
if (-not (Test-Path -LiteralPath $iniSource)) { throw "找不到 ini 模板（$iniSource）" }
$iniText = [IO.File]::ReadAllText($iniSource)
$iniText = [regex]::Replace($iniText, '(?m)^\s*profiles\s*=.*$', 'profiles=mods/ER-Echo/profiles/builtin_sanvenir.json')
$iniText = ($iniText -split "`r?`n" | Where-Object { $_ -notmatch 'from_save_account|ER0000\.sl2|7656|本账号' }) -join "`r`n"
$header = @'
; ============================================================
; ER Echo (plugin layout)
; 本文件在 mods\ER-Echo\ 里，DLL 会优先读自己同目录的 er_echo.ini。
; profiles 仍以**游戏根目录**为基准，所以写成 mods/ER-Echo/profiles/...
; 默认带内置角色 Sanvenir（彩蛋 / 备用，Lv1）：它固定留在 profiles= 末尾。
; 换成自己的角色：
;   python mods\ER-Echo\tools\export_profile_from_save.py --slot N -o mods\ER-Echo\profiles\me.json
;   再把 [clone] 的 profiles= 改成 mods/ER-Echo/profiles/me.json,mods/ER-Echo/profiles/builtin_sanvenir.json
; 卸载：删掉 mods\ER-Echo\ 和游戏根目录的 config-er-echo.toml 即可。
; ============================================================

'@
[IO.File]::WriteAllText((Join-Path $plugin 'er_echo.ini'), ($header + $iniText), [Text.UTF8Encoding]::new($false))

New-Item -ItemType Directory -Force -Path (Join-Path $plugin 'profiles') | Out-Null
Copy-One (Join-Path $repo 'tools\profile.example.json') (Join-Path $plugin 'profiles')
Copy-One (Join-Path $repo 'install\profiles\builtin_sanvenir.json') (Join-Path $plugin 'profiles')

# 赐福菜单需要挂载这份 ESD（实测：不挂载 ezstate 注入会报
# "cannot find grace root list start state"，菜单不出现）
Copy-One (Join-Path $repo 'ui\out_vanilla\m00_00_00_00.talkesdbnd.dcx') (Join-Path $plugin 'mod\script\talk')

$toolExclude = @(
    'live_*.ps1', 'restart_and_test*.ps1', 'restart_and_probe.ps1', 'restart_with_new_dll.ps1',
    '_probe_magic*.py', 'analyze_dump.py', 'profile.*.json', '_inspect_regulation.mjs',
    'package_release.ps1', 'package_nexus.ps1', 'package_plugin.ps1', 'reset_to_vanilla.ps1', 'install_plugin.ps1',
    'from_save', 'from_save_account', '__pycache__', '*.pyc'
)
Copy-Tree (Join-Path $repo 'tools') (Join-Path $plugin 'tools') $toolExclude
Copy-One (Join-Path $repo 'tools\profile.example.json') (Join-Path $plugin 'tools')
Copy-Tree (Join-Path $repo 'bridge') (Join-Path $plugin 'bridge') @('__pycache__', '*.pyc')

# 附带图形工具（onedir）：tools\Setup\ —— 装完能直接导出角色 / 改配置 / 装到 Convergence
$guiSrc = Join-Path $repo 'dist\tools\ER-Echo-Setup'
if (-not (Test-Path -LiteralPath $guiSrc)) {
    throw "缺少 GUI 产物：$guiSrc（先跑 tools\build_gui_exe.ps1）"
}
Copy-Tree $guiSrc (Join-Path $plugin 'tools\Setup') @('profiles', '*.json', '__pycache__')

New-Item -ItemType Directory -Force -Path (Join-Path $plugin 'docs') | Out-Null
foreach ($doc in @('INSTALL.md', 'INSTALL.en.md', 'i18n.md', 'usage.md', 'PLUGIN.md', 'CONVERGENCE.md')) {
    $src = Join-Path $repo ('docs\' + $doc)
    if (Test-Path -LiteralPath $src) { Copy-One $src (Join-Path $plugin 'docs') }
}

# ---------------------------------------------------------------- 3) 自带配置 + 启动器
Say '[4/5] 生成 config + launcher ...' 'Cyan'
$config = @'
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
[IO.File]::WriteAllText((Join-Path $stage 'config-er-echo.toml'), $config, [Text.UTF8Encoding]::new($false))

$launcher = @'
@echo off
chcp 65001 >nul
:: ER Echo plugin launcher (non-elevated).
::
:: - cd to the game root (this file lives in mods\ER-Echo\)
:: - -c points at our own config, so config_eldenring.toml is untouched
:: - -p skips ModEngine2 2.1.0's Steam path detection (0xC0000409 in ucrtbase.dll)
::
:: If the game window closes after ~10 s (WER: eldenring.exe / 0xc0000005 /
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
Write-Crlf (Join-Path $plugin 'launch-er-echo.bat') $launcher

$adminLauncher = @'
@echo off
chcp 65001 >nul
:: ER Echo plugin launcher (self-elevating).
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
Write-Crlf (Join-Path $plugin 'launch-er-echo-admin.bat') $adminLauncher

Write-Crlf (Join-Path $plugin 'Export-Profiles.bat') @'
@echo off
chcp 65001 >nul
:: 打开图形导出工具：选存档 -> 导出角色 -> 自动写入 er_echo.ini
:: Opens the profile exporter: pick save -> export -> writes er_echo.ini for you.
start "" "%~dp0tools\Setup\ER-Echo-Setup.exe"
'@

$readme = @'
ER Echo 0.1.0 - pluggable plugin (ER Echo / 可插拔插件)
======================================================

中文
----
这个文件夹是自包含的：装进游戏目录后只多出 mods\ER-Echo\ 和 ..\config-er-echo.toml，
不会改 config_eldenring.toml / launchmod_eldenring.bat / modengine2\。

首次使用（3 步，不用手改任何 ini）
  1. 确认已装 Mod Engine 2 到 ...\ELDEN RING\Game。
  2. 双击 Export-Profiles.bat -> 自动列出你存档里的角色 -> 选一个 -> 导出选中
     -> 弹窗选「是」，工具会把 profiles= 写进 er_echo.ini（自动备份原文件）。
     内置角色 Sanvenir（profiles\builtin_sanvenir.json，Lv1 彩蛋/备用）会保留在名单末尾；
     什么都不导出也能直接玩。
     内置角色 Sanvenir（profiles\builtin_sanvenir.json，Lv1 彩蛋/备用）会保留在名单末尾；
     什么都不导出也能直接玩。
  3. 双击 launch-er-echo-admin.bat（本机需要管理员；普通机器可试 launch-er-echo.bat）。
     进游戏坐赐福 -> 「战友（n/m）」，或按 F8 召唤。

English
-------
Self-contained: installing adds only mods\ER-Echo\ and ..\config-er-echo.toml.
It does not touch config_eldenring.toml / launchmod_eldenring.bat / modengine2\.

First run (3 steps, no manual ini editing)
  1. Make sure Mod Engine 2 is installed in ...\ELDEN RING\Game.
  2. Run Export-Profiles.bat -> your save is detected -> pick a character -> Export selected
     -> choose "Yes" to write profiles= into er_echo.ini (a backup is made).
  3. Run launch-er-echo-admin.bat (needs admin on this machine; try launch-er-echo.bat
     on machines without the 10-second Steam-overlay crash).

Notes / 注意
  * ELDEN RING 1.17.2 only (exe 2.7.2.0 / 2.7.2.1); offline only.
  * Built-in companion: profiles\builtin_sanvenir.json (Sanvenir, Lv1) is pinned at the end of
    profiles= and already works before you export anything. Export-Profiles.bat only writes
    slot<N>_*.json and keeps the builtin entry, so exporting your own characters never removes it.
  * The bundled profile.example.json is only a format sample.
  * If the game core-dumps ~10 s after launch, use the admin launcher or disable the
    Steam overlay (see docs/INSTALL.md section 3).

SELF-CHECK
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\doctor.ps1 -Target ..\..

UNINSTALL
  Delete mods\ER-Echo\ and ..\config-er-echo.toml. Runtime files in the game root:
  er_echo.log*, er_echo_*.json, er_echo_heartbeat.txt.

LAYOUT
  er_echo.dll               the mod
  er_echo.ini               config (read from the DLL's own directory)
  Export-Profiles.bat       GUI profile exporter (writes profiles= for you)
  launch-er-echo.bat        launcher (normal)
  launch-er-echo-admin.bat  launcher (elevated)
  mod\script\talk\...dcx    ESD mounted for the grace menu (required)
  profiles\                 exported characters (builtin Sanvenir + example + yours)
  tools\Setup\           the GUI tool (onedir: keep _internal next to the exe)
  tools\  bridge\  docs\  install\  LICENSES\
  ..\config-er-echo.toml    ME2 config (next to eldenring.exe)
'@
$readme = $readme -replace '(?m)^ER Echo \d+\.\d+\.\d+', ("ER Echo " + $Version)
[IO.File]::WriteAllText((Join-Path $plugin 'README-PLUGIN.txt'), $readme, [Text.UTF8Encoding]::new($false))

# ---------------------------------------------------------------- 4) BOM/脱敏 + 打包
Say '[5/5] 收尾 + 压缩 ...' 'Cyan'
Get-ChildItem -Path $plugin -Recurse -Filter *.ps1 | ForEach-Object {
    $bytes = [IO.File]::ReadAllBytes($_.FullName)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) { return }
    $text = [IO.File]::ReadAllText($_.FullName, [Text.UTF8Encoding]::new($false))
    if ($text -match '[^\x00-\x7F]') {
        [IO.File]::WriteAllText($_.FullName, $text, [Text.UTF8Encoding]::new($true))
    }
}
$textExt = @('.md', '.json', '.ini', '.py', '.toml', '.txt', '.bat')
Get-ChildItem -Path $stage -Recurse -File | Where-Object { $textExt -contains $_.Extension } | ForEach-Object {
    $text = [IO.File]::ReadAllText($_.FullName)
    if ($text -match '\b7656\d{13}\b') {
        [IO.File]::WriteAllText($_.FullName, ($text -replace '\b7656\d{13}\b', '<SteamID>'), [Text.UTF8Encoding]::new($false))
    }
}

if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -CompressionLevel Optimal
$mb = [Math]::Round((Get-Item -LiteralPath $zip).Length / 1MB, 2)
Say ("[ok] {0} ({1} MB)" -f $zip, $mb) 'Green'
$files = @(Get-ChildItem -LiteralPath $stage -Recurse -File).Count
Say ("插件目录: {0}  ({1} 个文件)" -f $stage, $files)
Say ("DLL SHA256: {0}" -f $dllHash)
Say '安装：把压缩包解到游戏根目录，然后双击 mods\ER-Echo\launch-er-echo.bat'
exit 0
