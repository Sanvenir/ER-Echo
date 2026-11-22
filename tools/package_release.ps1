#requires -Version 5.1
<#
.SYNOPSIS
  打一个可直接发给别人的 ER Echo 发布包（只含运行必需文件 + 工具 + 文档）。

.DESCRIPTION
  输出：er-echo\dist\ER-Echo-<版本>\ 和同名 .zip。
  刻意**不**打包：作者自己的存档导出物（tools\from_save*、profile.*.json）、
  临时调试脚本（live_test* / restart_and_test* / _probe_magic* / _inspect_regulation.mjs）、编译中间产物
  （mod\target、mod\src）、以及任何 .sl2 / 日志。

.PARAMETER OutDir
  输出目录，默认 er-echo\dist。

.PARAMETER Version
  版本号/目录名后缀，默认当天日期 yyyyMMdd。

.PARAMETER SkipBuild
  跳过 cargo 构建，直接用 mod\target\release\er_echo.dll。

.PARAMETER NoZip
  只生成目录，不压 zip。

.PARAMETER SkipCheck
  生成后不跑 doctor.ps1 自检。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\package_release.ps1
#>
[CmdletBinding()]
param(
    [string]$OutDir,
    [string]$Version,
    [switch]$SkipBuild,
    [switch]$NoZip,
    [switch]$SkipCheck
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot          # er-echo/
. (Join-Path $PSScriptRoot 'gamedir.ps1')
$game = Get-ErEchoGameDir   # 源码已搬出游戏目录，统一走探测（见 gamedir.ps1）
if (-not $OutDir) { $OutDir = Join-Path $repo 'dist' }
if (-not $Version) { $Version = Get-Date -Format 'yyyyMMdd' }

$stage = Join-Path $OutDir ("ER-Echo-" + $Version)
$zip = $stage + '.zip'

function Say([string]$Text, [string]$Color = 'Gray') {
    Write-Host $Text -ForegroundColor $Color
}

function Copy-One([string]$Source, [string]$DestDir) {
    if (-not (Test-Path -LiteralPath $Source)) { throw "缺少文件: $Source" }
    New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
    Copy-Item -LiteralPath $Source -Destination $DestDir -Force
}

function Copy-Tree([string]$SourceDir, [string]$DestDir, [string[]]$Exclude = @()) {
    if (-not (Test-Path -LiteralPath $SourceDir)) { return }
    New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
    foreach ($item in Get-ChildItem -LiteralPath $SourceDir -Force) {
        $skip = $false
        foreach ($pattern in $Exclude) {
            if ($item.Name -like $pattern) { $skip = $true; break }
        }
        if ($skip) { continue }
        if ($item.PSIsContainer) {
            Copy-Tree $item.FullName (Join-Path $DestDir $item.Name) $Exclude
        } else {
            Copy-Item -LiteralPath $item.FullName -Destination $DestDir -Force
        }
    }
}

# ---------------------------------------------------------------- 0) 构建
$builtDll = Join-Path $repo 'mod\target\release\er_echo.dll'
if (-not $SkipBuild) {
    Say '[1/6] cargo build --release ...' 'Cyan'
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'mod\build.ps1')
    if ($LASTEXITCODE -ne 0) { throw "构建失败（exit $LASTEXITCODE），先修编译再打包" }
}
if (-not (Test-Path -LiteralPath $builtDll)) { throw "找不到 $builtDll（去掉 -SkipBuild 重新构建）" }
$dllHash = (Get-FileHash -LiteralPath $builtDll -Algorithm SHA256).Hash

# ---------------------------------------------------------------- 1) 目录
Say '[2/6] 准备发布目录 ...' 'Cyan'
if (Test-Path -LiteralPath $stage) {
    $full = [IO.Path]::GetFullPath($stage)
    $root = [IO.Path]::GetFullPath($OutDir)
    if (-not $full.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
        throw "拒绝删除不在 dist 目录里的路径: $full"
    }
    Remove-Item -LiteralPath $stage -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $stage | Out-Null

# ---------------------------------------------------------------- 2) 运行必需
Say '[3/6] 拷贝运行必需文件 ...' 'Cyan'
Copy-One $builtDll $stage
Copy-One (Join-Path $game 'config_eldenring.toml') $stage
$batMain = Join-Path $game 'launchmod_eldenring.bat'
if (-not (Test-Path -LiteralPath $batMain)) { $batMain = Join-Path $repo 'install\launchmod_eldenring.bat.template' }
$batAdmin = Join-Path $game 'launchmod_eldenring_admin.bat'
if (-not (Test-Path -LiteralPath $batAdmin)) { $batAdmin = Join-Path $repo 'install\launchmod_eldenring_admin.bat.template' }
Copy-Item -LiteralPath $batMain -Destination (Join-Path $stage 'launchmod_eldenring.bat') -Force
Copy-Item -LiteralPath $batAdmin -Destination (Join-Path $stage 'launchmod_eldenring_admin.bat') -Force
$esdSrc = Join-Path $game 'mod\script\talk\m00_00_00_00.talkesdbnd.dcx'
if (-not (Test-Path -LiteralPath $esdSrc)) { $esdSrc = Join-Path $repo 'ui\out_vanilla\m00_00_00_00.talkesdbnd.dcx' }
Copy-One $esdSrc (Join-Path $stage 'mod\script\talk')

# 发布版 config：关掉 ME2 的 debug 日志（作者本机排障时才开）
$tomlPath = Join-Path $stage 'config_eldenring.toml'
$tomlText = [IO.File]::ReadAllText($tomlPath)
$tomlText = [regex]::Replace($tomlText, '(?m)^\s*debug\s*=\s*true', 'debug = false')
# 平铺包必须真的加载 DLL 和 mod/（reset 后根目录配置可能是 external_dlls=[] / mods=[]）
$tomlText = [regex]::Replace($tomlText, '(?ms)^\s*external_dlls\s*=\s*\[.*?\]', 'external_dlls = ["er_echo.dll"]')
if ($tomlText -notmatch '(?ms)^\s*mods\s*=\s*\[[^\]]*path\s*=\s*"mod"') {
    $modsBlock = "mods = [`r`n  { enabled = true, name = `"er-echo`", path = `"mod`" },`r`n]"
    if ($tomlText -match '(?ms)^\s*mods\s*=\s*\[.*?\]') {
        $tomlText = [regex]::Replace($tomlText, '(?ms)^\s*mods\s*=\s*\[.*?\]', $modsBlock)
    } else {
        $tomlText = $tomlText.TrimEnd() + "`r`n`r`n[extension.mod_loader]`r`nenabled = true`r`nloose_params = false`r`n" + $modsBlock + "`r`n"
    }
}
[IO.File]::WriteAllText($tomlPath, $tomlText, [Text.UTF8Encoding]::new($false))

# er_echo.ini：沿用本机的完整默认值，但把 profiles 指到示例档案并加发布头
$iniSource = Join-Path $game 'er_echo.ini'
if (-not (Test-Path -LiteralPath $iniSource)) { $iniSource = Join-Path $repo 'install\er_echo.ini.template' }
if (-not (Test-Path -LiteralPath $iniSource)) { throw "找不到 ini 模板（$iniSource）" }
$iniText = [IO.File]::ReadAllText($iniSource)
$iniText = [regex]::Replace(
    $iniText,
    '(?m)^\s*profiles\s*=.*$',
    'profiles=profiles/profile.example.json'
)
$header = @'
; ============================================================
; ER Echo 发布包配置
; 第一次用：先导出自己的角色（docs/INSTALL.md 第 4 步），
; 再把下面 [clone] 段的 profiles= 改成你自己的 json（逗号分隔可放多份）。
; 示例档案 equipment_param_ids 全是 0，只保证「能跑起来」。
; ============================================================

'@
$iniText = $header + $iniText
# 发布包不带作者信息：删掉「下面两份是从本账号主存档导出的」这类注释
$iniText = ($iniText -split "`r?`n" | Where-Object { $_ -notmatch 'from_save_account|ER0000\.sl2|7656|本账号' }) -join "`r`n"
[IO.File]::WriteAllText((Join-Path $stage 'er_echo.ini'), $iniText, [Text.UTF8Encoding]::new($false))

New-Item -ItemType Directory -Force -Path (Join-Path $stage 'profiles') | Out-Null
Copy-One (Join-Path $repo 'tools\profile.example.json') (Join-Path $stage 'profiles')

# ---------------------------------------------------------------- 3) 工具/文档
Say '[4/6] 拷贝工具、bridge、文档 ...' 'Cyan'
$toolExclude = @(
    'live_*.ps1', 'restart_and_test*.ps1', 'restart_and_probe.ps1',
    '_probe_magic*.py', 'analyze_dump.py', 'profile.*.json', 'package_release.ps1',
    '_inspect_regulation.mjs',
    'from_save', 'from_save_account', '__pycache__', '*.pyc'
)
Copy-Tree (Join-Path $repo 'tools') (Join-Path $stage 'er-echo\tools') $toolExclude
Copy-One (Join-Path $repo 'tools\profile.example.json') (Join-Path $stage 'er-echo\tools')
Copy-Tree (Join-Path $repo 'bridge') (Join-Path $stage 'er-echo\bridge') @('__pycache__', '*.pyc')
Copy-Tree (Join-Path $repo 'config') (Join-Path $stage 'er-echo\config')
Copy-Tree (Join-Path $repo 'ui') (Join-Path $stage 'er-echo\ui') @('esd', 'base', 'talk', 'fake', 'out', 'out_bnd', '__pycache__')

New-Item -ItemType Directory -Force -Path (Join-Path $stage 'er-echo\docs') | Out-Null
foreach ($doc in @('INSTALL.md', 'INSTALL.en.md', 'i18n.md', 'usage.md')) {
    $src = Join-Path $repo ('docs\' + $doc)
    if (Test-Path -LiteralPath $src) { Copy-One $src (Join-Path $stage 'er-echo\docs') }
}
Copy-One (Join-Path $repo 'README.md') (Join-Path $stage 'er-echo')

# ---------------------------------------------------------------- 4) 多语言示例
Say '[5/6] 生成多语言示例与说明 ...' 'Cyan'
$i18nExample = @'
; ============================================================
; ER Echo 菜单文案覆盖示例（可选）
; 用法：
;   1) 复制本文件为 er_echo_i18n.ini（同目录）
;   2) 把 er_echo.ini 里 [i18n] 的 language 改成下面的语言代码
;   3) 重启游戏（DLL 在启动时读一次）
; 只写想改的键；没写的键回退内置（zh-CN / zh-TW / en / ja），再回退英文。
; 占位符 {count} {n} {i} {name} {level} 不要翻译、不要删。
; 键表见 docs/i18n.md。
; ============================================================

[en]
; root=Comrades ({count}/{n})
; count_row=Party size: {count} (click to change)
; slot=Slot {i}: {name} (click to change)
; resummon=Resummon now
; back=Back
; count_none=Don't summon
; count_n=Party of {count}
; profile={name}  Lv{level}

[ja]
; root=戦友（{count}/{n}）
; count_row=人数：{count}（クリックで変更）
; slot={i}番：{name}（クリックで変更）
; resummon=いますぐ再召喚
; back=戻る
; count_none=召喚しない
; count_n=パーティ {count} 人
; profile={name}  Lv{level}

[ko]
; root=동료 ({count}/{n})
; count_row=파티 인원: {count} (클릭하여 변경)
; slot={i}번: {name} (클릭하여 변경)
; resummon=즉시 재소환
; back=돌아가기
; count_none=소환 안 함
; count_n={count}명
; profile={name}  Lv{level}
'@
[IO.File]::WriteAllText((Join-Path $stage 'er_echo_i18n.example.ini'), $i18nExample, [Text.UTF8Encoding]::new($false))

$readme = @'
# ER Echo 发布包

把**本目录里的所有内容**覆盖到 ELDEN RING 游戏根目录（和 `eldenring.exe` 同级），
然后按 `er-echo/docs/INSTALL.md` 装 ModEngine2、导出自己的角色档案、用
`launchmod_eldenring.bat` 启动。

装完先自检：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\doctor.ps1
```

要点：

* 只支持 ELDEN RING **1.17.2**（exe 2.7.2.0 全球版 / 2.7.2.1 日版）；换版本必须重编译。
* 只离线：用 `launchmod_eldenring.bat` 启动（绕开 EAC）；带 mod 存档上线会被 soft-ban。
* 启动后游戏**约 10 秒就闪退**（WER：eldenring.exe / 0xc0000005 / 偏移 0x1EBCEF9）？改用
  `launchmod_eldenring_admin.bat`（管理员启动，Steam 覆盖层注不进去），或在 Steam → 设置 → 游戏中
  里关掉「启用 Steam 界面」。
* `er_echo.ini` 里的 `profiles=` 默认指向示例档案；换成你自己导出的 json 才会变成「你的另一个存档角色」。
* 菜单语言：`er_echo.ini` → `[i18n] language=auto|zh-CN|zh-TW|en|ja`；自定义语言见
  `er_echo_i18n.example.ini` 与 `er-echo/docs/i18n.md`。

English: see `er-echo/docs/INSTALL.en.md`.
'@
[IO.File]::WriteAllText((Join-Path $stage 'README.md'), $readme, [Text.UTF8Encoding]::new($false))

# ---------------------------------------------------------------- 4.5) 收尾处理
# Windows PowerShell 5.1 会把「无 BOM 的 UTF-8 脚本」当 ANSI 读，中文注释/字符串会乱码，
# 严重时直接解析失败（build.ps1 顶部也踩过这个坑）。发布前统一补 BOM。
Get-ChildItem -Path (Join-Path $stage 'er-echo') -Recurse -Filter *.ps1 | ForEach-Object {
    $bytes = [IO.File]::ReadAllBytes($_.FullName)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        return
    }
    $text = [IO.File]::ReadAllText($_.FullName, [Text.UTF8Encoding]::new($false))
    if ($text -match '[^\x00-\x7F]') {
        [IO.File]::WriteAllText($_.FullName, $text, [Text.UTF8Encoding]::new($true))
    }
}

# 文档/示例里出现的作者 SteamID 一律脱敏
$textExt = @('.md', '.json', '.ini', '.py', '.toml', '.bat')
Get-ChildItem -Path $stage -Recurse -File | Where-Object { $textExt -contains $_.Extension } | ForEach-Object {
    $text = [IO.File]::ReadAllText($_.FullName)
    if ($text -match '\b7656\d{13}\b') {
        [IO.File]::WriteAllText($_.FullName, ($text -replace '\b7656\d{13}\b', '<SteamID>'), [Text.UTF8Encoding]::new($false))
    }
}

# ---------------------------------------------------------------- 5) 自检
if (-not $SkipCheck) {
    Say '[6/6] 对发布目录跑 doctor ...' 'Cyan'
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $repo 'tools\doctor.ps1') -Target $stage
    if ($LASTEXITCODE -ne 0) {
        Say ("[warn] doctor 报了 {0} 项阻断 —— 发布前请确认是不是预期内的（目录里没有游戏本体/ME2 属正常）" -f $LASTEXITCODE) 'Yellow'
    }
}

# ---------------------------------------------------------------- 6) 打包
if (-not $NoZip) {
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
    Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -CompressionLevel Optimal
    $size = [Math]::Round((Get-Item -LiteralPath $zip).Length / 1MB, 2)
    Say ("[ok] zip: {0} ({1} MB)" -f $zip, $size) 'Green'
}

$fileCount = @(Get-ChildItem -LiteralPath $stage -Recurse -File).Count
Say ''
Say ("发布目录: {0}" -f $stage) 'Green'
Say ("文件数: {0}" -f $fileCount)
Say ("DLL SHA256: {0}" -f $dllHash)
Say '把这个目录（或 zip）拷到目标机器，覆盖到游戏根目录即可；别忘了装 ME2。'
exit 0
