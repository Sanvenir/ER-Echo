# Direct debug spawn test (bypasses SummonBuddyManager).
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
Set-Location (Join-Path $game 'er-echo')

function DumpChrs([string]$tag) {
    & python.exe .\tools\ipc_client.py dump_chrs --wait 4 2>&1 | Out-Null
    $j = Get-Content (Join-Path $game 'er_echo_chrs.json') -Encoding utf8 -ErrorAction SilentlyContinue | ConvertFrom-Json
    if ($j) {
        Write-Host ("  [{0}] nearby={1} player_pos=({2},{3},{4})" -f $tag, $j.count, $j.player_pos[0], $j.player_pos[1], $j.player_pos[2])
        $j.rows | Select-Object -First 6 | ForEach-Object {
            Write-Host ("     npc={0} team={1} dist={2}" -f $_.npc_param_id, $_.team_type, $_.dist)
        }
    }
}

Write-Host "== spawn_debug (c0000, mimic body params) =="
& python.exe .\tools\ipc_client.py spawn_debug --npc 100000010 --think 100000010 --chara 26050 --wait 4 2>&1 | Select-String 'ack' | Out-Null
Start-Sleep -Seconds 1; DumpChrs "d1"
Start-Sleep -Seconds 3; DumpChrs "d4"
Start-Sleep -Seconds 4; DumpChrs "d8"

Write-Host "=== log ==="
Select-String -Path $log -Pattern 'spawn_debug|debug' | Select-Object -Last 6 | ForEach-Object { $_.Line }
