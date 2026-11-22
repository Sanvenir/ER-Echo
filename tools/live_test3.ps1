# Keep-alive summon test.
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
        $ids = ($j.chrs | ForEach-Object { "$($_.npc_param_id)/t$($_.team_type)" }) -join ", "
        Write-Host ("  [{0}] count={1} active={2} chrs=[{3}]" -f $tag, $j.count, $j.active_summon_speffect_id, $ids)
    }
}

Write-Host "== keep_summons ON =="
& python.exe .\tools\ipc_client.py keep_summons --on true --wait 4 2>&1 | Select-String 'ack' | Out-Null

Write-Host "== summon (profile + request_summon + keep-alive) =="
& python.exe .\tools\ipc_client.py summon --wait 4 2>&1 | Select-String 'ack' | Out-Null

for ($i = 1; $i -le 7; $i++) { Start-Sleep -Seconds 2; Snap "k_$i" }

Write-Host "== dismiss =="
& python.exe .\tools\ipc_client.py dismiss --wait 4 2>&1 | Select-String 'ack' | Out-Null
Start-Sleep -Seconds 2
Snap "after_dismiss"

Write-Host "=== log tail ==="
Get-Content $log -Encoding utf8 -Tail 25 -ErrorAction SilentlyContinue
