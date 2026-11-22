# Spawn templates +2m above player to test visibility/ground clipping.
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
Set-Location (Join-Path $game 'er-echo')

function DumpChrs([string]$tag) {
    & python.exe .\tools\ipc_client.py dump_chrs --wait 4 2>&1 | Out-Null
    $j = Get-Content (Join-Path $game 'er_echo_chrs.json') -Encoding utf8 -ErrorAction SilentlyContinue | ConvertFrom-Json
    if ($j) {
        Write-Host ("  [{0}] player=({1},{2},{3})" -f $tag, $j.player_pos[0], $j.player_pos[1], $j.player_pos[2])
        $j.rows | Select-Object -First 8 | ForEach-Object {
            Write-Host ("     npc={0} team={1} dist={2}" -f $_.npc_param_id, $_.team_type, $_.dist)
        }
    }
}

Start-Sleep -Seconds 3
Write-Host "== spawn Fia +2m =="
& python.exe .\tools\ipc_client.py spawn_debug --npc 523220179 --think 523220000 --chara 23221 --dy 2 --wait 4 2>&1 | Select-String 'ack' | Out-Null
Start-Sleep -Seconds 1; DumpChrs "g1"
Start-Sleep -Seconds 2; DumpChrs "g3"

Write-Host "== spawn Rogier +2m =="
& python.exe .\tools\ipc_client.py spawn_debug --npc 523250079 --think 523250000 --chara 23250 --dy 2 --wait 4 2>&1 | Select-String 'ack' | Out-Null
Start-Sleep -Seconds 2; DumpChrs "g5"
Start-Sleep -Seconds 3; DumpChrs "g8"

Write-Host "=== log ==="
Select-String -Path $log -Pattern 'spawn_debug at' | Select-Object -Last 4 | ForEach-Object { $_.Line }
