# 安装 · 跨机器生效检查（ER Echo）

> **最省事的装法**：运行发布包里的 `ER-Echo-Setup.exe` → 「安装 / 配置」页 →
> 游戏路径填 `...\ELDEN RING\Game`（原版）或 `...\Convergence3\ConvergenceER`（Convergence）→
> 一键安装。它会拷文件、导出你自己的角色、写好 `profiles=`、改配置（全部带备份），
> 卸载也在同一个页面。下面的内容留着解释原理和手动排查。
> Convergence / me3 的适配见 [CONVERGENCE.md](CONVERGENCE.md)。
>
> 装完同一页就能**一键启动**：原版（ME2）走 `mods\ER-Echo\launch-er-echo*.bat`，
> Convergence（me3）走 `me3\Windows\me3.exe launch -p .\me3\convergence*.me3`
> （有 SeamlessCoop 就自动用无缝配置）。原版启动后约 10 秒闪退时，勾上
> 「以管理员身份启动」再点。安装完成的弹窗也会问「现在启动游戏？」。
>
> **更新已安装的版本**：关掉游戏，重新运行同一个 `ER-Echo-Setup.exe`，选同一个游戏路径 → 安装。
> 它会用安装器 payload 里的新 `er_echo.dll` 覆盖 `mods\ER-Echo\er_echo.dll`，并重新导出存档角色、
> 重写 `er_echo.ini` 的 `profiles=`（其它配置行保留）。如果队友已经被自动升级写进
> `profiles\slot*.json`，**先备份这些档案**再更新，因为重新导出会用存档里的等级覆盖同名文件。
> 只想换 DLL 的话，也可以直接把新 `er_echo.dll` 覆盖到 `mods\ER-Echo\er_echo.dll`（不用安装器）。
>
> **安装器设置会记住**：GUI 默认英文；界面语言、游戏路径、存档、导出目录、`er_echo.ini` 路径、
> **游戏内菜单语言**和上次页签都存在 Windows 用户配置（`QSettings`，注册表
> `HKCU\Software\ER-Echo\ProfileExport`），下次打开沿用。
> 以前在旧版里手动切过中文的，升级后第一次会按新默认英文启动（旧版没有 `lang_explicit` 标记，
> 无法区分「手动选的」和「当年的系统默认」）；在新版里再选一次中文就会带标记记住。
> 安装器新生成的 `er_echo.ini` 里 `[i18n] language=game`（跟随游戏文本语言）；
> 想固定中文/英文，就在「安装 / 配置」页的**「游戏内菜单语言」**下拉框里选，改完立刻写入
> `er_echo.ini`（先备份），重启游戏生效。详见 [i18n.md](i18n.md)。

> **路径约定（2026-11-21 起）**：源码已搬到 `D:\Projects\ER-Echo\`，**不再放在游戏目录里**。
> 下文例子里的 `er-echo\tools\...`、`er-echo\bridge\...` 都指**仓库根目录**
> （即 `D:\Projects\ER-Echo\tools\...`）。脚本会自动探测游戏目录
> （`-GameDir` 参数 → `$env:ER_ECHO_GAME_DIR` → Steam 注册表/libraryfolders.vdf），
> 不需要再靠「脚本自己在 Game\er-echo 里」猜路径。
>
> **已经用安装器装进游戏的**：游戏侧的 `mods\ER-Echo\` 就对应这里的 `er-echo\`。
> 把下文的 `er-echo\...` 换成 `mods\ER-Echo\...`（例如 `er-echo\tools\doctor.ps1` →
> `mods\ER-Echo\tools\doctor.ps1`，`er-echo\docs\` → `mods\ER-Echo\docs\`）。
> 手动包（解压到游戏根目录）则保持 `er-echo\...` 不变。

> 结论先说：**能生效，但不是「拷过去就能跑」**。它有三道硬门槛——**游戏版本**、
> **加载器配置**、**目录写权限**；再加一个软门槛：**角色档案要自己导出**。
> 本文按「另一台干净机器」写一遍，最后给症状对照表。

---

## 0. 一句话兼容性

| 项目 | 要求 | 不满足会怎样 |
|---|---|---|
| 游戏版本 | **1.17.2**：`eldenring.exe` 产品版本 `2.7.2.0`（全球版）或 `2.7.2.1`（日版） | 不加载或闪退（RVA/AOB 全部错位） |
| 系统 | Windows 10/11 x64 | 根本加载不了（DLL 是 x64） |
| 运行库 | **不需要** VC++ / .NET / Python | —（DLL 只依赖系统 DLL） |
| 加载器 | ModEngine2 2.x（实测 2.1.0）+ 正确的 `config_eldenring.toml` | DLL 不被注入，游戏里毫无反应 |
| 网络 | 离线；**必须**用 `launchmod_eldenring.bat` 启动（绕开 EAC） | 带 mod 上线 = 隔离 / soft-ban |
| 存档 | 不改 `.sl2`：注入只发生在内存 | 但仍建议先备份 |
| 其他 mod | 不要和改 `m00_00_00_00.talkesdbnd.dcx` 或大改 param 的 mod 混用 | 菜单冲突 / 参数行语义不对 |

**证据（不是猜的）**：

* `mod/vendor/fromsoftware-rs-main/crates/eldenring/src/rva.rs` 里只注册了两个版本：
  `(LANG_ID_EN, "2.7.2.0")` 和 `(LANG_ID_JP, "2.7.2.1")`，其他版本 `rva::get()` 直接 panic；
* `mod/src/ui.rs`、`ezstate.rs` 的 AOB 注释标注「1.17.2 实测」，是逐字节匹配的；
* `er_echo.dll` 的导入表只有 `kernel32 / msvcrt / ntdll / oleaut32 / user32 / ws2_32 /
  bcryptprimitives / api-ms-win-core-synch-l1-2-0`，没有一个第三方运行库；
* 版本不对时启动路径有 `catch_unwind` 兜底：实测（脱离游戏单独 `LoadLibrary`）
  会写一条 `wait_for_instance panicked（exe 名/版本不匹配）` 然后空转，不会把宿主带崩——
  但仍不要指望它在错版本上能用；
* 赐福菜单靠 `mod/script/talk/m00_00_00_00.talkesdbnd.dcx`（版本绑定的 ESD）。

---

## 1. 全新安装（另一台机器）

下面命令都在**游戏根目录**（和 `eldenring.exe` 同级）执行。
`<Game>` 代表类似 `...\steamapps\common\ELDEN RING\Game` 的路径。

### 第 0 步：备份 + 锁版本 + 先确认「不带 mod 能进标题」

1. **先裸启动一次**：不经过 ME2，直接 `eldenring.exe`，能进标题界面并稳定站 1 分钟。
   如果这一步就崩/秒退，问题在游戏本体或 EAC，不在 mod——先校验文件 / 重装 EAC / 重装游戏
   （详见 §3 的「坑 2」），别往 mod 上找。
2. 退出游戏和 Steam 云同步；备份存档：
   `%APPDATA%\EldenRing\<你的SteamID>\ER0000.sl2`。
3. **别让 Steam 自动更新游戏**：Steam 里对 ELDEN RING 关闭自动更新，或用离线模式。
   一旦更新到 1.17.3+，本 DLL 需要重新逆向 + 重编译才能用。

### 第 1 步：装 ModEngine2

从 [Mod Engine 2 官方 release](https://github.com/soulsmods/ModEngine2/releases) 解压到游戏根目录，确认有：

```
modengine2_launcher.exe
modengine2\bin\modengine2.dll
config_eldenring.toml
launchmod_eldenring.bat          ← 官方版没有 -p；用发布包里的替换（见第 2 步）
launchmod_eldenring_admin.bat    ← 发布包新增，自提权
```

> 下载页：[Mod Engine 2 Releases](https://github.com/soulsmods/ModEngine2/releases)
> （ME2 已停止更新、仓库已归档；继任者是 [me3](https://github.com/garyttierney/me3/releases)）。
> 安装器 exe 的「加载器安装步骤…」里有同样的图文步骤和跳转按钮；
> **安装器不打包、也不分发 ME2 / me3**，只写 ER Echo 文件和配置引用。
> 玩 Convergence 的话**不用装 ME2**：它自带 me3，见 [CONVERGENCE.md](CONVERGENCE.md)。

> **为什么要换 bat**：ME2 2.1.0 的 `-t er` 会去探测 Steam 安装路径，个别机器上直接
> `0xC0000409` 崩在 `ucrtbase.dll`（双击 bat 一闪就没）。发布包的 bat 固定带
> `-p ".\eldenring.exe"`，跳过这段探测。

### 第 2 步：放 mod 文件

把发布包（`ER-Echo-<日期>`）里的内容覆盖进来，至少要有：

```
er_echo.dll                         ← 注入的游戏内逻辑
er_echo.ini                         ← 配置（profiles / 菜单语言）
er_echo_i18n.example.ini            ← 多语言覆盖模板（可选，复制成 er_echo_i18n.ini 才生效）
mod\script\talk\m00_00_00_00.talkesdbnd.dcx   ← 赐福菜单必需（见下）
profiles\builtin_sanvenir.json      ← 内置角色 Sanvenir（彩蛋 / 备用，默认名单里就有）
profiles\profile.example.json       ← 格式示例（不想要可删）
er-echo\tools\...                   ← 导出档案 / IPC 工具
er-echo\bridge\...                  ← LLM 导演（可选）
er-echo\docs\...                    ← 文档
```

> **关于 `mod\script\talk`（实测修正）**：这个 ESD **必须挂载**，否则 EzState 注入会报
> `cannot find grace root list start state`，赐福里不会出现「战友」。
> 也就是说 `config_eldenring.toml` 里要有 `mod_loader` 的 `mods` 条目指向它。
> （早期以为「运行时注入不需要 ESD」，2026-11-21 实测证伪。）

### 第 3 步：确认 `config_eldenring.toml`

两处都要对，缺一处就「什么都没发生」：

```toml
[modengine]
debug = false
external_dlls = ["er_echo.dll"]

[extension.mod_loader]
enabled = true
mods = [
  { enabled = true, name = "er-echo", path = "mod" },
]
```

> `mods = []` 时 ME2 不会读 `mod/`，赐福里不会有「战友」——这是最常见的坑。

### 第 4 步：导出你自己的角色档案

```powershell
# 4.1 列出存档里的角色（自动找 %APPDATA%\EldenRing 下最新的 ER0000.sl2）
python er-echo\tools\export_profile_from_save.py --list

# 4.2 导出某个槽（0..9）
python er-echo\tools\export_profile_from_save.py --slot 2 -o profiles\me.slot2.json

# 4.3 想一次导出全部
python er-echo\tools\export_profile_from_save.py --all -d profiles
```

然后改 `er_echo.ini`：

```ini
[clone]
profiles=profiles/me.slot2.json
```

> 不导出也能玩（`profiles` 留空）——但召唤出来的会用**玩家自己**的装备外观，
> 不是「另一个存档的角色」。

### 第 5 步：启动

```powershell
.\launchmod_eldenring.bat
```

**不要**在 Steam 里点「开始游戏」：那会拉起 `start_protected_game.exe`（EAC），
mod 不加载，而且带 mod 存档上线有封号风险。

如果这样启动后**游戏窗口大约 10 秒就消失**（事件查看器里 `eldenring.exe`
`0xc0000005`、偏移 `0x1EBCEF9`），改用管理员版：

```powershell
.\launchmod_eldenring_admin.bat
```

它只是多了一步 UAC 提权：提权后 Steam 的游戏内覆盖层注不进游戏进程，
就不会和 ModEngine2 的钩子在输入层打架。代价是游戏里没有 Steam 覆盖层。
不想每次弹 UAC 的话，也可以改成在 Steam → 设置 → 游戏中 里关掉
「启用 Steam 界面」，然后继续用普通版 bat。

### 第 6 步：验证

先跑自检（只读，游戏不用开）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\doctor.ps1
```

进游戏后看 `er_echo.log`（UTF-8）：

```
er_echo attached (target exe 2.7.2.0)
i18n: language=zh-CN (source=manifest, er_echo.ini language="game", ...)
ui: message hook installed at ... (rva ...)
ezstate: ...
```

* 坐着赐福 → 最上面一项是「战友（n/m）」或「Comrades (n/m)」；
* 用一次骨灰，或按 **F8** 手动召唤；
* `er_echo.log` 里应出现 `summon: using profile '...' lv..`。

### 第 7 步（可选）：LLM 导演

```powershell
python er-echo\bridge\director.py --llm mock          # 先跑 mock 自测
python er-echo\bridge\director.py --llm openai --model gpt-4o-mini --api-key $env:OPENAI_API_KEY
```

只用标准库，不需要 `pip install`。

## 1.1 加载器（Mod Engine 2 / me3）：下载页与选择

| 玩法 | 加载器 | 获取方式 | 本工具的做法 |
|---|---|---|---|
| 原版 | **Mod Engine 2** 2.1.0 | [ME2 Releases](https://github.com/soulsmods/ModEngine2/releases) 下载 `ModEngine-*-win64.zip`，解压到游戏根目录（`modengine2_launcher.exe` 与 `eldenring.exe` 同级） | 自动写 ME2 配置，一键启动 |
| Convergence 3.x | **me3**（整合包自带） | [The Convergence](https://www.nexusmods.com/eldenring/mods/3419)；装好后就有 `me3\Windows\me3.exe` | 自动往 `me3\convergence*.me3` 追加引用，一键启动 |
| 原版 + me3 | **me3**（独立安装） | [me3 Releases](https://github.com/garyttierney/me3/releases) 里的 `me3_installer.exe`，或便携版解压到本地目录 | 加载器选「me3（独立安装）」→ 自动写 `<Game>\er-echo.me3`（`[[natives]]` + `[[package]]`）→ 一键启动 |

**ME2 安装步骤（原版）**

1. 打开 [ME2 Releases](https://github.com/soulsmods/ModEngine2/releases)，在 Assets 里下载最新的
   `ModEngine-*-win64.zip`。
2. 解压后把 `modengine2_launcher.exe` 和 `modengine2\` 文件夹放到游戏根目录，
   和 `eldenring.exe` 同级。
3. 回 `ER-Echo-Setup.exe`：游戏路径填 `...\ELDEN RING\Game`，加载器选「Mod Engine 2」或「自动」，
   点「自动检测」→「一键安装」→「一键启动游戏」。
4. 启动后约 10 秒闪退时勾「以管理员身份启动」（Steam 覆盖层 × ME2 钩子的老问题）。

**me3 安装步骤（原版独立安装 / Convergence 自带）**

1. 玩 **The Convergence** 不需要单独装 me3：整合包自带 `me3\Windows\me3.exe`，
   直接把 Convergence 根目录填进安装器即可（加载器会自动固定为 me3）。
2. 只装 me3：打开 [me3 Releases](https://github.com/garyttierney/me3/releases)，下载
   `me3_installer.exe` 按向导安装；或下载便携版解压到本地目录（不要放 OneDrive）。
3. **原版 + me3**：游戏路径填 `...\ELDEN RING\Game`，加载器选「me3（独立安装）」。
   `me3.exe` 路径可以留空（自动查 PATH / 注册表 / 常见目录），找不到就点「浏览…」指定
   （例如 `D:\Games\me3\bin\me3.exe`）。
4. 点「一键安装」：会在游戏根目录生成 `er-echo.me3`
   （`[[natives]]` → `mods\ER-Echo\er_echo.dll`，`[[package]]` → 赐福菜单 ESD），
   并在 `mods\ER-Echo\er_echo_loader.json` 记录这次用 me3。
5. 点「一键启动游戏」：执行
   `me3 launch --auto-detect -p .\er-echo.me3`；装好后命令行手动跑这条也一样。
6. 验证：`me3 info` 正常、游戏能进；`er_echo.log` 里应有 `er_echo attached`。

> 三种组合（原版 + ME2 / 原版 + me3 / Convergence + 自带 me3）都支持「一键安装 + 一键启动」；
> 装完后想换加载器，改下拉再点一次「一键安装」即可（会重写 `er_echo_loader.json` 和对应的 profile）。

> **合规说明**：本仓库和 `ER-Echo-Setup.exe` **不包含、也不分发** Mod Engine 2 / me3 /
> Convergence 的任何文件。安装器只写 ER Echo 自己的文件，并在你已有的加载器配置里追加引用
> （全部带备份）；加载器请从上面的官方页面下载，并遵守各自的许可证。
> 安装器界面里的「获取 Mod Engine 2」「获取 me3」「加载器安装步骤…」就是这几个官方页面的入口。

---

## 2. 换机器迁移清单

| 项目 | 直接拷过去行不行 | 要改什么 |
|---|---|---|
| `er_echo.dll` | ✅ | 版本必须一致 |
| `mod\script\talk\*.dcx` | ✅ | 只对 1.17.2 有效 |
| `config_eldenring.toml` | ✅ | 路径都是相对游戏根目录 |
| `er_echo.ini` | ⚠️ | `profiles=` 换成新机器上你自己导出的 json；想换菜单语言改 `[i18n] language`（`game` = 跟随游戏文本，默认） |
| 作者导出的 profile | ❌ | 那是作者存档里角色的外观/装备，换成你自己的 |
| `er-echo\tools\*.ps1` | ✅ | 都按脚本位置推游戏根目录，不写死盘符 |
| `er-echo\bridge` | ✅ | LLM key 自己配 |
| ME2 本体 | ❌ | 目标机器自己装 |
| 存档 `.sl2` | — | 不要拷别人的存档（会触发存档校验/隔离） |

工具里只有几个**作者调试用**的临时脚本写死了盘符（`live_*.ps1`、`restart_and_test*.ps1`、
`restart_and_probe.ps1`、`analyze_dump.py`、`_probe_magic*.py`），发布包已经排除；
日常用的 `doctor / auto_start / sit_grace / switch_menu_mode / swap_dll_on_exit`
都是按 `$PSScriptRoot` 推路径的。

---

## 3. 症状 → 原因 → 处理

| 症状 | 最可能的原因 | 处理 |
|---|---|---|
| 游戏里完全没有变化，`er_echo.log` 也没生成 | DLL 没被注入 | 检查 `external_dlls`；确认是用 bat 启动；看 `modengine2\logs\*.log` 里有没有 `Loaded external DLL ...er_echo.dll` |
| 有 `er_echo.log`，但没有 `attached` | 游戏版本不对 / exe 名不对 | 升级/降级到 1.17.2；看日志里 `CSTaskImp not found` 或 `wait_for_instance panicked` |
| 游戏直接闪退 | 版本不匹配导致 panic，或与其它 DLL mod 冲突 | 先只留 `er_echo.dll` 试；看 `crashdumps\` 和 `er_echo.log` 末尾 |
| 启动约 10 秒后闪退，WER 里 `eldenring.exe` / `0xc0000005` / 偏移 `0x1EBCEF9` | Steam 游戏内覆盖层（`gameoverlayrenderer64.dll`）与 ModEngine2 的钩子在输入层冲突；dump 里的 panic 是 `DLUserInputManagerImpl_win32.cpp(98)` | 用 `launchmod_eldenring_admin.bat`（提权后覆盖层注不进去），或在 Steam → 设置 → 游戏中 关掉「启用 Steam 界面」 |
| 双击 bat 后命令窗一闪就没，事件查看器里 `modengine2_launcher.exe` / `0xC0000409` | ME2 的 `-t er` 会走 Steam 安装路径自动探测，个别机器上这段抛未捕获异常 | 确认启动命令带 `-p ".\eldenring.exe"`（两个 bat 都已带），它会跳过探测 |
| 赐福里没有「战友」 | nested 模式：消息/EzState 钩子没装上（AOB 不匹配）；fallback：`mods = []` 或 ESD 没加载 | 看日志 `ui: message hook installed` / `ezstate:`；fallback 模式下补 `mods`、确认 ESD 在；F8 仍可召唤 |
| 菜单是空白/乱码 | 消息钩子没装上（AOB 不匹配）或语言字体缺字 | 看日志 `message hook installed`；把 `[i18n] language` 改成 `game`（跟随游戏文本语言，默认）或和游戏文本一致的语言 |
| 召唤出来是玩家自己 | `profiles` 为空/路径错 | 重新导出并改 `profiles=` |
| 能召唤但外观不对 | profile 太旧（游戏大版本变了） | 用当前存档重新跑 `export_profile_from_save.py` |
| 游戏目录里没有日志/JSON | 装在 `Program Files` 下没有写权限 | 给目录授权 / 搬出 Program Files / 管理员运行 |
| 卡顿、日志暴涨 | `config_eldenring.toml` 的 `debug = true` | 改 `false`（发布包默认已关） |
| 联机被隔离 | 带着 mod 上线 | 只离线玩；换回干净存档再上线 |

---

## 4. 这个 mod 会往游戏目录写什么

| 文件 | 用途 |
|---|---|
| `er_echo.log`（+ `.1`/`.2`，8 MB 轮转） | 运行日志，排障第一现场 |
| `er_echo_heartbeat.txt` | 上次退出时停在哪一帧/哪个操作（闪退排查） |
| `er_echo_profile.json` / `er_echo_buddies.json` / `er_echo_ride.json` / `er_echo_npc.json` / `er_echo_think.json` / `er_echo_equip.json` / `er_echo_magic.json` | 手动 dump 命令的产物（不自动生成） |
| `er_echo_roster.json` / `er_echo_status.json` / `er_echo_clone_info.json` / `er_echo_weights.json` / `er_echo_summon_state.json` / `er_echo_combat.json` / `er_echo_spirit.json` | 状态 / 名单 / 战斗探针 |
| `er_echo.ini` / `er_echo_i18n.ini` | 只读配置 |

**不写**：`regulation.bin`、`Data*.bdt/bhd`、`.sl2` 存档、`mod\` 下的资源。

---

## 5. 安全与合规

* 只离线；EAC 关闭（`launchmod_eldenring.bat` 直接启动 `eldenring.exe`）。
* 带 mod 的存档上线会被 FromSoftware 隔离（soft-ban），请用干净存档上线。
* 不要分发别人的存档/存档导出物；本仓库的 profile 示例是占位数据。
* 改文件前备份；出问题先删 `er_echo.dll` 再启动一次，确认「游戏本身没问题」。

---

## 6. 升级游戏后要做什么

1. 用 `tools/doctor.ps1` 看版本（会直接报「不受支持」）；
2. 重新确认 RVA/AOB：`docs/implementation-log.md` §1 的工具链 + 重新对偏移；
3. 重编 ESD：`ui/README.md`（`talkesdbnd` 是版本绑定的）；
4. 重新导出 profile（大版本后字段可能变）；
5. 重跑 `tools/verify_after_restart.py` 做回归。
