#requires -Version 5.1
<#
.SYNOPSIS
  把 dist\nexus\ 的发布 zip 传到 GitHub Releases：建/移动 tag、建 release、上传资产、打印链接。

.DESCRIPTION
  走 GitHub REST API（不依赖 gh CLI）。token 解析顺序：
      1) -Token 参数
      2) $env:GITHUB_TOKEN
      3) 本机 git credential（只要 git push 不用输密码，这一步就能过）

  release 正文默认取 docs\RELEASE-NOTES-<Version>.md；资产默认是三个 zip +
  nexus\release-checksums.txt。

.PARAMETER Version
  版本号，默认 0.1.0。决定默认 tag（v0.1.0）、release 标题和资产文件名。

.PARAMETER Tag
  显式 tag。默认 v<Version>。

.PARAMETER Repo
  owner/name，默认 Sanvenir/ER-Echo。

.PARAMETER NotesFile
  release 正文（Markdown）。默认 docs\RELEASE-NOTES-<Version>.md。

.PARAMETER Assets
  要上传的文件。默认三个 zip + nexus\release-checksums.txt。

.PARAMETER Token
  GitHub token（classic 需 repo；fine-grained 需 Contents: Read and write）。不给就读环境变量/凭据。

.PARAMETER MoveTag
  tag 已存在但不在 HEAD 时，强制移动并 force push。默认拒绝，避免误移。

.PARAMETER UpdateExisting
  release 已存在时更新标题/正文，并补传缺失资产（默认报错）。

.PARAMETER Draft
  建草稿（不公开）。

.PARAMETER Prerelease
  标预发布。

.PARAMETER DryRun
  只打印计划（tag/commit/资产/hash），不改任何东西、不发请求。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\publish_github_release.ps1 -DryRun

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\publish_github_release.ps1 -MoveTag
#>
[CmdletBinding()]
param(
    [string]$Version = '0.1.0',
    [string]$Tag,
    [string]$Repo = 'Sanvenir/ER-Echo',
    [string]$NotesFile,
    [string[]]$Assets,
    [string]$Token,
    [switch]$MoveTag,
    [switch]$UpdateExisting,
    [switch]$Draft,
    [switch]$Prerelease,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not $Tag) { $Tag = "v$Version" }
if (-not $NotesFile) { $NotesFile = Join-Path $repoRoot ('docs\RELEASE-NOTES-' + $Version + '.md') }
if (-not (Test-Path -LiteralPath $NotesFile)) { throw "找不到 release 正文: $NotesFile" }

if (-not $Assets -or $Assets.Count -eq 0) {
    $Assets = @(
        (Join-Path $repoRoot ('dist\nexus\ER-Echo-Setup-' + $Version + '.zip')),
        (Join-Path $repoRoot ('dist\nexus\ER-Echo-' + $Version + '.zip')),
        (Join-Path $repoRoot ('dist\nexus\ER-Echo-' + $Version + '-ESD-fallback.zip')),
        (Join-Path $repoRoot 'nexus\release-checksums.txt')
    )
}
$Assets = @($Assets | ForEach-Object { [IO.Path]::GetFullPath($_) })
foreach ($a in $Assets) {
    if (-not (Test-Path -LiteralPath $a)) { throw "缺少资产: $a" }
    if ((Get-Item -LiteralPath $a).Length -gt 2GB) { throw "资产超过 GitHub 2 GB 限制: $a" }
}

# ---------------------------------------------------------------- git 状态
$head = (& git -C $repoRoot rev-parse HEAD).Trim()
$dirty = @(& git -C $repoRoot status --porcelain)
if ($dirty.Count -gt 0) {
    Write-Warning ("工作区有 {0} 处未提交改动；release 仍然只包含已提交的 {1}" -f $dirty.Count, $head.Substring(0, 7))
}

try {
    & git -C $repoRoot fetch origin main --quiet 2>$null | Out-Null
    & git -C $repoRoot merge-base --is-ancestor HEAD origin/main 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'not ancestor' }
} catch {
    Write-Warning '无法确认 HEAD 已在 origin/main（网络或未 push）；tag push 可能失败，必要时先 git push origin main'
}

$tagSha = $null
$probe = & git -C $repoRoot rev-parse -q --verify ("refs/tags/" + $Tag) 2>$null
if ($LASTEXITCODE -eq 0 -and $probe) { $tagSha = $probe.Trim() }

$tagAction = 'create'
if ($tagSha) {
    if ($tagSha -eq $head) {
        $tagAction = 'exists-at-head'
    } elseif ($MoveTag) {
        $tagAction = 'move' + $(if ($DryRun) { ' (dry-run)' } else { '' })
    } else {
        throw ("tag {0} 指向 {1}，不是 HEAD {2}。确认要移动就加 -MoveTag（会 force push tag）" -f $Tag, $tagSha.Substring(0, 7), $head.Substring(0, 7))
    }
}

# ---------------------------------------------------------------- 计划 / token
Write-Host ''
Write-Host '=== plan ===' -ForegroundColor Cyan
Write-Host ("repo    : {0}" -f $Repo)
Write-Host ("version : {0}" -f $Version)
Write-Host ("tag     : {0}  ({1})" -f $Tag, $tagAction)
Write-Host ("commit  : {0}" -f $head)
Write-Host ("notes   : {0}" -f $NotesFile)
Write-Host ("draft   : {0}   prerelease: {1}" -f [bool]$Draft, [bool]$Prerelease)
Write-Host 'assets  :'
foreach ($a in $Assets) {
    $len = (Get-Item -LiteralPath $a).Length
    $sha = (Get-FileHash -LiteralPath $a -Algorithm SHA256).Hash
    Write-Host ("  {0,-34} {1,12:N0} bytes  {2}" -f (Split-Path -Leaf $a), $len, $sha)
}

if ($DryRun) {
    Write-Host ''
    Write-Host '[dry-run] 不做任何改动。去掉 -DryRun 正式发布。' -ForegroundColor Yellow
    exit 0
}

function Get-GitHubToken {
    if ($Token) { return $Token }
    if ($env:GITHUB_TOKEN) { return $env:GITHUB_TOKEN }
    $env:GIT_TERMINAL_PROMPT = '0'
    try {
        $lines = "protocol=https`nhost=github.com`n`n" | & git credential fill 2>$null
        $pass = ($lines | Where-Object { $_ -like 'password=*' }) -replace '^password=', ''
        if ($pass) { return $pass.Trim() }
    } catch { }
    throw '没有 GitHub token：设置 $env:GITHUB_TOKEN，或用 -Token；也可以先 git push 一次让凭据进 credential store'
}

$tok = Get-GitHubToken
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$headers = @{
    Authorization = 'Bearer ' + $tok
    'User-Agent'  = 'ER-Echo-release-script'
    Accept        = 'application/vnd.github+json'
}

# ---------------------------------------------------------------- tag
if ($tagAction -eq 'create') {
    & git -C $repoRoot tag $Tag $head
    if ($LASTEXITCODE -ne 0) { throw "git tag $Tag 失败" }
    & git -C $repoRoot push origin $Tag
    if ($LASTEXITCODE -ne 0) { throw "git push origin $Tag 失败" }
    Write-Host ("[ok] tag {0} -> {1}" -f $Tag, $head.Substring(0, 7)) -ForegroundColor Green
} elseif ($tagAction -like 'move*') {
    & git -C $repoRoot tag -f $Tag $head
    if ($LASTEXITCODE -ne 0) { throw "git tag -f $Tag 失败" }
    & git -C $repoRoot push --force origin $Tag
    if ($LASTEXITCODE -ne 0) { throw "git push --force origin $Tag 失败" }
    Write-Host ("[ok] tag {0} moved -> {1}（已 force push）" -f $Tag, $head.Substring(0, 7)) -ForegroundColor Green
}

# ---------------------------------------------------------------- release
$notes = [IO.File]::ReadAllText($NotesFile, [Text.UTF8Encoding]::new($false))
$payload = @{
    tag_name         = $Tag
    target_commitish = $head
    name             = "ER Echo $Version"
    body             = $notes
    draft            = [bool]$Draft
    prerelease       = [bool]$Prerelease
} | ConvertTo-Json -Depth 5
$payloadBytes = [Text.Encoding]::UTF8.GetBytes($payload)
$api = "https://api.github.com/repos/$Repo/releases"

function Get-ReleaseByTag([string]$t) {
    try { return Invoke-RestMethod -Uri "$api/tags/$t" -Headers $headers -TimeoutSec 60 } catch { return $null }
}

$release = $null
try {
    $release = Invoke-RestMethod -Method Post -Uri $api -Headers $headers `
        -ContentType 'application/json; charset=utf-8' -Body $payloadBytes -TimeoutSec 120
} catch {
    $detail = $_.ErrorDetails.Message
    if ($detail -match 'already_exists') {
        if (-not $UpdateExisting) {
            throw "tag $Tag 的 release 已存在。删掉它，或加 -UpdateExisting 更新正文并补传资产。"
        }
        $existing = Get-ReleaseByTag $Tag
        if (-not $existing) { throw "release 已存在但读取失败：$detail" }
        $release = Invoke-RestMethod -Method Patch -Uri "$api/$($existing.id)" -Headers $headers `
            -ContentType 'application/json; charset=utf-8' -Body $payloadBytes -TimeoutSec 120
        Write-Host ("[ok] 更新已有 release #{0}" -f $release.id) -ForegroundColor Green
    } else {
        throw
    }
}
if (-not $release) { throw '创建 release 失败（无返回）' }
Write-Host ("[ok] release: {0}" -f $release.html_url) -ForegroundColor Green

# ---------------------------------------------------------------- assets
$existingAssets = @()
try { $existingAssets = @(Invoke-RestMethod -Uri "$api/$($release.id)/assets" -Headers $headers -TimeoutSec 60) } catch { }
$existingNames = @($existingAssets | ForEach-Object { $_.name })

foreach ($file in $Assets) {
    $name = Split-Path -Leaf $file
    if ($existingNames -contains $name) {
        Write-Host ("[skip] {0}（已存在）" -f $name) -ForegroundColor Yellow
        continue
    }
    $uri = "https://uploads.github.com/repos/$Repo/releases/$($release.id)/assets?name=" + [uri]::EscapeDataString($name)
    $ok = $false
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            Invoke-RestMethod -Method Post -Uri $uri -Headers $headers `
                -ContentType 'application/octet-stream' -InFile $file -TimeoutSec 900 | Out-Null
            $ok = $true
            break
        } catch {
            $msg = $_.Exception.Message
            if ($attempt -lt 3) {
                Write-Warning ("上传 {0} 失败（第 {1} 次）：{2}；重试…" -f $name, $attempt, $msg)
                Start-Sleep -Seconds (5 * $attempt)
            } else {
                Write-Warning ("上传 {0} 失败：{1}" -f $name, $msg)
            }
        }
    }
    if ($ok) {
        Write-Host ("[ok] uploaded {0}" -f $name) -ForegroundColor Green
    } else {
        Write-Warning ("{0} 未上传成功；重跑脚本会跳过已上传的资产" -f $name)
    }
}

# ---------------------------------------------------------------- 汇总
Write-Host ''
Write-Host '=== release ===' -ForegroundColor Cyan
Write-Host $release.html_url
$final = @(Invoke-RestMethod -Uri "$api/$($release.id)/assets" -Headers $headers -TimeoutSec 60)
foreach ($a in $final) {
    Write-Host ("  {0,-34} {1,12:N0} bytes  {2}" -f $a.name, $a.size, $a.browser_download_url)
}
exit 0
