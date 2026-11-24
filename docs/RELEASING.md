# 发布到 GitHub Releases

仓库有两个分发渠道，**同一批 zip**：

| 渠道 | 用途 | 入口 |
|---|---|---|
| Nexus Mods | 主要受众、评论/问题都在这边 | `nexus/checklist.md` |
| GitHub Releases | 备份下载、给「不想用 Nexus / 想核对 hash」的人、给 CI/镜像 | 本文 |

GitHub Release 的资产就是 `dist/nexus/` 里那三个 zip（外加 `nexus/release-checksums.txt`）。
不要传源码 zip —— GitHub 每个 release 会自动附 `Source code (zip/tar.gz)`。

---

## 0. 发之前

```powershell
# 1) 构建（产物在 dist\nexus\，同时会更新 nexus\release-checksums.txt）
powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_all.ps1

# 2) 确认工作区干净、已 push
git status
git push origin main

# 3) 版本号三处一致：mod\Cargo.toml、页面、文件名
```

`tools\build_all.ps1` 会按顺序跑：DLL → 安装器 payload → `ER-Echo-Setup.exe` → 三个 zip，并打印
每个产物的路径/大小。构建细节见 README 的「从源码构建」。

---

## 1. 打 tag（当前仓库要先把 v0.1.0 挪到发布提交）

`v0.1.0` 这个 tag 之前打在早期提交 `a3e7fd7` 上，而**还没有任何 release 用过它**，所以直接把
tag 移到发布提交是安全的（GitHub 上也没有 release 会因此错位）。确认过没有 release：

```powershell
# 查看现有 release（应为空）
Invoke-RestMethod https://api.github.com/repos/Sanvenir/ER-Echo/releases |
    Select-Object tag_name, name
```

把 tag 移到当前 HEAD：

```powershell
git tag -f v0.1.0 HEAD
git push --force origin v0.1.0
```

以后每个版本都换新 tag，不需要 force：

```powershell
git tag v0.1.1
git push origin v0.1.1
```

> 如果哪天需要撤销：`git tag -f v0.1.0 a3e7fd7; git push --force origin v0.1.0`
> （发布页已经引用新 tag 时不要这么做）。

---

## 2. 方式 A：网页操作（一次性最省事）

1. 打开 <https://github.com/Sanvenir/ER-Echo/releases> → **Draft a new release**。
2. **Choose a tag** 选 `v0.1.0`（已经 push 上去的那个）。
3. Release title：`ER Echo 0.1.0`。
4. 描述：把 `docs/RELEASE-NOTES-0.1.0.md` 全文粘进去（或从 `nexus/changelog.md` 的 0.1.0 段复制）。
5. 拖入 4 个资产（顺序无所谓）：
   - `dist/nexus/ER-Echo-Setup-0.1.0.zip`（主文件，约 28 MB）
   - `dist/nexus/ER-Echo-0.1.0.zip`（手动安装）
   - `dist/nexus/ER-Echo-0.1.0-ESD-fallback.zip`
   - `nexus/release-checksums.txt`
6. 勾选 **Set as the latest release**；不要勾 pre-release（0.1.0 是首个公开版）。
7. **Publish release**。
8. 打开 release 页，逐个点资产确认能下载、大小对得上。

> 单文件上限 2 GB，我们这个 30 MB 没问题。GitHub 没有「病毒扫描隔离」流程，但 Windows 用户下载
> 未签名 exe 仍可能看到 SmartScreen 提示——页面上已经写了说明和 hash。

---

## 3. 方式 B：脚本 + token（可重复，推荐）

`tools/publish_github_release.ps1` 走 GitHub REST API：建 tag（必要时移动）→ 建 release →
逐个上传资产 → 打印 release 和资产 URL。它可以复用本机 `git credential` 里保存的 GitHub 凭据，
也可以读环境变量。

### 3.1 准备 token（任选一种）

- **复用本机凭据（最方便）**：脚本默认用 `git credential fill` 取 GitHub 的 OAuth token；
  只要 `git push` 不用输密码，这一步就能过。
- **自己建 PAT**：GitHub → Settings → Developer settings →
  - Classic token：勾 **repo**（`repo` 已包含 release 读写）；
  - 或 Fine-grained token：Repository access 选 `Sanvenir/ER-Echo`，Permissions →
    **Contents: Read and write**。
  然后：

  ```powershell
  $env:GITHUB_TOKEN = 'ghp_xxx'   # 只在当前窗口生效
  ```

### 3.2 先干跑

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\publish_github_release.ps1 -DryRun
```

会打印：将使用的 tag/commit、要上传的 4 个文件及 SHA-256、release 标题。不会改任何东西。

### 3.3 正式发

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\publish_github_release.ps1
```

常用参数：

| 参数 | 说明 |
|---|---|
| `-Version 0.1.0` | 版本号（默认 `0.1.0`），决定 tag `v0.1.0`、release 标题和默认资产名 |
| `-Tag v0.1.0` | 显式指定 tag |
| `-Repo Sanvenir/ER-Echo` | 换仓库时用 |
| `-NotesFile docs\RELEASE-NOTES-0.1.0.md` | release 正文来源（默认按版本号找） |
| `-Assets <路径...>` | 默认 `dist\nexus\*.zip` + `nexus\release-checksums.txt` |
| `-MoveTag` | tag 已存在但不在 HEAD 时，强制移动（等于上面的 `git tag -f` + force push） |
| `-Draft` / `-Prerelease` | 建草稿 / 标预发布 |
| `-DryRun` | 只打印计划 |

脚本的行为：工作区不干净会**警告**但继续；tag 不存在会自动创建并 push；已存在但不在 HEAD
且没有 `-MoveTag` 时会停下，避免误移；release 已存在时报错并提示去网页删除或换 tag。

---

## 4. 方式 C：GitHub CLI（如果你装了 gh）

```powershell
winget install --id GitHub.cli -e
gh auth login

gh release create v0.1.0 `
  dist/nexus/ER-Echo-Setup-0.1.0.zip `
  dist/nexus/ER-Echo-0.1.0.zip `
  dist/nexus/ER-Echo-0.1.0-ESD-fallback.zip `
  nexus/release-checksums.txt `
  --title "ER Echo 0.1.0" `
  --notes-file docs/RELEASE-NOTES-0.1.0.md `
  --latest
```

---

## 5. 发完之后

1. 在 Nexus 页面/README 里补 GitHub Release 链接（备用下载 + hash 核对）。
2. 核对 `nexus/release-checksums.txt` 里三个 zip 的 hash 与 release 资产一致。
3. 记到 `nexus/checklist.md` 的发布记录（日期 / tag / release URL / Nexus 状态）。
4. 下次发版流程：改 `Cargo.toml` 版本 → `tools\build_all.ps1` → 新 tag → 跑脚本。

---

## 6. 常见问题

| 现象 | 处理 |
|---|---|
| `401 Bad credentials` | token 过期/没带 `repo`（或 Contents 读写）权限；重新建 PAT 或 `git credential approve` 更新本机凭据 |
| `403 Forbidden` + `rate limit` | 未认证请求限额；脚本已用 token，确认 header 生效 |
| `422 Validation Failed`（建 release） | 同名 tag/release 已存在；去网页删掉旧 release，或换版本号 |
| 上传中途断（`unexpected EOF`） | GitHub 大文件偶发；脚本会重试 3 次，仍失败就重跑（已上传的资产会跳过） |
| 资产大小不对 | 传之前重新 `tools\build_all.ps1`，不要手工改名 |
| tag 指错提交 | `git tag -f vX.Y.Z <commit>; git push --force origin vX.Y.Z`，再重建 release |
