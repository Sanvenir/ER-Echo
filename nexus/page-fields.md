# Nexus 页面字段（复制粘贴用）

上传入口：Nexus Mods 顶部 **Mods → Upload a mod**（2026 年 4 月后的新版上传表单），
游戏选 **Elden Ring**。下面是每个字段建议填什么。

---

## 基本信息

| 字段 | 建议值 |
|---|---|
| Mod name | `ER Echo - Companions From Your Own Saves` |
| Summary（一句话） | `Summon characters from your own save files as Spirit Ash companions - real face, gear, level and spells, driven by the game's native AI. Offline only.` |
| Version | `0.1.0`（Beta；Cargo.toml 里也是 0.1.0） |
| Language | English, Chinese (Simplified)（正文末尾有简体中文段；繁中/日文不在页面上列） |
| Category | `Gameplay`（备选：`Utilities`） |
| Adult content | No |
| Comments | 开（Comments + Discussion 都开，问题都往这里收） |
| Donations | 可选，开不开都不影响审核 |

## 分类 / 标签

Nexus 的标签要在表单里从候选列表选，不要自己造词。优先找：

- `Gameplay`（主分类）
- `Companions` / `Summon` / `NPC`（有哪个选哪个）
- `Utility`、`User Interface`（赐福菜单那部分）
- `Offline`、`Singleplayer`（如果有）
- `Localisation`（有多语言菜单）

标题/摘要里已经带了 "companions / save / spirit ash / AI" 这些关键词，搜索能命中。

## Requirements（表单的 Requirements 区）

1. **Official requirements**：不勾 DLC（DLC 装不装都能用）。
2. **Required mods on the Nexus**：搜 `Mod Engine 2`。
   - 如果搜不到官方页（ME2 主要发布在 GitHub），就在 **Other required resources** 里加一条：
     - Name: `Mod Engine 2`
     - URL: `https://github.com/soulsmods/ModEngine2`
     - Notes: `Tested with 2.1.0. Any DLL loader that disables EAC works.`
3. **Other**：
   - `A working vanilla install` —— 先确认「不带 mod 能进标题」，否则先修游戏/EAC（页面里也要写）。
   - `ELDEN RING 1.17.2`（exe 2.7.2.0 / 2.7.2.1）—— 写清楚「其他版本不工作」。
   - `Python 3.9+`（可选，仅导出存档 / LLM sidecar）。

## Permissions（权限区块）

这一组只是**页面声明**，选完即生效，**没有「申请」流程**（也不用等 Nexus 审核）。
真正要事先确认的第三方授权见 `credits-and-licenses.md` §5 的结论表（结论：都不需要申请）。

推荐这一组（和 MIT/Apache 代码许可不冲突，又保留对发布物的控制）：

| 项 | 选 |
|---|---|
| Upload permission | You are **not** allowed to upload this file to other sites |
| Modification permission | You **must get permission** before modifying my files |
| Conversion permission | You are **not** allowed to convert this file |
| Asset use permission | You **must get permission** before using assets |
| Donation Points | 允许 |
| AI training / fork（2026 新增字段） | `Ask me`（默认即可；不想被拿去训练就选 `Disallow`） |

> 正文里已经写了「代码 MIT/Apache，可复用但请先问一声，源码在 GitHub」，两处保持一致。
> 如果审核问「为什么代码是 MIT 却选 must get permission」：Nexus 权限约束的是**本页压缩包**，
> 代码许可是另一回事——正文里已分开写。
>
> **不用申请的三项**（详见 `credits-and-licenses.md` §5）：fromsoftware-rs 只需附 NON-AI 全文；
> ME2 / me3 / ESDLang 不随包分发、署名即可；Convergence 参数表是运行时 dump 的数值，不是它的资产。
> 改过的 talk ESD 属于游戏数据，**没有授权渠道可申请**，只能按 Nexus 规则在页面披露。

## AI 声明（2026 起强制）

表单会问 generative AI 的使用情况。本项目的结论**已经定好**：选 **`AI-Generated Content`**
（代码主要由 AI 生成，人工负责设计、测试、排障与游戏内验证），`description.bbcode` 末尾已经是这个版本，
**不要再改回别的档**。

参考：另一档 `AI Assisted` 要求人工主导且页面能给出开发历史 / 代码理解证据；`docs/implementation-log.md`
虽然够详细，但为了不跟审核扯皮，还是选更诚实的那档。

另外两条容易踩的：

- 页面**图片**如果是 AI 生成的（不是游戏截图），还要勾 `AI Media`。
  本次准备的图都是游戏内截图，不需要。
- 页面**说明文字**如果是 AI 代写的，也属于 `AI Media`。
  建议：自己改写一遍，或如实勾选。**别不写**——被举报后是 Trust & Safety 处理。

## Files 标签页

| 字段 | 值 |
|---|---|
| File name | `ER Echo - Installer` |
| File version | `0.1.0` |
| Category | `Main files` |
| 勾选 | `This is the latest version` |
| Description | 用 `file-description.md` 的内容（安装器版） |
| 上传文件 | `dist/nexus/ER-Echo-Setup-0.1.0.zip` |

可选文件 1（手动安装）：

| 字段 | 值 |
|---|---|
| File name | `ER Echo - Manual Install (optional)` |
| Version | `0.1.0` |
| Category | `Optional files` |
| 文件 | `dist/nexus/ER-Echo-0.1.0.zip` |
| 说明 | 不想跑安装器时用；解压到 Game 目录，按包内 `README.txt` 手动加 `external_dlls` + `mod_loader` |

可选文件 2（ESD fallback）：

| 字段 | 值 |
|---|---|
| File name | `ER Echo - Root Menu ESD Fallback (optional)` |
| Version | `0.1.0` |
| Category | `Optional files` |
| 文件 | `dist/nexus/ER-Echo-0.1.0-ESD-fallback.zip` |
| 说明 | 只在「运行时菜单注入失败」时用；会替换 `mod/script/talk/*.dcx`，和其它改该文件的 mod 冲突 |

## 媒体（Images）

顺序就是页面展示顺序，**第一张是缩略图**：

1. `media/00-banner-1400x400.jpg` → 页头横幅（1400×400）
2. `media/01-grace-menu.jpg` → 赐福菜单根入口（`Comrades (3/11)`：3 个在场 / 11 份档案）
3. `media/02-party-menu.jpg` → 二级菜单 + 3 个号位
4. `media/03-companions.jpg` → 野外同行（3 个克隆体 + 你）
5. `media/04-combat.jpg` → 战斗
6. `media/05-closeup.jpg` → 角色特写（脸 / 盔甲）
7. `media/06-localisation.jpg` → 英文 / 简体中文菜单左右对照
> 图由 `nexus\make_media.py` 从 `media/incoming/*.jpg` 生成（1920×1080、JPEG q88、<2 MB），
> 原始截图不要直接传。`06` 的英文半边用的是英文二级菜单图（和 `02` 同一张）——没有单独的
> `i18n-en.jpg` 时脚本自动这么取，补了同名文件就会优先用它。

视频（可选）：Nexus 支持 YouTube 嵌入。60–90 秒足够，脚本见 `shotlist.md` §3。

## 发布前检查

- [ ] 版本号与 DLL 一致（`0.1.0`）
- [ ] `description.bbcode` 的 AI 段是 `AI-Generated Content`（已定，见上）
- [ ] 图片全部是游戏内截图、无 FPS 叠加层、无 debug 文本，且都是 1920×1080 / 1400×400
- [ ] 主文件（`ER-Echo-Setup-0.1.0.zip`）里**不含** `config_eldenring.toml`、ME2 / me3 / Convergence 的
      可执行文件、作者存档导出的 profile（`_internal\payload\tables\convergence\*.json` 只是参数 ID 表，
      用来校验装备 id，页面上已说明）
- [ ] 主文件 payload 里**含** `mod\script\talk\m00_00_00_00.talkesdbnd.dcx`（赐福菜单必需）、
      `tools\doctor.ps1` + `bridge\`（CLI 工具，和插件包一致）、
      `profiles\builtin_sanvenir.json`、`THIRD-PARTY-LICENSES.txt`、`LICENSES\`
- [ ] 手动包（`ER-Echo-0.1.0.zip`）里**含** `launchmod_eldenring.bat` + `launchmod_eldenring_admin.bat`
      （CRLF、都带 `-p`）
- [ ] 三个 zip 的 SHA256 与 `nexus/release-checksums.txt` 一致
- [ ] Requirements 里 ME2 / me3 链接可用
- [ ] 描述里有启动三分法排障（launcher `0xC0000409` / 10 秒 `0x1EBCEF9` / 无 mod 也崩）
- [ ] 先点 **Publish** 前用预览看一眼 BBCode 有没有漏标签
