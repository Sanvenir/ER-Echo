# Face copy test: profile has same gear + blue skin payload.
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
$profile = Join-Path $game 'er-echo\tools\profile.test_face.json'
Set-Location (Join-Path $game 'er-echo')

function Snap([string]$tag) {
    & python.exe .\tools\ipc_client.py dump_summons --wait 4 2>&1 | Out-Null
    $src = Join-Path $game 'er_echo_summons.json'
    $j = Get-Content $src -Encoding utf8 -ErrorAction SilentlyContinue | ConvertFrom-Json
    if ($j) {
        $ids = ($j.chrs | ForEach-Object { "$($_.npc_param_id)/t$($_.team_type)" }) -join ", "
        Write-Host ("  [{0}] count={1} chrs=[{2}]" -f $tag, $j.count, $ids)
    }
}

& python.exe .\tools\ipc_client.py load_profile --path $profile --wait 4 2>&1 | Out-Null
& python.exe .\tools\ipc_client.py keep_summons --on true --wait 4 2>&1 | Out-Null
Write-Host "== summon (blue-face profile) =="
& python.exe .\tools\ipc_client.py summon --wait 4 2>&1 | Select-String 'ack' | Out-Null
for ($i = 1; $i -le 8; $i++) { Start-Sleep -Seconds 2; Snap "f_$i" }

Write-Host "=== log ==="
Select-String -Path $log -Pattern 'profile loaded|face|summon:|restored' | Select-Object -Last 12 | ForEach-Object { $_.Line }
