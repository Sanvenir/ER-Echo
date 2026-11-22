# ASCII-only authorized summon test (avoid PowerShell 5.1 ANSI parsing issues).
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

Write-Host "USE THE LONE WOLF ASHES NOW (60s window)"
$deadline = (Get-Date).AddSeconds(60)
$spawned = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    & python.exe .\tools\ipc_client.py dump_summons --wait 4 2>&1 | Out-Null
    $j = Get-Content (Join-Path $game 'er_echo_summons.json') -Encoding utf8 -ErrorAction SilentlyContinue | ConvertFrom-Json
    if ($j -and $j.count -gt 1) { $spawned = $true; break }
}

Write-Host ("spawned={0}" -f $spawned)
if ($j) {
    $ids = ($j.chrs | ForEach-Object { "$($_.npc_param_id)/t$($_.team_type)" }) -join ", "
    Write-Host ("chrs=[{0}]" -f $ids)
    Start-Sleep -Seconds 2
    & python.exe .\tools\ipc_client.py dump_summons --wait 4 2>&1 | Out-Null
    $j2 = Get-Content (Join-Path $game 'er_echo_summons.json') -Encoding utf8 | ConvertFrom-Json
    $ids2 = ($j2.chrs | ForEach-Object { "$($_.npc_param_id)/t$($_.team_type)" }) -join ", "
    Write-Host ("after2s=[{0}]" -f $ids2)
}

& python.exe .\tools\ipc_client.py cancel_prep --wait 4 2>&1 | Out-Null
Select-String -Path $log -Pattern 'buddy row|prep_clone|detected summon|restored' | Select-Object -Last 12 | ForEach-Object { $_.Line }
