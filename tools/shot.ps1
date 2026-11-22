#requires -Version 5
<#
.SYNOPSIS
  抓一张当前主屏截图（默认写到 er-echo\shots\shot_<时间>.png）。

.DESCRIPTION
  用 System.Drawing 的 CopyFromScreen，足够验证赐福菜单/HUD。
  游戏是独占全屏也能抓到（Desktop 合成层）；多显示器只抓主屏。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\shot.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\shot.ps1 -Out er-echo\shots\menu.png
#>
param(
    [string]$Out = ""
)

Add-Type -AssemblyName System.Windows.Forms, System.Drawing

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not $Out) {
    $dir = Join-Path $root 'er-echo\shots'
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $Out = Join-Path $dir ("shot_" + (Get-Date -Format 'HHmmss') + ".png")
}

$screen = [System.Windows.Forms.Screen]::PrimaryScreen
$bounds = $screen.Bounds
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($bounds.X, $bounds.Y, 0, 0, $bmp.Size)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose()
$bmp.Dispose()
Write-Host "saved $Out"
