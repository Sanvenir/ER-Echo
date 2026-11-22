# Handoff：赐福「战友」二级菜单

> **状态：✅ 已完成（2026-11-16 23:0x）。**
> 实际走**路线 1（Rust 运行时注入）**，没有用 C++ sidecar，也没有再改离线 ESD。
> 实现与验收：[submenu-runtime-injection.md](submenu-runtime-injection.md)；
> 代码 `mod/src/ezstate.rs`；开关 `er_echo.ini [ui] nested_menu`；
> 根列表 fallback 用 `tools/switch_menu_mode.ps1 -Mode root` 切回。
> 下面保留原始交接内容（失败记录 / 参考实现 / 字节码线索）。

> 交接时间：2026-11-16 22:xx（Asia/Hong_Kong）
> 目标：把目前**根列表 5 项**的战友 UI，改成用户更想要的**二级菜单**
> （赐福 → 战友 → 人数/名单/重召/返回）。
> 当前根列表版本已实测可用，是必须保留的 fallback。

---

## 1. 一句话背景

Rust DLL `er_echo.dll` 通过 ModEngine2 加载；赐福 UI 是**离线改 ESD 文件**
（`mod/script/talk/m00_00_00_00.talkesdbnd.dcx` 里的 `t000001000`），
文字由 DLL 的 `CSMsgRepository::LookupEntry` 钩子提供。

**二级菜单用离线 ESD 试了三版都失败**（空菜单/立刻返回一级）；
参考 mod 能做二级菜单，是因为它们在**运行时往 live talk machine 注入 ezstate 状态**（C++）。
所以这个 handoff 的核心任务是：**把运行时的 `er::ezstate` 注入移植到 Rust**，
或者加一个 C++ sidecar DLL。

---

## 2. 当前已确认可用的状态

- 游戏：Elden Ring 1.17.2 / exe 2.7.2.0，离线，ME2 2.1.0。
- DLL：`er_echo.dll`（最新构建，含 F12 give、消息钩子、roster）。
- ESD：`mod/script/talk/m00_00_00_00.talkesdbnd.dcx` = **根列表 5 项版本**（30,202 B）。
- `config_eldenring.toml`：
  ```toml
  [extension.mod_loader]
  enabled = true
  loose_params = false
  mods = [ { enabled = true, name = "er-echo", path = "mod" } ]
  ```
  `mods = []` 时 ME2 不会加载 `mod/`，赐福里什么都看不到。
- 当前根列表（赐福最上面 5 项）：
  ```text
  队伍人数：2（点击切换）    <- AddTalkListData(61, 69100001)
  1号位：May（点击切换）     <- 62, 69100002
  2号位：May（点击切换）     <- 63, 69100003
  3号位：May（点击切换）     <- 64, 69100004
  立即重新召唤               <- 65, 69100005
  ```
  ESD 结果分支只 `SetEventFlag(...)`；DLL 读标志、改 `er_echo_roster.json`、刷新文字。
- 标志（`CSEventFlagMan` 真实可用，group 6，holder_count=14667）：
  | 标志 | 含义 |
  |---|---|
  | 6724 / 6725 / 6726 | 1/2/3 号位循环档案 |
  | 6727 | 立即重召 |
  | 6728 | 人数循环 0→1→2→3→0 |
  | 6720..6723 | 人数直接设为 0/1/2/3（旧版/预留） |
- 不能用的标志段：69031xxx（group 69031 不在 holder 表里，`get/set` 静默失败）。
- 文字 ID：
  | ID | 内容 |
  |---|---|
  | 69100000 | `战友（2/2）`（根列表版本未使用，二级菜单根项可复用） |
  | 69100001 | `队伍人数：N` |
  | 69100002..04 | `N号位：名字（点击切换）` |
  | 69100005 | `立即重新召唤` |
  | 69100006 | `返回` |
  | 69100010..13 | `不召唤 / 1 人 / 2 人 / 3 人` |
  | 69100100+ | profile 名字 + Lv |
- 实测日志（根列表版本）：
  ```text
  roster: count -> 3 / 0 / 1 / 2
  roster: slot 1 -> profile 1/0/1
  roster: slot 3 -> profile 1
  menu: apply roster -> dismiss + re-summon
  msg_test: id=69100001 -> "队伍人数：2（点击切换）"
  ```

---

## 3. 为什么离线 ESD 二级菜单失败

### 3.1 尝试 1：`x900` + `CloseShopMessage` + 所有分支 `return 0`

反编译 `x900` 看到：

```text
"""Unused"""
"""State 900"""
CloseShopMessage()
ClearTalkListData()
AddTalkListData(...)
ShowShopMessage(...)
```

即 ESDLANG 把菜单事件编进 **`Unused` 状态**，入口状态只剩 `if/else` + return。
游戏效果：点「战友」→ **空菜单、HUD 消失**。

### 3.2 尝试 2：vanilla `x78` 形状

`x900`：

```text
CloseShopMessage()
while True:
    ClearTalkListData()
    AddTalkListData(...)
    ShowShopMessage(...)
    assert not (CheckSpecificPersonMenuIsOpen(1, 0) and ...)
    if result == 1: assert x901()
    elif result == 2: SetEventFlag(...)
    ...
    else: return 0
```

游戏效果：点「战友」→ **立刻回到一级菜单**（没有子列表）。

### 3.3 尝试 3：去掉 `CloseShopMessage`

还是立刻返回一级。

### 3.4 结论

离线 ESD 重编译无法可靠产生「从 talk list 结果再开一个 talk list」的二级菜单。
vanilla 的 `x78` 能这样做，但 ESDLANG 重新生成的状态/CFG 不等价；
不要在这条路上继续堆时间。

---

## 4. 参考实现（关键）

### 4.1 erdGameTools（原生赐福菜单，1.16.1）

- https://github.com/ankerlcg1996/-Elden_Ring_game_tools
- 关键文件：
  - `src/grace_test_talkscript.cpp`（114 KB）
  - `src/utils/talkscript_utils.hpp`
  - `src/grace_test_messages.cpp`（消息钩子）
  - `Source/Features/EzStateTalkCommand.cpp`（运行时注入/命令）
- 思路：不修改 ESD 文件；在 `EzState::EnterState` 钩子里，找到赐福 state group
  （特征：entry_events 里有 `AddTalkListData(..., 15000395, ...)`），
  把自定义 `AddTalkListData` 事件和到自定义菜单 state 的 transition **追加到内存数组**。
- 文本：`CSMsgRepository::LookupEntry` 钩子（我们已有同款 Rust 实现）。
- 本机曾解压到：
  `%TEMP%\erdGameTools\-Elden_Ring_game_tools-main`
  （临时目录可能被清，重新下载 zip 即可）。

### 4.2 elden-ring-transmog

- https://github.com/ThomasJClark/elden-ring-transmog
- `src/ertransmogrify_talkscript.cpp`、`src/utils/talkscript_utils.hpp`
- 有最小可读的 `talkscript_menu_option` / `talkscript_menu_state` 构造器，
  以及 `EzState::EnterState` detour 的 AOB：
  ```text
  80 7e 18 00 74 15 4c 8d 44 24 40 48 8b d6 48 8b 4e 20 e8 ?? ?? ?? ??
  offset = 18, relative_offsets = {{1,5}}
  ```
  （1.17.2 要重新验证 AOB；1.16.1 是这条。）
- `ertransmogrify_messages.cpp` 有 `LookupEntry` 钩子和 `(this, unknown=language, bnd, msg)` 参数顺序。

### 4.3 elden-x

- https://github.com/ThomasJClark/elden-x
- `include/elden-x/ezstate/ezstate.hpp`（核心内存布局）：
  ```cpp
  struct state_group { int id; span<state> states; state* initial_state; };
  struct state {
      int id;
      span<transition*> transitions;
      span<event> entry_events;
      span<event> exit_events;
      span<event> while_events;
  };
  struct transition {
      state* target_state;
      span<event> pass_events;
      span<transition*> sub_transitions;
      span<unsigned char> evaluator;
  };
  struct command { int bank; int id; };
  struct event { command command; span<unsigned char> args; };
  ```
  Rust 里用 `(ptr, len)` 表示 `span`，`repr(C)`；注意 `transition` 的 evaluator 是
  **原始字节码表达式**（`0x82` + i32 LE + `0xA1` 之类，见 `talkscript_utils.hpp`）。
- `talk_commands.hpp` 有命令 bank/id；`AddTalkListData`、`ShowShopMessage`、
  `ClearTalkListData`、`GetTalkListEntryResult` 都能找到。
- 本机临时副本：`%TEMP%\errefs\elden-x\elden-x-main`、`%TEMP%\errefs\elden-ring-transmog\...`。

### 4.4 ESDLANG（离线工具，不要再用于二级菜单）

- https://github.com/thefifthmatt/ESDLang
- 本机 `%TEMP%\errefs\esdtool\esdtool-v0.5.1\esdtool.exe`
- 离线编译/反编译仍可用；但二级菜单不要走这条路。

---

## 5. 推荐实现路线（按优先级）

### 路线 1：Rust 运行时注入（主推）

复用现有 Rust 基础设施：

- `mod/src/ui.rs` 已有 `LookupEntry` 入口 inline hook：
  - 绝对跳转 15 字节 + trampoline；
  - 目标 RVA 1.17.2 = `0x2671370`；
  - 参数 `(this, language, bnd, msg)`；
  - `msg_test` 可验证。
- `mod/src/roster.rs` / `lib.rs` 已有标志轮询、roster、文字刷新。
- 需要新增：
  1. `ezstate.rs`：`repr(C)` 定义 `state_group/state/transition/event/command`，
     `span` 用 `(ptr,len)`；所有注入对象用 `Box::leak`/`static` 保活。
  2. `EnterState` 钩子：
     - AOB 同 transmog；`EzState::EnterState` 签名需要确认
       （transmog 的 detour 是 `ezstate_enter_state(state, machine, unk)`）。
     - 目标函数 prologue 未知，**不要**盲抄 14 字节；可以用：
       - hook **call site**（`e8 rel32`，5 字节）到 ±2GB relay（类似我们给
         `LookupEntry` 做的 relay 思路，但 call site 只改 5 字节）；
       - 或先反汇编 prologue 再用 12–15 字节绝对跳转 + trampoline。
     - 在 detour 里：遍历 `state_group->states`，找 entry_events 里
       `AddTalkListData(..., 15000395, ...)` 的 group → 这就是赐福。
     - 把自定义 `AddTalkListData(60, 69100000, -1)` 事件追加到该 group 的
       首个菜单 state 的 `entry_events`（容量 100，transmog 用固定数组）。
     - 把到 `x900_menu` 的 transition 追加到该 state 的 transitions：
       evaluator = `GetTalkListEntryResult() == 60`。
  3. 构造 `x900_menu`：
     - entry_events：`ClearTalkListData`、`AddTalkListData(1, 69100001, -1)`…、
       `AddTalkListData(99, 69100006, -1)`、`ShowShopMessage`；
     - transitions：每个 option 的 `GetTalkListEntryResult() == N` →
       一个 callback state（SetEventFlag 6724..6727 / 6728）；
     - 返回 transition 到父 state（`GetTalkListEntryResult() == 99`）。
     - 具体命令 bank/id 从 `talk_commands.hpp` 抄，表达式字节从
       `talkscript_utils.hpp` 抄。
  4. 不要重复实现文本钩子：`ui.rs` 的 `69100000+` 已经能返回所有文字。
  5. 加 feature flag / ini `[ui] nested_menu=true`，失败可回退根列表 ESD。

**难点**：ESD 表达式字节码、`EnterState` 签名/prologue、注入对象生命周期。
参考 transmog 的 `talkscript_utils.hpp` 里 `make_int_expression` /
`make_talk_list_result_expression` / `talk_menu_closed_expression`，逐字节照抄。

### 路线 2：C++ sidecar DLL（更稳，但工具链）

- 用 elden-x + erdGameTools 的 `grace_test_talkscript.cpp` 思路，
  编一个 `er_echo_ui.dll`，ME2 `external_dlls` 一起加载；
- 它只负责 ESD 注入/二级菜单；Rust DLL 继续管 spawn/roster/F12；
- 两者通过 **事件标志 6720..6728** 或本地 TCP 通信。
- 本机 Rust 是 `stable-x86_64-pc-windows-gnu`，没有 VS/C++ 编译器
  （`where cl` 为空）；如果要走这条，需要先装 VS Build Tools + CMake，
  或把 C++ 工程交给有 MSVC 的环境编。
- 优点：直接复用参考代码，风险最低；缺点：多一个 DLL/构建链。

### 路线 3：不做二级菜单

保留根列表 5 项（当前已验证）。如果时间紧，这是可交付状态。

---

## 6. 现有文件与构建/部署

### 6.1 ESD 根列表（当前部署）

- 反编译源：`er-echo/ui/esd/py/t000001000.py`（原始）
- 补丁脚本：`er-echo/tools/patch_grace_esd.py`（当前根列表 61-65）
- 编辑结果：`er-echo/ui/esd/edit/t000001000.py`
- 模板 BND：`er-echo/ui/base/m00_00_00_00.talkesdbnd`
- 重打包：`er-echo/ui/out_bnd/m00_00_00_00.talkesdbnd.dcx`
- 部署：`mod/script/talk/m00_00_00_00.talkesdbnd.dcx`

重建命令（在游戏根目录）：

```powershell
python er-echo\tools\patch_grace_esd.py
& "$env:TEMP\errefs\esdtool\esdtool-v0.5.1\esdtool.exe" -er -noannotate `
  -esddir "er-echo\ui\base" -f t000001000 `
  -i "er-echo\ui\esd\edit\t000001000.py" `
  -writebnd "er-echo\ui\out_bnd"
python er-echo\tools\pack_talk_esd.py
Copy-Item er-echo\ui\out_bnd\m00_00_00_00.talkesdbnd.dcx `
          mod\script\talk\m00_00_00_00.talkesdbnd.dcx -Force
```

`pack_talk_esd.py` 需要 `er-echo/ui/talk/m00_00_00_00.raw.dcx`（原始 KRAK 头）
和游戏根目录 `oo2core_6_win64.dll`。

### 6.2 Rust DLL

- `er-echo/mod/src/lib.rs`：
  - `poll_roster_flags()`（6724..6728 → roster）
  - `give_selected()`（F12，改内存 profile，`apply_to_clones(false)`）
  - `msg_test` / `flag_test` / `sit_grace` 命令
- `er-echo/mod/src/roster.rs`：roster JSON、flags、slot_for_clone。
- `er-echo/mod/src/ui.rs`：
  - `LookupEntry` hook（RVA 0x2671370）
  - `refresh_texts()`：69100000+ 文本
  - `msg_test` 直接调 hook
- 构建：
  ```powershell
  cd er-echo\mod
  $env:PATH="$env:USERPROFILE\er-tools\binutils\mingw64\bin;$env:USERPROFILE\.cargo\bin;$env:PATH"
  $env:RUSTFLAGS="-C target-feature=+crt-static"
  cargo build --release
  ```
  产物 `target\release\er_echo.dll` → 复制到游戏根目录 `er_echo.dll`（游戏占用时先停）。
- 警告在 stderr，pwsh 会报 `[exit code: 1]`，看 “Finished” 即成功。

### 6.3 启动/坐火自动化

- `er-echo/tools/auto_start.ps1`：
  - 启动、找**真正的游戏窗口**（ME2 控制台会占 `MainWindowHandle`；
    脚本用 `FindWindowW(null,"ELDEN RING™")`，找不到回退主窗口）；
  - 点标题/断线/离线对话框 + 继续游戏；检测 `er_echo_status.json` clones。
- `er-echo/tools/sit_grace.ps1`：`keybd_event` 发键盘 E，实测能开赐福菜单。
- 注意：注入的 E 只能**打开**赐福菜单，菜单里的确认键注入无效；
  菜单选项需要用户手柄 A 或真实键盘操作。自动化测试可考虑运行时直接触发
  `EnterState` / 注入菜单，而不是模拟按键。

---

## 7. 验收标准

1. 赐福菜单最上面出现「战友（2/2）」；
2. 选「战友」进入二级菜单，**不空白、HUD 正常**；
3. 二级菜单 6 项文字正确（现有 69100000+ 文本 ID）：
   人数 / 1/2/3 号位 / 立即重召 / 返回；
4. 选人数进入 0/1/2/3 子菜单或循环，返回后标签刷新；
5. 选号位循环 profile，`er_echo_roster.json` 变化，标签刷新；
6. 选返回回到赐福根菜单；
7. 原有根列表 fallback 可通过 ini/feature flag 切回；
8. 不改 `EquipMagicData.equip_game_data` 回指、不碰死亡/加载中的 summon manager；
9. 连续开关菜单 20 次不崩、HUD 不消失。

---

## 8. 已知坑（务必看）

- **ESDLANG**：`if GetTalkListEntryResult()` 分支全 `return` → 菜单事件进
  `Unused`；`CloseShopMessage` 位置/循环会改变行为，不要再用离线 ESD 试二级菜单。
- **ME2 `mods=[]`**：不会加载 `mod/script/talk`；必须写
  `mods = [ { enabled = true, name = "er-echo", path = "mod" } ]`。
- **事件标志范围**：只能用 group 存在的 ID（6720 段实测有效）；
  69031xxx 无效。
- **文本钩子参数顺序**：`(this, language, bnd, msg)`；`msg_test` 传
  `(repo, 0, 33, id)`；原版 `15000395 -> "整理木箱"` 验证 trampoline。
- **游戏窗口**：`eldenring.exe` 同时有 ConsoleWindowClass（ME2 debug console）
  和 `ELDEN RING™` 游戏窗口；截图/点击/前台必须找后者。
- **注入 E 不能确认菜单**：keybd_event 能开赐福，菜单项需要手柄 A/真实键盘；
  自动化测试不要依赖注入 E 选单。
- **不要动** `summon_buddy_manager`（死亡/加载中会空指针）；不要写
  `EquipMagicData.equip_game_data`。
- **ESD 文件与游戏版本绑定**；升级后按 `ui/README.md` 重新抽/反编译/编译。
- **存档标志**：菜单标志会写存档；DLL 读完立刻清零，启动时 `clear_flags()`。

---

## 9. 交接后的第一步建议

1. 先读 `er-echo/mod/src/ui.rs` 的 `install_msg_hook`（已有 inline hook 模板）
   和 `talkscript_utils.hpp` / `ertransmogrify_talkscript.cpp`。
2. 用 `msg_test`/`flag_test` 确认现有链路；
3. 在 **不改变根列表 fallback** 的前提下，新增 `[ui] nested_menu=false`；
4. 实现 `EnterState` 钩子 + 最小注入：只加一个 `AddTalkListData(60, ...)` +
   一个空菜单 state，先看能否显示空菜单（不崩溃），再填 6 项；
5. 每步写日志（注入 state 地址/state_group/option 数），用 `status`/截图验证；
6. 失败可随时把 `nested_menu=false`，保持根列表可交付。

---

## 10. 相关文档

- `er-echo/docs/implementation-log.md` §18（UI 全过程、失败记录、消息钩子）
- `er-echo/docs/usage.md` §3.2（当前根列表用法）/ §3.4（自动启动/坐火）
- `er-echo/ui/README.md`（ESD 抽取/编译/打包）
- `er-echo/docs/design.md` §13（M6）
