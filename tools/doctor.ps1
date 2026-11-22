#requires -Version 5.1
<#
.SYNOPSIS
  ER Echo 安装自检：在**另一台机器**上判断这个 mod 能不能生效、缺什么。

.DESCRIPTION
  只读检查，不改任何文件（唯一的写操作是在游戏目录建一个临时文件测权限、随即删除）。
  检查项：
    * 游戏本体版本（本 mod 只支持 1.17.2 / exe 2.7.2.0 或 2.7.2.1）
    * ModEngine2 加载器 + config_eldenring.toml（external_dlls / mods 两处）
    * er_echo.dll 架构 + 依赖（只允许系统 DLL，缺哪个）
    * er_echo.ini（profiles 是否存在、JSON 是否合法、language 是否认得）
    * 游戏内菜单的 ESD 是否就位
    * 游戏目录是否可写（Program Files 下常见坑）
    * 可选组件（Python / oo2core，仅工具用）

.PARAMETER Target
  要检查的目录，默认是本脚本所在 `er-echo\tools` 往上两级的游戏根目录。
  也可以指向打包出来的发布目录（没有 eldenring.exe 时自动跳过游戏本体检查）。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\doctor.ps1

.EXAMPLE
  # 校验打好的发布目录
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\doctor.ps1 -Target er-echo\dist\ER-Echo-20261120
#>
[CmdletBinding()]
param(
    [string]$Target
)

$ErrorActionPreference = 'Stop'
if (-not $Target) {
    # 脚本在 <game>\er-echo\tools 下，往上两级就是游戏根目录
    . (Join-Path $PSScriptRoot 'gamedir.ps1')
    $Target = Get-ErEchoGameDir
}
$script:fails = 0
$script:warns = 0

function Write-Check {
    param(
        [ValidateSet('PASS', 'WARN', 'FAIL', 'INFO')]
        [string]$Status,
        [string]$Title,
        [string]$Detail
    )
    $color = switch ($Status) {
        'PASS' { 'Green' }
        'WARN' { 'Yellow' }
        'FAIL' { 'Red' }
        default { 'Gray' }
    }
    $tag = switch ($Status) {
        'PASS' { '[ OK ]' }
        'WARN' { '[WARN]' }
        'FAIL' { '[FAIL]' }
        default { '[INFO]' }
    }
    Write-Host ("{0} {1}" -f $tag, $Title) -ForegroundColor $color
    if ($Detail) { Write-Host ("       " + $Detail) -ForegroundColor DarkGray }
    if ($Status -eq 'FAIL') { $script:fails++ }
    if ($Status -eq 'WARN') { $script:warns++ }
}

function Read-Pe {
    param([string]$Path)
    $b = [IO.File]::ReadAllBytes($Path)
    if ($b.Length -lt 0x100 -or $b[0] -ne 0x4D -or $b[1] -ne 0x5A) {
        throw "不是 PE 文件：$Path"
    }
    $pe = [BitConverter]::ToInt32($b, 0x3C)
    if ($b[$pe] -ne 0x50 -or $b[$pe + 1] -ne 0x45) { throw "缺少 PE 签名：$Path" }
    $machine = [BitConverter]::ToUInt16($b, $pe + 4)
    $nsec = [BitConverter]::ToUInt16($b, $pe + 6)
    $optSize = [BitConverter]::ToUInt16($b, $pe + 20)
    $opt = $pe + 24
    $magic = [BitConverter]::ToUInt16($b, $opt)
    if ($magic -eq 0x20B) { $dirOff = $opt + 112 } else { $dirOff = $opt + 96 }
    $impRva = [BitConverter]::ToUInt32($b, $dirOff + 8)
    $secOff = $opt + $optSize
    $sections = @()
    for ($i = 0; $i -lt $nsec; $i++) {
        $s = $secOff + $i * 40
        $sections += [pscustomobject]@{
            VirtualAddress = [BitConverter]::ToUInt32($b, $s + 12)
            VirtualSize    = [BitConverter]::ToUInt32($b, $s + 8)
            RawSize        = [BitConverter]::ToUInt32($b, $s + 16)
            RawPtr         = [BitConverter]::ToUInt32($b, $s + 20)
        }
    }
    [pscustomobject]@{
        Bytes     = $b
        Machine   = $machine
        Magic     = $magic
        Sections  = $sections
        ImportRva = $impRva
    }
}

function Get-RvaOffset {
    param($Pe, [uint32]$Rva)
    foreach ($s in $Pe.Sections) {
        $size = [Math]::Max($s.VirtualSize, $s.RawSize)
        if ($Rva -ge $s.VirtualAddress -and $Rva -lt ($s.VirtualAddress + $size)) {
            return [int64]$Rva - [int64]$s.VirtualAddress + [int64]$s.RawPtr
        }
    }
    return -1
}

function Get-PeImports {
    param($Pe)
    $names = @()
    if ($Pe.ImportRva -eq 0) { return $names }
    $b = $Pe.Bytes
    $off = Get-RvaOffset $Pe $Pe.ImportRva
    if ($off -lt 0) { return $names }
    for ($i = 0; $i -lt 512; $i++) {
        $d = $off + $i * 20
        if (($d + 20) -gt $b.Length) { break }
        $nameRva = [BitConverter]::ToUInt32($b, $d + 12)
        $firstThunk = [BitConverter]::ToUInt32($b, $d + 16)
        if ($nameRva -eq 0 -and $firstThunk -eq 0) { break }
        $no = Get-RvaOffset $Pe $nameRva
        if ($no -ge 0) {
            $sb = New-Object System.Text.StringBuilder
            while ($no -lt $b.Length -and $b[$no] -ne 0) {
                [void]$sb.Append([char]$b[$no])
                $no++
            }
            if ($sb.Length -gt 0) { $names += $sb.ToString() }
        }
    }
    return $names
}

function Get-IniValues {
    param([string]$Path)
    $values = @{}
    if (-not (Test-Path $Path)) { return $values }
    foreach ($line in [IO.File]::ReadAllLines($Path)) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith(';') -or $t.StartsWith('#') -or $t.StartsWith('[')) { continue }
        $i = $t.IndexOf('=')
        if ($i -lt 1) { continue }
        $values[$t.Substring(0, $i).Trim()] = $t.Substring($i + 1).Trim()
    }
    return $values
}

Write-Host ''
Write-Host '=== ER Echo 安装自检 ===' -ForegroundColor Cyan
Write-Host ("目标目录: " + $Target) -ForegroundColor DarkGray
Write-Host ''

if (-not (Test-Path -LiteralPath $Target)) {
    Write-Check FAIL '目标目录不存在' $Target
    Write-Host ''
    Write-Host ("结论: 无法继续，失败 {0} 项" -f $script:fails) -ForegroundColor Red
    exit 1
}
$Target = (Resolve-Path -LiteralPath $Target).Path

# ---------------------------------------------------------------- 游戏本体
$exe = Join-Path $Target 'eldenring.exe'
$isModDir = $false
foreach ($rel in @(
    'er_echo.dll', 'er-echo\er_echo.dll', 'mods\ER-Echo\er_echo.dll',
    'er_echo.ini', 'er-echo\er_echo.ini', 'mods\ER-Echo\er_echo.ini',
    'config-er-echo.toml'
)) {
    if (Test-Path -LiteralPath (Join-Path $Target $rel)) { $isModDir = $true; break }
}
if (-not (Test-Path -LiteralPath $exe)) {
    if ($isModDir) {
        Write-Check INFO '没有 eldenring.exe：按「发布目录」校验，跳过游戏本体检查' $Target
    } else {
        Write-Check FAIL '没有 eldenring.exe，也不像 ER Echo 的安装目录' '请把 -Target 指向 ...\ELDEN RING\Game'
    }
} else {
    $vi = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($exe)
    $ver = if ($vi.ProductVersion) { $vi.ProductVersion } else { $vi.FileVersion }
    if ($ver -eq '2.7.2.0' -or $ver -eq '2.7.2.1') {
        Write-Check PASS ("游戏版本 {0}（1.17.2，受支持）" -f $ver) 'mod 的 RVA 表与 AOB 就是按这个版本逆向的'
    } else {
        Write-Check FAIL ("游戏版本 {0} 不受支持" -f $ver) `
            '本 mod 只支持 1.17.2（exe 2.7.2.0 全球版 / 2.7.2.1 日版）。升级后需要重新逆向 RVA/AOB 再重编译，不能直接套用。'
    }
    if ($vi.ProductName -and $vi.ProductName -notmatch 'ELDEN RING') {
        Write-Check WARN 'ProductName 不是 ELDEN RING' $vi.ProductName
    }
}

# ---------------------------------------------------------------- ModEngine2
$me2 = Join-Path $Target 'modengine2_launcher.exe'
$me2dll = Join-Path $Target 'modengine2\bin\modengine2.dll'

# 支持两种布局：平铺（旧/完整包）和可插拔（er-echo\ 子目录 + 自己的 config/launcher）
$batCandidates = @(
    (Join-Path $Target 'launchmod_eldenring.bat'),
    (Join-Path $Target 'launch-er-echo.bat'),
    (Join-Path $Target 'er-echo\launch-er-echo.bat'),
    (Join-Path $Target 'mods\ER-Echo\launch-er-echo.bat')
)
$bat = $null
foreach ($c in $batCandidates) {
    if (Test-Path -LiteralPath $c) {
        if (-not $bat) { $bat = $c }
        $t = [IO.File]::ReadAllText($c)
        if ($t -match 'config-er-echo\.toml') { $bat = $c; break }
    }
}
if (-not $bat) { $bat = $batCandidates[0] }

$tomlCandidates = @(
    (Join-Path $Target 'config_eldenring.toml'),
    (Join-Path $Target 'config-er-echo.toml')
)
$toml = $null
foreach ($c in $tomlCandidates) {
    if (Test-Path -LiteralPath $c) {
        if (-not $toml) { $toml = $c }
        $t = [IO.File]::ReadAllText($c)
        if ($t -match 'er_echo\.dll') { $toml = $c; break }
    }
}
if (-not $toml) { $toml = $tomlCandidates[0] }

$missing = @()
if (-not (Test-Path -LiteralPath $me2)) { $missing += 'modengine2_launcher.exe' }
if (-not (Test-Path -LiteralPath $me2dll)) { $missing += 'modengine2\bin\modengine2.dll' }
if (-not (Test-Path -LiteralPath $bat)) { $missing += 'launch*.bat' }
if (-not (Test-Path -LiteralPath $toml)) { $missing += 'config*.toml' }
$isBundle = -not (Test-Path -LiteralPath $exe)
if ($missing.Count -eq 0) {
    Write-Check PASS 'ModEngine2 加载器文件齐全' ("launcher / modengine2\bin / {0} / {1}" -f (Split-Path -Leaf $bat), (Split-Path -Leaf $toml))
} elseif ($isBundle) {
    Write-Check INFO '发布目录不含 ModEngine2（正常）' '把本目录内容覆盖到 ...\ELDEN RING\Game，再按 INSTALL.md 装 ME2'
} else {
    Write-Check FAIL ('ModEngine2 缺文件: ' + ($missing -join ', ')) '从 Mod Engine 2 官方 release 解压到游戏根目录（本 mod 实测 2.1.0）'
}

if (Test-Path -LiteralPath $toml) {
    $tomlLeaf = Split-Path -Leaf $toml
    $ownConfig = ($tomlLeaf -ne 'config_eldenring.toml')
    $text = [IO.File]::ReadAllText($toml)
    if ($text -match '(?ms)^\s*external_dlls\s*=\s*\[(.*?)\]') {
        if ($Matches[1] -match 'er_echo\.dll') {
            Write-Check PASS ("{0}: external_dlls 含 er_echo.dll" -f $tomlLeaf) ''
        } else {
            Write-Check FAIL ("{0}: external_dlls 里没有 er_echo.dll" -f $tomlLeaf) 'DLL 不会被注入，游戏里什么都不会发生'
        }
    } else {
        Write-Check FAIL ("{0}: 找不到 external_dlls" -f $tomlLeaf) ''
    }
    if ($ownConfig) {
        Write-Check PASS ("{0}: 自带配置（不需要 mods 条目）" -f $tomlLeaf) '插件布局：本 mod 不替换游戏文件'
    } else {
        $modsOk = $false
        $modPath = ''
        if ($text -match '(?ms)^\s*mods\s*=\s*\[(.*?)\]') {
            # 平铺布局写 path = "mod"，插件布局写 path = "mods/ER-Echo/mod"；都算
            $block = $Matches[1] -replace "'", '"'
            if ($block -match 'path\s*=\s*"([^"]+)"') {
                $modPath = $Matches[1]
                if ($modPath -match '(^|/)mod$') { $modsOk = $true }
            }
        }
        if ($modsOk) {
            Write-Check PASS ("{0}: mod_loader 指向 {1}" -f $tomlLeaf, $modPath) '赐福菜单的 ESD 从这里加载'
        } else {
            Write-Check FAIL ('{0}: mods 里没有指向 mod 目录的 path' -f $tomlLeaf) 'mods=[] 时 ME2 不读 mod/script，游戏里没有「战友」菜单'
        }
    }
    if ($text -match '(?m)^\s*debug\s*=\s*true') {
        Write-Check WARN ("{0}: debug = true" -f $tomlLeaf) '正式游玩建议改 false（ME2 日志会很大）'
    }
}

# ---------------------------------------------------------------- 启动链（见 docs/handoff-launch.md）
$isAdmin = $false
try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $isAdmin = ([Security.Principal.WindowsPrincipal]::new($identity)).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
} catch { }
if ($isAdmin) {
    Write-Check PASS '当前是管理员权限' '可以用 launchmod_eldenring_admin.bat；代价是游戏里没有 Steam 覆盖层'
} else {
    Write-Check INFO '当前不是管理员权限' '普通 bat 即可；若启动约 10 秒闪退，换 admin 版或关 Steam 覆盖层'
}

$adminCandidates = @(
    (Join-Path $Target 'launchmod_eldenring_admin.bat'),
    (Join-Path $Target 'launch-er-echo-admin.bat'),
    (Join-Path $Target 'er-echo\launch-er-echo-admin.bat'),
    (Join-Path $Target 'mods\ER-Echo\launch-er-echo-admin.bat')
)
$adminBat = $adminCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$batLeaf = Split-Path -Leaf $bat
if (Test-Path -LiteralPath $bat) {
    $batText = [IO.File]::ReadAllText($bat)
    if ($batText -match '-p\s+"?[^"\r\n]*eldenring\.exe') {
        Write-Check PASS ("{0} 带 -p（跳过 ME2 的 Steam 路径探测）" -f $batLeaf) ''
    } else {
        Write-Check WARN ("{0} 没有 -p" -f $batLeaf) '个别机器上 ME2 2.1.0 的 -t er 会以 0xC0000409 崩在 ucrtbase.dll：加上 -p ".\eldenring.exe"'
    }
} else {
    Write-Check INFO '没有启动 bat' '用 ME2 自带启动脚本时，确保命令里有 -p ".\eldenring.exe"'
}
if (-not $adminBat) {
    Write-Check INFO '没有 admin 版启动 bat' '出现 10 秒闪退时需要提权启动；发布包里带这个文件'
}

# ---------------------------------------------------------------- DLL
$dll = @(
    (Join-Path $Target 'er_echo.dll'),
    (Join-Path $Target 'er-echo\er_echo.dll'),
    (Join-Path $Target 'mods\ER-Echo\er_echo.dll')
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $dll) { $dll = Join-Path $Target 'er_echo.dll' }
if (-not (Test-Path -LiteralPath $dll)) {
    Write-Check FAIL '没有 er_echo.dll' '把它放到游戏根目录（和 eldenring.exe 同级）'
} else {
    $size = [Math]::Round((Get-Item -LiteralPath $dll).Length / 1KB, 1)
    try {
        $pe = Read-Pe $dll
        if ($pe.Machine -eq 0x8664) {
            Write-Check PASS ("er_echo.dll 是 64 位 PE（{0} KB）" -f $size) ''
        } else {
            Write-Check FAIL ("er_echo.dll 架构不对（machine 0x{0:X4}）" -f $pe.Machine) '游戏是 x64，DLL 必须是 0x8664'
        }
        $imports = @(Get-PeImports $pe)
        $miss = @()
        foreach ($name in $imports) {
            $sys = Join-Path $env:SystemRoot ("System32\" + $name)
            if (-not (Test-Path -LiteralPath $sys)) { $miss += $name }
        }
        if ($miss.Count -eq 0) {
            Write-Check PASS ("DLL 依赖全部是系统 DLL（{0} 个）" -f $imports.Count) ($imports -join ', ')
        } else {
            $hard = @($miss | Where-Object { $_ -notmatch '^api-ms-win-' })
            if ($hard.Count -eq 0) {
                Write-Check INFO ('API Set 转发 DLL 不在 System32（正常）: ' + ($miss -join ', ')) '由 Windows 的 api-set schema 解析，不影响加载'
            } else {
                Write-Check FAIL ('缺少依赖 DLL: ' + ($hard -join ', ')) '装 VC++ 运行库没用：本 DLL 是 Rust GNU 目标，只依赖系统 DLL'
            }
        }
    } catch {
        Write-Check FAIL 'er_echo.dll 不是有效 PE' $_.Exception.Message
    }
}

# ---------------------------------------------------------------- 配置
$ini = @(
    (Join-Path $Target 'er_echo.ini'),
    (Join-Path $Target 'er-echo\er_echo.ini'),
    (Join-Path $Target 'mods\ER-Echo\er_echo.ini')
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $ini) { $ini = Join-Path $Target 'er_echo.ini' }
$cfg = @{}
if (-not (Test-Path -LiteralPath $ini)) {
    Write-Check FAIL '没有 er_echo.ini' 'DLL 会用内置默认值（不加载档案、不召唤）'
} else {
    $cfg = Get-IniValues $ini
    Write-Check PASS 'er_echo.ini 存在' ''

    $profiles = @()
    if ($cfg.ContainsKey('profiles') -and $cfg['profiles']) {
        $profiles = @($cfg['profiles'].Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    }
    if ($profiles.Count -eq 0) {
        Write-Check WARN 'profiles 为空' '仍可召唤，但克隆体用玩家自己的装备/外观；要「另一个存档的角色」必须导出 profile'
    } else {
        $bad = @()
        foreach ($rel in $profiles) {
            $p = $rel
            if (-not [IO.Path]::IsPathRooted($p)) { $p = Join-Path $Target $rel }
            if (-not (Test-Path -LiteralPath $p)) { $bad += "$rel（不存在）"; continue }
            try {
                $j = Get-Content -LiteralPath $p -Raw -Encoding UTF8 | ConvertFrom-Json
                if (-not $j.name) { $bad += "$rel（缺 name）" }
                $eq = @($j.equipment_param_ids).Count
                if ($eq -ne 22) { $bad += "$rel（equipment_param_ids=$eq，应为 22）" }
            } catch {
                $bad += "$rel（JSON 解析失败）"
            }
        }
        if ($bad.Count -eq 0) {
            Write-Check PASS ("profiles 可用（{0} 个）" -f $profiles.Count) ($profiles -join ', ')
        } else {
            Write-Check FAIL ('profiles 有问题: ' + ($bad -join '; ')) '用 tools\export_profile_from_save.py 从自己的存档重新导出'
        }
    }

    $lang = if ($cfg.ContainsKey('language')) { $cfg['language'] } else { 'game' }
    $builtin = @('game', 'steam', 'follow', 'auto', 'zh-cn', 'zh-tw', 'en', 'ja')
    if ($builtin -contains $lang.ToLower()) {
        $note = if ($lang.ToLower() -eq 'game' -or $lang.ToLower() -eq 'steam') {
            '跟随游戏文本语言（Steam per-game 语言 → manifest / 模拟器 → Windows）'
        } else {
            '菜单文案语言（ui.rs / i18n.rs）'
        }
        Write-Check PASS ("language = {0}" -f $lang) $note
    } else {
        $ov = Join-Path $Target 'er_echo_i18n.ini'
        if (Test-Path -LiteralPath $ov) {
            Write-Check PASS ("language = {0}（自定义，用 er_echo_i18n.ini）" -f $lang) ''
        } else {
            Write-Check WARN ("language = {0} 不是内置语言，也没有 er_echo_i18n.ini" -f $lang) `
                '会回退英文；新增语言见 docs\i18n.md'
        }
    }

    if ($cfg.ContainsKey('token') -and $cfg['token'] -eq 'change-me') {
        Write-Check WARN 'IPC token 还是默认值 change-me' '只监听 127.0.0.1，单机影响不大；跑 bridge 时建议改掉'
    }
}

# ---------------------------------------------------------------- 游戏内菜单 ESD
# 赐福菜单的 EzState 注入**需要**挂载这份 ESD：实测不挂载时
# `find_list_start_state` 失败（cannot find grace root list start state），
# 赐福里不会出现「战友」。root 列表 fallback 另有一份 ESD，二者都要。
$esdCandidates = @(
    (Join-Path $Target 'mod\script\talk\m00_00_00_00.talkesdbnd.dcx'),
    (Join-Path $Target 'mods\ER-Echo\mod\script\talk\m00_00_00_00.talkesdbnd.dcx'),
    (Join-Path $Target 'er-echo\ui\out_vanilla\m00_00_00_00.talkesdbnd.dcx')
)
$esd = $esdCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$nested = $true
if ($cfg.ContainsKey('nested_menu')) {
    $nested = -not ($cfg['nested_menu'] -match '^(false|0|no|off)$')
}
if (-not $esd) {
    Write-Check WARN '没有赐福菜单 ESD（mod\script\talk\*.dcx）' '实测必需：不挂载时注入报 cannot find grace root list start state，赐福里没有「战友」'
} else {
    $len = (Get-Item -LiteralPath $esd).Length
    if ($len -gt 10000 -and $len -lt 200000) {
        Write-Check PASS ("赐福菜单 ESD 就位（{0} KB）" -f [Math]::Round($len / 1KB, 1)) ''
    } else {
        Write-Check WARN ("ESD 大小异常（{0} 字节）" -f $len) '正常是 30 KB 左右；版本不对时可能静默失效'
    }
}

# ---------------------------------------------------------------- 写权限
try {
    $probe = Join-Path $Target ('.er_echo_write_test_' + [Guid]::NewGuid().ToString('N').Substring(0, 8))
    [IO.File]::WriteAllText($probe, 'ok')
    Remove-Item -LiteralPath $probe -Force
    Write-Check PASS '游戏目录可写' 'DLL 要在这里写 er_echo.log / *.json'
} catch {
    Write-Check FAIL '游戏目录不可写' '装在 Program Files 下时常见：给目录授权、把游戏搬出 Program Files，或以管理员运行'
}

# ---------------------------------------------------------------- 可选组件
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
    Write-Check INFO ("Python: " + (& $py.Source --version 2>&1)) '只有导出存档 / LLM bridge 需要，DLL 本身不依赖'
} else {
    Write-Check WARN '没找到 python' '要导出自己的角色存档就必须装 Python 3.9+；不导出也能玩（克隆体＝玩家装备）'
}
if (-not (Test-Path -LiteralPath (Join-Path $Target 'oo2core_6_win64.dll'))) {
    Write-Check INFO '没有 oo2core_6_win64.dll（游戏自带的 Oodle 解压库）' '只有游戏升级后重建 ESD 才需要'
}

# ---------------------------------------------------------------- 结论
Write-Host ''
if ($script:fails -eq 0) {
    Write-Host ("结论: 通过（警告 {0} 项）。用 {1} 启动，进游戏看 er_echo.log 里的 'i18n:' 和 'attached'。" -f $script:warns, $batLeaf) -ForegroundColor Green
} else {
    Write-Host ("结论: 有 {0} 项阻断（警告 {1} 项），先修 FAIL 再启动。" -f $script:fails, $script:warns) -ForegroundColor Red
}
Write-Host ''
exit ([Math]::Min($script:fails, 100))
