# Wait for exit -> swap DLL -> launch -> wait for save -> run live_test.ps1
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
if (Get-Process eldenring -ErrorAction SilentlyContinue) { Write-Host "TIMEOUT"; exit 1 }

Write-Host "[2/5] swapping DLL"
Copy-Item $newDll $dll -Force
Remove-Item (Join-Path $game 'er_echo_*.json') -Force -ErrorAction SilentlyContinue
Remove-Item $log -Force -ErrorAction SilentlyContinue
Write-Host ("      {0} bytes" -f (Get-Item $dll).Length)

Write-Host "[3/5] launching game"
Start-Process -FilePath (Join-Path $game 'launchmod_eldenring.bat') -WorkingDirectory $game
$deadline = (Get-Date).AddMinutes(3)
while (-not (Get-Process eldenring -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 1
}

Write-Host "[4/5] waiting for save load (er_echo_profile.json, max 12 min)..."
$deadline = (Get-Date).AddMinutes(12)
$profile = Join-Path $game 'er_echo_profile.json'
while (-not (Test-Path $profile) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 3
}
if (-not (Test-Path $profile)) { Write-Host "no save loaded"; Get-Content $log -Encoding utf8 -Tail 15; exit 2 }

Write-Host "[5/5] running live test"
& powershell.exe -ExecutionPolicy Bypass -File (Join-Path $game 'er-echo\tools\live_test.ps1')
