# 安装 · 跨机器生效检查（ER Echo）

> **最省事的装法**：运行发布包里的 `ER-Echo-Setup.exe` → 「安装 / 配置」页 →
> 游戏路径填 `...\ELDEN RING\Game`（原版）或 `...\Convergence3\ConvergenceER`（Convergence）→
> 一键安装。它会拷文件、导出你自己的角色、写好 `profiles=`、改配置（全部带备份），
> 卸载也在同一个页面。下面的内容留着解释原理和手动排查。
> Convergence / me3 的适配见 [CONVERGENCE.md](CONVERGENCE.md)。
>
> **更新已安装的版本**：关掉游戏，重新运行同一个 `ER-Echo-Setup.exe`，选同一个游戏路径 → 安装。
> 它会用安装器 payload 里的新 `er_echo.dll` 覆盖 `mods\ER-Echo\er_echo.dll`，并重新导出存档角色、
> 重写 `er_echo.ini` 的 `profiles=`（其它配置行保留）。如果队友已经被自动升级写进
> `profiles\slot*.json`，**先备份这些档案**再更新，因为重新导出会用存档里的等级覆盖同名文件。
> 只想换 DLL 的话，也可以直接把新 `er_echo.dll` 覆盖到 `mods\ER-Echo\er_echo.dll`（不用安装器）。
>
> **安装器设置会记住**：GUI 默认英文；语言、游戏路径、存档、导出目录、`er_echo.ini` 路径和上次页签
> 都存在 Windows 用户配置（`QSettings`，注册表 `HKCU\Software\ER-Echo\ProfileExport`），下次打开沿用。
> 以前在旧版里手动切过中文的，升级后第一次会按新默认英文启动（旧版没有 `lang_explicit` 标记，
> 无法区分「手动选的」和「当年的系统默认」）；在新版里再选一次中文就会带标记记住。
> 安装器新生成的 `er_echo.ini` 里 `[i18n] language=en`；想让游戏菜单跟随系统就改成 `auto`。

> **路径约定（2026-11-21 起）**：源码已搬到 `D:\Projects\ER-Echo\`，**不再放在游戏目录里**。
> 下文例子里的 `er-echo\tools\...`、`er-echo\bridge\...` 都指**仓库根目录**
> （即 `D:\Projects\ER-Echo\tools\...`）。脚本会自动探测游戏目录
> （`-GameDir` 参数 → `$env:ER_ECHO_GAME_DIR` → Steam 注册表/libraryfolders.vdf），
> 不需要再靠「脚本自己在 Game\er-echo 里」猜路径。

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

从 Mod Engine 2 官方 release 解压到游戏根目录，确认有：

```
modengine2_launcher.exe
modengine2\bin\modengine2.dll
config_eldenring.toml
launchmod_eldenring.bat          ← 官方版没有 -p；用发布包里的替换（见第 2 步）
launchmod_eldenring_admin.bat    ← 发布包新增，自提权
```

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
profiles\profile.example.json       ← 占位档案，换成你自己的
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
i18n: language=zh-CN (er_echo.ini language="auto", ...)
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

---

## 2. 换机器迁移清单

| 项目 | 直接拷过去行不行 | 要改什么 |
|---|---|---|
| `er_echo.dll` | ✅ | 版本必须一致 |
| `mod\script\talk\*.dcx` | ✅ | 只对 1.17.2 有效 |
| `config_eldenring.toml` | ✅ | 路径都是相对游戏根目录 |
| `er_echo.ini` | ⚠️ | `profiles=` 换成新机器上你自己导出的 json；想换菜单语言改 `[i18n] language` |
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
| 菜单是空白/乱码 | 消息钩子没装上（AOB 不匹配）或语言字体缺字 | 看日志 `message hook installed`；把 `[i18n] language` 改成和游戏文本一致 |
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
