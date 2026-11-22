# Diagnostic: override Mimic's BuddyParam row to spawn a known-visible NPC (Fia).
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
Set-Location (Join-Path $game 'er-echo')

function Snap([string]$tag) {
    & python.exe .\tools\ipc_client.py dump_summons --wait 4 2>&1 | Out-Null
    $j = Get-Content (Join-Path $game 'er_echo_summons.json') -Encoding utf8 -ErrorAction SilentlyContinue | ConvertFrom-Json
    if ($j) {
        $ids = ($j.chrs | ForEach-Object { "$($_.npc_param_id)/t$($_.team_type)" }) -join ", "
        Write-Host ("  [{0}] count={1} chrs=[{2}]" -f $tag, $j.count, $ids)
    }
}

Write-Host "== override buddy row 20700000 -> Fia params =="
& python.exe .\tools\ipc_client.py set_buddy_row --id 20700000 --npc 523220179 --think 523220000 --init 23221 --wait 4 2>&1 | Select-String 'ack' | Out-Null
Write-Host "== request_summon 207000 =="
& python.exe .\tools\ipc_client.py request_summon --id 207000 --wait 4 2>&1 | Select-String 'ack' | Out-Null
Start-Sleep -Seconds 2; Snap "v2"
Start-Sleep -Seconds 3; Snap "v5"
Start-Sleep -Seconds 3; Snap "v8"

Write-Host "=== log ==="
Select-String -Path $log -Pattern 'buddy row|request_summon' | Select-Object -Last 6 | ForEach-Object { $_.Line }
