param([string]$Game,[string]$Out,[string]$Shot)
try {
  Start-Process -FilePath (Join-Path $Game 'mods\ER-Echo\launch-er-echo-admin.bat') -WorkingDirectory $Game -WindowStyle Minimized
  $deadline=(Get-Date).AddSeconds(150)
  while((Get-Date) -lt $deadline){
    Start-Sleep -Seconds 2
    $p=Get-Process eldenring -ErrorAction SilentlyContinue
    if($p -and $p.MainWindowHandle -ne 0){ break }
  }
  Add-Content -LiteralPath $Out -Value ("window up: " + (Get-Date -Format 'HH:mm:ss'))
  Start-Sleep -Seconds 35
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Game 'er-echo\tools\press_key.ps1') -Key E | Out-Null
  Start-Sleep -Seconds 10
  Add-Type -AssemblyName System.Drawing,System.Windows.Forms
  $b=[System.Windows.Forms.SystemInformation]::VirtualScreen
  $bmp=New-Object System.Drawing.Bitmap($b.Width,$b.Height)
  $g=[System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($b.Left,$b.Top,0,0,$bmp.Size)
  $bmp.Save($Shot,[System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $bmp.Dispose()
  & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Game 'er-echo\tools\press_key.ps1') -Key E | Out-Null
  Start-Sleep -Seconds 5
  if (Test-Path (Join-Path $Game 'er_echo.log')) {
    Get-Content (Join-Path $Game 'er_echo.log') -Encoding utf8 | Add-Content -LiteralPath $Out
  }
} catch { Add-Content -LiteralPath $Out -Value ("ERROR: " + $_.Exception.ToString()) }