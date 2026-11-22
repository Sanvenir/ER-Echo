# Test 21: profiles exported OFFLINE from the account's MAIN save (ER0000.sl2).
# Expect: clone[0] = Sv lv15 (armor 660000, face 0000..09), clone[1] = May lv6 (armor 630000, face 0a00..67),
#         clone[2] = Sv lv15.
$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$log = Join-Path $game 'er_echo.log'
Set-Location (Join-Path $game 'er-echo')

function Ipc([string[]]$argv) {
    & python.exe .\tools\ipc_client.py @argv --wait 4 2>&1 | Out-Null
}

Write-Host "USE THE LONE WOLF ASHES NOW (360s) - profiles = ER0000.sl2 offline export (Sv lv15 / May lv6)"
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
    Write-Host ("=== clones={0} (expect Sv lv15 / May lv6 / Sv lv15) ===" -f $clones.Count)
    $i = 0
    foreach ($cl in $clones) {
        Write-Host ("clone[{0}] lv={1} vit={2} eq0={3} eq1={4} head={5} body={6} face={7}" -f `
            $i, $cl.level, $cl.vigor, $cl.equip[0], $cl.equip[1], $cl.equip_head, $cl.equip_body, $cl.face_prefix)
        $i++
    }
}

Write-Host "=== log ==="
Select-String -Path $log -Pattern 'clone profile|auto_apply|follow:' | Select-Object -Last 10 | ForEach-Object { $_.Line }
