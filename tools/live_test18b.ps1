# Test 18b: multi-profile injection in the CURRENT session (no restart).
# Expects clone profiles already set (test_face = lv9, live_test = lv15) and apply_stats on.
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
Set-Location (Join-Path $game 'er-echo')

function Ipc([string[]]$argv) {
    & python.exe .\tools\ipc_client.py @argv --wait 4 2>&1 | Out-Null
}

Write-Host "USE THE LONE WOLF ASHES NOW (360s window) - second summon, 2 profiles"
$deadline = (Get-Date).AddSeconds(360)
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
    Ipc @('apply_to_clone')
    Ipc @('clone_info')
    $c = Get-Content (Join-Path $game 'er_echo_clone_info.json') -Encoding utf8 | ConvertFrom-Json
    $clones = @($c.rows | Where-Object { $_.is_player_ins })
    Write-Host ("=== clones={0} (expect level pattern 9,15,9 for 2 profiles) ===" -f $clones.Count)
    $i = 0
    foreach ($cl in $clones) {
        Write-Host ("clone[{0}] lv={1} vigor={2} eq0={3} eq1={4} head={5} face={6}" -f `
            $i, $cl.level, $cl.vigor, $cl.equip[0], $cl.equip[1], $cl.equip_head, $cl.face_prefix)
        $i++
    }
}

Write-Host "=== log ==="
Select-String -Path $log -Pattern 'clone profile|auto_apply|apply_to_clone|set_clone_profiles' | Select-Object -Last 14 | ForEach-Object { $_.Line }
