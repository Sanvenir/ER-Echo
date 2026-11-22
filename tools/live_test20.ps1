# Test 20: summon using profiles exported OFFLINE from the isolated old save.
# Expect: clone[0] = Sirenix lv17, clone[1] = Ludwig lv9, clone[2] = Sirenix lv17.
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
Set-Location (Join-Path $game 'er-echo')

function Ipc([string[]]$argv) {
    & python.exe .\tools\ipc_client.py @argv --wait 4 2>&1 | Out-Null
}

Write-Host "USE THE LONE WOLF ASHES NOW (360s) - profiles came from an offline .sl2 export"
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
    Ipc @('clone_info')
    $c = Get-Content (Join-Path $game 'er_echo_clone_info.json') -Encoding utf8 | ConvertFrom-Json
    $clones = @($c.rows | Where-Object { $_.is_player_ins })
    Write-Host ("=== clones={0} (expect Sirenix lv17 / Ludwig lv9 / Sirenix lv17) ===" -f $clones.Count)
    $i = 0
    foreach ($cl in $clones) {
        Write-Host ("clone[{0}] lv={1} vit={2} eq0={3} eq1={4} eq3={5} face={6} dist={7}" -f `
            $i, $cl.level, $cl.vigor, $cl.equip[0], $cl.equip[1], $cl.equip[3], $cl.face_prefix, $cl.distance)
        $i++
    }
    Ipc @('dump_profile')
}

Write-Host "=== log ==="
Select-String -Path $log -Pattern 'clone profile|auto_apply|apply_to_clone|follow:' | Select-Object -Last 12 | ForEach-Object { $_.Line }
