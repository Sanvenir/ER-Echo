# Survive test: buff clone (fall immunity + hp) then summon, watch 16s.
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
$profile = Join-Path $game 'er-echo\tools\profile.example.json'
Set-Location (Join-Path $game 'er-echo')

function Snap([string]$tag) {
    & python.exe .\tools\ipc_client.py dump_summons --wait 4 2>&1 | Out-Null
    $src = Join-Path $game 'er_echo_summons.json'
    $j = Get-Content $src -Encoding utf8 -ErrorAction SilentlyContinue | ConvertFrom-Json
    if ($j) {
        $ids = ($j.chrs | ForEach-Object { "$($_.npc_param_id)/t$($_.team_type)@$([math]::Round($_.pos[0]))" }) -join ", "
        Write-Host ("  [{0}] count={1} chrs=[{2}]" -f $tag, $j.count, $ids)
    }
}

& python.exe .\tools\ipc_client.py load_profile --path $profile --wait 4 2>&1 | Out-Null
& python.exe .\tools\ipc_client.py keep_summons --on true --wait 4 2>&1 | Out-Null
Write-Host "== summon (fall-immune clone) =="
& python.exe .\tools\ipc_client.py summon --wait 4 2>&1 | Select-String 'ack' | Out-Null

for ($i = 1; $i -le 8; $i++) { Start-Sleep -Seconds 2; Snap "s_$i" }

Write-Host "=== log ==="
Select-String -Path $log -Pattern 'buffed|summon:|restored' | Select-Object -Last 10 | ForEach-Object { $_.Line }
