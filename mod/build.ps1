# 构建 er_echo.dll（已验证可编译）
#
# 前置：
#   1. rustup + x86_64-pc-windows-gnu 工具链（安装见 docs/implementation-log.md）
#   2. MSYS2 binutils 解压到 %USERPROFILE%\er-tools\binutils
#      （rust 的 gnu 工具链自带 dlltool 但缺 as.exe，需要 binutils 的 as.exe）
#
# 用法：powershell -ExecutionPolicy Bypass -File .\build.ps1
#
# 注意：本文件必须保存为 **UTF-8 with BOM**。PowerShell 5.1 会把无 BOM 的
# UTF-8 当 ANSI(GBK) 读，中文注释末尾的字节可能吞掉换行，把下一行代码并进注释
# （2026-11-16 实测：`$live = ...` 整行被吞，导致 DLL 一直没被复制到游戏目录）。

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot          # er-echo/
. (Join-Path $root 'tools\gamedir.ps1')
try { $game = Get-ErEchoGameDir } catch { $game = $null }   # 只用于顺手拷 DLL，找不到就跳过
$binutils = Join-Path $env:USERPROFILE 'er-tools\binutils\mingw64\bin'
$selfcontained = Join-Path $env:USERPROFILE '.rustup\toolchains\stable-x86_64-pc-windows-gnu\lib\rustlib\x86_64-pc-windows-gnu\bin\self-contained'
$cargoBin = Join-Path $env:USERPROFILE '.cargo\bin'

foreach ($p in @($binutils, $selfcontained, $cargoBin)) {
    if (-not (Test-Path $p)) { throw "missing toolchain dir: $p" }
}
$env:Path = "$binutils;$selfcontained;$cargoBin;$env:Path"

Push-Location $PSScriptRoot
try {
    & cargo.exe build --release
    if ($LASTEXITCODE -ne 0) { throw "cargo build failed (exit $LASTEXITCODE)" }

    $dll = Join-Path $PSScriptRoot 'target\release\er_echo.dll'
    if (-not (Test-Path $dll)) { throw "dll not found: $dll" }
    $size = [math]::Round((Get-Item $dll).Length / 1KB, 1)
    Write-Host "[ok] built  $dll ($size KB)"

    # 游戏在跑时 er_echo.dll 被映射，覆盖会失败：退回写 er_echo.new.dll，
    # 由 tools/swap_dll_on_exit.ps1 在退出后替换。
    if (-not $game) {
        Write-Host '[i] 没找到游戏目录，跳过拷贝（只编译）'
        return
    }
    # 只往「已经装好的」位置拷：插件布局 mods\ER-Echo\，或游戏根目录已有 er_echo.dll 的平铺布局。
    # 都没装（纯净游戏目录）就只编译、不往游戏目录扔文件 —— 安装用 ER-Echo-Setup.exe。
    $pluginDir = Join-Path $game 'mods\ER-Echo'
    $flat = Join-Path $game 'er_echo.dll'
    if (Test-Path -LiteralPath $pluginDir) {
        $live = Join-Path $pluginDir 'er_echo.dll'
    } elseif (Test-Path -LiteralPath $flat) {
        $live = $flat
    } else {
        Write-Host '[i] 游戏目录里没装 ER Echo（无 mods\ER-Echo\，也无 er_echo.dll），只编译不拷贝'
        return
    }
    $staged = Join-Path (Split-Path -Parent $live) 'er_echo.new.dll'
    try {
        Copy-Item $dll $live -Force -ErrorAction Stop
        Write-Host "[ok] copied $live"
    } catch {
        Copy-Item $dll $staged -Force
        Write-Host "[warn] $live is locked (game running); staged to $staged"
        Write-Host "       restart with tools/swap_dll_on_exit.ps1 (it swaps the DLL after exit)"
    }
} finally {
    Pop-Location
}
