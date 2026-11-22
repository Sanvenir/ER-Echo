# 发布操作清单（Nexus Mods）

按顺序做，每步都有「做完的标准」。上传入口：**Mods → Upload a mod**（新版表单，2026-04 起）。

---

## 阶段 0：发布前（本地）

- [ ] `powershell -File tools\doctor.ps1` → 0 阻断
- [ ] `dist/nexus/ER-Echo-Setup-0.1.0.zip` 已生成（顺序：`tools\package_payload.ps1` →
      `tools\build_gui_exe.ps1` → `tools\package_nexus.ps1`）
- [ ] `dist/nexus/ER-Echo-0.1.0.zip` + `ER-Echo-0.1.0-ESD-fallback.zip` 已生成
- [ ] 安装器 payload 里**没有** `config_eldenring.toml` / 作者 profile；`mod\script\talk` 的 ESD 作为 payload 一部分是**必需**的
- [ ] 安装器 `_internal\payload` 里**有** `er_echo.dll`、`er_echo_i18n.example.ini`、
      `profiles\profile.example.json`、`profiles\builtin_sanvenir.json`（内置彩蛋；安装后 `profiles=`
      末尾要有它）、两个 `launch-er-echo*.bat`（CRLF）、`THIRD-PARTY-LICENSES.txt`、`er-echo\docs\`
      （`er_echo.ini` 由安装器按内置模板生成，不在 payload 里）
- [ ] 手动包（Optional）里**有** `er_echo.dll`、`er_echo.ini`、`er_echo_i18n.example.ini`、
      `profiles\profile.example.json`、`profiles\builtin_sanvenir.json`、两个 `launchmod_eldenring*.bat`
      （CRLF）、`THIRD-PARTY-LICENSES.txt`、`er-echo\docs\`
- [ ] bat 都带 `-p ".\eldenring.exe"`；admin 版能自提权
- [ ] 版本号统一为 `0.1.0`（DLL / 页面 / 文件名）
- [ ] 三个 zip 的大小 / SHA256 与 `nexus\release-checksums.txt` 一致
- [ ] 图片按 `shotlist.md` 重拍并处理完（无 FPS 叠加层、16:9、1920×1080 / 1400×400）
- [ ] `description.bbcode` 的 AI 段是 `AI-Generated Content`（已定档）
- [ ] **干净环境实测两条启动路径**：普通 bat ×1（不提权）、admin bat ×1（提权）
- [ ] 安装器「一键启动游戏」实测三种组合：原版 + ME2（含勾管理员）×1、
      原版 + 独立 me3 ×1（生成 `<Game>\er-echo.me3`）、Convergence + 自带 me3（普通/无缝）
- [ ] 原版切换加载器：ME2 ↔ me3 各重装一次，`er_echo_loader.json` 跟着变，启动走记录的那条；
      另一条可用时作为兜底
- [ ] 安装器「加载器安装步骤…」里的三个官方链接可达；未装 ME2 时弹窗跳转、以及
      「仍然安装文件」两条路都正常；包里**没有** ME2 / me3 / Convergence 的文件
- [ ] 确认 README.txt 里有「约 10 秒闪退 → admin 版 / 关覆盖层」和「先确认无 mod 能进标题」

## 阶段 1：建页面

1. Upload a mod → 选 **Elden Ring**。
2. 填 name / summary / category / tags / language / version（照 `page-fields.md`）。
3. 贴 description（BBCode 直接贴；先预览）。
4. Requirements：DLC 不勾；Other 里加 ME2（GitHub）与「ER 1.17.2」。
5. Permissions：照 `page-fields.md` 那组选；AI training / fork 用默认 `Ask me`。
6. **先别 Publish**，页面可以先存草稿。

## 阶段 2：传文件

1. Files → Upload file。
2. 主文件：`ER-Echo-Setup-0.1.0.zip`，version `0.1.0`，category `Main files`，
   勾 `This is the latest version`，描述用 `file-description.md`（安装器版）。
3. 可选文件 1：`ER-Echo-0.1.0.zip`（手动安装），category `Optional files`，
   描述里写清「解压到 Game 目录 + 按 README.txt 改 config」。
4. 可选文件 2：`ER-Echo-0.1.0-ESD-fallback.zip`，category `Optional files`，
   描述里写清「会替换 `mod/script/talk`，和其它改该文件的 mod 冲突」。
5. 等病毒扫描通过（zip 一般几秒；`.rar` 容易被误判，我们用的是 zip）。

## 阶段 3：图片

1. Images → Add images，按顺序上传：
   `00-banner` → `01-grace-menu` → `02-party-menu` → `03-companions` → `04-combat` → `05-closeup` → `06-localisation`。
2. 第一张 = 缩略图，确认在搜索列表里能看清。
3. Banner（1400×400）设为 header image。
4. 如果加了视频：Videos → 贴 YouTube 链接。

## 阶段 4：发布

1. 预览整页（尤其 BBCode 的 `[list]` / `[code]` 有没有漏闭合）。
2. Publish。
3. 立刻发一条置顶评论：**已知限制 + 反馈请附 `er_echo.log` 最后 50 行 + 游戏版本**。
4. 在描述里留一个「更新日志」链接（Nexus 有 Changelogs 标签，把 `changelog.md` 贴进去）。

## 阶段 5：发布后 48 小时

- [ ] 盯评论：版本不对（99%）、ME2 配置没加 DLL、没导出 profile——这三类占大多数，回答时直接贴
      `doctor.ps1` 和 `er_echo.log` 的检查方法
- [ ] 有人报崩溃：要 `crashdumps\` + `er_echo.log` 尾巴，别在评论里猜
- [ ] 更新 `changelog.md` 和页面版本号（下次）

---

## 常见审核问题（提前规避）

| 风险 | 规避 |
|---|---|
| 版权：包里有没有游戏原始文件 | 主包**含** `mod\script\talk` 的 ESD（赐福菜单必需，实测不挂载就不出现「战友」）；它是改过的 vanilla ESD，页面写明 |
| 第三方代码许可 | `THIRD-PARTY-LICENSES.txt` + `LICENSES\` 里有 fromsoftware-rs 的 NON-AI 许可全文 |
| 联网行为 | 页面写明「DLL 只监听 127.0.0.1；LLM 是你自己选的端点，默认 mock 离线」 |
| 多人环境 | 页面顶部红字「OFFLINE ONLY」，正文再写一次 |
| AI 未披露 | AI 声明段必填（2026-11-03 起强制，缓冲期到 2027-01-02） |
| 图片误导 | 只用游戏内截图；不用 AI 图；不 P 战斗数值 |
| 启动失败 = 差评 | 描述里有三分法排障（launcher `0xC0000409` / 10 秒 `0x1EBCEF9` / 无 mod 也崩），两个 bat 都在包里 |

---

## 评论回复模板（发布后直接用）

| 玩家说 | 先让他做 |
|---|---|
| 「bat 一闪就没」 | 用包里的 bat（带 `-p`）；确认不是从 Steam 点启动 |
| 「游戏 10 秒闪退」 | `launchmod_eldenring_admin.bat`，或关 Steam 覆盖层；要 WER 的模块 + 偏移 |
| 「没有战友菜单」 | 看 `er_echo.log` 的 `ezstate:` / `message hook installed`；先确认 vanilla 能启动 |
| 「召唤出来是我自己」 | `profiles=` 路径错 / 没导出；跑 `doctor.ps1` |
| 「报错/闪退」 | 附 `er_echo.log` 最后 50 行 + `crashdumps\` + 游戏 exe 版本 |
