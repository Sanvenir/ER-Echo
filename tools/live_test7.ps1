# Locate the visible clone: dump all nearby characters at intervals.
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
$profile = Join-Path $game 'er-echo\tools\profile.test_face.json'
$out = Join-Path $game 'summons_test'
New-Item -ItemType Directory -Force -Path $out | Out-Null
Set-Location (Join-Path $game 'er-echo')

function DumpChrs([string]$tag) {
    & python.exe .\tools\ipc_client.py dump_chrs --wait 4 2>&1 | Out-Null
    $src = Join-Path $game 'er_echo_chrs.json'
    if (Test-Path $src) { Copy-Item $src (Join-Path $out "chrs_$tag.json") -Force }
    $j = Get-Content $src -Encoding utf8 -ErrorAction SilentlyContinue | ConvertFrom-Json
    if ($j) {
        Write-Host ("  [{0}] nearby={1}" -f $tag, $j.count)
        $j.rows | Select-Object -First 8 | ForEach-Object {
            Write-Host ("     npc={0} team={1} dist={2} pos=({3},{4},{5})" -f $_.npc_param_id, $_.team_type, $_.dist, $_.pos[0], $_.pos[1], $_.pos[2])
        }
    }
}

& python.exe .\tools\ipc_client.py load_profile --path $profile --wait 4 2>&1 | Out-Null
& python.exe .\tools\ipc_client.py keep_summons --on true --wait 4 2>&1 | Out-Null
Write-Host "== summon =="
& python.exe .\tools\ipc_client.py summon --wait 4 2>&1 | Select-String 'ack' | Out-Null

Start-Sleep -Seconds 1; DumpChrs "t1"
Start-Sleep -Seconds 2; DumpChrs "t3"
Start-Sleep -Seconds 3; DumpChrs "t6"
Start-Sleep -Seconds 4; DumpChrs "t10"

Write-Host "=== log ==="
Select-String -Path $log -Pattern 'profile loaded|face|summon:|restored' | Select-Object -Last 10 | ForEach-Object { $_.Line }
