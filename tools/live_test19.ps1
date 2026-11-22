# Test 19: zero-command flow. er_echo.ini does everything (profiles + buddy rows + auto apply).
# Expectation after using the Lone Wolf ashes:
#   clone[0] lv=9, clone[1] lv=15, clone[2] lv=9  (2 profiles, i % 2)
#   all: equip[0]=31330000, equip[1]=2000000, face=0000000009...
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
Set-Location (Join-Path $game 'er-echo')

function Ipc([string[]]$argv) {
    & python.exe .\tools\ipc_client.py @argv --wait 4 2>&1 | Out-Null
}

Write-Host "config-driven test: just USE THE LONE WOLF ASHES (no manual commands, 300s window)"
$deadline = (Get-Date).AddSeconds(300)
$spawned = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 3
    Ipc @('dump_summons')
    $j = Get-Content (Join-Path $game 'er_echo_summons.json') -Encoding utf8 -ErrorAction SilentlyContinue | ConvertFrom-Json
    if ($j -and ($j.chrs | Where-Object { $_.npc_param_id -eq 100000010 })) { $spawned = $true; break }
}
Write-Host ("spawned={0}" -f $spawned)

if ($spawned) {
    Start-Sleep -Seconds 4
    Ipc @('clone_info')
    $c = Get-Content (Join-Path $game 'er_echo_clone_info.json') -Encoding utf8 | ConvertFrom-Json
    $clones = @($c.rows | Where-Object { $_.is_player_ins })
    Write-Host ("=== clones={0} ===" -f $clones.Count)
    $i = 0
    foreach ($cl in $clones) {
        Write-Host ("clone[{0}] lv={1} vigor={2} eq0={3} eq1={4} head={5} face={6}" -f `
            $i, $cl.level, $cl.vigor, $cl.equip[0], $cl.equip[1], $cl.equip_head, $cl.face_prefix)
        $i++
    }
    Ipc @('dump_profile')
    $p = Get-Content (Join-Path $game 'er_echo_profile.json') -Encoding utf8 | ConvertFrom-Json
    Write-Host ("player: lv={0} block_pos={1} block={2}" -f $p.level, ($p.block_position -join ','), $p.block_id)
}

Write-Host "=== log ==="
Select-String -Path $log -Pattern 'config profile|config: BuddyParam|config applied|auto_apply|follow:' | Select-Object -Last 14 | ForEach-Object { $_.Line }
