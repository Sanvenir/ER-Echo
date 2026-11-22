# Snapshot-based summon experiment (no DLL restart needed).
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
Set-Location (Join-Path $game 'er-echo')
$out = Join-Path $game 'summons_test'
New-Item -ItemType Directory -Force -Path $out | Out-Null

function Snap([string]$tag) {
    & python.exe .\tools\ipc_client.py dump_summons --wait 4 2>&1 | Out-Null
    $src = Join-Path $game 'er_echo_summons.json'
    if (Test-Path $src) { Copy-Item $src (Join-Path $out "summons_$tag.json") -Force }
    $j = Get-Content $src -Encoding utf8 -ErrorAction SilentlyContinue | ConvertFrom-Json
    if ($j) {
        $ids = ($j.chrs | ForEach-Object { "$($_.npc_param_id)/team$($_.team_type)" }) -join ", "
        Write-Host ("  [{0}] count={1} request={2} active={3} chrs=[{4}]" -f $tag, $j.count, $j.request_summon_speffect_id, $j.active_summon_speffect_id, $ids)
    }
}

Write-Host "== baseline =="
Snap "a_before"

Write-Host "== request_summon(207000) =="
& python.exe .\tools\ipc_client.py request_summon --id 207000 --wait 4 2>&1 | Select-String 'ack' | Out-Null
for ($i = 1; $i -le 5; $i++) { Start-Sleep -Seconds 1; Snap "b_$i" }

Write-Host "== summon (spEffect 207000 on player) =="
& python.exe .\tools\ipc_client.py summon --wait 4 2>&1 | Select-String 'ack' | Out-Null
for ($i = 1; $i -le 5; $i++) { Start-Sleep -Seconds 1; Snap "c_$i" }

Write-Host "=== log tail ==="
Get-Content $log -Encoding utf8 -Tail 20 -ErrorAction SilentlyContinue
