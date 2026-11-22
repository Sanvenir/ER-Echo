# Pure summon test at a flat grace: no keep-alive, no alpha forcing.
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
$profile = Join-Path $game 'er-echo\tools\profile.test_face.json'
Set-Location (Join-Path $game 'er-echo')

function Snap([string]$tag) {
    & python.exe .\tools\ipc_client.py dump_summons --wait 4 2>&1 | Out-Null
    $j = Get-Content (Join-Path $game 'er_echo_summons.json') -Encoding utf8 -ErrorAction SilentlyContinue | ConvertFrom-Json
    if ($j) {
        $ids = ($j.chrs | ForEach-Object { "$($_.npc_param_id)/t$($_.team_type)" }) -join ", "
        Write-Host ("  [{0}] count={1} chrs=[{2}]" -f $tag, $j.count, $ids)
    }
}

& python.exe .\tools\ipc_client.py load_profile --path $profile --wait 4 2>&1 | Out-Null
Write-Host "== pure summon (flat grace) =="
& python.exe .\tools\ipc_client.py summon_plain --wait 4 2>&1 | Select-String 'ack' | Out-Null
Start-Sleep -Seconds 1; Snap "p1"
Start-Sleep -Seconds 2; Snap "p3"
Start-Sleep -Seconds 3; Snap "p6"
Start-Sleep -Seconds 4; Snap "p10"

Write-Host "=== log ==="
Select-String -Path $log -Pattern 'summon\(|buffed|restored' | Select-Object -Last 8 | ForEach-Object { $_.Line }
