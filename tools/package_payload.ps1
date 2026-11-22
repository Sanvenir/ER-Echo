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
    [string]$OutDir
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
Copy-One (Join-Path $repo 'nexus\THIRD-PARTY-LICENSES.txt') $shared

Write-Crlf (Join-Path $shared 'README-PLUGIN.txt') @'
ER Echo 0.2.0
=============

安装（不用手动放文件、不用改 ini）
  ER-Echo-Setup.exe -> 「安装 / Setup」页 -> 游戏路径 填或选：
    原版 + Mod Engine 2： ...\steamapps\common\ELDEN RING\Game
    Convergence 3.x    ： ...\Games\Convergence3\ConvergenceER
  -> 自动检测 -> 一键安装。装完按钮会告诉你从哪启动。

Install (nothing to copy by hand, no ini editing)
  Run ER-Echo-Setup.exe -> "Setup" tab -> Game path:
    vanilla + Mod Engine 2: ...\steamapps\common\ELDEN RING\Game
    Convergence 3.x       : ...\Games\Convergence3\ConvergenceER
  -> Detect -> Install. The dialog afterwards tells you what to launch.

本目录内容 / what is here
  er_echo.dll                mod 本体
  profiles\profile.example.json   示例档案（安装器会用你自己的角色覆盖 profiles=）
  docs\                      安装 / 插件 / Convergence 说明
  LICENSES\ THIRD-PARTY-LICENSES.txt

注意 / notes
  * 只支持 ELDEN RING 1.17.2（exe 2.7.2.0 / 2.7.2.1），离线模式。
  * 原版需要先装 Mod Engine 2；Convergence 自带 me3，不用另装。
  * 卸载：setup exe -> 「卸载 / Uninstall」，会自动恢复改过的配置。
'@

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
