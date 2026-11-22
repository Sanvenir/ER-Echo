# Wait for game exit -> swap er_echo.new.dll -> launch -> wait save -> live_test17
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$newDll = Join-Path $game 'er_echo.new.dll'
$dll = Join-Path $game 'er_echo.dll'
$log = Join-Path $game 'er_echo.log'

Write-Host "[1/4] waiting for game exit (max 45 min)..."
$deadline = (Get-Date).AddMinutes(45)
while ((Get-Process eldenring -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 2 }
if (Get-Process eldenring -ErrorAction SilentlyContinue) { Write-Host "TIMEOUT"; exit 1 }

Write-Host "[2/4] swapping DLL"
Copy-Item $newDll $dll -Force
Remove-Item (Join-Path $game 'er_echo_*.json') -Force -ErrorAction SilentlyContinue
Remove-Item $log -Force -ErrorAction SilentlyContinue
Write-Host ("      {0} bytes" -f (Get-Item $dll).Length)

Write-Host "[3/4] launching"
Start-Process -FilePath (Join-Path $game 'launchmod_eldenring.bat') -WorkingDirectory $game
$deadline = (Get-Date).AddMinutes(3)
while (-not (Get-Process eldenring -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 1 }

Write-Host "[4/4] waiting for save load..."
$deadline = (Get-Date).AddMinutes(12)
while (-not (Test-Path (Join-Path $game 'er_echo_profile.json')) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 3 }

& powershell.exe -ExecutionPolicy Bypass -File (Join-Path $game 'er-echo\tools\live_test17.ps1')
