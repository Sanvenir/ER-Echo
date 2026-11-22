# Assumes the game is running with a save loaded. Runs the summon experiments.
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
Set-Location (Join-Path $game 'er-echo')

Write-Host "== A. current summons =="
& python.exe .\tools\ipc_client.py dump_summons --wait 5 2>&1 | Select-Object -Last 6

Write-Host "== B. request_summon via SummonBuddyManager =="
& python.exe .\tools\ipc_client.py request_summon --id 207000 --wait 5 2>&1 | Select-Object -Last 6
Start-Sleep -Seconds 3

Write-Host "== C. summons after request =="
& python.exe .\tools\ipc_client.py dump_summons --wait 5 2>&1 | Select-Object -Last 6

Write-Host "== D. summon via spEffect on player =="
& python.exe .\tools\ipc_client.py summon --wait 6 2>&1 | Select-Object -Last 6
Start-Sleep -Seconds 4

Write-Host "== E. summons after spEffect =="
& python.exe .\tools\ipc_client.py dump_summons --wait 5 2>&1 | Select-Object -Last 6

Write-Host "=== log tail ==="
Get-Content $log -Encoding utf8 -Tail 30 -ErrorAction SilentlyContinue
Write-Host "=== summons json ==="
Get-Content (Join-Path $game 'er_echo_summons.json') -Encoding utf8 -ErrorAction SilentlyContinue
