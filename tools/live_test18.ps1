# Test 18: multiple profiles at once - clone i gets profile i % n (different saves in one summon).
# Prereq: er_echo.new.dll staged; run restart_and_test18.ps1 (or reuse a running game).
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
Set-Location (Join-Path $game 'er-echo')

function Ipc([string[]]$argv) {
    & python.exe .\tools\ipc_client.py @argv --wait 4 2>&1 | Out-Null
}

# Two distinct profiles: level 9 (test face) and level 15 (live dump export).
Ipc @('set_clone_profiles', '--paths', 'tools/profile.test_face.json,tools/profile.live_test.json')
Ipc @('apply_stats', '--on', 'true')
Ipc @('auto_apply', '--on', 'true')
foreach ($row in 23200000, 23200001, 23200002) {
    Ipc @('set_buddy_row', '--id', "$row", '--npc', '100000010', '--think', '100000010', '--init', '26050', '--follow', '2')
}

Write-Host "USE THE LONE WOLF ASHES NOW (240s window)"
$deadline = (Get-Date).AddSeconds(240)
$spawned = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    Ipc @('dump_summons')
    $j = Get-Content (Join-Path $game 'er_echo_summons.json') -Encoding utf8 -ErrorAction SilentlyContinue | ConvertFrom-Json
    if ($j -and ($j.chrs | Where-Object { $_.npc_param_id -eq 100000010 })) { $spawned = $true; break }
}
Write-Host ("spawned={0}" -f $spawned)

if ($spawned) {
    Start-Sleep -Seconds 3
    Ipc @('apply_to_clone')
    Ipc @('clone_info')
    $c = Get-Content (Join-Path $game 'er_echo_clone_info.json') -Encoding utf8 | ConvertFrom-Json
    $clones = @($c.rows | Where-Object { $_.is_player_ins })
    Write-Host ("clones={0}" -f $clones.Count)
    $i = 0
    foreach ($cl in $clones) {
        Write-Host ("  clone[{0}] level={1} equip0={2} equip1={3} face_prefix={4}" -f $i, $cl.level, $cl.equip[0], $cl.equip[1], $cl.face_prefix)
        $i++
    }
    Write-Host "EXPECTED: level pattern 9,15,9 (profile i % 2); equip[0]=31330000 equip[1]=2000000 on all."
}

Write-Host "=== log ==="
Select-String -Path $log -Pattern 'clone profile|auto_apply|apply_to_clone|set_clone_profiles' | Select-Object -Last 14 | ForEach-Object { $_.Line }
