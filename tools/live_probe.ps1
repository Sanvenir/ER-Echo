# Probe: is the summoned Mimic a PlayerIns (has PlayerGameData/face_data)?
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
Set-Location (Join-Path $game 'er-echo')

& python.exe .\tools\ipc_client.py set_buddy_row --id 23200000 --npc 133201000 --think 133200000 --init -1 --wait 4 2>&1 | Out-Null
& python.exe .\tools\ipc_client.py set_buddy_row --id 23200001 --npc 100000010 --think 100000010 --init 26050 --wait 4 2>&1 | Out-Null
& python.exe .\tools\ipc_client.py set_buddy_row --id 23200002 --npc 100000010 --think 100000010 --init 26050 --wait 4 2>&1 | Out-Null

Write-Host "USE THE LONE WOLF ASHES NOW (180s window)"
$deadline = (Get-Date).AddSeconds(180)
$spawned = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    & python.exe .\tools\ipc_client.py dump_summons --wait 4 2>&1 | Out-Null
    $j = Get-Content (Join-Path $game 'er_echo_summons.json') -Encoding utf8 -ErrorAction SilentlyContinue | ConvertFrom-Json
    if ($j -and $j.count -ge 3) { $spawned = $true; break }
}

Write-Host ("spawned={0}" -f $spawned)
if ($spawned) {
    & python.exe .\tools\ipc_client.py dump_summons --wait 4 2>&1 | Out-Null
    Get-Content (Join-Path $game 'er_echo_summons.json') -Encoding utf8
    & python.exe .\tools\ipc_client.py clone_info --wait 6 2>&1 | Select-String 'ack' | Out-Null
    Write-Host "=== clone_info ==="
    Get-Content (Join-Path $game 'er_echo_clone_info.json') -Encoding utf8 -ErrorAction SilentlyContinue
}

Write-Host "=== log ==="
Select-String -Path $log -Pattern 'buddy row|clone_info' | Select-Object -Last 8 | ForEach-Object { $_.Line }
