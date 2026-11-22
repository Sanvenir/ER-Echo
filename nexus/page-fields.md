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
| Language | English（正文末尾有简体中文段） |
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

推荐这一组（和 MIT/Apache 代码许可不冲突，又保留对发布物的控制）：

| 项 | 选 |
|---|---|
| Upload permission | You are **not** allowed to upload this file to other sites |
| Modification permission | You **must get permission** before modifying my files |
| Conversion permission | You are **not** allowed to convert this file |
| Asset use permission | You **must get permission** before using assets |
| Donation Points | 允许 |
| AI training / fork（2026 新增字段） | `Ask me`（默认即可） |

> 正文里已经写了「代码 MIT/Apache，可复用但请先问一声」，两处保持一致。

## AI 声明（2026 起强制）

表单会问 generative AI 的使用情况，正文 `description.bbcode` 末尾已经放了两个版本，**发布前二选一删掉另一个**：

- **Option A → `AI-Generated Content`**：代码主要由 AI 生成（本项目的情况更接近这个）。
- **Option B → `AI Assisted`**：人工主导、AI 只做辅助，并且页面能给出开发历史/代码理解证据；
  选了它但页面没有证据，审核可能改成 AI-Generated。

另外两条容易踩的：

- 页面**图片**如果是 AI 生成的（不是游戏截图），还要勾 `AI Media`。
  本次准备的图都是游戏内截图，不需要。
- 页面**说明文字**如果是 AI 代写的，也属于 `AI Media`。
  建议：自己改写一遍，或如实勾选。**别不写**——被举报后是 Trust & Safety 处理。

## Files 标签页

| 字段 | 值 |
|---|---|
| File name | `ER Echo - Companions From Your Own Saves` |
| File version | `0.1.0` |
| Category | `Main files` |
| 勾选 | `This is the latest version` |
| Description | 用 `file-description.md` 的内容 |
| 上传文件 | `dist/nexus/ER-Echo-0.1.0.zip` |

可选文件（第二个 file）：

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
2. `media/01-grace-menu.jpg` → 赐福菜单根入口
3. `media/02-party-menu.jpg` → 二级菜单 + 3 个克隆体
4. `media/03-companions.jpg` → 野外同行
5. `media/04-combat.jpg` → 战斗（待补拍）
6. `media/05-localisation.jpg` → 英文/日文/繁中菜单拼图（待补拍）
> 现在的图是**旧的开发截图**（中文界面、旧版本），只用来占位/验证流程。
> 正式发布前按 `shotlist.md` 重拍，替换同名文件即可。

视频（可选）：Nexus 支持 YouTube 嵌入。60–90 秒足够，脚本见 `shotlist.md` §3。

## 发布前检查

- [ ] 版本号与 DLL 一致（`0.1.0`）
- [ ] `description.bbcode` 里的 AI 段二选一
- [ ] 图片全部是游戏内截图、无 FPS 叠加层、无 debug 文本
- [ ] 主文件里**不含** `config_eldenring.toml` / `mod\script\talk` / 游戏原始文件
- [ ] 主文件里**含** `launchmod_eldenring.bat` + `launchmod_eldenring_admin.bat`（CRLF、都带 `-p`）
- [ ] 主文件里含 `THIRD-PARTY-LICENSES.txt`、`LICENSES\`
- [ ] Requirements 里 ME2 链接可用
- [ ] 描述里有启动三分法排障（launcher `0xC0000409` / 10 秒 `0x1EBCEF9` / 无 mod 也崩）
- [ ] 先点 **Publish** 前用预览看一眼 BBCode 有没有漏标签
