param([string]$Game,[string]$Out,[string]$Shot)
try {
  $log = Join-Path $Game 'er_echo.log'
  $len0 = if (Test-Path $log) { (Get-Item $log).Length } else { 0 }
  Start-Process -FilePath (Join-Path $Game 'mods\ER-Echo\launch-er-echo-admin.bat') -WorkingDirectory $Game -WindowStyle Minimized
  $deadline = (Get-Date).AddSeconds(150)
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    if (Get-Process eldenring -ErrorAction SilentlyContinue) { break }
  }
  Start-Sleep -Seconds 30
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Game 'er-echo\tools\press_key.ps1') -Key E
  Start-Sleep -Seconds 8
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Game 'er-echo\tools\press_key.ps1') -Key E
  Start-Sleep -Seconds 6
  Add-Type -AssemblyName System.Drawing,System.Windows.Forms
  $b=[System.Windows.Forms.SystemInformation]::VirtualScreen
  $bmp=New-Object System.Drawing.Bitmap($b.Width,$b.Height)
  $g=[System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($b.Left,$b.Top,0,0,$bmp.Size)
  $bmp.Save($Shot,[System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $bmp.Dispose()
  $lines = if (Test-Path $log) { Get-Content -LiteralPath $log -Encoding utf8 } else { @() }
  $lines | Where-Object { $_ -match 'ezstate|menu|profile|summon: using|auto_apply' } |
    Select-Object -Last 40 | Set-Content -LiteralPath $Out -Encoding utf8
} catch {
  "ERROR: " + $_.Exception.ToString() | Set-Content -LiteralPath $Out -Encoding utf8
}