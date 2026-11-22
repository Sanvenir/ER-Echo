#requires -Version 5.1
<#
.SYNOPSIS
  Build the ER Echo installer + profile exporter (PyQt5, onedir) and embed the mod payload.

.DESCRIPTION
  Output:
      dist\tools\ER-Echo-Setup\ER-Echo-Setup.exe
      dist\tools\ER-Echo-Setup\_internal\payload\...   <- mod files used by the installer
      dist\tools\ER-Echo-Setup-0.2.0.zip

  Ship that zip: the user unzips it anywhere, runs the exe, types the game path.

  Dependencies go to er-echo\build\pydeps (does not touch the system Python).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\build_gui_exe.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\build_gui_exe.ps1 -SkipInstall -SkipPayload
#>
[CmdletBinding()]
param(
    [switch]$SkipInstall,
    [switch]$SkipIcon,
    [switch]$SkipPayload,
    [switch]$Onefile,
    [string]$Version = '0.1.0'
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$deps = Join-Path $repo 'build\pydeps'
$cache = Join-Path $repo 'build\pipcache'
$tools = Join-Path $repo 'tools'
$dist = Join-Path $repo 'dist\tools'
$payload = Join-Path $repo 'build\payload'
New-Item -ItemType Directory -Force -Path $deps, $cache, $dist | Out-Null

$env:PIP_CACHE_DIR = $cache
$env:PYTHONPATH = "$tools;$deps"
$env:PYTHONIOENCODING = 'utf-8'

function Has-Module([string]$name) {
    & python -c "import $name" 2>$null
    return $LASTEXITCODE -eq 0
}

# ---------------------------------------------------------------- deps
if (-not $SkipInstall) {
    $need = @()
    if (-not (Has-Module 'PyQt5')) { $need += 'PyQt5' }
    if (-not (Has-Module 'PyInstaller')) { $need += 'pyinstaller' }
    if (-not (Has-Module 'PIL')) { $need += 'pillow' }
    if ($need.Count -gt 0) {
        Write-Host ("[..] install deps: " + ($need -join ', ')) -ForegroundColor Cyan
        & python -m pip install --disable-pip-version-check --no-input --target $deps @need `
            -i https://pypi.tuna.tsinghua.edu.cn/simple
        if ($LASTEXITCODE -ne 0) { throw 'pip install failed' }
    } else {
        Write-Host '[ok] deps already present' -ForegroundColor Green
    }
}

# ---------------------------------------------------------------- payload
if (-not $SkipPayload) {
    Write-Host '[..] building payload ...' -ForegroundColor Cyan
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $tools 'package_payload.ps1') -SkipBuild
    if ($LASTEXITCODE -ne 0) { throw "payload build failed (exit $LASTEXITCODE)" }
}
if (-not (Test-Path (Join-Path $payload 'shared\er_echo.dll'))) {
    throw "missing payload: $payload (run package_payload.ps1 first)"
}

# ---------------------------------------------------------------- icon
$icon = Join-Path $repo 'build\icon.ico'
if (-not $SkipIcon) {
    Write-Host '[..] building icon ...' -ForegroundColor Cyan
    & python (Join-Path $tools 'make_gui_icon.py')
    if ($LASTEXITCODE -ne 0) { throw 'icon build failed' }
}

$verFile = Join-Path $repo 'build\version_info.txt'
$script = Join-Path $tools 'profile_export_gui.py'
$name = 'ER-Echo-Setup'

# ---------------------------------------------------------------- onedir (recommended)
Write-Host '[..] packaging onedir ...' -ForegroundColor Cyan
$pyArgs = @(
    '-m', 'PyInstaller', '--noconfirm', '--clean',
    '--onedir', '--windowed',
    '--name', $name,
    '--paths', $tools,
    '--distpath', $dist,
    '--workpath', (Join-Path $repo 'build\pyinstaller-onedir'),
    '--specpath', (Join-Path $repo 'build'),
    '--add-data', ($payload + ';payload'),
    '--hidden-import', 'er_echo_setup',
    '--hidden-import', 'profile_export_gui',
    '--hidden-import', 'export_profile_from_save'
)
if (Test-Path $icon) { $pyArgs += @('--icon', $icon) }
if (Test-Path $verFile) { $pyArgs += @('--version-file', $verFile) }
$pyArgs += $script
& python @pyArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller(onedir) failed (exit $LASTEXITCODE)" }

$onedir = Join-Path $dist $name
$exe = Join-Path $onedir ($name + '.exe')
if (-not (Test-Path $exe)) { throw "no artifact: $exe" }
Write-Host ("[ok] {0} ({1} MB)" -f $exe, [math]::Round((Get-Item $exe).Length / 1MB, 1)) -ForegroundColor Green

$readme = Join-Path $dist 'README-Setup.txt'
if (-not (Test-Path $readme)) {
    $text = @"
ER Echo 0.2.0 - installer / profile exporter
============================================

Run ER-Echo-Setup.exe -> "Setup" tab -> enter the game path -> Install.

  vanilla + Mod Engine 2 : ...\steamapps\common\ELDEN RING\Game
  Convergence 3.x        : ...\Convergence3\ConvergenceER

The same program exports your characters ("Profiles" tab).
onedir build: copy the whole folder, not just the exe.
"@
    [IO.File]::WriteAllText($readme, $text, [Text.UTF8Encoding]::new($false))
}

$onedirZip = Join-Path $dist ($name + '-' + $Version + '.zip')
if (Test-Path $onedirZip) { Remove-Item $onedirZip -Force }
Compress-Archive -Path @($onedir, $readme) -DestinationPath $onedirZip -CompressionLevel Optimal
Write-Host ("[ok] {0} ({1} MB)" -f $onedirZip, [math]::Round((Get-Item $onedirZip).Length / 1MB, 2)) -ForegroundColor Green

# ---------------------------------------------------------------- frozen selftest
Write-Host '[..] frozen selftest (--selftest-setup) ...' -ForegroundColor Cyan
$probe = Join-Path $repo ('build\selftest-setup-' + [guid]::NewGuid().ToString('N').Substring(0, 6) + '.json')
$p = $null
& $exe --selftest-setup $probe | Out-Null
$rc = $LASTEXITCODE
Write-Host ("[i] selftest exit={0}" -f $rc)
if (Test-Path $probe) {
    $info = Get-Content $probe -Raw -Encoding utf8 | ConvertFrom-Json
    Write-Host ("[i] payload={0} files={1} errors={2}" -f $info.payload, @($info.payload_files).Count, @($info.errors).Count)
    foreach ($e in $info.errors) { Write-Warning $e }
    foreach ($t in $info.targets) { Write-Host ("[i] target: {0} {1}" -f $t.kind, $t.path) }
    Remove-Item $probe -Force
} else {
    Write-Warning 'no selftest output'
}

# ---------------------------------------------------------------- onefile (optional)
if ($Onefile) {
    Write-Host '[..] packaging onefile (not recommended) ...' -ForegroundColor Cyan
    $oneArgs = @(
        '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--onefile', '--windowed',
        '--name', ($name + '-onefile'),
        '--paths', $tools,
        '--distpath', (Join-Path $repo 'build\onefile'),
        '--workpath', (Join-Path $repo 'build\pyinstaller-onefile'),
        '--specpath', (Join-Path $repo 'build'),
        '--add-data', ($payload + ';payload')
    )
    if (Test-Path $icon) { $oneArgs += @('--icon', $icon) }
    if (Test-Path $verFile) { $oneArgs += @('--version-file', $verFile) }
    $oneArgs += $script
    & python @oneArgs
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller(onefile) failed' }
    $oneExe = Join-Path $repo ('build\onefile\' + $name + '-onefile.exe')
    Copy-Item $oneExe (Join-Path $dist ($name + '-onefile.exe')) -Force
}

Write-Host ''
Write-Host ("done. run: dist\tools\{0}\{0}.exe" -f $name) -ForegroundColor Green
Write-Host '(onedir: copy the whole folder, not just the exe)'
