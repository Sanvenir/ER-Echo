#requires -Version 5
<#
.SYNOPSIS
  在「二级菜单（运行时注入）」和「根列表 5 项（离线 ESD fallback）」之间切换。

.DESCRIPTION
  两份 ESD 都留在仓库里：
    er-echo/ui/out_vanilla/   原版 t000001000（二级菜单模式下部署）
    er-echo/ui/out_rootmenu/  根列表 5 项补丁版（fallback）

  二级菜单模式：部署 vanilla ESD + er_echo.ini 里 nested_menu=true
                （DLL 在 EzState::EnterState 里注入「战友」→ 6 项子菜单）
  根列表模式：  部署根列表 ESD + nested_menu=false
                （不注入；赐福最上面直接是 人数/号位/重召 五项，已实测）

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\switch_menu_mode.ps1 -Mode nested
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\switch_menu_mode.ps1 -Mode root
#>
param(
    [ValidateSet('nested', 'root')]
    [string]$Mode = 'nested'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'gamedir.ps1')
$repo = Split-Path -Parent $PSScriptRoot      # 源码根（ESD 构建产物在这里）
$game = Get-ErEchoGameDir

# 插件布局（mods\ER-Echo\）优先，老平铺布局兜底
$ini = Join-Path $game 'mods\ER-Echo\er_echo.ini'
if (-not (Test-Path -LiteralPath $ini)) { $ini = Join-Path $game 'er_echo.ini' }
$talk = Join-Path $game 'mods\ER-Echo\mod\script\talk\m00_00_00_00.talkesdbnd.dcx'
if (-not (Test-Path -LiteralPath (Split-Path -Parent $talk))) {
    $talk = Join-Path $game 'mod\script\talk\m00_00_00_00.talkesdbnd.dcx'
}

$source = if ($Mode -eq 'nested') {
    Join-Path $repo 'ui\out_vanilla\m00_00_00_00.talkesdbnd.dcx'
} else {
    Join-Path $repo 'ui\out_rootmenu\m00_00_00_00.talkesdbnd.dcx'
}
if (-not (Test-Path $source)) { throw "missing ESD build: $source" }

Copy-Item $source $talk -Force
Write-Host "[ok] deployed $Mode ESD -> $talk"

# 改 ini：有 nested_menu 就替换，没有就补一个 [ui] 段。
$text = Get-Content $ini -Raw -Encoding UTF8
$value = if ($Mode -eq 'nested') { 'true' } else { 'false' }
if ($text -match '(?m)^\s*nested_menu\s*=') {
    $text = [regex]::Replace($text, '(?m)^\s*nested_menu\s*=.*$', "nested_menu=$value")
} else {
    $text = $text.TrimEnd() + "`r`n`r`n[ui]`r`n; 赐福「战友」二级菜单（运行时 EzState 注入）`r`nnested_menu=$value`r`n"
}
[System.IO.File]::WriteAllText($ini, $text, [System.Text.UTF8Encoding]::new($false))
Write-Host "[ok] er_echo.ini nested_menu=$value"
Write-Host "     重启游戏生效（ESD 只在启动时加载）"
