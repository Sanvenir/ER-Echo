#requires -Version 5.1
<#
.SYNOPSIS
  按顺序构建发布所需的全部产物：DLL → 安装器 payload → ER-Echo-Setup.exe → 三个 Nexus zip。

.DESCRIPTION
  等价于依次运行：
      mod\build.ps1
      tools\package_payload.ps1 -SkipBuild
      tools\build_gui_exe.ps1 -SkipPayload
      tools\package_nexus.ps1 -SkipBuild

  产物在 dist\nexus\；同时更新 nexus\release-checksums.txt。
  前置工具链见 README「从源码构建」。

.PARAMETER Version
  版本号（默认 0.1.0），透传给打包脚本，决定文件名和 release 标题。

.PARAMETER SkipDll
  跳过 Rust DLL（复用 mod\target\release\er_echo.dll）。

.PARAMETER SkipInstaller
  跳过安装器（复用 dist\tools\ER-Echo-Setup），只重打 zip。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_all.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_all.ps1 -Version 0.1.1
#>
[CmdletBinding()]
param(
    [string]$Version = '0.1.0',
    [switch]$SkipDll,
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$script:start = Get-Date

function Invoke-Step {
    param([string]$Title, [scriptblock]$Body)
    Write-Host ''
    Write-Host ("=== {0} ===" -f $Title) -ForegroundColor Cyan
    $t = Get-Date
    & $Body
    if ($LASTEXITCODE -ne 0) { throw ("{0} failed (exit {1})" -f $Title, $LASTEXITCODE) }
    Write-Host ("[ok] {0}  ({1:N1}s)" -f $Title, ((Get-Date) - $t).TotalSeconds) -ForegroundColor Green
}

# ---------------------------------------------------------------- 1) DLL
if (-not $SkipDll) {
    Invoke-Step 'Rust DLL' {
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'mod\build.ps1')
    }
}
$dll = Join-Path $repo 'mod\target\release\er_echo.dll'
if (-not (Test-Path -LiteralPath $dll)) { throw "找不到 $dll（先跑 mod\build.ps1）" }

# ---------------------------------------------------------------- 2) payload
Invoke-Step 'installer payload' {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'tools\package_payload.ps1') `
        -SkipBuild -Version $Version
}

# ---------------------------------------------------------------- 3) installer
if (-not $SkipInstaller) {
    Invoke-Step 'ER-Echo-Setup.exe (PyInstaller)' {
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'tools\build_gui_exe.ps1') `
            -SkipPayload -Version $Version
    }
}

# ---------------------------------------------------------------- 4) zips
Invoke-Step 'release zips' {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'tools\package_nexus.ps1') `
        -SkipBuild -Version $Version
}

# ---------------------------------------------------------------- 汇总
Write-Host ''
Write-Host '=== artifacts ===' -ForegroundColor Cyan
$outDir = Join-Path $repo 'dist\nexus'
$assets = @(Get-ChildItem -LiteralPath $outDir -Filter "*.zip" -File |
    Where-Object { $_.Name -like "*$Version*" } | Sort-Object Name)
if ($assets.Count -eq 0) { throw "在 $outDir 没找到 $Version 的 zip" }
foreach ($a in $assets) {
    Write-Host ("  {0,-34} {1,12:N0} bytes  {2:N2} MB" -f $a.Name, $a.Length, ($a.Length / 1MB))
}
$sumFile = Join-Path $repo 'nexus\release-checksums.txt'
if (Test-Path -LiteralPath $sumFile) {
    Write-Host ("  hashes: {0}" -f $sumFile)
}
Write-Host ("  total: {0:N1}s" -f ((Get-Date) - $script:start).TotalSeconds)
Write-Host ''
Write-Host '下一步：' -ForegroundColor Cyan
Write-Host '  Nexus  -> nexus\checklist.md'
Write-Host '  GitHub -> docs\RELEASING.md（或 tools\publish_github_release.ps1 -DryRun 先看计划）'
exit 0
