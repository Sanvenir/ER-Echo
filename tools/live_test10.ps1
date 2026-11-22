# Direct spawn with deferred position (waits until player chunk_position is valid).
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
Set-Location (Join-Path $game 'er-echo')

function DumpChrs([string]$tag) {
    & python.exe .\tools\ipc_client.py dump_chrs --wait 4 2>&1 | Out-Null
    $j = Get-Content (Join-Path $game 'er_echo_chrs.json') -Encoding utf8 -ErrorAction SilentlyContinue | ConvertFrom-Json
    if ($j) {
        Write-Host ("  [{0}] player=({1},{2},{3})" -f $tag, $j.player_pos[0], $j.player_pos[1], $j.player_pos[2])
        $j.rows | Select-Object -First 6 | ForEach-Object {
            Write-Host ("     npc={0} team={1} dist={2}" -f $_.npc_param_id, $_.team_type, $_.dist)
        }
    }
}

Start-Sleep -Seconds 2
Write-Host "== spawn_debug (queued until position valid) =="
& python.exe .\tools\ipc_client.py spawn_debug --npc 100000010 --think 100000010 --chara 26050 --wait 4 2>&1 | Select-String 'ack' | Out-Null
Start-Sleep -Seconds 1; DumpChrs "e1"
Start-Sleep -Seconds 2; DumpChrs "e3"
Start-Sleep -Seconds 4; DumpChrs "e7"

Write-Host "=== log ==="
Select-String -Path $log -Pattern 'spawn_debug' | Select-Object -Last 5 | ForEach-Object { $_.Line }
