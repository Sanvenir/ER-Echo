# 等游戏退出 → 换新 DLL → 启动 → 等自动 dump
# 用法：powershell -ExecutionPolicy Bypass -File .\restart_with_new_dll.ps1

$ErrorActionPreference = 'Continue'
$game = 'D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game'
$newDll = Join-Path $game 'er_echo.new.dll'
$dll = Join-Path $game 'er_echo.dll'

Write-Host "[1/4] waiting for eldenring.exe to exit (max 6 min)…"
$deadline = (Get-Date).AddMinutes(6)
while ((Get-Process eldenring -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
}
if (Get-Process eldenring -ErrorAction SilentlyContinue) {
    Write-Host "TIMEOUT: game still running, nothing changed"
    exit 1
}

Write-Host "[2/4] swapping DLL"
Copy-Item $newDll $dll -Force
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $dll)) { Write-Host "swap failed"; exit 1 }
Remove-Item (Join-Path $game 'er_echo_*.json') -Force -ErrorAction SilentlyContinue
Write-Host ("      {0} bytes" -f (Get-Item $dll).Length)

Write-Host "[3/4] launching via launchmod_eldenring.bat"
Start-Process -FilePath (Join-Path $game 'launchmod_eldenring.bat') -WorkingDirectory $game

$deadline = (Get-Date).AddMinutes(3)
while (-not (Get-Process eldenring -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 1
}
if (Get-Process eldenring -ErrorAction SilentlyContinue) {
    Write-Host "      eldenring.exe started"
} else {
    Write-Host "      WARN: eldenring.exe did not start"
}

Write-Host "[4/4] waiting for auto dumps (max 5 min)…"
$deadline = (Get-Date).AddMinutes(5)
while ((Get-Date) -lt $deadline) {
    $files = Get-ChildItem (Join-Path $game 'er_echo_*.json') -ErrorAction SilentlyContinue
    if ($files -and $files.Count -ge 2) { break }
    Start-Sleep -Seconds 3
}

Write-Host "=== dumps ==="
Get-ChildItem (Join-Path $game 'er_echo_*.json') -ErrorAction SilentlyContinue |
    Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize

Write-Host "=== log tail ==="
Get-Content (Join-Path $game 'er_echo.log') -Encoding utf8 -Tail 20 -ErrorAction SilentlyContinue
