# 实验记录：纯净安装 + 可插拔布局（2026-11-21 21:18–21:27）

## 结论

**通过。** 从「无 mod 的干净目录」开始，只解压一个插件包（`mods\ER-Echo\` + `config-er-echo.toml`），
DLL 被 ME2 从**子目录**加载、成功 attached、EzState 钩子装上、自动召唤出 1 个克隆体并跟随
（2.7 m），持续运行约 4 分钟无崩溃。

同时确认：**ME2 的 `external_dlls` 支持子目录相对路径**（`mods/ER-Echo/er_echo.dll`），
插件布局成立。

---

## 1. 基线（重置后、无 mod）

`reset_to_vanilla.ps1` 之后，根目录只剩 `config_eldenring.toml`（干净版）+ ME2 原版 bat。

| 启动方式 | 结果 |
|---|---|
| 直接 `eldenring.exe`（**不提权**） | 标题界面出现，**+15 s 退出**；WER：`eldenring.exe` / `0xc0000005` / 偏移 `0x1EBCEF9` |
| 直接 `eldenring.exe`（**提权**） | 稳定存活 **70 s**（窗口 `ELDEN RING™`），手动结束 |

崩溃 dump（`eldenring.exe.9364.dmp`）里：

* 有 `DLUserInputManagerImpl` 字符串 → 就是 handoff 里那个输入管理器 panic；
* 有 `gameoverlayrenderer64.dll`（Steam 覆盖层），**没有** `modengine2.dll` / `er_echo.dll`。

即：这台机器现在**不带任何 mod、不提权**也会被 Steam 覆盖层触发同一个 panic；
提权后正常。与 `handoff-launch.md` 的坑 3 一致，只是这次连 ME2 都不需要。

## 2. 安装

```
install_plugin.ps1 -Package dist\plugin\ER-Echo-Plugin-0.1.0.zip
  [ok] 基线干净，游戏版本 2.7.2.0
  [ok] 文件已就位（mods\ER-Echo\ + config-er-echo.toml）
  doctor: 通过（警告 1 项：IPC token 默认值）
```

新增到游戏根目录的只有：`mods\ER-Echo\` 和 `config-er-echo.toml`。
`config_eldenring.toml`、`launchmod_eldenring.bat`、`modengine2\` 均未改动。

## 3. 启动（admin 版，因为本机需要提权）

用 `mods\ER-Echo\launch-er-echo-admin.bat` 启动（自提权 → 覆盖层注不进去）。

ME2 日志：

```
[2026-11-21 21:22:44] [modengine] [info] Loaded external DLL
  D:\...\ELDEN RING\Game\mods/ER-Echo/er_echo.dll
```

`er_echo.log`：

```
[Info +0.0s] er_echo thread spawned; waiting for CSTaskImp (target exe 2.7.2.0)
[Info +0.0s] i18n: language=zh-CN (er_echo.ini language="auto", ...)
[Info +0.1s] er_echo attached (target exe 2.7.2.0)
[Info +0.1s] ezstate: EnterState hook installed at 0x7ff62651be00 (rva 0x208be00, ...)
[Info +0.1s] ezstate: ezstate enabled=true hooked=true ...
```

运行期状态（持续到 +253 s）：

```
status: clones=1 dists=[2.7] hp=[1900/1900] roster(count=1 slots=[0,0,0])
        flags(anywhere=true events=true apply=true stats=true glow=true fp=true)
        rows(b=0 t=100000010 n=0)
```

说明 `summon_events` 在进图后自动召了一队（示例档案），跟随距离稳定 2.7 m。

## 4. 结束方式与异常

游戏在 +253 s 后退出，**WER 没有新增 1000 事件、没有新 dump**，`er_echo.log` 也没有 panic/错误行。
当时外层的测试脚本正好被移到后台/取消（`job_kill`），子进程树被一起终止是最可能的原因；
不是 mod 崩溃。若再复现，优先看 WER + dump 是否出现。

## 5. 修正（21:36–21:39）：ESD 必须挂载，档案要换成真实导出

第一次纯净安装时**没有**带 `mod/script/talk` 的 ESD，结果：

* 赐福菜单不出现；日志 `ezstate: cannot find grace root list start state`（+45 s）；
* 克隆体用的是示例档案（`Example Tarnished`），外观自然不是任何真实角色。

**修正后**（插件里加回 ESD + `mod_loader` 条目 + 两份真实档案）：

* `config-er-echo.toml` 增加：
  ```toml
  [extension.mod_loader]
  enabled = true
  loose_params = false
  mods = [ { enabled = true, name = "er-echo", path = "mods/ER-Echo/mod" } ]
  ```
* `er_echo.ini`：`profiles=mods/ER-Echo/profiles/slot0_Sv.json,mods/ER-Echo/profiles/slot1_May.json`
* 第二次启动日志：
  ```
  config profile[0/2]: 'Sv' lv15
  config profile[1/2]: 'May' lv6
  ezstate: patched grace group x31 (...): item at state ..., events 2 -> 3, transitions 17 -> 18
  ```
  截图确认赐福菜单第一项是 **「战友（1/2）」**；克隆体血量 680（真实档案数值），
  `auto_apply: 1 clone(s) -> equip=1 face=1`。

结论修正：**默认（nested）模式也依赖 `mod/script/talk` 的 ESD**，之前「运行时注入不需要 ESD」
的判断是错的。插件包 / Nexus 包都要带这份 ESD 并在配置里挂载。

## 6. 待确认

* 本机**不提权**启动插件（`launch-er-echo.bat`）是否也会 10 秒闪退——按基线结果推断会；
  所以本机日常请用 admin 版（或关掉 Steam 覆盖层）。
* 菜单文案/截图只验证了日志层面的 EzState 注入，没在屏幕上确认「Comrades」那一行；
  下次进游戏坐赐福时看一眼即可。
* 示例档案（`profile.example.json`）装备全 0，克隆体外观不代表真实角色；换自己的 profile 再验一次外观。

## 6. 复现命令

```powershell
# 重置（先 -DryRun 看一眼）
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\reset_to_vanilla.ps1 -DryRun
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\reset_to_vanilla.ps1 `
    -BackupDir "$PWD\er-echo\backups"

# 基线：直接跑 eldenring.exe（本机需提权），确认稳定

# 安装 + 自检
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\install_plugin.ps1 `
    -Package er-echo\dist\plugin\ER-Echo-Plugin-0.1.0.zip

# 启动（本机需 admin）
mods\ER-Echo\launch-er-echo-admin.bat
```
