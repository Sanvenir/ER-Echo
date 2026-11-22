# Wait for the game to exit, swap in the new DLL, relaunch, then run the summon test.
# Usage: powershell -ExecutionPolicy Bypass -File .\restart_and_test.ps1

$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$newDll = Join-Path $game 'er_echo.new.dll'
$dll = Join-Path $game 'er_echo.dll'
$log = Join-Path $game 'er_echo.log'

Write-Host "[1/5] waiting for eldenring.exe to exit (max 10 min)..."
$deadline = (Get-Date).AddMinutes(10)
while ((Get-Process eldenring -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
}
if (Get-Process eldenring -ErrorAction SilentlyContinue) {
    Write-Host "TIMEOUT: game still running; nothing changed"
    exit 1
}

Write-Host "[2/5] swapping DLL"
Copy-Item $newDll $dll -Force
if (-not (Test-Path $dll)) { Write-Host "swap failed"; exit 1 }
Remove-Item (Join-Path $game 'er_echo_*.json') -Force -ErrorAction SilentlyContinue
Remove-Item $log -Force -ErrorAction SilentlyContinue
Write-Host ("      {0} bytes" -f (Get-Item $dll).Length)

Write-Host "[3/5] launching game"
Start-Process -FilePath (Join-Path $game 'launchmod_eldenring.bat') -WorkingDirectory $game
$deadline = (Get-Date).AddMinutes(3)
while (-not (Get-Process eldenring -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 1
}
if (-not (Get-Process eldenring -ErrorAction SilentlyContinue)) {
    Write-Host "      WARN: game did not start"
}

Write-Host "[4/5] waiting for a save to be loaded (er_echo_profile.json, max 12 min)..."
$deadline = (Get-Date).AddMinutes(12)
$profile = Join-Path $game 'er_echo_profile.json'
while (-not (Test-Path $profile) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 3
}
if (-not (Test-Path $profile)) {
    Write-Host "      no profile dump (save not loaded?) - stopping before summon test"
    Get-Content $log -Encoding utf8 -Tail 15 -ErrorAction SilentlyContinue
    exit 2
}

Write-Host "[5/5] save loaded; sending summon command"
Set-Location (Join-Path $game 'er-echo')
& python.exe .\tools\ipc_client.py summon --wait 4 2>&1 | Select-Object -Last 10
Start-Sleep -Seconds 4

Write-Host "=== log tail ==="
Get-Content $log -Encoding utf8 -Tail 25 -ErrorAction SilentlyContinue
Write-Host "=== dumps ==="
Get-ChildItem (Join-Path $game 'er_echo_*.json') -ErrorAction SilentlyContinue |
    Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize
