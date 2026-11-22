#requires -Version 5.1
<#
  ELDEN RING 游戏目录定位（给本仓库的脚本共用）。

  源码已经搬出游戏目录（D:\Projects\ER-Echo），所以不能再靠
  「$PSScriptRoot 的爷爷目录」猜游戏路径了。查找顺序：

    1. -Path 参数
    2. 环境变量 ER_ECHO_GAME_DIR
    3. 老布局：源码仍在 <Game>\er-echo\ 里
    4. 当前工作目录（在 Game 里跑脚本时）
    5. Steam 注册表 + libraryfolders.vdf 里的所有库

  用法：
      . (Join-Path $PSScriptRoot 'gamedir.ps1')
      $game = Get-ErEchoGameDir            # 或 Get-ErEchoGameDir -Path 'D:\...\Game'
#>

function Get-ErEchoGameDir {
    [CmdletBinding()]
    param([string]$Path)

    $cands = New-Object System.Collections.ArrayList
    if ($Path) { [void]$cands.Add($Path) }
    if ($env:ER_ECHO_GAME_DIR) { [void]$cands.Add($env:ER_ECHO_GAME_DIR) }
    # 老布局：<Game>\er-echo\tools\gamedir.ps1
    [void]$cands.Add((Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
    [void]$cands.Add((Get-Location).Path)

    $steamRoots = @()
    foreach ($entry in @(
        @{ Hive = 'HKCU:\Software\Valve\Steam'; Name = 'SteamPath' },
        @{ Hive = 'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam'; Name = 'InstallPath' },
        @{ Hive = 'HKLM:\SOFTWARE\Valve\Steam'; Name = 'InstallPath' })) {
        try {
            $v = (Get-ItemProperty -Path $entry.Hive -Name $entry.Name -ErrorAction Stop).($entry.Name)
            if ($v) { $steamRoots += $v }
        } catch { }
    }
    foreach ($steam in $steamRoots) {
        [void]$cands.Add((Join-Path $steam 'steamapps\common\ELDEN RING\Game'))
        $vdf = Join-Path $steam 'steamapps\libraryfolders.vdf'
        if (Test-Path -LiteralPath $vdf) {
            foreach ($m in [regex]::Matches((Get-Content -LiteralPath $vdf -Raw), '"path"\s+"([^"]+)"')) {
                $lib = $m.Groups[1].Value -replace '\\\\', '\'
                [void]$cands.Add((Join-Path $lib 'steamapps\common\ELDEN RING\Game'))
            }
        }
    }

    foreach ($c in $cands) {
        if (-not $c) { continue }
        try { $p = (Resolve-Path -LiteralPath $c -ErrorAction Stop).Path } catch { continue }
        if (Test-Path -LiteralPath (Join-Path $p 'eldenring.exe')) { return $p }
    }
    throw ("找不到 ELDEN RING 游戏目录（含 eldenring.exe）。" +
           "用 -GameDir 指定，或设置环境变量 ER_ECHO_GAME_DIR。")
}
