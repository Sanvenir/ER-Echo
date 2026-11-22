# Test 17: inject a profile into the summoned PlayerIns clone (player untouched).
# Also probes WHICH equipment source the engine honors (chr_asm vs pgd.equipment.chr_asm vs entries).
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
$root = Join-Path $game 'er-echo'
Set-Location $root

function Ipc([string[]]$argv) {
    & python.exe .\tools\ipc_client.py @argv --wait 4 2>&1 | Out-Null
}

$profile = (Resolve-Path (Join-Path $root 'tools\profile.test_face.json')).Path
Ipc @('load_profile', '--path', $profile)
foreach ($row in 23200000, 23200001, 23200002) {
    Ipc @('set_buddy_row', '--id', "$row", '--npc', '100000010', '--think', '100000010', '--init', '26050', '--follow', '2')
}
Ipc @('auto_apply', '--on', 'true')
Ipc @('dump_profile')

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
    Ipc @('apply_to_clone', '--stats', 'true')
    Ipc @('equip_probe')
    Ipc @('clone_info')
    $c = Get-Content (Join-Path $game 'er_echo_clone_info.json') -Encoding utf8 | ConvertFrom-Json
    $clones = @($c.rows | Where-Object { $_.is_player_ins })
    Write-Host ("=== clones={0} ===" -f $clones.Count)
    $i = 0
    foreach ($cl in $clones) {
        Write-Host ("clone[{0}] lv={1} face={2}" -f $i, $cl.level, $cl.face_prefix)
        Write-Host ("  chr_asm   : {0}" -f (($cl.equip[0..5]) -join ','))
        Write-Host ("  pgd_asm   : {0}" -f (($cl.pgd_chr_asm[0..5]) -join ','))
        Write-Host ("  entries   : {0}" -f (($cl.entries[0..5]) -join ','))
        Write-Host ("  idx_list  : {0}" -f (($cl.equip_idx_list[0..5]) -join ','))
        Write-Host ("  gaitem0   : {0}" -f $cl.gaitem_handles[0])
        $i++
    }
    Write-Host "EXPECTED: lv=9, face starts 0000000009..., chr_asm/pgd_asm[0..1]=31330000,2000000"
}

Write-Host "=== log ==="
Select-String -Path $log -Pattern 'apply_to_clone|equip_probe|auto_apply|profile loaded|follow:' | Select-Object -Last 16 | ForEach-Object { $_.Line }
