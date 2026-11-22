# Test: clone should copy a *different* profile's equipment (naked = all zeros).
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
$profile = Join-Path $game 'er-echo\tools\profile.example.json'
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
        Write-Host ("  [{0}] count={1} chrs=[{2}]" -f $tag, $j.count, $ids)
    }
}

Write-Host "== load_profile (all-zero equipment => naked clone) =="
& python.exe .\tools\ipc_client.py load_profile --path $profile --wait 4 2>&1 | Select-String 'ack' | Out-Null

Write-Host "== keep_summons ON =="
& python.exe .\tools\ipc_client.py keep_summons --on true --wait 4 2>&1 | Select-String 'ack' | Out-Null

Write-Host "== summon =="
& python.exe .\tools\ipc_client.py summon --wait 4 2>&1 | Select-String 'ack' | Out-Null

for ($i = 1; $i -le 6; $i++) { Start-Sleep -Seconds 2; Snap "p_$i" }

Write-Host "=== log tail ==="
Get-Content $log -Encoding utf8 -Tail 20 -ErrorAction SilentlyContinue
