# Nexus 发布包（素材 + 流程）

这个目录是给 **Nexus Mods 发布**准备的东西，不是 mod 运行需要的文件。运行包在
`dist\nexus\ER-Echo-<version>.zip`。

## 目录内容

| 文件 | 用途 | 状态 |
|---|---|---|
| `page-fields.md` | 表单每个字段填什么（标题/摘要/分类/标签/权限/AI/文件/图片） | ✅ 可直接照抄 |
| `description.bbcode` | 模组页正文（英文 + 中文段 + FAQ + 许可 + AI 声明） | ✅ 贴进 Description |
| `file-description.md` | Files 标签页里主文件的说明 | ✅ |
| `changelog.md` | Changelogs 标签页 / 更新说明 | ✅ |
| `credits-and-licenses.md` | 署名、代码许可、AI 披露、联网行为、 multiplayer 声明 | ✅ |
| `THIRD-PARTY-LICENSES.txt` | 压缩包内必须带的三方许可全文说明（含安装器运行时那一节） | ✅ 打包脚本会放进去 |
| `third-party/` | 安装器运行时（Qt6/PySide6/Python/OpenSSL/libffi/PyInstaller）许可全文 + `Qt-PySide6-NOTICE.txt` | ✅ 打包时进两个包的 `LICENSES\` |
| `shotlist.md` | **需要你在游戏里录/截的素材清单**（含技术设置、构图、视频分镜） | ✅ 图已齐（视频可选） |
| `make_media.py` | `media/incoming/*.jpg` → 裁 16:9 / 1400×400、压到 2 MB 内、写 `media/manifest.json` | ✅ 可重跑 |
| `make_placeholder_media.py` | 旧脚本：把更早的开发截图做成占位图（已被 `make_media.py` 取代） | 🗄️ 仅存档 |
| `media/` | 发布用图（游戏内实拍 7 张：banner + 01..06，全部 1920×1080 / 1400×400） | ✅ |
| `release-checksums.txt` | 三个 zip + DLL 的 SHA256 / 大小（打完包生成） | ✅ 每次发布更新 |
| `false-positive-report.md` | 杀毒/VirusTotal 误报的解释、各厂商提交入口、可直接粘贴的申诉文本 | ✅ 上传前过一遍 |
| `checklist.md` | 上传当天按顺序勾的清单 | ✅ |

## 发布流程速览（2026 现行规则）

Nexus 在 2026 年 4 月换了新版上传表单（[公告](https://www.nexusmods.com/wands/news/15491)），流程是：
建页面 → 填元数据 → 传文件 → 传图 → 发布。要点：

1. **页面**：name / summary / description（BBCode）/ category / tags / language / version。
   分类和标签从站点候选里选，别自己造词（[Best Practices](https://help.nexusmods.com/article/136-best-practices-for-mod-authors)）。
2. **Requirements**：DLC 勾选 + Nexus 上的前置 mod + 外部资源（ME2 在 GitHub，填 Other）。
3. **Permissions**：上传/修改/转换/资产/AI 训练 五组；新字段默认 `Ask me`。
4. **Files**：zip 最稳（`.rar` 容易被判可疑，
   [说明](https://help.nexusmods.com/article/117-why-has-my-mod-been-quarantined)）；
   版本号建议语义化；主文件勾 “latest”。
5. **Images**：页头 1400×400；图库 16:9、1920×1080、每张 ≤2 MB，至少 5 张，
   第一张就是缩略图（[页面创建说明](https://wiki.nexusmods.com/index.php/Creating_a_mod_page)）。
6. **合规**：不能包含未授权的版权内容；不能是「占位/不可用」文件；
   联网行为要说明；多人环境不能破坏
   （[File Submission Guidelines](https://help.nexusmods.com/article/28-file-submission-guidelines)）。
7. **AI 披露**：2026-11-03 起强制，三档 AI-Generated / AI Media / AI Assisted，
   缓冲期到 2027-01-02（[AI Policy Changes 2026](https://help.nexusmods.com/article/180-ai-policy-changes-2026)）。

### 对这个 mod 的具体影响

| 规则 | 我们怎么处理 |
|---|---|
| 版权：不得上传游戏原始文件 | 主包**含** `mod\script\talk` 的 ESD（赐福菜单必需，实测不挂载时 EzState 注入失败），它是改过的 vanilla ESD，页面写明；另带两份 Convergence 参数 ID 表（JSON，校验装备 id 用，页面也写明）。不含 `config_eldenring.toml`（ME2 的配置，覆盖会破坏别人的设置） |
| 启动链修复 | 安装器包**含** `launch-er-echo*.bat`，手动包**含** `launchmod_eldenring*.bat`：`-p` 绕开 ME2 2.1.0 启动器 `0xC0000409`；admin 变体绕开「Steam 覆盖层 × ME2 钩子」的 10 秒闪退 |
| 第三方许可 | `fromsoftware-rs` 是 **MIT-NON-AI / Apache-NON-AI**，必须随包附全文 → `THIRD-PARTY-LICENSES.txt` + `LICENSES\` |
| 联网行为 | DLL 只监听 `127.0.0.1:7811`；LLM 是可选脚本、默认 `mock` 离线；页面写明 |
| 多人环境 | 页面顶部红字「OFFLINE ONLY」；正文再写一次 |
| AI 披露 | 正文已经是 **`AI-Generated Content`** 那一档（只有这一版，不再二选一） |
| 图片 | 只用游戏内截图（`shotlist.md`），不用 AI 图 → 不需要 `AI Media`（除非描述也用 AI 写） |

## 2026-11-21 启动链补充（来源：[docs/handoff-launch.md](../docs/handoff-launch.md)）

那次排查发现三个互相独立的崩溃，都会表现成「游戏打不开」，但修法完全不同。发布素材已按这个补齐：

| 崩溃 | 指纹 | 处理 | 素材里的体现 |
|---|---|---|---|
| ME2 启动器 | `0xC0000409`，`ucrtbase.dll +0xa527e` | bat 加 `-p ".\eldenring.exe"` | 主包带改好的 `launchmod_eldenring.bat`（+ 正文章节 1） |
| Steam 覆盖层 × ME2 钩子 | 启动约 10 秒闪退，`0xc0000005` @ `0x1EBCEF9`，dump 里 `DLUserInputManagerImpl_win32.cpp(98)` | 提权启动（覆盖层注不进去）或关 Steam 界面 | 主包带 `launchmod_eldenring_admin.bat`（+ 正文章节 2 + FAQ） |
| 游戏本体 / EAC 坏 | 同一偏移但 dump 里没有 `modengine2.dll` / `er_echo.dll` | 校验文件 / 修 EAC / 重装游戏 | 正文「先确认无 mod 能进标题」+ 章节 3 |

同步改动：

- `description.bbcode`：Requirements 加「vanilla 先跑通」；Installation 改为「用包里的 bat」；
  新增 **If the game does not start** 三分法排障；FAQ 加 4 条；中文段加一句。
- `file-description.md`：Contents 列出两个 bat，加排障小表。
- `checklist.md`：发布前必须实测「普通 bat / admin bat」两条路径；加评论回复模板。
- `page-fields.md`：Requirements 加 vanilla 检查；发布前检查改成「含两个 bat」。
- `tools/doctor.ps1`：新增「是否提权」「bat 是否带 `-p`」两项自检（handoff TODO #3）。
- `docs/INSTALL.md` / `INSTALL.en.md`：第 0 步「先确认无 mod 能进标题」；第 1 步说明为什么换 bat。
- `tools/package_nexus.ps1`：把两个 bat 打进主包，README.txt 写清三条排障。

> 注意 handoff 里的原则：**10 秒闪退是环境相关的小概率坑**（同一套文件 11-17 不提权也能跑），
> 所以文档写的是「先试普通版，闪退再换 admin」，没有把提权写成硬性要求。

## 还缺什么

1. **游戏内素材**：静态图已齐（`media/` 7 张，全部 16:9 / 1400×400）。可选：60–90 秒 trailer、
   `summon` / `f12-gear` / `glow-off` 这类加分图。
2. AI 声明：已定为 `AI-Generated Content`，`description.bbcode` 末尾就是这一档（见 `page-fields.md`）。
3. 可选包（root-menu ESD fallback）**要发**——体积小，留一条「注入失败时的退路」。
4. **未验证**（handoff TODO）：admin 模式下 Steam 成就 / 云存档是否正常；关掉 Steam 覆盖层后
   普通 bat 是否能跑（能跑就省掉每次 UAC）。发布前最好各测一次，并在 FAQ 里写实。

## 打包

源码在仓库根目录（不在游戏目录里），按顺序跑：

```powershell
# 1) Rust DLL
powershell -NoProfile -ExecutionPolicy Bypass -File mod\build.ps1

# 2) 安装器 payload（拷 DLL + 文档 + bat + ESD 到 build\payload）
powershell -NoProfile -ExecutionPolicy Bypass -File tools\package_payload.ps1 -SkipBuild

# 3) 安装器 exe（PyInstaller onedir → dist\tools\ER-Echo-Setup）
powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_gui_exe.ps1 -SkipPayload

# 4) 三个发布 zip（安装器 + 手动包 + ESD fallback）
powershell -NoProfile -ExecutionPolicy Bypass -File tools\package_nexus.ps1 -SkipBuild
```

产物：

```
dist\nexus\ER-Echo-Setup-0.1.0.zip            ← 传这个当 Main file（一键安装器）
dist\nexus\ER-Echo-0.1.0.zip                  ← Optional：手动安装（解压 + 改 config）
dist\nexus\ER-Echo-0.1.0-ESD-fallback.zip     ← Optional：root 菜单退路
```

打完包核对 `nexus\release-checksums.txt`（三个 zip + DLL 的 SHA256 / 大小），
上传到 Nexus 后用 `checklist.md` 最后一项对一遍。
