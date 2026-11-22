# Pure summon + fix_clone (move buddies into player block, force alpha).
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
Write-Host "== summon_plain =="
& python.exe .\tools\ipc_client.py summon_plain --wait 4 2>&1 | Select-String 'ack' | Out-Null
Start-Sleep -Seconds 1
Write-Host "== fix_clone (x3) =="
for ($i = 0; $i -lt 3; $i++) {
    & python.exe .\tools\ipc_client.py fix_clone --wait 4 2>&1 | Select-String 'ack' | Out-Null
    Start-Sleep -Seconds 1
}
Snap "x1"
Start-Sleep -Seconds 2; Snap "x3"
Start-Sleep -Seconds 3; Snap "x6"
Start-Sleep -Seconds 4; Snap "x10"

Write-Host "=== log ==="
Select-String -Path $log -Pattern 'summon\(|fix_clone|block' | Select-Object -Last 10 | ForEach-Object { $_.Line }
