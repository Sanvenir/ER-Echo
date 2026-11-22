# Visibility test: force alpha, then summon and dump nearby chrs.
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
$profile = Join-Path $game 'er-echo\tools\profile.test_face.json'
Set-Location (Join-Path $game 'er-echo')

function DumpChrs([string]$tag) {
    & python.exe .\tools\ipc_client.py dump_chrs --wait 4 2>&1 | Out-Null
    $j = Get-Content (Join-Path $game 'er_echo_chrs.json') -Encoding utf8 -ErrorAction SilentlyContinue | ConvertFrom-Json
    if ($j) {
        $near = ($j.rows | Select-Object -First 6 | ForEach-Object { "$($_.npc_param_id)/t$($_.team_type)@d$($_.dist)" }) -join ", "
        Write-Host ("  [{0}] nearby={1} [{2}]" -f $tag, $j.count, $near)
    }
}

& python.exe .\tools\ipc_client.py load_profile --path $profile --wait 4 2>&1 | Out-Null
& python.exe .\tools\ipc_client.py keep_summons --on true --wait 4 2>&1 | Out-Null
Write-Host "== summon =="
& python.exe .\tools\ipc_client.py summon --wait 4 2>&1 | Select-String 'ack' | Out-Null
Start-Sleep -Seconds 1; DumpChrs "a1"
Start-Sleep -Seconds 3; DumpChrs "a4"
Start-Sleep -Seconds 4; DumpChrs "a8"

Write-Host "=== log ==="
Select-String -Path $log -Pattern 'summon:|face' | Select-Object -Last 8 | ForEach-Object { $_.Line }
