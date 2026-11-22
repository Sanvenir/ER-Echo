#requires -Version 5.1
<#
.SYNOPSIS
  打 Nexus Mods 发布包（主文件 + 可选 ESD fallback），和 dist 里的「完整安装包」区分。

.DESCRIPTION
  和 package_release.ps1 的区别：
    * **不含** config_eldenring.toml（那是 Mod Engine 2 的配置，覆盖会破坏别人的设置）；
    * **含** 两个启动 bat：它们带 -p（绕开 ME2 2.1.0 的 0xC0000409 启动器崩溃）和 admin 变体
      （绕开「Steam 覆盖层 × ME2 钩子」导致的 10 秒闪退）；
    * **含** `mod\script\talk` 的 ESD（赐福菜单必需，实测不挂载时注入失败），
      但不含 `config_eldenring.toml`（ME2 配置，覆盖会破坏别人的设置）；
    * 附带 THIRD-PARTY-LICENSES.txt + LICENSES\（fromsoftware-rs 的 NON-AI 许可要求随包分发）；
    * 附带 er-echo\install\（配置片段 + 安装说明）；
    * 另外打一个可选的 root 菜单 ESD fallback 包。

.PARAMETER Version
  版本号，默认 0.1.0（要和 Cargo.toml / Nexus 页面一致）。

.PARAMETER SkipBuild
  不重新编译，直接用 mod\target\release\er_echo.dll。

.PARAMETER OutDir
  输出目录，默认 er-echo\dist\nexus。
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
if (-not $OutDir) { $OutDir = Join-Path $repo 'dist\nexus' }

$mainDir = Join-Path $OutDir ("ER-Echo-" + $Version)
$fallbackDir = Join-Path $OutDir ("ER-Echo-" + $Version + "-ESD-fallback")
$mainZip = $mainDir + '.zip'
$fallbackZip = $fallbackDir + '.zip'

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

function Reset-Dir([string]$Path, [string]$Root) {
    if (Test-Path -LiteralPath $Path) {
        $full = [IO.Path]::GetFullPath($Path)
        $rootFull = [IO.Path]::GetFullPath($Root)
        if (-not $full.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) {
            throw "拒绝删除不在输出目录里的路径: $full"
        }
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
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

# ---------------------------------------------------------------- 1) 主包
Say '[2/5] 主文件（不含游戏文件 / ME2 配置）...' 'Cyan'
Reset-Dir $mainDir $OutDir
Copy-One $builtDll $mainDir
# 启动器：优先用仓库里的模板（发布包可复现，不依赖作者本机游戏目录的改动）
$batMain = Join-Path $repo 'install\launchmod_eldenring.bat.template'
if (-not (Test-Path -LiteralPath $batMain)) { $batMain = Join-Path $game 'launchmod_eldenring.bat' }
$batAdmin = Join-Path $repo 'install\launchmod_eldenring_admin.bat.template'
if (-not (Test-Path -LiteralPath $batAdmin)) { $batAdmin = Join-Path $game 'launchmod_eldenring_admin.bat' }
Copy-Item -LiteralPath $batMain -Destination (Join-Path $mainDir 'launchmod_eldenring.bat') -Force
Copy-Item -LiteralPath $batAdmin -Destination (Join-Path $mainDir 'launchmod_eldenring_admin.bat') -Force
# 赐福菜单必需：ESD 要挂载到 mod/（实测不挂载时 EzState 注入失败）
Copy-One (Join-Path $repo 'ui\out_vanilla\m00_00_00_00.talkesdbnd.dcx') (Join-Path $mainDir 'mod\script\talk')
Copy-One (Join-Path $repo 'nexus\THIRD-PARTY-LICENSES.txt') $mainDir
Copy-One (Join-Path $repo 'install\er_echo_i18n.example.ini') $mainDir
Copy-Tree (Join-Path $repo 'install') (Join-Path $mainDir 'er-echo\install')

# 许可证全文（fromsoftware-rs 用 NON-AI 许可，要求随二进制分发）
$licDir = Join-Path $mainDir 'LICENSES'
New-Item -ItemType Directory -Force -Path $licDir | Out-Null
Copy-One (Join-Path $repo 'vendor\fromsoftware-rs-main\LICENSE-MIT-NON-AI') $licDir
Copy-One (Join-Path $repo 'vendor\fromsoftware-rs-main\LICENSE-ASL2-NON-AI') $licDir

# er_echo.ini：沿用默认值，profiles 指向示例；去掉作者存档相关注释
$iniSource = Join-Path $repo 'install\er_echo.ini.template'
if (-not (Test-Path -LiteralPath $iniSource)) { $iniSource = Join-Path $game 'er_echo.ini' }
if (-not (Test-Path -LiteralPath $iniSource)) { throw "找不到 ini 模板（$iniSource）" }
$iniText = [IO.File]::ReadAllText($iniSource)
$iniText = [regex]::Replace($iniText, '(?m)^\s*profiles\s*=.*$', 'profiles=profiles/profile.example.json')
$iniText = ($iniText -split "`r?`n" | Where-Object { $_ -notmatch 'from_save_account|ER0000\.sl2|7656|本账号' }) -join "`r`n"
$header = @'
; ============================================================
; ER Echo (Nexus release)
; 1) 导出你自己的角色：er-echo\tools\export_profile_from_save.py --slot N -o profiles\me.json
; 2) 把下面 [clone] 的 profiles= 改成你的文件
; 3) config_eldenring.toml 的 external_dlls 里加上 "er_echo.dll"
; 示例档案 equipment_param_ids 全是 0，只保证能跑起来。
; ============================================================

'@
[IO.File]::WriteAllText((Join-Path $mainDir 'er_echo.ini'), ($header + $iniText), [Text.UTF8Encoding]::new($false))

New-Item -ItemType Directory -Force -Path (Join-Path $mainDir 'profiles') | Out-Null
Copy-One (Join-Path $repo 'tools\profile.example.json') (Join-Path $mainDir 'profiles')

$toolExclude = @(
    'live_*.ps1', 'restart_and_test*.ps1', 'restart_and_probe.ps1', 'restart_with_new_dll.ps1',
    '_probe_magic*.py', 'analyze_dump.py', 'profile.*.json', '_inspect_regulation.mjs',
    'package_release.ps1', 'package_nexus.ps1',
    'from_save', 'from_save_account', '__pycache__', '*.pyc'
)
Copy-Tree (Join-Path $repo 'tools') (Join-Path $mainDir 'er-echo\tools') $toolExclude
Copy-One (Join-Path $repo 'tools\profile.example.json') (Join-Path $mainDir 'er-echo\tools')
Copy-Tree (Join-Path $repo 'bridge') (Join-Path $mainDir 'er-echo\bridge') @('__pycache__', '*.pyc')

New-Item -ItemType Directory -Force -Path (Join-Path $mainDir 'er-echo\docs') | Out-Null
foreach ($doc in @('INSTALL.md', 'INSTALL.en.md', 'i18n.md', 'usage.md')) {
    $src = Join-Path $repo ('docs\' + $doc)
    if (Test-Path -LiteralPath $src) { Copy-One $src (Join-Path $mainDir 'er-echo\docs') }
}

$readme = @'
ER Echo 0.1.0  (Nexus release)
================================

Summon characters from your own save files as Spirit Ash companions.
Offline only. Requires ELDEN RING 1.17.2 and Mod Engine 2.

BEFORE YOU INSTALL
  Confirm the vanilla game reaches the title screen and stays up for a minute
  WITHOUT Mod Engine 2. If it crashes without mods, this mod cannot help -
  verify the game files / repair Easy Anti-Cheat / reinstall the game first.

INSTALL
  1. Extract this folder into  ...\ELDEN RING\Game  (next to eldenring.exe).
  2. In config_eldenring.toml:
       - add "er_echo.dll" to the existing external_dlls array;
       - enable mod_loader and add the bundled mod\ folder:
         [extension.mod_loader]
         enabled = true
         loose_params = false
         mods = [ { enabled = true, name = "er-echo", path = "mod" } ]
     See er-echo\install\config.snippet.toml. The mod folder carries the talk ESD that
     the grace-menu patch needs; without it there is no "Comrades" entry.
  3. Export a character:
        python er-echo\tools\export_profile_from_save.py --list
        python er-echo\tools\export_profile_from_save.py --slot 2 -o profiles\slot2.json
     then set  profiles=profiles/slot2.json  under [clone] in er_echo.ini.
  4. Launch with launchmod_eldenring.bat (not through Steam).

IF IT DOES NOT START
  * Console flashes, nothing happens; Event Viewer: modengine2_launcher.exe /
    0xC0000409 in ucrtbase.dll
      -> ME2 2.1.0's Steam path auto-detection aborted. The bundled .bat passes
         -p ".\eldenring.exe"; if you use your own .bat, add that argument.
  * Game window appears, then closes after ~10 seconds; WER: eldenring.exe /
    0xc0000005 / offset 0x1EBCEF9; dump says DLUserInputManagerImpl_win32.cpp(98)
      -> Steam in-game overlay colliding with ME2 hooks. Run
         launchmod_eldenring_admin.bat, or disable the Steam overlay
         (Steam > Settings > In Game). Cost: no Steam overlay in game.
  * Crashes even with no mods loaded -> not this mod; verify game files/reinstall.

VERIFY
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\doctor.ps1
  Then check er_echo.log for "er_echo attached" and "ui: message hook installed".

CONTENTS
  er_echo.dll                     the mod
  er_echo.ini                     configuration
  er_echo_i18n.example.ini        menu translation override template
  launchmod_eldenring.bat         launcher (carries the -p workaround)
  launchmod_eldenring_admin.bat   self-elevating launcher (10-second crash)
  mod\script\talk\...dcx          grace-menu ESD (must be mounted via mod_loader)
  profiles\                       your exported characters
  er-echo\docs\                   install (incl. section 3 troubleshooting), usage, i18n
  er-echo\tools\                  profile export, doctor, IPC client
  er-echo\bridge\                 optional LLM battle director (off by default)
  er-echo\install\                config snippet + install notes
  LICENSES\, THIRD-PARTY-LICENSES.txt

NOTES
  * Do not go online with a modded save.
  * A game update breaks the mod until it is rebuilt.
  * This folder replaces no game files; there is no "mod" folder to merge.
  * If you already have your own launchmod_eldenring.bat, back it up before
    extracting; merge the -p argument rather than losing your customisations.
'@
[IO.File]::WriteAllText((Join-Path $mainDir 'README.txt'), $readme, [Text.UTF8Encoding]::new($false))

# ---------------------------------------------------------------- 2) 可选 ESD fallback
Say '[3/5] 可选 ESD fallback 包 ...' 'Cyan'
Reset-Dir $fallbackDir $OutDir
Copy-One (Join-Path $repo 'ui\out_rootmenu\m00_00_00_00.talkesdbnd.dcx') (Join-Path $fallbackDir 'mod\script\talk')
Copy-One (Join-Path $repo 'ui\out_vanilla\m00_00_00_00.talkesdbnd.dcx') (Join-Path $fallbackDir 'er-echo\ui\out_vanilla')
Copy-One (Join-Path $repo 'ui\out_rootmenu\m00_00_00_00.talkesdbnd.dcx') (Join-Path $fallbackDir 'er-echo\ui\out_rootmenu')
Copy-One (Join-Path $repo 'tools\switch_menu_mode.ps1') (Join-Path $fallbackDir 'er-echo\tools')

$fbReadme = @'
ER Echo 0.1.0 - root menu ESD fallback (OPTIONAL)
=================================================

You only need this if the runtime-injected "Comrades" entry does not appear in the
Site of Grace menu. The default (nested) mode does NOT use this file.

What it does
  * replaces mod\script\talk\m00_00_00_00.talkesdbnd.dcx with a patched vanilla ESD that
    adds the five root-menu options directly (no runtime injection),
  * sets nested_menu=false in er_echo.ini.

Install
  1. Extract into ...\ELDEN RING\Game (merge with the main archive).
  2. Make sure config_eldenring.toml has a mod_loader block pointing at mod/ (see below).
  3. er_echo.ini: set [ui] nested_menu=false (er-echo\tools\switch_menu_mode.ps1 -Mode root
     does both steps).
  4. Restart the game.

config_eldenring.toml:
  [extension.mod_loader]
  enabled = true
  mods = [ { enabled = true, name = "er-echo", path = "mod" }, ]

WARNING
  * This file is a modified copy of ELDEN RING game data. Do not redistribute it.
  * It conflicts with any other mod that replaces the same talk ESD; merge instead of overwrite.
  * Switching back to the default mode: er-echo\tools\switch_menu_mode.ps1 -Mode nested
'@
[IO.File]::WriteAllText((Join-Path $fallbackDir 'README.txt'), $fbReadme, [Text.UTF8Encoding]::new($false))

# ---------------------------------------------------------------- 3) 收尾：BOM + 脱敏
Say '[4/5] 规范化脚本编码 / 脱敏 ...' 'Cyan'
foreach ($stageDir in @($mainDir, $fallbackDir)) {
    Get-ChildItem -Path $stageDir -Recurse -Filter *.ps1 -ErrorAction SilentlyContinue | ForEach-Object {
        $bytes = [IO.File]::ReadAllBytes($_.FullName)
        if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) { return }
        $text = [IO.File]::ReadAllText($_.FullName, [Text.UTF8Encoding]::new($false))
        if ($text -match '[^\x00-\x7F]') {
            [IO.File]::WriteAllText($_.FullName, $text, [Text.UTF8Encoding]::new($true))
        }
    }
    $textExt = @('.md', '.json', '.ini', '.py', '.toml', '.txt', '.bat')
    Get-ChildItem -Path $stageDir -Recurse -File | Where-Object { $textExt -contains $_.Extension } | ForEach-Object {
        $text = [IO.File]::ReadAllText($_.FullName)
        if ($text -match '\b7656\d{13}\b') {
            [IO.File]::WriteAllText($_.FullName, ($text -replace '\b7656\d{13}\b', '<SteamID>'), [Text.UTF8Encoding]::new($false))
        }
    }
}

# ---------------------------------------------------------------- 4) 打包
Say '[5/5] 压缩 ...' 'Cyan'
foreach ($pair in @(@($mainDir, $mainZip), @($fallbackDir, $fallbackZip))) {
    $dir = $pair[0]; $zip = $pair[1]
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
    Compress-Archive -Path (Join-Path $dir '*') -DestinationPath $zip -CompressionLevel Optimal
    $mb = [Math]::Round((Get-Item -LiteralPath $zip).Length / 1MB, 2)
    Say ("[ok] {0} ({1} MB)" -f $zip, $mb) 'Green'
}

$mainFiles = @(Get-ChildItem -LiteralPath $mainDir -Recurse -File).Count
Say ''
Say ("主包: {0}  ({1} 个文件)" -f $mainDir, $mainFiles)
Say ("可选包: {0}" -f $fallbackDir)
Say ("DLL SHA256: {0}" -f $dllHash)
Say '下一步：按 er-echo\nexus\checklist.md 上传；游戏内素材见 er-echo\nexus\shotlist.md。'
exit 0
