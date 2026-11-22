# Authorized Mimic summon with 180s window (ASCII only).
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
$profile = Join-Path $game 'er-echo\tools\profile.test_face.json'
Set-Location (Join-Path $game 'er-echo')

& python.exe .\tools\ipc_client.py set_buddy_row --id 23200000 --npc 133201000 --think 133200000 --init -1 --wait 4 2>&1 | Out-Null
& python.exe .\tools\ipc_client.py set_buddy_row --id 23200001 --npc 100000010 --think 100000010 --init 26050 --wait 4 2>&1 | Out-Null
& python.exe .\tools\ipc_client.py set_buddy_row --id 23200002 --npc 100000010 --think 100000010 --init 26050 --wait 4 2>&1 | Out-Null
& python.exe .\tools\ipc_client.py load_profile --path $profile --wait 4 2>&1 | Out-Null
& python.exe .\tools\ipc_client.py prep_clone --wait 4 2>&1 | Out-Null

Write-Host "USE THE LONE WOLF ASHES NOW (180s window), player will look blue until used"
$deadline = (Get-Date).AddSeconds(180)
$spawned = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    & python.exe .\tools\ipc_client.py dump_summons --wait 4 2>&1 | Out-Null
    $j = Get-Content (Join-Path $game 'er_echo_summons.json') -Encoding utf8 -ErrorAction SilentlyContinue | ConvertFrom-Json
    if ($j -and $j.count -ge 3) { $spawned = $true; break }
}

Write-Host ("spawned={0}" -f $spawned)
if ($j) {
    $ids = ($j.chrs | ForEach-Object { "$($_.npc_param_id)/t$($_.team_type)" }) -join ", "
    Write-Host ("chrs=[{0}]" -f $ids)
    Start-Sleep -Seconds 3
    & python.exe .\tools\ipc_client.py dump_summons --wait 4 2>&1 | Out-Null
    $j2 = Get-Content (Join-Path $game 'er_echo_summons.json') -Encoding utf8 | ConvertFrom-Json
    $ids2 = ($j2.chrs | ForEach-Object { "$($_.npc_param_id)/t$($_.team_type)" }) -join ", "
    Write-Host ("after3s=[{0}]" -f $ids2)
}

& python.exe .\tools\ipc_client.py cancel_prep --wait 4 2>&1 | Out-Null
Select-String -Path $log -Pattern 'prep_clone|summon detected|restored' | Select-Object -Last 12 | ForEach-Object { $_.Line }
