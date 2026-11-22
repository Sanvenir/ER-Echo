# 与 Convergence（Mod Engine 3）共存

> 实测环境：ELDEN RING 1.17.2（exe `2.7.2.0`）+ **Convergence 3.0.x**（自带 me3 0.13.0），
> 目录 `D:\Games\Convergence3\ConvergenceER`。2026-11-21 实测记录见本文末。

## 1. 为什么能共存

Convergence 3 换了一套加载器：它不用 Mod Engine 2，而是自带 **me3**（`me3\Windows\me3.exe`），
通过 `.me3` 配置（TOML）声明要加载什么：

| 机制 | ME2（原版安装） | me3（Convergence） |
| --- | --- | --- |
| DLL 注入 | `[modengine] external_dlls` | `[[natives]] path = '...'` |
| 资源覆盖 | `[extension.mod_loader] mods` | `[[package]] id/path` |
| 配置位置 | `<Game>\config_eldenring.toml` | `<Conv>\me3\convergence.me3` |

ER Echo 的 DLL 本身就是「外部注入的 native DLL」，所以只要在 Convergence 的 `.me3` 里加一条
`[[natives]]` 就能一起加载——和它自带的 `ErdTools.dll` / `erdyes.dll` 走同一条路。

安装器（`ER-Echo-Setup.exe`）就是这么做的：

```text
D:\Games\Convergence3\ConvergenceER\
├─ er-echo\                      ← 新增，删掉即卸载
│  ├─ er_echo.dll
│  ├─ er_echo.ini                ← DLL 优先读同目录这一份
│  └─ profiles\slot1_May.json ...（自动从存档导出，写绝对路径）
└─ me3\convergence.me3           ← 追加一条（原文件已备份 *.bak-er-echo-<时间>）
   [[natives]]
   path = './../er-echo/er_echo.dll'
```

`convergence.me3` 和 `convergence - seamless.me3` 两份都会被改，所以
`Start_Convergence.bat`（含无缝联机版）照常启动就带上了 ER Echo。

## 1.1 从安装器一键启动（原版 / Convergence 分开处理）

`ER-Echo-Setup.exe` 的「安装 / 配置」页在安装按钮下面有「一键启动游戏」，
按识别出的目标类型走不同的启动链：

| 目标 | 实际执行 | 说明 |
| --- | --- | --- |
| 原版（ME2） | `mods\ER-Echo\launch-er-echo.bat`（勾管理员则 `launch-er-echo-admin.bat` + UAC） | 和双击插件 bat 等价 |
| Convergence（me3） | `me3\Windows\me3.exe launch --auto-detect -p .\me3\convergence*.me3` | 有 `SeamlessCoop\ersc.dll` 时优先无缝配置，和 `Start_Convergence.bat` 的选择一致 |

* 按钮下面那行会写清当前会用哪个启动器；没安装时按钮禁用并提示先「一键安装」。
* 不会先 `taskkill` 已经在跑的 `eldenring.exe`（`Start_Convergence.bat` 会这么做）；
  检测到游戏在跑时会先弹确认框，避免误杀正在玩的进程。
* 「以管理员身份启动」主要给原版（Steam 覆盖层 × ME2 钩子的 10 秒闪退），Convergence 一般不用勾。
* 安装成功的弹窗会问「现在启动游戏？」，选「是」就等同于点这个按钮。
* 命令行同款（不开窗口）：

  ```powershell
  ER-Echo-Setup.exe --launch "D:\Games\Convergence3\ConvergenceER"
  ER-Echo-Setup.exe --launch "D:\...\ELDEN RING\Game" --admin
  ER-Echo-Setup.exe --launch --dry-run     # 只打印会执行的命令，不启动
  ```

> **加载器从哪来（合规）**：Convergence 整合包自带 me3（`me3\Windows\me3.exe`），
> 不需要单独下载；独立安装 me3 见 [me3 Releases](https://github.com/garyttierney/me3/releases)，
> 原版 + me3 也支持（安装器加载器选「me3（独立安装）」，会生成 `<Game>\er-echo.me3`）。
> Convergence 本身见 [Nexus 发布页](https://www.nexusmods.com/eldenring/mods/3419)。
> 本仓库 / 安装器**不打包、也不分发** ME2 / me3 / Convergence 的任何文件，只写配置引用。
> 安装器里的「获取 me3」「加载器安装步骤…」按钮就是这些官方页面的入口。

## 2. 特意没做的事：不覆盖 Convergence 的 talk ESD

ME2 安装里那份 `mod\script\talk\m00_00_00_00.talkesdbnd.dcx` 是**赐福菜单的挂载锚点**
（不挂载时日志报 `cannot find grace root list start state`，菜单不出现）。
Convergence 自己也提供同名的 ESD（且改过圆桌厅堂的对话），两个包同时挂载必然互相覆盖：

* 装我们的 → Convergence 的圆桌对话改动丢失；
* 装它的 → 我们的菜单锚点没了。

因此 **Convergence 模式下安装器不装 ESD**：Convergence 本来就会挂载自己那份 ESD，
DLL 的运行时 EzState 注入只需要「ESD 已被挂载」这个条件，菜单文字由 DLL 通过
`CSMsgRepository` 钩子在运行时写入，不依赖 ESD 内容。

> 如果你在 Convergence 下发现赐福里没有「战友」：先看 `er_echo.log` 里
> `ezstate: patched grace group x31 ...` 有没有打印。没有的话把 `er-echo\er_echo.ini`
> 的 `[ui] nested_menu` 改成 `false`，再把 ESD 手动放进 `er-echo\mod\script\talk\`
> 并在 `.me3` 里加 `[[package]] id="er-echo" path='./../er-echo/mod'`（会覆盖 Convergence 的
> `m00_00_00_00`，只在排查时用）。

## 3. 存档：Convergence 用的是 `ER0000.cnv`

`convergence.me3` 里有 `savefile = "ER0000.cnv"`，me3 是把**整个文件名**换掉，所以
Convergence 的角色存在（注意**没有 `.sl2` 后缀**）：

```text
%APPDATA%\EldenRing\<SteamID>\ER0000.cnv         ← Convergence 存档（就是 SL2 格式）
%APPDATA%\EldenRing\<SteamID>\ER0000.cnv.bak     ← 游戏自己留的上一份
%APPDATA%\EldenRing\<SteamID>\ER0000.sl2         ← 原版存档，两者互不影响
```

本机实测（2026-11-22 00:00，刚玩过一轮）：

```text
%APPDATA%\EldenRing\<SteamID>\ER0000.cnv   28,967,888 字节
```

> 同目录里可能还有 `ER0000.mod`、`ER0000.cnv.co2`、甚至一个乱码文件名 —— 那是以前别的
> mod 整合包留下的同名变体，不是本 mod 产生的，别删也别用。

导出工具以前只找 `*.sl2`，所以**找不到 Convergence 的存档**（会退回原版存档，
物品 id 对不上、克隆体穿错装备）。已修（2026-11-22）：

* `tools/export_profile_from_save.py::_save_files()` 与 `tools/er_echo_setup.py::find_saves()`
  改成扫 `ER0000*`（排除 `.bak`/`.co2`/`.tmp`/`.vdf`）；
* 安装器按目标挑存档：Convergence 优先 `*.cnv`，原版优先 `ER0000.sl2`；
* Convergence 目标重装时会删掉之前用**原版存档**导出的旧 profile（id 不同，会穿错）。

### 3.1 参数 id 表（`er_echo_equip.json` / `er_echo_magic.json`）

「这个装备 id 真的存在吗」靠这两张表硬校验；没有表时只能做弱校验（要求四件防具像同一套），
混搭套装的角色会被误判成「缺装备」而跳过（本机 `Cina` 就是这样）。

现在两条路都通了：

1. **随包发布**：`install\tables\convergence\` 已放进仓库，打包时进
   `payload\tables\convergence\`，安装器自动用它（本机实测 `w=4900 p=978 a=212`，
   `magic 736` 条），5 个角色全部通过；
2. **用户自己 dump**：exe 的「安装 / 配置」页有「导出参数表」按钮 —— 游戏运行时点一下，
   工具在 `127.0.0.1:7811` 等 DLL 连上来，发 `dump_equip` / `dump_magic`，
   文件落在游戏根目录（进程 CWD）。命令行同款：

   ```powershell
   ER-Echo-Setup.exe --dump-tables "D:\Games\Convergence3\ConvergenceER"
   ```

> 表跟着**当前 `regulation.bin`** 走：Convergence 存档要在 Convergence 里 dump，
> 原版存档要在原版（ME2）里 dump。两者 id 不一样，别混用。

安装器按目标类型挑存档：

* Convergence：优先最新 `*.cnv` 存档；没有就退回最新原版存档，并在日志里提醒
  「装备 id 可能与 Convergence 不同」。
* 原版：优先 `ER0000.sl2`。

> **重要**：Convergence 改了 `regulation.bin`，物品 id 和原版不完全一样。
> 想让自己在 Convergence 里的角色当克隆体，就该用 **Convergence 存档**导出
> （装完进一次 Convergence 存个档，再回「角色导出」页重导一次）。

## 4. 和原版安装互不影响

两套安装可以同时存在：

```
<Game>\mods\ER-Echo\...           ← ME2 安装（原版）
<Game>\config-er-echo.toml
D:\Games\Convergence3\ConvergenceER\er-echo\...   ← me3 安装（Convergence）
```

* 用 ME2 启动原版：只加载 `mods\ER-Echo`。
* 用 `Start_Convergence.bat` 启动：只加载 `<Conv>\er-echo`。
* 唯一共享的是**游戏本体进程**，所以两者不能同时开（游戏本身也不允许开两份）。

运行期文件（`er_echo.log`、`er_echo_*.json` 参数转储、`er_echo_heartbeat.txt`）落在
**进程 CWD** = 游戏根目录（me3 也是把 CWD 设在游戏目录），所以两种启动方式写的是同一批文件。
排查时以文件名带时间戳的最新一段日志为准。

## 5. 实测记录（2026-11-21 22:56）

### 5.0 菜单文字显示 `EventTextForTalk`（已修）

第一次在 Convergence 里进游戏时，赐福菜单能出现、「战友」那一行也在，但**文字是
`EventTextForTalk`**（ER 对「查不到的文本 ID」用的占位名）。日志给出了原因：

```text
[Warn] ui: LookupEntry prologue mismatch at 0x7ff6041f1370: E9 59 FC 94 FD 44 3B 41 14 ...
```

`E9` 是相对跳转 —— `CSMsgRepository::LookupEntry` 的入口**已经被别的 mod detour 掉了**
（Convergence 的 native 里 `ErdTools.dll` / `ertransmogrify.dll` 都会 hook 消息系统）。
我们的文字钩子依赖「入口前 15 字节还是原版那两条 `cmp/jae`」，prologue 一变就装不上，
69100000+ 这些 ID 于是查不到 → 显示占位名。

修法（`mod/src/ui.rs`，三次迭代后的最终方案）：入口被占用时改成**借跳板接替入口**——

1. 读入口的 `E9 rel32`，得到别人的 handler（实测指向一个 `FF 25 [rip+0]` IAT 桩 →
   `0x7FFCA9FE60`，即别的 mod 的 DLL）；
2. 在**游戏镜像附近**（±1.5GB 内逐 64KB 试 `VirtualAlloc`）申请一页，
   写上 `FF 25 00 00 00 00 <u64 我们的 detour>`——因为我们的 DLL 被加载在
   `0x7FFC…`、游戏在 `0x7FF6…`，**相距超过 ±2GB，rel32 根本够不着**（这就是第一次
   「170 个调用点一个也没改写成功」的原因）；
3. 把入口那 5 字节 `E9` 改指到这块跳板；detour 没命中我们的 ID 时再 `call` 别人的
   handler——它的 hook 效果原样保留（`mode=entry-chain`）；
4. 兜底：若入口不是 `E9`，就扫镜像里所有 `call rel32 -> LookupEntry`（静态数过 170 处），
   逐条改成 `call 跳板`（`mode=call-site`）；
5. 重入保护：`DEPTH` 计数，链式调用若绕回自己就返回空，避免死循环。

日志会变成：

```text
ui: stub allocated at 0x… (jmp -> 0x…)
ui: message hook installed by taking over existing detour
    (entry 0x… -> stub 0x…, chained to 0x…)
msg_hook=true mode=entry-chain ...
```

排查工具：`tools/probe_msg_hook.py <pid> <module_base>`（只读，不写游戏内存）会打印入口
字节、跳转目标、以及镜像里 `call` 到原入口/跳转目标各多少处 —— 判断该挂哪儿靠它。

原版 / ME2 里入口干净时仍走原来的入口 inline hook（`mode=entry`）。

### 5.1 启动与加载

用安装器装到真实的 `D:\Games\Convergence3\ConvergenceER` 后，用 me3 直接启动：

```powershell
cd D:\Games\Convergence3\ConvergenceER
.\me3\Windows\me3.exe launch --auto-detect -p .\me3\convergence.me3
```

观察到（`Game\er_echo.log` 当前会话段）：

```text
er_echo thread spawned; waiting for CSTaskImp (target exe 2.7.2.0)
i18n: language=zh-CN (source=manifest, ...)
er_echo attached (target exe 2.7.2.0)
ezstate: EnterState hook installed at 0x7ff63bfdbe00 (rva 0x208be00, ...)
ezstate: enabled=true hooked=true ...
auto er_echo_npc.json: 2036415 bytes     ← 比原版的 1832094 大：确认吃的是 Convergence 的 regulation
auto er_echo_buddies.json: 172161 bytes  ← 原版是 68153
```

me3 侧日志确认 native 列表里有我们的 DLL：

```text
natives: [ ... , Native { path: ModFile("...\er-echo\er_echo.dll"), optional: false, enabled: true } ]
```

`me3 profile show .\me3\convergence.me3` 也能列出 `er_echo.dll`，说明追加的 TOML 合法。

**还差的一步（需要真人进游戏）**：Convergence 的存档是全新的 `ER0000.cnv`，
要新建角色走到赐福才能看到菜单。验证清单：

1. `er_echo.log` 出现 `config profile[0/1]: 'May' lv6`（说明读的是 `er-echo\er_echo.ini`
   里的绝对路径 profile）；
2. 坐赐福后出现 `ezstate: patched grace group x31 ... events 2 -> 3`；
3. 菜单第一项是「战友（n/m）」，进去能选人数 / 1-3 号位 / 队友 AI（三级菜单）/ 立即重召 / 友伤 / 返回。

## 6. 卸载

安装器「安装 / 配置」页选同一路径 → 卸载：

* 恢复 `me3\convergence*.me3` 的最近一次备份；
* 删除 `<Conv>\er-echo\`。

Convergence 自己的文件（`mod\`、`me3\Windows\`、`SeamlessCoop\`）一个都不动。
