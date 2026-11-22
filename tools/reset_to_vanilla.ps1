#requires -Version 5.1
<#
.SYNOPSIS
  把游戏目录恢复成「没有 ER Echo 的干净状态」，用于纯净安装实验。

.DESCRIPTION
  做四件事：
    1. 备份当前 mod 相关文件到 %USERPROFILE%\ER-Echo-Backups\pre-reset-<时间>.zip
    2. 删掉平铺安装（er_echo.dll / er_echo.ini / launchmod_*admin* / mod\script\talk 的 ESD …）
    3. 删掉可插拔安装（mods\ER-Echo\ + config-er-echo.toml）
    4. 把 config_eldenring.toml 写回最小干净版（除非 -KeepMe2Config）

  不会碰：游戏本体文件、modengine2\、存档、er-echo\ 源码目录。

.PARAMETER KeepMe2Config
  保留现有 config_eldenring.toml（默认会备份后写成 external_dlls=[] 的干净版）。

.PARAMETER SteamVerify
  重置后打开 Steam 的「验证文件完整性」（steam://validate/1245620）。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\reset_to_vanilla.ps1
#>
[CmdletBinding()]
param(
    [switch]$KeepMe2Config,
    [switch]$SteamVerify,
    [switch]$DryRun,
    [string]$BackupDir
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'gamedir.ps1')
$game = Get-ErEchoGameDir   # 源码已搬出游戏目录，统一走探测（见 gamedir.ps1）
if (-not (Test-Path (Join-Path $game 'eldenring.exe'))) { throw "不是游戏根目录: $game" }
if (Get-Process eldenring -ErrorAction SilentlyContinue) { throw '游戏还在运行，先完全退出（含 Steam 覆盖层进程）' }

Write-Host "目标: $game" -ForegroundColor Cyan

# ---------------------------------------------------------------- 1) 备份
$backupDir = if ($BackupDir) { $BackupDir } else { Join-Path $env:USERPROFILE 'ER-Echo-Backups' }
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backupZip = Join-Path $backupDir ("pre-reset-" + $stamp + ".zip")

$backupItems = @(
    'er_echo.dll', 'er_echo.ini', 'er_echo_i18n.ini',
    'config_eldenring.toml', 'config-er-echo.toml',
    'launchmod_eldenring.bat', 'launchmod_eldenring_admin.bat',
    'launch-er-echo.bat', 'launch-er-echo-admin.bat',
    'er_echo_roster.json', 'er_echo_status.json', 'er_echo_profile.json',
    'er_echo_heartbeat.txt'
)
$existing = @()
foreach ($name in $backupItems) {
    $p = Join-Path $game $name
    if (Test-Path -LiteralPath $p) { $existing += $p }
}
if (Test-Path (Join-Path $game 'mods\ER-Echo')) { $existing += (Join-Path $game 'mods\ER-Echo') }

if ($DryRun) {
    Write-Host ''
    Write-Host '[dry-run] 以下内容会被备份并删除/移动：' -ForegroundColor Yellow
    $existing | ForEach-Object { Write-Host ('  ' + $_.Replace($game, '.')) }
    if (Test-Path (Join-Path $game 'profiles')) { Write-Host '  .\profiles\  （移到备份目录）' }
    Write-Host ('  .\config_eldenring.toml  （写成 external_dlls=[] 的干净版' + $(if ($KeepMe2Config) { '；-KeepMe2Config 已指定，跳过' } else { '' }) + '）')
    Write-Host '  .\launchmod_eldenring.bat  （若有 .bak-20261120，还原成 ME2 原版）'
    Write-Host ''
    Write-Host '没有做任何修改。去掉 -DryRun 才会真的执行。' -ForegroundColor DarkGray
    exit 0
}

New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
if ($existing.Count -gt 0) {
    Compress-Archive -Path $existing -DestinationPath $backupZip -CompressionLevel Optimal
    Write-Host ("[ok] 备份: {0}" -f $backupZip) -ForegroundColor Green
} else {
    Write-Host '[i] 没有可备份的 mod 文件' -ForegroundColor DarkGray
}

# profiles\ 是用户数据：移走而不是删
$profiles = Join-Path $game 'profiles'
if (Test-Path -LiteralPath $profiles) {
    $dest = Join-Path $backupDir ("profiles-" + $stamp)
    Move-Item -LiteralPath $profiles -Destination $dest -Force
    Write-Host ("[ok] profiles\ 移到 {0}" -f $dest) -ForegroundColor Green
}

# ---------------------------------------------------------------- 2) 平铺安装
$remove = @(
    'er_echo.dll', 'er_echo.ini', 'er_echo_i18n.ini',
    'config-er-echo.toml',
    'launch-er-echo.bat', 'launch-er-echo-admin.bat',
    'launchmod_eldenring_admin.bat',
    'er_echo.log', 'er_echo.log.1', 'er_echo.log.2',
    'er_echo_heartbeat.txt',
    'er_echo_roster.json', 'er_echo_status.json', 'er_echo_profile.json',
    'er_echo_buddies.json', 'er_echo_ride.json', 'er_echo_npc.json',
    'er_echo_think.json', 'er_echo_equip.json', 'er_echo_magic.json',
    'er_echo_magic_probe.json', 'er_echo_spirit.json', 'er_echo_combat.json',
    'er_echo_clone_info.json', 'er_echo_weights.json', 'er_echo_summon_state.json',
    'er_echo_chrs.json'
)
foreach ($name in $remove) {
    $p = Join-Path $game $name
    if (Test-Path -LiteralPath $p) {
        Remove-Item -LiteralPath $p -Force
        Write-Host ("[del] " + $name)
    }
}

# 赐福菜单 ESD：只在确实是我们那两个版本时删（避免误删别人的 mod）
$talk = Join-Path $game 'mod\script\talk\m00_00_00_00.talkesdbnd.dcx'
$ours = @(
    (Join-Path $game 'er-echo\ui\out_vanilla\m00_00_00_00.talkesdbnd.dcx'),
    (Join-Path $game 'er-echo\ui\out_rootmenu\m00_00_00_00.talkesdbnd.dcx')
)
if (Test-Path -LiteralPath $talk) {
    $h = (Get-FileHash -LiteralPath $talk).Hash
    $known = @()
    foreach ($o in $ours) { if (Test-Path -LiteralPath $o) { $known += (Get-FileHash -LiteralPath $o).Hash } }
    if ($known -contains $h) {
        Remove-Item -LiteralPath $talk -Force
        Write-Host '[del] mod\script\talk\m00_00_00_00.talkesdbnd.dcx（ours）'
    } else {
        Write-Host '[warn] mod\script\talk 的 ESD 不是本 mod 的版本，保留不动' -ForegroundColor Yellow
    }
    foreach ($dir in @('mod\script\talk', 'mod\script', 'mod')) {
        $full = Join-Path $game $dir
        if ((Test-Path -LiteralPath $full) -and @(Get-ChildItem -LiteralPath $full -Force).Count -eq 0) {
            Remove-Item -LiteralPath $full -Force
        }
    }
}

# ---------------------------------------------------------------- 3) 可插拔安装
$plugin = Join-Path $game 'mods\ER-Echo'
if (Test-Path -LiteralPath $plugin) {
    Remove-Item -LiteralPath $plugin -Recurse -Force
    Write-Host '[del] mods\ER-Echo\'
}

# ---------------------------------------------------------------- 4) ME2 配置/启动器
if (-not $KeepMe2Config) {
    $cleanToml = @'
# Clean Mod Engine 2 config restored by reset_to_vanilla.ps1
# (backup of the previous file is in %USERPROFILE%\ER-Echo-Backups)
[modengine]
debug = false
external_dlls = []

[extension.mod_loader]
enabled = true
loose_params = false
mods = []
'@
    [IO.File]::WriteAllText((Join-Path $game 'config_eldenring.toml'), $cleanToml, [Text.UTF8Encoding]::new($false))
    Write-Host '[ok] config_eldenring.toml 已写成干净版（external_dlls=[]）'
}

$originalBat = Join-Path $game 'launchmod_eldenring.bat.bak-20261120'
if (Test-Path -LiteralPath $originalBat) {
    Copy-Item -LiteralPath $originalBat -Destination (Join-Path $game 'launchmod_eldenring.bat') -Force
    Write-Host '[ok] launchmod_eldenring.bat 已还原成 ME2 原版（无 -p）'
} else {
    Write-Host '[i] 没有原版 bat 备份，launchmod_eldenring.bat 保持现状' -ForegroundColor DarkGray
}

# ---------------------------------------------------------------- 5) 结果
Write-Host ''
$left = Get-ChildItem -LiteralPath $game -Force | Where-Object { $_.Name -match '^er_echo|^config-er-echo|^launch-er-echo' }
if ($left) {
    Write-Host '[warn] 还剩下：' -ForegroundColor Yellow
    $left | ForEach-Object { Write-Host ("       " + $_.Name) }
} else {
    Write-Host '[ok] 游戏根目录已无 ER Echo 文件' -ForegroundColor Green
}

if ($SteamVerify) {
    Start-Process 'steam://validate/1245620'
    Write-Host '[ok] 已打开 Steam 验证文件完整性' -ForegroundColor Green
}

Write-Host ''
Write-Host '下一步（纯净基线验证）：' -ForegroundColor Cyan
Write-Host '  1. 直接运行 eldenring.exe（不经 ME2），确认能进标题并稳定 1 分钟'
Write-Host '  2. 通过 Steam「开始游戏」走一次 EAC（可选，确认在线入口正常）'
Write-Host '  3. 基线 OK 后，装插件包并双击 mods\ER-Echo\launch-er-echo.bat'
Write-Host ("  备份在: " + $backupDir)
