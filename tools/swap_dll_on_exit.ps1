# 等游戏退出 -> 只把 er_echo.new.dll 换成 er_echo.dll，不重启、不跑测试。
# 用法：powershell -ExecutionPolicy Bypass -File tools\swap_dll_on_exit.ps1 [-TimeoutMinutes 240]
param([int]$TimeoutMinutes = 240)
$ErrorActionPreference = 'Continue'
# 脚本在 <game>\er-echo\tools 下：往上两级 = 游戏根目录（换机器不用改路径）
$game = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$newDll = Join-Path $game 'er_echo.new.dll'
$dll = Join-Path $game 'er_echo.dll'

if (-not (Test-Path $newDll)) { Write-Host "no er_echo.new.dll"; exit 1 }

Write-Host "[swap] waiting for eldenring.exe to exit (max $TimeoutMinutes min)..."
$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
while ((Get-Process eldenring -ErrorAction SilentlyContinue) -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 2 }
if (Get-Process eldenring -ErrorAction SilentlyContinue) { Write-Host "[swap] TIMEOUT (still running)"; exit 1 }

for ($i = 0; $i -lt 20; $i++) {
    try {
        Copy-Item $newDll $dll -Force -ErrorAction Stop
        Write-Host ("[swap] done: er_echo.dll = {0} bytes ({1})" -f (Get-Item $dll).Length, (Get-Item $dll).LastWriteTime)
        exit 0
    } catch {
        Start-Sleep -Seconds 1
    }
}
Write-Host "[swap] FAILED: er_echo.dll still locked"
exit 1
