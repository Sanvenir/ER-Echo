# 使用指南（离线 · 单人）

> 目标：把**你另一个存档里的角色**召唤成同伴。外观/装备/等级来自那个存档，
> 战斗用游戏原生 AI，跟随用骨灰原生跟随，玩家自己**完全不变**。

## 0. 前置

- 正版 1.17.2 + ModEngine2（`launchmod_eldenring.bat` 启动，EAC 关闭、离线）；
  用 `ER-Echo-Setup.exe` 装的话，同一页的「一键启动游戏」会按目标和加载器自动选对启动器
  （原版 + ME2 → `mods\ER-Echo\launch-er-echo*.bat`；原版 + me3 → `er-echo.me3`；
  Convergence → me3 + `convergence*.me3`），安装完成时也会问「现在启动游戏？」
- 游戏根目录有：`er_echo.dll`、`er_echo.ini`、`config_eldenring.toml`（`external_dlls=["er_echo.dll"]`）
- Python 3（只有导出/调试脚本需要；日常使用**不需要**开着 Python）
- 从零安装 / 换到另一台机器 / 自检：[INSTALL.md](INSTALL.md)（`er-echo\tools\doctor.ps1` 一键预检）
- 菜单语言（跟随游戏 / 中/繁/英/日/自定义）：[i18n.md](i18n.md)，`er_echo.ini` → `[i18n] language=`；
  安装器「安装 / 配置」页的「游戏内菜单语言」下拉框会直接写这一项

## 1. 导出「另一个存档」的角色

有两条路，**推荐 B（离线解析 .sl2）**——不需要切号，也不要求那个存档能进游戏。

### A. 运行时导出（要能进那个档）

```powershell
# ① 游戏里切换到目标存档（读档完成、能走动）
# ② 让 DLL 导出一份运行时档案
cd "D:\...\ELDEN RING\Game\er-echo"
python tools\ipc_client.py dump_profile

# ③ 把 dump 转成 profile
python tools\dump_to_profile.py "..\er_echo_profile.json" -o tools\profile.slot2.json --name "Slot 2"
```

### B. 离线解析 `.sl2`（推荐，不用切号）

有图形界面和命令行两种，功能一样：

```powershell
# 图形界面（推荐给不想记参数的人）：
#   双击 build 出来的 dist\tools\ER-Echo-Setup\ER-Echo-Setup.exe →「导出 / Export」页
#   （onedir 版，整个文件夹一起拷；支持中文/English，导出后可直接写入 er_echo.ini）
# 或从源码跑： python tools\profile_export_gui.py
```

```powershell
cd "D:\...\ELDEN RING\Game\er-echo"

# 列出当前账号存档里所有角色（槽位 / 等级 / 名字 / 装备）
python tools\export_profile_from_save.py --list

# 列出某个「隔离」的旧存档（目录名随便，比如 "... - 副本"）
python tools\export_profile_from_save.py --save "%APPDATA%\EldenRing\<SteamID> - 副本\ER0000.sl2" --list

# 导出全部可解析角色到 tools/from_save/
python tools\export_profile_from_save.py --save "...\ER0000.sl2" --all -d tools\from_save

# 只导出某个槽
python tools\export_profile_from_save.py --save "...\ER0000.sl2" --slot 2 -o tools\profile.slot2.json
```

原理：PC 版 `.sl2` 是**明文 BND4**，前 10 个 entry 是角色槽（`0x10 MD5 + 0x280000` 数据）。
解析器在槽数据里定位四块：

| 数据 | 定位方式 |
|---|---|
| 等级/属性/名字 | 8 个 u32 属性 + ER 硬约束 `level == sum(stats) - 79` + 角色名 UTF-16 |
| HP/FP/耐力上限 | PGD `+0x0C / +0x18 / +0x28`（引擎算好的最终值，直接抄，不用按属性重算） |
| 外观 FaceData | `ffffffff FACE 04000000 20010000` + 276 字节（0x12F 块） |
| 装备 22 槽 | FaceData 前 0xA8 处的 22×i32 表（旧版本有偏移，会就近搜索校验） |
| 记忆法术 14 槽 | PGD `+0x93B4`，14 × `(id, charges)`；**不带这张表，队友就不会施法**（见 §3.1） |

`magic` 字段需要 `Magic` 参数表做校验：进游戏跑一次 `python tools\ipc_client.py dump_magic`
会生成 `er_echo_magic.json`，导出器自动找它（也可 `--magic-ids` 指定）；没有也能导，
只是退回「id 落在法术区间」的弱校验。

导出结果与运行时 dump 逐字节对比（同一角色，游戏里正好登录着 May）：

```
level 6 = 6    stats 8/8    equipment 22/22
face payload 276B 一致
hp 396/396   fp 95/95   stamina 94/94   ← 全部一致
```

自检命令（游戏里登录着对应角色时）：

```powershell
python tools\ipc_client.py dump_profile --wait 2
python tools\diff_profile.py er_echo_profile.json tools\from_save_account\sl2\slot1_May.json
# → ALL MATCH；退出码 0，可直接当回归测试
```

已知限制：2024 年的旧存档里个别角色（如 lvl 227 的 "Sanvenir"）装备表用了不同编码，
会被标记 `incomplete` 并跳过；名字/等级/脸仍能读出来。
装备表只含 param id，**不含强化等级**（+N 存在 inventory 的 gaitem 句柄里，暂未解析）。

导出器会校验「四件防具是一套」（同高位区、跨度小、至少两件），不满足就标 `incomplete` 跳过 ——
宁可不导出也不导出错位/占位的装备 id（详见 implementation-log §13.9）。

同一个账号目录下可能有好几份存档，都能直接解析（不需要是「当前登录」的那份）：

| 文件 | 含义 |
|---|---|
| `ER0000.sl2` | 主存档 |
| `ER0000.sl2.bak` | 主存档自动备份 |
| `ER0000.cnv` / `ER0000.cnv.co2` | Seamless Coop 存档 / 备份 |
| `ER0000.mod` | 某些 mod 的独立存档（可能是旧编码，装备表可能读不出） |

> 你也可以用 Smithbox/存档工具离线抠 FaceData，但本脚本一条命令就能批量导出，且字段与 DLL 完全对齐。

## 1.5 让 ME2 加载游戏内 UI 的 ESD

`config_eldenring.toml` 里 `[extension.mod_loader]` 的 `mods` **不能是空数组**，否则
ME2 不会加载 `mod/` 下的松散文件（`mod/script/talk/m00_00_00_00.talkesdbnd.dcx` 就进不去，
坐火看不到「战友」）：

```toml
[extension.mod_loader]
enabled = true
loose_params = false
mods = [
  { enabled = true, name = "er-echo", path = "mod" },
]
```

改完重启游戏。日志里 ESD 不会单独报错；如果菜单没有「战友」，先确认这一项。

> 默认（`nested_menu=true`）部署的是**原版** ESD，二级菜单由 DLL 运行时注入；
> 只有 `nested_menu=false` 的根列表 fallback 才依赖 `mod/script/talk` 里的补丁 ESD。

## 2. 配置 `er_echo.ini`

```ini
[clone]
; 第 i 个克隆体用第 i % n 个档案
profiles=er-echo/tools/profile.test_face.json,er-echo/tools/profile.slot2.json
auto_apply=true
apply_stats=true
; 队友伤害修正 = 玩家褪色者：摘掉拟态泪滴行上的灵体削弱 spEffect（296000/20297000），
; 不修改 SpEffectParam 行本身，所以不会连带强化玩家用其它骨灰召出来的灵体
player_damage=true
; 玩家升级时队友跟着升：按玩家这次的属性增量追给所有已加载档案，并写回 profile JSON
auto_level=true

[combat]
; 友伤初始默认值：只在第一次生成 er_echo_roster.json 时生效；
; 之后在赐福菜单「战友 → 友伤」里点到的状态会持久化到 roster 文件，优先于这里
friendly_fire=false
; 友伤倍率：0.2 = 玩家/队友互相只造成 20% 伤害。只影响「对玩家类目标」的伤害，
; 打普通敌人仍是 100%；POISE/削韧不缩放
friendly_fire_rate=0.2

[balance]
; 战友模式：按当前出战的战友人数补正**敌人**的生命上限（默认开）
; 0 人 = 不补正；1 / 2 / 3 人 = 下列倍率；超过 3 人按 3 人算
enemy_hp_scaling=true
enemy_hp_rates=1.5,1.8,2.0

[summon]
; 进游戏自动把这些骨灰行改成「人形泪滴」（留空 = 不改）
buddy_rows=23200000,23200001,23200002
; 把「拟态泪滴本体」这一行 BuddyParam 整行复制过去（跟随/掉队全靠它）
buddy_copy_from=20700001
buddy_npc=100000010
buddy_think=100000010
buddy_init=26050
buddy_follow=0
; 召唤请求用的 trigger spEffect（留空 = 取 buddy_rows 第一行自己的，现在是 232000）
; summon_trigger=232000
; 跳过「召唤石范围」限制（dead zone 的原凶）：把全表 activate_range 抬到 9999
stone_range=9999
; 每帧把管理器的范围/冷却门禁位强行置真（物品可用性由引擎重算，真正管用的是下面这条）
summon_anywhere=true
; 允许已有召唤物时再召（原版一次只能一队）
multi_summon=true
; 去掉灵体的蓝白虚影（spEffect 295000 普通 / 295200 傀儡 / 295190 灵体着色）
no_spirit_glow=true
glow_speffects=295000,295200,295190

[tuning]
follow_distance=35.0
; 掉队只告警（DLL 自己传送已实测不可行，见 implementation-log §14.6）
auto_recall=false
; 掉队保底：全体都 >150 m 且持续 15 s → 解散重召（引擎不配合时退化成「补一队」）
lost_resummon=true
lost_distance=150
lost_seconds=15

[ai]
; 同伴无限蓝：施法要 FP，每帧顶回上限（否则放两下就退化成平砍）
infinite_fp=true
; 权重落到哪几行（0 = 不写）。think 默认拟态泪滴本体行，set_weights 开箱即用；
; 行为概率表（NpcAiBehaviorProbability）对 player 型 AI 的槽位语义还没证实，默认不动
think_row=100000010
behavior_row=0
npc_row=0
; 「队友 AI」给 1/2/3 号位各借一行 NpcThinkParam（拟态泪滴家族里行为相同的几行）；
; 运行时先把 think_row 整行复制过去，再只改该号位的 aggression/guard/target_switch。
; 行不存在 / 填 0 = 该号位跟随全局 think_row（功能仍可用，只是交战半径不按人分开）。
; 注意：这几行只在**当前这局**被改，重启游戏会从 regulation 重新读回。
teammate_think_rows=100000020,100000030,100000040

[debug]
; 闪退排查：关掉事件召唤 / 灵体摘除 / 木桩 / 调试生成
safe_mode=false
; 每 30 秒往日志里打一条紧凑状态
auto_status=true

[i18n]
; 赐福菜单文案：默认 game（跟随游戏文本语言）；auto = 跟 Windows 显示语言
; 也可以写死 zh-CN / zh-TW / ja / 自定义；自定义语言用 er_echo_i18n.ini 覆盖
; 安装器「安装 / 配置」页有「游戏内菜单语言」下拉框，改完立即写入本文件
language=game
```

- `language` 只影响 mod 注入的那几行菜单字。**默认 `game`** = 和游戏「文本语言」一致
  （Elden Ring 的语言由 Steam 的 per-game 语言决定），这样不会因为字体缺字显示方块；
  想固定中文就写 `zh-CN`。`er_echo.log` 里 `i18n: language=... (source=...)` 是实际生效值。

- `buddy_rows` 是**野狼骨灰**的 3 行（一次召 3 个）。想用别的骨灰：先用
  `python tools\ipc_client.py dump_buddies` 找到它的行 id 填进来。
- `buddy_copy_from=20700001` 是关键：只改 npc/think/init/follow 不够，**整行复制**
  才会把「跟随/掉队传送」这套骨灰行为一起带过来（实测掉队 42 m 后引擎自己拉回到 1 m）。
- `summon_trigger` / `stone_range` / `summon_anywhere` / `multi_summon` 都是为了
  **不经过骨灰物品**就能召唤（细见 implementation-log §15）：F8 直接写
  `request_summon_speffect_id`，区域/召唤石/冷却/「已有一队」全不参与。
- `summon_events=true`：**坐火 / 传送 / 复活 / 重进游戏**之后自动召唤一队
  （真正的「篝火菜单项」要改 ESD/前端，见 §15.6；这里是事件驱动的等价物）。
  坐火是**坐下那一刻**排程（世界刷新也在那时做），约 2.5 秒后出人。
  诊断：`python tools\ipc_client.py event_probe`。
- `no_spirit_glow` 改的是 spEffect，不是 `regulation.bin`；`glow_speffects` 可以按需增减。
- `player_damage=true` 会从 **拟态泪滴的 NpcParam 常驻槽**（100000010 / 133201000）里去掉
  `296000`（对敌/对玩家伤害 ×0.25、受伤 ×0.5、削韧 ×0.05）和 `20297000`（受伤削韧 ×0.5），
  并在每 15 帧兜底从场上克隆体身上摘掉；改完后队友的伤害/受伤/削韧倍率都是 1.0（= 玩家褪色者）。
  没有修改 `SpEffectParam` 行，所以其它骨灰的削弱保持原样；`damage_probe` 可验证。
- `auto_level=true`：玩家在赐福升级后，DLL 读取等级 / 8 维属性 / HP·FP·耐力基础上限的增量，
  把同样的加点追给 `profiles` 里的**每一份**档案（不只是当前出场的那几个），
  然后写回各自的原 JSON 文件；场上克隆体立刻重写等级/属性。写盘失败只告警，内存里的档案仍然跟升。
  读档 / 切号（等级下降）不会触发；`level_status` 可看基线和每份档案的路径。
- `teammate_think_rows=100000020,100000030,100000040`：「队友 AI」给 1/2/3 号位各借的
  `NpcThinkParam` 行。每个号位在菜单里选过 AI 之后，DLL 会先把 `think_row` 整行复制到它那行，
  再只改 `aggression / guard_rate / target_switch` 三个字段（`spell_rate` 不写 think，
  而是改该克隆体的记忆槽数量，立即生效）。这些行只在**当前这局**被改，重启游戏就从
  regulation 重新读回；填 0 或行不存在时该号位自动退回跟随全局。
  手改数字 / 清除设置：`set_teammate_ai --args '{"slot":0,"inherit":true}'`，或直接删掉
  profile JSON 里的 `ai` 段。
- `friendly_fire`：赐福菜单「战友 → 友伤」的初始默认值。打开后把 `AtkParam_Pc` 里
  `friendlyTarget` 全开——**玩家和同伴（都是 PlayerIns）的攻击可以命中对方**；
  同伴仍是 team 47、`isBuddyAI`、`team_attack_effectivity=0`，不会把玩家当敌人；
  同时给克隆体钉上 `disable_lock_on`，玩家/敌人不会把队友当锁定目标。
- `friendly_fire_rate=0.2`：友伤伤害倍率（20%）。实现是运行时把一条无引用的 spEffect
  `20011466` 改成 `atkPlayerDmgCorrectRate=0.2` + `defPlayerDmgCorrectRate=0.2`，
  `atkEnemy/defEnemy/defObj=1`。**只挂在我们的克隆体上，不挂玩家**：
  - 克隆体→玩家走 `atkPlayer=0.2`；
  - 玩家→克隆体走克隆体 `defPlayer=0.2`；
  - 敌人打玩家/克隆体走 `defEnemy=1`，伤害不变；玩家打普通敌人也不变。
  菜单打开时再挂一次，关闭时摘掉并还原该行。削韧/POISE 不缩放；要更痛/更轻可改 0.05–1.0。
  该状态写入 `er_echo_roster.json` 的 `friendly_fire`，下次进游戏沿用；`friendly_fire_status` 可看补丁行数与倍率。
- `[balance] enemy_hp_scaling=true` / `enemy_hp_rates=1.5,1.8,2.0`：**战友模式**的敌人生命补正。
  当前出场**活着**的战友为 0 / 1 / 2 / 3 人时，敌人生命上限分别 ×1.0 / ×1.5 / ×1.8 / ×2.0
  （`enemy_hp_scaling=false` 等于永远 ×1.0）。详见 §3.3。
- 路径相对**游戏根目录**。

### 2.1 内置档案：Sanvenir（彩蛋 / 备用）

发布包固定带一份 `builtin_sanvenir.json`（Lv1，脸 / 体型 / 装备是发布时的快照），
当作彩蛋兼「备用角色」：

- 安装器每次把它复制到 `<Game>\mods\ER-Echo\profiles\builtin_sanvenir.json`，
  并**追加在 `profiles=` 名单末尾**——赐福菜单里把 1/2/3 号位循环到最后就是 Sanvenir；
- **用户导出不会覆盖它**：导出工具只写/删 `slot<N>_<名字>.json`，内置档案用的是
  `builtin_` 前缀；GUI 的「写入 er_echo.ini」也会把已有的 `builtin_*` 条目保留下来；
- 新机器没有存档 / 导出失败时，名单里至少还有它（不再只剩空壳 `profile.example.json`）；
- `auto_level` 会像其它档案一样把玩家升级追给它并写回 JSON；**重装安装器**会用发布版
  覆盖回来，改坏了也能还原；
- 不想要：装完后把 `profiles=` 里那一段删掉即可；下次重装安装器会再加回来
  （它本来就是随包的固定彩蛋）。

## 3. 进游戏

1. 启动 `launchmod_eldenring.bat`，读档；
2. **按 F8** 召唤 3 个克隆体（不需要骨灰、不看区域/召唤石/冷却）；
   - 在允许召唤的地方继续用骨灰物品也行，效果一样；
   - **进游戏 / 坐火 / 传送 / 复活之后会自动召唤一队**（`summon_events=true`）；
   - **F7** 收回，**F9** 重新读档案，**F10** 开/关调试注入；
3. 3 个克隆体出现在脚下 2~3 m，1 秒内变成目标存档的角色（外观/装备/等级/法术）；
4. 它们会跟随、参战；跟丢时原生骨灰 AI 会自己把它们拉回来（不用 DLL 干预）。
5. **法系角色真的会放法术**：档案里的 `magic`（记忆法术 14 槽）会写进克隆体的
   `EquipMagicData`，AI 用的是原版拟态泪滴那套（默认 think `100000010`；在菜单里设过
   「队友 AI」的号位用它自己那行，见 §3.2）。
   May（int16）现在带 `[4000, 4070]`，战斗里会丢石头；Sv（int9）没法术，只能砍。
   **注意交战半径**：拟态 think 行出厂值只有 2 m（贴脸才反应），启动时会写一次默认权重
   （`eye=13 m / battle_start=7 m`），否则法系同伴根本不会在射程外进入战斗
   （这是「有法术却不放」的第二层原因，见 implementation-log §17.1）。

### 3.1 施法 / 观测命令

```powershell
python tools\ipc_client.py status               # 一行状态 + er_echo_status.json（克隆体/木桩/敌人/权重）
python tools\ipc_client.py damage_probe         # 灵体削弱 spEffect 是否已摘掉 / 克隆体锁定位
python tools\ipc_client.py level_status         # 玩家升级基线 + 每份档案的等级/路径（自动跟升排障）
python tools\ipc_client.py friendly_fire --args "{\"on\":true}"   # 不用菜单直接开/关友伤（默认 20%）
python tools\ipc_client.py friendly_fire --args "{\"on\":true,\"rate\":0.15}"  # 改成 15%
python tools\ipc_client.py friendly_fire_status # AtkParam_Pc 里 friendlyTarget 行数 / 我们改过多少行
python tools\ipc_client.py teammate_ai_status   # 每号位的 AI 预设 / think 行 / 载体行当前 think id
python tools\ipc_client.py set_teammate_ai --args "{\"slot\":0,\"preset\":\"caster\"}"  # 等价于菜单里点 1 号位
python tools\ipc_client.py set_teammate_ai --args "{\"slot\":0,\"aggression\":0.9,\"spell_rate\":0.2}"  # 手调数字
python tools\ipc_client.py set_teammate_ai --args "{\"slot\":0,\"inherit\":true}"      # 删掉 ai，回到跟随全局
python tools\ipc_client.py magic_probe          # 玩家 + 克隆体的记忆槽 → er_echo_magic_probe.json
python tools\ipc_client.py magic_copy           # 把玩家的法术抄给克隆体（兜底/验证）
python tools\ipc_client.py magic_set --args "{\"ids\":[4000,4070]}"
python tools\ipc_client.py infinite_fp --args "{\"on\":false}"   # 关掉无限蓝
python tools\ipc_client.py bullet_probe         # 场上子弹按施法者归类（看 clone= 那栏）
python tools\ipc_client.py combat_probe         # 战斗采样（木桩血量/克隆体血量/子弹）
python tools\ipc_client.py weights_probe        # 读回 think 行里权重写过的字段
python tools\ipc_client.py dummy --args '{\"on\":true,\"who\":0}'   # 第 1 只克隆体 → 敌对木桩
python tools\ipc_client.py dummy --args '{\"on\":false}'            # 还原
python tools\ipc_client.py resummon             # 解散 + 重召（引擎不配合时补一队）
python tools\ipc_client.py safe_mode --args '{\"on\":true}'         # 关高风险特性
python tools\ipc_client.py dump_magic           # 全部 Magic 行（id / 耗蓝 / 需求）
```

`dummy` 是**自测用**：把一只克隆体临时改成 team 6（敌对），另外两只就会去打它，
这样不用真找敌人也能验证「会不会打 / 会不会放法术 / 权重有没有效果」。
`on:false` 会把它恢复成同伴（队伍号 + 血量）。血量上限改不了（引擎每帧按属性重算），
所以看的是「掉血多少 / 多久打死」。

日志里出现下面这行就说明克隆体真的在放法术（不是平砍）：

```
[Info] bullet: clone=2 other=0 samples=["npc=100000010 team=47", ...]
```

> 为什么不能直接按骨灰：物品「能不能用」是引擎在菜单层判定的，且依赖地图里真的存在
> **召唤石实体**；死区里 `buddy_stone_entity_id = 0`，DLL 改标志位会被引擎每帧重算覆盖。
> 直接写召唤请求则没有区域概念 —— 实测在「按骨灰没反应」的位置照样召出 3 个。

日志在 `er_echo.log`（UTF-8）：

```
config profile[0/2]: 'Blue Face Test' lv9
config: BuddyParam 23200000 -> npc=100000010 think=100000010 init=26050 follow=0
config: buddy_copy_from=20700001 applied to 3 row(s)
config applied: profiles=2 auto_apply=true apply_stats=true buddy_rows=3
auto_apply: 3 clone(s) -> equip=3 face=3 (profiles=2)
follow: far(>35)=0 resolved=3/3 dists=[2.9 2.9 3.1] (physics world pos)
```

### 3.2 游戏内 UI：赐福菜单 / 给队友装备

**赐福菜单**（原生 UI，不用 ImGui）：

1. 走到赐福按交互键（手柄 Y / 键盘 E）；
2. 菜单最上面多出 **「战友（n/m）」**（n = 当前人数，m = 已加载档案数）；
3. 选它进入**二级菜单**：
   - **队伍人数：N（点击切换）**：点一次 0→1→2→3→0；
   - **1/2/3 号位：名字（点击切换）**：点一次切到下一个档案（`er_echo.ini` `profiles` 顺序）；
   - **队友 AI（点击进入）**：三级菜单里给 **1/2/3 号位分别**点 AI 风格
     （默认 → 均衡 → 近战 → 法术 → 守护 → 激进 → 均衡…）；点完立刻写回该队友的 profile 文件；
   - **立即重新召唤**：按新人数/新名单立刻重召（多出来的队友会被移除；旧版「切了人数还是 3 人」已修）；
   - **友伤：开（20%，点击切换）**：打开后玩家和同伴的攻击能命中对方，但只造成 20% 伤害；同伴不会把玩家当敌人，
     也不能被锁定。状态写入 `er_echo_roster.json`；
   - **返回**：回到赐福根菜单；
4. 选项点完会回到二级菜单并刷新文字（人数/号位立刻变）；**返回**回赐福根菜单。
   人数/名单在「立即重新召唤」、坐火、传送、复活时都会按当前值重召。

> **队友 AI 的生效时机**：`spell_rate`（记忆槽开几发）是每个克隆体自己写的，**立刻生效**；
> `aggression / guard_rate / target_switch` 写在 think 行上、引擎在**生成那一刻**按
> `BuddyParam.npc_think_param_id` 取，所以改完要**下一次召唤**才完全生效
> （在赐福点「立即重新召唤」，或坐火/传送后自动重召）。
> 每个号位的 think 行默认是 `100000020 / 100000030 / 100000040`（拟态泪滴家族里行为相同的几行），
> 运行时先整行复制基准行 `100000010` 再覆盖差异字段，所以不会把别的 AI 带进来；
> 可用 `[ai] teammate_think_rows=` 改（行不存在时该号位自动退回跟随全局）。

**队友 AI 的预设**（写在每个队友自己的 profile 里，见下）：

| 预设 | aggression | spell_rate | guard_rate | target_switch | 效果 |
|---|---|---|---|---|---|
| 默认（`inherit`） | 全局 | 全局 | 全局 | 全局 | 不写 `ai` 字段，跟随 LLM/全局权重 |
| 均衡 `balanced` | 0.50 | 0.50 | 0.50 | 0.50 | 和出厂权重一样 |
| 近战 `melee` | 0.75 | 0.00 | 0.25 | 0.50 | 清空记忆槽、只砍人 |
| 法术 `caster` | 0.50 | 1.00 | 0.20 | 0.60 | 记忆槽全开、交战半径更大 |
| 守护 `guardian` | 0.25 | 0.30 | 1.00 | 0.25 | 举盾、少追人、少换目标 |
| 激进 `aggressive` | 1.00 | 0.50 | 0.15 | 0.90 | 20 m 就开打、频繁换目标 |

点完之后 profile JSON 里会多出一段（可直接手改数字，菜单会显示「自定义」）：

```json
"ai": {
  "preset": "caster",
  "aggression": 0.5,
  "spell_rate": 1.0,
  "guard_rate": 0.2,
  "target_switch": 0.6
}
```

不想开菜单时，可以用 IPC 模拟/检查（等价于在菜单里点一下）：

```powershell
python tools\ipc_client.py flag_test --args "{\"id\":6730,\"keep\":true}"   # = 1 号位 AI 切到下一个（6731/6732 = 2/3 号位）
python tools\ipc_client.py set_teammate_ai --args "{\"slot\":0,\"preset\":\"caster\"}"
python tools\ipc_client.py teammate_ai_status   # 看 slots[].ai / buddy_think / 每份档案的路径
```

> 二级菜单是 DLL 在运行时往 live `EzState` 注入的（`mod/src/ezstate.rs`：
> 钩 `EzState::EnterState`，往赐福 state group 追加 `AddTalkListData` 与 transition），
> **不是**离线改 ESD。详见 [submenu-runtime-injection.md](submenu-runtime-injection.md)。
> 离线 ESD 只保留原版，供注入模式使用。

**玩家升级时队友跟升**：在赐福坐火升级后，日志会出现

```
levelup: player +1 -> companions 3/3 profile(s) follow (stat deltas [1, 0, ...], pool deltas [30, 0, 2]); wrote [Sv Lv14, Edr Lv10, Rio Lv10]
levelup: stats applied to 3 clone(s)
```

* 按玩家**这一次**的属性增量追给所有已加载档案（保留各档案原本的等级差/流派）；
* HP/FP/耐力上限按玩家本次升级的绝对增量增加（档案里有 `pools` 时）；
* 写回 `profiles` 指向的 JSON；写盘失败只告警，内存档案仍然跟升；
* 读档/切号（等级下降）不会触发；`level_status` 可看基线。

**友伤**：打开后玩家和同伴的攻击可以命中对方（`AtkParam_Pc.friendlyTarget`），
并通过临时 spEffect `20011466` 把「对玩家类目标」的伤害压到 **20%**
（`[combat] friendly_fire_rate`；打普通敌人仍是 100%）；
同伴的队伍号仍为 47、`isBuddyAI` 仍开、`team_attack_effectivity=0` 仍为 0，
所以战斗 AI 不会把玩家列为敌人；克隆体的 `disable_lock_on` 被钉住，不会被锁定。
关掉后摘掉该 spEffect、还原它原来的字段，并且只还原本 mod 打开的那些攻击行。验证：

```powershell
python tools\ipc_client.py damage_probe
python tools\ipc_client.py friendly_fire_status
```

如果最上面没有「战友」：

* 确认 `er_echo.ini` 里 `[ui] nested_menu=true`；
* 确认 `mod/script/talk/m00_00_00_00.talkesdbnd.dcx` 是原版（`nested` 模式）且被 ME2 加载
  （`config_eldenring.toml` 的 `mods` 不能是 `[]`）；
* 看 `er_echo.log` 里有没有
  `ezstate: EnterState hook installed` / `ezstate: patched grace group`；
* 跑 `python tools/ipc_client.py menu_status` / `menu_dump`（后者下一次坐火时打印 state group）。

**回退到根列表 5 项**（旧版、已实测；根列表版本没有「友伤」和「队友 AI」项，
仍可用 IPC 切换）：

```powershell
# 换成根列表 ESD + nested_menu=false，重启游戏
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\switch_menu_mode.ps1 -Mode root

# 切回二级菜单
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\switch_menu_mode.ps1 -Mode nested
```

名单和人数存在游戏根目录 `er_echo_roster.json`：

```json
{ "v": 1, "count": 2, "slots": [0, 1, 0] }
```

`count` = 出场人数（0–3），`slots[i]` = 第 i 个位置用 `profiles` 里的第几个档案（0 起）。

> **队友 AI 不在 roster 里**：它写在每个队友自己的 profile JSON 的 `ai` 段
> （换一套 `profiles` / 换号时 AI 跟着角色走）。两个号位选中同一份档案时，两者共享这份 AI。

**给队友装备**：

1. 打开置物包/装备菜单，把光标停在要给的武器/防具/护符/法术上；
2. 按 `F12`：
   - 武器 → 右手**当前**武器槽（不是待切换的 2/3 号槽）；
   - 防具 → 对应部位直接替换；
   - 护符 → 第 1 个护符槽；
   - 法术 → 插到克隆体记忆列表**最前面**（注入按 `spell_rate` 只取前几发，放末尾在低施法率下不生效）；
3. 如果菜单没识别到光标（`selected_goods_item` / `selected_magic_item` 都为空，或选中的不是武器/防具/
   护符/法术），`F12` **不复制玩家装备**，而是把出场队友的装备和法术**恢复成档案里原本的值**
   （加载档案时留的快照）；名单人数为 0 时报 `no active companion (summon first)`；
4. 改的是**档案**（内存里的 profile），所以不会被每 15 帧的自动注入刷回去；重启游戏后恢复原档案。

当前限制：武器只写 param id，**强化等级/质变不保留**；技能/战灰也不跟随；恢复原样只回滚装备和法术，
不动等级/属性/外观。

**热键总表**：F6 状态、F7 收回、F8 召唤、F9 重读档案、F10 调试、F11 注入开关、**F12 给队友选中项（没选中则恢复档案原样）**。

### 3.3 战友模式：敌人生命值补正

带战友打架时，敌人会按**当前出场且还活着的战友人数**提高生命上限（默认）：

| 战友人数 | 敌人生命上限 |
|---|---|
| 0 | ×1.0（不补正） |
| 1 | ×1.5 |
| 2 | ×1.8 |
| 3 | ×2.0 |

示例：孤狼骨灰召出 3 个克隆体后，场上敌人（包括**已经在打的 Boss**）的生命上限变成 2 倍；
Boss 的血条/受击/死亡判定都按新上限走。0.25 秒内生效（每 15 帧钉一次），
**已经掉的血按百分比保留**（满血 Boss 补正后仍满血；半血仍半血）。

* 只作用于**敌对 NPC**：玩家、战友（team 47）、以及入侵者/其他玩家（`PlayerIns`）不动。
  普通骨灰召出来的原版灵体也不动。
* 后生成的敌人（换区、Boss 阶段、援军）会在第一次被看到时补正；
  阶段切换把上限改回去时，下一次 tick 会重新补上。
* 战友倒下 / 收回 / 功能关闭后恢复原上限（当前 HP 按百分比投影回去，不会借机回血）。
* 实现是运行时写每个角色的 `CSChrDataModule { hp, max_hp, max_uncapped_hp, base_hp }`，
  **不修改 `NpcParam` 行、不改 `regulation.bin`**；所以只影响当前这局，重启即还原。

配置（`er_echo.ini`，可留空用默认值）：

```ini
[balance]
enemy_hp_scaling=true
; 1 / 2 / 3 名战友对应的敌人生命上限倍率
enemy_hp_rates=1.5,1.8,2.0
```

运行时查看 / 临时改：

```powershell
# 看当前人数、倍率、跟踪了多少只敌人、每只的 hp/max/base（另写 er_echo_enemy_hp.json）
python tools\ipc_client.py enemy_hp_status

# 临时关掉 / 打开（不写 ini，重启还原）
python tools\ipc_client.py enemy_hp_scale --args "{\"on\":false}"

# 改倍率（下次 tick 立即生效）
python tools\ipc_client.py enemy_hp_scale --args "{\"rates\":[1.5,2.0,2.5]}"
```

日志里人数/倍率变化时会有一行：

```
enemy_hp: comrades 3 -> 2, enemy max HP x2.00 -> x1.80
```

`status` 的 `flags(... ehp=2.00 ...)` 也能看到当前倍率。
如果 `enemy_hp_status` 里 `consistent_live` 长期是 0（跟踪了但数值对不上），
说明引擎在两次 tick 之间把上限重算了，请把该 JSON 和 `er_echo.log` 留着排查。

### 3.4 自动进游戏（替代连点器，**仅仓库开发工具**）

> 这一节的 `auto_start` / `sit_grace` / `press_key` / `shot` 会模拟按键，属于**开发/测试工具**，
> 只在仓库里有，**发布包不带**（杀软启发式容易把它们当可疑行为，普通用户也不需要）。
> 正式安装后用安装器「安装 / 配置」页的「一键启动游戏」即可。

```powershell
# 启动 + 自动点掉标题/断线/离线提示 + 点「继续游戏」，进游戏后自动停
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\auto_start.ps1

# 游戏已经开着，只从标题菜单开始点
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\auto_start.ps1 -NoLaunch

# 进游戏后单独发一次 E 坐火/开赐福菜单（键盘 E 用 keybd_event 发，游戏能收到）
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\sit_grace.ps1

# 更稳的按键：同一个进程里先聚焦游戏再接按键（支持 E/Q/W/A/S/D/方向键/Enter）
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\press_key.ps1 -Key E -HoldMs 600
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\press_key.ps1 -Key DOWN

# 抓主屏截图（验证菜单/HUD）
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\shot.ps1
```

> 合成 E 有时要按 2–3 次才坐火（第一次可能被窗口激活吞掉），`-HoldMs 600` 更稳；
> 如果按 E 一直没反应，先走开再走回赐福（`-Key S` 然后 `-Key W`）重置交互状态。

原理：标题/对话框用鼠标点（`0.55h` 是「确定」，`0.78h` 是「继续游戏」），同时补 Enter；
检测到 `er_echo_status.json` 里 `clones > 0` 或日志 `event: entered game` 后停止。

`tools/vpad.py` 还带了一个 ViGEm 虚拟 Xbox 手柄（A/Y/B/X/Start），但本机 XInput slot 0
被真实/GeniTech 手柄占用，游戏只读 slot 0，所以脚本默认不用它；没有实体手柄时可用：

```powershell
python er-echo\tools\vpad.py a
python er-echo\tools\vpad.py y
```

## 4. 让 LLM 调行为（可选）

必须先告诉 DLL「克隆体用的是哪一行 NpcThinkParam」（默认就是 `buddy_think`）：

```powershell
python tools\ipc_client.py set_rows --think 100000010
python tools\ipc_client.py set_weights --aggression 0.8 --dodge_rate 0.6 --guard_rate 0.6 --repeat 10
```

- `set_weights` 每包只平滑 15%，`--repeat N` 用来逼近目标值；`seq` 必须**递增**，DLL 才会再次应用。
  只发想改的字段就行，没发的沿用上一轮（示例：`set_weights --spell_rate 0` 不会动 aggression）。
- 权重真正落地的字段（逐条实测见 implementation-log §17.2）：

  | 权重 | 落点 | 能看到的效果 |
  |---|---|---|
  | `aggression` | `eye_dist`/`search_eye_dist` 6–20 m、`battle_start_dist` 3–12 m | 会不会脱离跟随去交战、多早开打 |
  | `spell_rate` | 记忆槽开几发（0 = 关，0.5 = 一半，1 = 全开） | `status` 里的 `magic`；`bullet_probe` 有没有弹 |
  | `guard_rate` | `is_guard_act` + 格挡角/物减 | 举盾倾向 |
  | `target_switch` | 忘记目标时间 1–20 s | 换目标快慢 |

- `combo_rate / item_rate / heal_priority / spacing` 目前**没有可靠落点**
  （`NpcAiBehaviorProbability` 的槽位对 player 型 AI 不生效，见 §16.1/§17.7），
  发过去不会报错，但别期待可见变化。
- **同伴的 `team_attack_effectivity` 固定写 0**：这个字段拉高会让召唤物误伤玩家。
- `backhome_dist`（绳长）默认不碰（拟态本体是 9979 = 不回家）；只有 `keep_close --dist N`
  才会把它压到 N 米。

### 4.1 LLM 能看到什么

DLL 每秒发一条 state（`python tools\watch_state.py --seconds 30` 可以直接看）：

```
[state 001] hp=0.72 fp=0.55 lv=6 clones=3 [Sv lv15 hp0.95 d4.2] [May lv6 hp0.61 d6.0] … enemy_dist=6.3
[state 002] hp=0.33 fp=0.40 lv=6 clones=3 … events=player_low_hp
```

- `clones[]` 给的是每个克隆体的等级 / 血量比例 / **引擎算的**到玩家距离；
- `enemy` 是最近敌对单位（`team_type` 既不是玩家也不是同伴）；
- `events` 只在跳变时报一次：`player_low_hp` / `player_dead` / `revive` / `enemy_engaged` /
  `enemy_dead` / `clone_summoned` / `clone_gone`。

### 4.2 让 LLM 换装/加点（可选，默认关）

```powershell
python bridge\director.py --llm ollama --model qwen2.5:7b --allow-tools
# 或云： --llm openai --model gpt-4o-mini --api-key $env:OPENAI_API_KEY
```

- `--allow-tools` 关掉时只调权重，不会动装备/属性；
- 打开后 LLM 可以输出 `loadout` / `upgrade` / `stats` / `level` / `rollback`，
  sidecar 转成 `set_equipment` / `set_stats` / `rollback_equipment` 命令；
- **作用对象是克隆体，不是玩家**；DLL 侧还有一层护栏：槽位白名单、参数存在性检查、
  单步 ±20% clamp、改前存回滚点。

## 5. 常见问题

### Q: 队友体型不对（和玩家一样）/ 改了体型没反应？

体型（身高、骨架、四肢粗细）只在**召唤出生那一刻**从 `CharaInitParam → FACE_PARAM` 烘焙进模型；
出生后再改档案 / 装备不会变。模组会为 1/2/3 号位各复制一行 spawn 参数，写入该号位档案的
`body_type` + 5 个体型滑条，**下次召唤**（菜单「立即重新召唤」/ F8 / 重进图）生效。
换过 `profiles=` 列表后也要重召一次，否则场上克隆体的身体还是旧映射烘焙的。


| 现象 | 原因 / 处理 |
|---|---|
| 召唤出来还是默认褪色者 | `profiles` 没加载（看日志 `config profile`）；或 `auto_apply=false` |
| 召唤物打你 | 旧版权重映射的 bug；更新 DLL（`team_attack_effectivity` 现在写死 0） |
| 骨灰用不了 | 刚解散/刚死需要休息（赐福）或离开区域再回来 |
| 克隆体不动/不跟 | 先看日志 `auto_apply: N clone(s)`；确认 `buddy_copy_from=20700001` 生效（日志里有 `buddy_copy_from=... applied`） |
| 装备变回默认 | 只写了 `PlayerIns.chr_asm`；新版同时写 `pgd.equipment.chr_asm` + `equipment_entries` |
| 等级变了但血没变 | 旧版只写 `level/stats`；新档案带 `pools`（存档里引擎算好的 HP/FP/耐力上限）会一起写进去 |
| `set_equipment` 报 not present | 那个 id 不在参数表里（多半是别的版本/别的 mod 的 id）；先用 `dump_equip` 看真实 id |
| 法系克隆体只平砍不放法术 | ①`magic_probe` 看槽是不是空的（空 = 档案没带 `magic`，重跑 `export_profile_from_save.py`）；②`weights_probe` 看 `eye_dist` 是不是 2（出厂值 = 贴脸才反应，抬到 13–20 m 才会在射程外开打，见 §17.1）；③`infinite_fp` 关了且 FP 干了；④手上没有对应触媒（法杖/圣印记） |
| 克隆体放两下就停 | 旧 DLL 没有 `keep_clone_fp`；或档案 `pools.fp` 太小；或 `spell_rate` 被调低（记忆槽只开了一发） |
| 想看队友到底在打谁 / 打掉多少血 | `dummy` 造一个敌对木桩 + `combat_probe` 采样；或看 `status` 的 `dummy=hp/dmg` |
| 赐福菜单最上面没有「队伍人数」 | ①`config_eldenring.toml` 的 `mods` 是否包含 `path = "mod"`；②`mod/script/talk/m00_00_00_00.talkesdbnd.dcx` 是否被 ME2 加载；③ESD 是否与当前游戏版本匹配（升级后按 `ui/README.md` 重编）；④`python tools/ipc_client.py msg_test --args "{\"id\":69100001}"` 应返回「队伍人数…」，`flag_test --args "{\"id\":6728,\"keep\":true}"` 应看到 `menu: companion count -> ...` |
| F12 给装备没反应 | ①光标没被 `selected_goods_item` 捕获时走的是「恢复档案原样」分支（日志 `give: restore original gear ...`），不会给装备；②没召唤队友 → `no active companion (summon first)`；③没加载档案 → `no clone profiles loaded` |
| 队友伤害还是明显偏低 | `damage_probe` 看克隆体的 `speffects` 里是否还有 `296000` / `20297000`，`has_correction` 应为 false；`[clone] player_damage=true`；日志应有 `damage_fix: removed ...` |
| 玩家升级后队友没跟升 | `level_status` 看 `baseline` 和档案 `level`；确认 `[clone] auto_level=true`；日志 `levelup: player +N -> companions ...`；如果玩家用调试工具直接改等级而属性没变，也会跟升但属性增量是 0 |
| 友伤打开了但打不到队友 | `friendly_fire_status` 看 `friendly_target_rows` 是否接近 `pc_rows`；确认同伴是 PlayerIns（`status` 里 npc=100000010）；日志 `friendly_fire -> true` |
| 队友被锁定 / 准星粘在队友身上 | 友伤打开时每 15 帧钉 `disable_lock_on`；`damage_probe` 的 `disable_lock_on` 应为 true |
| 菜单「队友 AI」里点了没变化 | ①现在是不是坐在赐福上、场上还有旧克隆体？think 行要**下次召唤**才生效（点「立即重新召唤」或起身让事件召唤重召）；②`teammate_ai_status` 看 `slots[].ai`（`inherit` = 没设置）和 `buddy_think`（是否指到了 100000020/30/40）；③日志 `ai: think row per slot [...]` / `ai: slot N profile[i] ... -> caster`；④`teammate_think_rows` 那几行在 regulation 里不存在时会退回全局（日志会显示 `assigned` 里是 100000010） |
| AI 预设写不进 profile | profile 是只读 / 路径不在磁盘：日志 `ai: write '...' failed` 或 `no source path`；内存里仍会改，重载后丢失。用 `set_clone_profiles` / `load_profile` 带路径加载，或恢复文件写权限 |
| 想清掉某个队友的 AI | `set_teammate_ai --args '{"slot":0,"inherit":true}'`，或删掉该 profile JSON 的 `ai` 段后重开 |
| 敌人 / Boss 血量没有翻倍 | ①`[balance] enemy_hp_scaling=true`；②场上至少有一个**活着**的战友（`status` 的 `clones`）；③`enemy_hp_status` 看 `multiplier` / `tracked_live` / `consistent_live`；④日志有没有 `enemy_hp: comrades ... -> enemy max HP x...`；⑤`consistent_live` 长期为 0 = 引擎在两次 tick 之间重算了上限，把 `er_echo_enemy_hp.json` + 日志留下排查 |
| 敌人血量补正太高 / 太低 | 改 `[balance] enemy_hp_rates=`（1/2/3 人三个值）或临时 `enemy_hp_scale --args "{\"rates\":[...]}"`；不需要就 `enemy_hp_scaling=false` |
| 战友倒下后 Boss 血量上限变了 | 补正按**当前活着**的战友数算：3 人 → 2 人会从 ×2.0 降到 ×1.8（已掉血按百分比保留）。想固定按队伍人数算，请保持战友存活或在倒下后重召 |

## 6. 安全

- **只离线**：带 mod 存档上线会被隔离/soft-ban。
- 改 `regulation.bin` / `.sl2` 前先备份；本仓库不含存档或他人存档。
  `ui/` 下是赐福菜单 ESD 的构建资产（`ui/base` 是重打包用的原版模板，`ui/out_*` 是改过的版本）；
  发布包里只有改过的版本，原版模板不随包分发。
- 外观数据属于个人信息，分发 mod 时不要打包别人的脸。
