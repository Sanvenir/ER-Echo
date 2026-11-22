# 运行时 EzState 注入：赐福「战友」二级 / 三级菜单

> 实现：2026-11-16（ELDEN RING 1.17.2 / exe 2.7.2.0）；三级「队友 AI」2026-11-22
> 代码：`er-echo/mod/src/ezstate.rs`、`roster.rs`、`ui.rs`
> 交接背景与失败路线：[handoff-submenu.md](handoff-submenu.md)

## 1. 结果

赐福根菜单第一项（引擎的时间行之后）出现 **「战友（n/m）」**，点进去是 8 项二级菜单；
其中「队友 AI」再进 4 项三级菜单：

```text
战友（3/2）
  队伍人数：3（点击切换）      6728 循环 0→1→2→3→0
  1号位：May（点击切换）       6724 循环档案
  2号位：Sv（点击切换）        6725
  3号位：May（点击切换）       6726
  队友 AI（点击进入）          → 三级菜单（见下）
  立即重新召唤                 6727 解散 + 按新名单重召
  友伤：关（点击开启）         6729 开关友伤（AtkParam_Pc friendlyTarget）
  返回                         —   回赐福根菜单

队友 AI（三级菜单）
  1号位 May：均衡（点击切换）  6730 该档案 ai 预设 → 下一个
  2号位 Sv：法术（点击切换）   6731
  3号位 May：默认（点击切换）  6732
  返回                         —   回二级菜单
```

不空白、HUD 正常、连续切换不崩。**没有改 ESD 文件**：部署的是原版
`t000001000`（`ui/out_vanilla/`），菜单完全由 DLL 在运行时注入。

## 2. 钩子

目标：`EzState::EnterState(state, machine, unk)`，1.17.2 RVA `0x208be00`。

不硬编码 RVA：扫调用点 AOB（和 elden-ring-transmog 同一形状，1.16.1/1.17.2 通用）：

```text
80 7e 18 00            cmp byte ptr [rsi+0x18], 0
74 15                  jz +0x15
4c 8d 44 24 40         lea r8, [rsp+0x40]
48 8b d6               mov rdx, rsi
48 8b 4e 20            mov rcx, [rsi+0x20]
e8 ?? ?? ?? ??         call EzState::EnterState
```

从 `call rel32` 算出函数入口，校验入口 15 字节：

```text
48 8b c4               mov rax, rsp
57                     push rdi
41 56                  push r14
41 57                  push r15
48 81 ec 20 04 00 00   sub rsp, 0x420
```

这段没有 RIP 相对寻址，可以整段搬进 trampoline；入口写 14 字节绝对跳转
（`FF 25 00 00 00 00` + u64）+ 1 字节 NOP。trampoline 执行完原 prologue 后跳到
`target+15`，原函数 `ret` 直接回到调用者。

detour 里只做两件事：`nested_menu` 开关为真时处理注入，然后调用 trampoline。
用 `catch_unwind` 包住注入逻辑，panic 不会穿过 FFI 带走游戏。

## 3. 内存结构（`#[repr(C)]`，与 elden-x `ezstate.hpp` 一致）

```text
machine      : vtable, unk[0x20], state_group*   (1.17.2 实测 state_group 在 +0x28)
state_group  : i32 id, span<state> states, state* initial_state
state        : i32 id, span<transition*> transitions,
               span<event> entry_events, exit_events, while_events
transition   : state* target, span<event> pass_events,
               span<transition*> sub_transitions, span<u8> evaluator
event        : {i32 bank, i32 id}, span<span<u8>> args
```

`span<T>` = `{ T* ptr; size_t len; }`。注入对象全部 `Box::leak`/`Vec::leak`，
活到进程结束。

**定位 state group 不写死偏移**：从 machine 起按 8 字节步长扫 `+0x08..+0x200`，
要求候选指针可读（`VirtualQuery`）、states 数组长度 1..8192、initial_state 落在
数组内，再用「某个 state 的 entry_events 里有 `AddTalkListData(_, 15000395, _)`
（原版赐福「整理木箱」）」确认是赐福 group。确认后才缓存偏移，避免把机器内部
其它像 span 的指针误认成 group。实测 1.17.2 缓存到 `+0x28`。

## 4. 注入内容

### 4.1 根菜单项

赐福根菜单不是由单个 state 一次性建好：state 1 只 `ClearTalkListData`，
state 2 加头几项，state 17 再加 4..9 项，最后 state 3 `ShowShopMessage`。
所以从 `initial_state` 做 BFS，找**第一个加菜单项**的 state（x31 的 state 2），
把 `AddTalkListData(60, 69100000, -1)` 插到它 `entry_events` 开头。

> 插在「整理木箱」那个 state（state 17）会排在「圣杯瓶」后面（实测）；
> 插在 state 2 开头才是引擎时间行之后的第一项。时间行「下午/中午」是引擎
> 自己加的，不是 ESD 项。

### 4.2 结果分支

在含「`GetTalkListEntryResult() == 6 → OpenRepository`」转移的 state（x31 的 state 8）
的 transitions 里插入：

```text
GetTalkListEntryResult() == 60  →  二级菜单 state
```

顺序插在该转移之前，保证先于 `else` 转移被求值。

### 4.3 二级菜单 state

`entry_events`：

```text
CloseShopMessage()
ClearTalkListData()
AddTalkListData(1, 69100001, -1)   # 队伍人数
AddTalkListData(2, 69100002, -1)   # 1 号位
AddTalkListData(3, 69100003, -1)   # 2 号位
AddTalkListData(4, 69100004, -1)   # 3 号位
AddTalkListData(5, 69100008, -1)   # 队友 AI（进三级菜单）
AddTalkListData(6, 69100005, -1)   # 立即重新召唤
AddTalkListData(7, 69100007, -1)   # 友伤
AddTalkListData(99, 69100006, -1)  # 返回
ShowShopMessage(TalkOptionsType.Regular)
```

`transitions` 只有一条：`talk_menu_closed_expression → branch state`。

`branch state` 的 transitions 按顺序：

| 结果 | 目标 |
|---|---|
| `GetTalkListEntryResult() == 1` | callback: SetEventFlag(6728) → 回二级菜单 |
| `== 2/3/4` | callback: SetEventFlag(6724/6725/6726) → 回二级菜单 |
| `== 5` | 三级「队友 AI」菜单 state |
| `== 6` | callback: SetEventFlag(6727) → 回二级菜单 |
| `== 7` | callback: SetEventFlag(6729) → 回二级菜单 |
| `== 99`（true） | 根菜单循环入口 state |

> 「返回」**不能**跳到 group 的 `initial_state`：直接跳初始 state 不会重新
> `ShowShopMessage`，二级菜单关掉后根菜单不出现（实测）。必须跳 BFS 父链上最近的
> 「清空列表」state（x31 的 state 1 = 循环标签 L0），它后面会重新 AddTalkListData →
> ShowShopMessage。

### 4.4 三级「队友 AI」菜单

`entry_events`：

```text
CloseShopMessage()
ClearTalkListData()
AddTalkListData(1, 69100020, -1)   # 1 号位 <名字>：<预设>
AddTalkListData(2, 69100021, -1)   # 2 号位
AddTalkListData(3, 69100022, -1)   # 3 号位
AddTalkListData(99, 69100006, -1)  # 返回（复用「返回」的文字 ID）
ShowShopMessage(TalkOptionsType.Regular)
```

`transitions`：`talk_menu_closed_expression → AI branch state`。AI branch：

| 结果 | 目标 |
|---|---|
| `== 1/2/3` | callback: SetEventFlag(6730/6731/6732) → 回三级菜单（可连续调几个人） |
| `== 99`（true） | 二级菜单 state（重跑它的 entry_events，重新长出路菜单） |

> 选完一个号位回三级菜单而不是二级：玩家通常要连着调 2–3 个人；
> 文字由 `ui::refresh_texts()` 在 0.25 秒等待期内重建成新预设名。

### 4.5 刷新延时（重要）

ESD 置标志和 DLL 轮询不在同一帧：如果 callback 立刻回二级菜单，菜单会用**旧文本**
建列表（实测「人数 2→3」后菜单仍显示 2）。

早先试过事件标志回执（DLL 置 6729、ESD `GetEventFlag(6729) == 1` 再返回），
运行时 **ESD 侧看不到 DLL 置的标志**：每次都要等 2.5 秒超时才回菜单。原因没深挖
（可能是 `GetEventFlag` 表达式编码/求值时机），改成简单可靠的固定延时：

* callback state 的转移条件 = `GetCurrentStateElapsedTime() > 0.25`；
* 0.25 秒 ≈ 15 帧，`poll_roster_flags()` 早已读完标志、改完 `er_echo_roster.json`、
  `ui::refresh_texts()` 过，菜单再建列表时就是新文字；
* 实测体验上没有可感知的停顿（0.25 秒），也不写任何存档标志。

## 5. ESD 表达式字节

| 表达式 | 字节 |
|---|---|
| `true` | `41 a1` |
| int 常量（-64..63） | `(v+64) a1` |
| int 常量 | `82 <i32 LE> a1` |
| 函数 `f()` | `<id+64 或 82 <id>> 84` |
| 函数 `f(a,b)` | `<id> <a> <b> 86` |
| `GetTalkListEntryResult() == n` | `57 84 82 <n LE> 95 a1` |
| `GetEventFlag(id) == 1` | `4f 82 <id LE> 85 41 95`（**实测 ESD 侧读不到 DLL 置的 6729，未采用**） |
| `GetCurrentStateElapsedTime()` | `82 <103 LE> 84` |
| `float` 常量 | `80 <f32 LE>` |
| 运算符 | `95 ==`, `94 >`, `99 \|\|`, `98 &&` |
| `talk_menu_closed_expression` | `7b 41 40 86 41 95 7a 40 85 40 95 98 40 95 a1` |

函数 ID：`GetEventFlag=15`、`GetTalkListEntryResult=23`、`ShowShopMessage=10`、
`SetEventFlag=11`、`AddTalkListData=19`、`ClearTalkListData=20`、
`OpenRepository=30`、`GetCurrentStateElapsedTime=103`。
枚举：`FlagState.On=1`、`TalkOptionsType.Regular=1`。

## 6. 开关 / fallback

`er_echo.ini`：

```ini
[ui]
nested_menu=true
```

* `true`：部署原版 ESD（`ui/out_vanilla`），DLL 注入二级菜单；
* `false`：DLL 不注入（钩子仍在，只做一次原子读就放行），配合离线 ESD 根列表
  版本（`ui/out_rootmenu`，5 项直接挂根菜单，已实测）。

一键切换（会同时换 ESD 和 ini，重启游戏生效）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\switch_menu_mode.ps1 -Mode root
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\switch_menu_mode.ps1 -Mode nested
```

诊断命令：

```powershell
python er-echo\tools\ipc_client.py menu_status   # 钩子/偏移/patched 状态
python er-echo\tools\ipc_client.py menu_dump     # 下一次坐火打印赐福 state group
python er-echo\tools\ipc_client.py menu_reset    # 下一次进入赐福初始 state 重打补丁
python er-echo\tools\ipc_client.py menu_enable --args "{\"on\":false}"  # 运行期关注入
```

## 7. 已知限制 / 风险

* 钩子是版本绑定的：游戏升级后如果 AOB 或 prologue 变了，日志会打
  `ezstate: EnterState call-site AOB not found` / `prologue mismatch`，此时**不注入**，
  游戏退回原版赐福菜单（配置文件换成根列表 ESD 仍可用）；
* 只有赐福 talk script（`t000001000`，所有赐福共用）有菜单；其它 NPC 对话不受影响；
* 注入状态不是 ESD 文件里的一部分，`menu_dump` 看到的是**运行时**的 state group，
  和 `ui/esd/py/t000001000.py` 的行号对不上；
* 「立即重新召唤」依赖 `er_echo_roster.json` 与 `profiles` 已加载；没有档案时菜单
  仍会在 0.25 秒后返回，只是 roster 不变；
* 菜单文字在**建列表时**取（不是每帧刷新），所以 callback 固定延时的作用就是让
  DLL 先把文字改好；
* 自动化测试里合成 E 有时要按 2–3 次才触发坐火（第一次可能被窗口激活吞掉），
  与菜单代码无关；`tools/press_key.ps1` 可用 `-HoldMs 600` 多试。

## 8. 验收结果（2026-11-16 23:0x，1.17.2）

| 验收项 | 结果 | 证据 |
|---|---|---|
| 赐福第一项出现「战友（n/m）」 | ✅（引擎时间行之后第一项） | `images/menu_root_nested.jpg` |
| 选「战友」进二级菜单，不空白、HUD 正常 | ✅ 8 项（+ 三级 4 项） | `images/menu_sublist.jpg` |
| 二级菜单文字正确 | ✅ 人数 / 1-3 号位 / 重召 / 返回 | `images/menu_sublist.jpg` |
| 选人数循环 0/1/2/3，标签刷新 | ✅ 0.25s 后菜单回来、文字已更新 | `images/menu_count_refresh.jpg` |
| 选号位循环档案、`er_echo_roster.json` 变化、标签刷新 | ✅ slots `[1,0,1]`、2号位变 Sv | `images/menu_slot_refresh.jpg` |
| 选「返回」回赐福根菜单 | ✅ | `images/menu_back_to_root.jpg` |
| 「立即重新召唤」触发 dismiss+重召、菜单不崩 | ✅ 日志 `menu: apply roster -> dismiss + re-summon` | — |
| 连续开关不崩、HUD 不消失 | ✅ 42 次人数循环 + 多次进出子菜单，进程 Responding | — |
| 根列表 fallback 可切回 | ✅ `switch_menu_mode.ps1 -Mode root` + 重启，5 项挂根菜单 | `images/menu_root_fallback.jpg` |
