# 等游戏退出（= er_echo.dll 不再被映射）-> 把编译好的 er_echo.new.dll 换成正式 DLL。
# 不重启游戏、不跑测试。
#
# 用法：powershell -NoProfile -ExecutionPolicy Bypass -File tools\swap_dll_on_exit.ps1 [-TimeoutMinutes 240]
#
# 支持两种安装布局（和 build.ps1 一致）：
#   - 插件：<Game>\mods\ER-Echo\er_echo.new.dll -> er_echo.dll
#   - 平铺：<Game>\er_echo.new.dll             -> er_echo.dll
#
# 注意：**不要**用 `Get-Process eldenring` 判断是否退出 —— 这个脚本常常在
# 沙箱/受限令牌里跑，看不到游戏进程（tasklist 会直接 Access denied）。所以这里
# 只看「文件还能不能覆盖」：锁着就等，能覆盖就说明进程已经放开 DLL。
param([int]$TimeoutMinutes = 240)
$ErrorActionPreference = 'Continue'

. (Join-Path $PSScriptRoot 'gamedir.ps1')
try {
    $game = Get-ErEchoGameDir
} catch {
    Write-Host "[swap] 找不到游戏目录：$($_.Exception.Message)"
    exit 1
}

$cands = @()
$pluginDir = Join-Path $game 'mods\ER-Echo'
$cands += [pscustomobject]@{ New = Join-Path $pluginDir 'er_echo.new.dll'; Live = Join-Path $pluginDir 'er_echo.dll' }
$cands += [pscustomobject]@{ New = Join-Path $game 'er_echo.new.dll'; Live = Join-Path $game 'er_echo.dll' }

$job = $null
foreach ($c in $cands) {
    if (Test-Path -LiteralPath $c.New) { $job = $c; break }
}
if (-not $job) {
    Write-Host '[swap] 没找到 er_echo.new.dll（先跑 mod\build.ps1）'
    exit 1
}
if (-not (Test-Path -LiteralPath $job.Live)) {
    Write-Host "[swap] 目标位置没有 er_echo.dll：$($job.Live)（还没安装？）"
    exit 1
}

Write-Host "[swap] $($job.New)"
Write-Host "[swap]   -> $($job.Live)"
Write-Host "[swap] 等游戏退出、DLL 解锁（最多 $TimeoutMinutes 分钟）..."

$deadline = (Get-Date).AddMinutes($TimeoutMinutes)
$lastLog = Get-Date
while ((Get-Date) -lt $deadline) {
    try {
        Copy-Item -LiteralPath $job.New -Destination $job.Live -Force -ErrorAction Stop
        $item = Get-Item -LiteralPath $job.Live
        Write-Host ("[swap] done: er_echo.dll = {0} bytes ({1})" -f $item.Length, $item.LastWriteTime)
        Remove-Item -LiteralPath $job.New -Force -ErrorAction SilentlyContinue
        exit 0
    } catch {
        # 游戏还开着（文件被映射）时 Copy-Item 会失败；等 2 秒再试。
        if (((Get-Date) - $lastLog).TotalSeconds -ge 60) {
            Write-Host ('[swap] 还在等（{0:HH:mm:ss}）：{1}' -f (Get-Date), $_.Exception.Message)
            $lastLog = Get-Date
        }
        Start-Sleep -Seconds 2
    }
}
Write-Host '[swap] TIMEOUT：游戏一直没退出，er_echo.new.dll 保留在原处'
exit 1
