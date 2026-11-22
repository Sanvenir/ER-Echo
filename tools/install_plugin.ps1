#requires -Version 5.1
<#
.SYNOPSIS
  纯净安装实验：把一个插件包（zip 或目录）装进干净的游戏目录，并可选地启动验证。

.DESCRIPTION
  前提（脚本会检查）：游戏根目录没有任何 ER Echo 残留
    - 没有 mods\ER-Echo\
    - 没有 config-er-echo.toml
    - 没有 er_echo.dll
  否则先跑 reset_to_vanilla.ps1。

  安装 = 把压缩包解到游戏根目录（只新增 mods\ER-Echo\ 和 config-er-echo.toml）。

.PARAMETER Package
  插件包路径：dist\plugin\ER-Echo-Plugin-0.1.0.zip 或同名目录。

.PARAMETER Launch
  安装后直接启动游戏，并等 er_echo.log 里出现 "er_echo attached"（最长 180 秒）。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\install_plugin.ps1 `
      -Package er-echo\dist\plugin\ER-Echo-Plugin-0.1.0.zip -Launch
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Package,
    [switch]$Launch,
    [switch]$SkipDoctor
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'gamedir.ps1')
$game = Get-ErEchoGameDir   # 源码已搬出游戏目录，统一走探测（见 gamedir.ps1）
if (-not (Test-Path (Join-Path $game 'eldenring.exe'))) { throw "不是游戏根目录: $game" }
if (-not (Test-Path -LiteralPath $Package)) { throw "找不到安装包: $Package" }
$Package = (Resolve-Path -LiteralPath $Package).Path

# ---------------------------------------------------------------- 1) 干净基线检查
$dirty = @()
if (Test-Path (Join-Path $game 'mods\ER-Echo')) { $dirty += 'mods\ER-Echo\' }
if (Test-Path (Join-Path $game 'config-er-echo.toml')) { $dirty += 'config-er-echo.toml' }
if (Test-Path (Join-Path $game 'er_echo.dll')) { $dirty += 'er_echo.dll（平铺安装残留）' }
if (Test-Path (Join-Path $game 'er_echo.ini')) { $dirty += 'er_echo.ini（平铺安装残留）' }

if ($dirty.Count -gt 0) {
    Write-Host '[x] 目录不是干净状态：' -ForegroundColor Red
    $dirty | ForEach-Object { Write-Host ('    ' + $_) }
    Write-Host '    先运行：powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\reset_to_vanilla.ps1' -ForegroundColor Yellow
    exit 2
}

$exeVer = ([System.Diagnostics.FileVersionInfo]::GetVersionInfo((Join-Path $game 'eldenring.exe'))).ProductVersion
if ($exeVer -notin @('2.7.2.0', '2.7.2.1')) {
    Write-Host ("[x] 游戏版本 {0} 不受支持（需要 2.7.2.0 / 2.7.2.1）" -f $exeVer) -ForegroundColor Red
    exit 2
}
Write-Host ("[ok] 基线干净，游戏版本 {0}" -f $exeVer) -ForegroundColor Green

if (-not (Test-Path (Join-Path $game 'modengine2_launcher.exe'))) {
    Write-Host '[x] 没有 Mod Engine 2（modengine2_launcher.exe）' -ForegroundColor Red
    exit 2
}

# ---------------------------------------------------------------- 2) 解包
Write-Host ("[..] 安装 {0}" -f $Package) -ForegroundColor Cyan
if ((Get-Item -LiteralPath $Package).PSIsContainer) {
    Copy-Item -Path (Join-Path $Package '*') -Destination $game -Recurse -Force
} else {
    Expand-Archive -LiteralPath $Package -DestinationPath $game -Force
}

foreach ($p in @('mods\ER-Echo\er_echo.dll', 'mods\ER-Echo\er_echo.ini', 'mods\ER-Echo\launch-er-echo.bat', 'config-er-echo.toml')) {
    if (-not (Test-Path (Join-Path $game $p))) { throw "安装后缺少: $p" }
}
Write-Host '[ok] 文件已就位（mods\ER-Echo\ + config-er-echo.toml）' -ForegroundColor Green

# ---------------------------------------------------------------- 3) 自检
if (-not $SkipDoctor) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $game 'mods\ER-Echo\tools\doctor.ps1') -Target $game
    $doctorExit = $LASTEXITCODE
    if ($doctorExit -ne 0) {
        Write-Host ("[warn] doctor 报了 {0} 项阻断，先修再启动" -f $doctorExit) -ForegroundColor Yellow
        if (-not $Launch) { exit $doctorExit }
    }
}

# ---------------------------------------------------------------- 4) 启动并等待 attached
if ($Launch) {
    $log = Join-Path $game 'er_echo.log'
    $before = if (Test-Path $log) { (Get-Item $log).Length } else { 0 }
    Write-Host '[..] 启动游戏（launch-er-echo.bat），等待 er_echo.log 出现 attached …' -ForegroundColor Cyan
    Start-Process -FilePath (Join-Path $game 'mods\ER-Echo\launch-er-echo.bat') -WorkingDirectory $game -WindowStyle Minimized

    $deadline = (Get-Date).AddSeconds(180)
    $attached = $false
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 3
        if (Test-Path $log) {
            $tail = Get-Content -LiteralPath $log -Tail 80 -Encoding utf8 -ErrorAction SilentlyContinue
            if ($tail -match 'er_echo attached') { $attached = $true; break }
            if ($tail -match 'panicked|CSTaskImp not found') { break }
        }
        if (-not (Get-Process eldenring -ErrorAction SilentlyContinue)) { break }
    }

    Write-Host ''
    if ($attached) {
        Write-Host '[ok] DLL 已注入并 attached —— 进游戏坐赐福，应能看到 Comrades (n/m)，F8 可召唤' -ForegroundColor Green
    } else {
        Write-Host '[x] 没等到 attached：看下面的日志尾巴 + WER' -ForegroundColor Red
        if (-not (Get-Process eldenring -ErrorAction SilentlyContinue)) {
            Write-Host '    游戏进程已退出（可能是 10 秒闪退 → 换 launch-er-echo-admin.bat，或关 Steam 覆盖层）' -ForegroundColor Yellow
        }
    }
    if (Test-Path $log) {
        Write-Host ''
        Write-Host '--- er_echo.log（最后 15 行）---' -ForegroundColor DarkGray
        Get-Content -LiteralPath $log -Tail 15 -Encoding utf8
    }
}

Write-Host ''
Write-Host '卸载：删除 mods\ER-Echo\ 和 config-er-echo.toml（运行日志在游戏根目录）' -ForegroundColor DarkGray
