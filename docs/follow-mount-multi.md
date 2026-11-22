# 追加研究：跟随 / 爬梯 / 骑乘 / 多召唤
## 对 v0.1 设计的三处修订（v0.2）

> 这份文档回答三个追加问题：① 能否让同伴**始终跟随、不靠传送**；② 能否让同伴**骑马**；③ 能否**一次召唤多个**（一个骨灰出多个 / 多个骨灰并存）。
> 结论会改变 v0.1 的三条设计前提，先看下面的「决策变化」。

---

## 0. 决策变化（和 v0.1 的区别）

| v0.1 的假设 | v0.2 的修正 | 依据 |
|---|---|---|
| 传送是主要跟随手段 | **传送降级为兜底**：优先导航跟随，只在「路径失败 / 电梯 / 大落差 / 换区 / 雾门」时 warp | 敌人能爬梯；黑骑士骨灰 mod 能跟玩家爬梯；骨灰失败才 warp |
| 一个骨灰 = 一个 NPC | **一个骨灰可以出 N 个不同 NPC**（N 行 `BuddyParam` 共用 `triggerSpEffectId`），这是原版机制 | Wandering Nobles/大盾士兵 = 5 体；Nexus 教程实证 |
| 「只能一个骨灰」是参数限制 | 限制在 **exe 代码**（数量/区域/重召检查）；`BuddyParam` 无计数字段 | [Spirit Multiplier](https://www.nexusmods.com/eldenring/mods/11168) 用 DLL 一次解掉三件事 |
| 同伴只能步行 | **可召唤即骑乘**：`BuddyParam.npcParamId_ridden` 就是「被骑乘方」参数；Torrent = `c8000`，玩家↔Torrent 的 `RideParam` 已存在 | Paramdex `RideParam` / Smithbox Chr IDs |
| 跟随逻辑只能靠 param 调 | param 只能**减少**传送；「永不传送」需要 **自定义 Lua AI 脚本**或 DLL 位置/输入注入 | ER AI 是 Havok Script(Lua) goal 栈，`logicId` 可指自定义脚本；`NpcAiActionParam` 证明 AI 走虚拟手柄 |

---

## 1. 跟随与移动：为什么原生会「传送」，怎么减少

### 1.1 引擎事实
- NPC AI 不是 C++ 硬编码行为树，而是 **Havok Script（Lua）的 goal 栈**：`NpcThinkParam.logicId` 指向「逻辑脚本」，`battleGoalID` 指向战斗脚本；社区已能把 `logicId` 指到自己加载的脚本（例如加载 `030000` 脚本、`logicId=30000`）。
- 移动是「导航网格 + 寻路」；AI 输出是**虚拟手柄输入**（`NpcAiActionParam`：`moveDir` / `key1..3` / 长按 / 手势），所以「跑、跳、翻滚、上梯」理论上都能由 AI 触发，前提是**动画 + 导航节点 + 参数**齐全。
- 梯子等节点默认关闭：`NpcThinkParam.enableNaviFlg_Ladder`（默认 0）、`enableNaviFlg_Door/Hole/InSideWall/Lava`、`enableJumpMove(_onBattle)`、`useFall_onNormalCaution/onSearchBattle`。

### 1.2 爬梯：可行，但有三个前提
| 前提 | 说明 | 证据 |
|---|---|---|
| 导航 flag | `enableNaviFlg_Ladder=1`（还有 Door/Hole/Edge） | paramdef 注释「Can you pass through the node ladder? (def: 0)」 |
| 动画 | 该 NPC 的 anibnd 里要有爬梯/翻越动画；c0000 玩家模型自带全套 | Age of Spirits 作者：没有动画的骨灰会「退化为传送到玩家身边」 |
| 导航网格 | 梯子必须在 navimesh 里连通；失败时走 `actTypeOnFailedPath` | 同上 |

正向证据：
- **敌人会爬梯追你**（评测明确描述「有些敌人会跟着你上梯子」）。
- **黑骑士骨灰 mod** 明确写「还会跟着你爬梯子」（c0000 + 正确 flag/动画在 buddy AI 下过梯）。
- Age of Spirits / Better Spirit Ashes 把「能走梯子、悬崖、岩石」当作卖点。

反向证据：原生骨灰**普遍**不爬（默认 flag 关）、Mimic Tear 是否爬梯**没有可靠实测**（按未验证处理）。

> 结论：**不要假定「引擎禁止 NPC 爬梯」**。先把 `enableNaviFlg_Ladder` 等打开做 A/B 测试；能过梯就大幅减少 warp。

### 1.3 原生 warp 的触发条件（社区可观察到的）
| 触发 | 现象 | 可控性 |
|---|---|---|
| 路径失败 / 大落差 | 同伴「闪现」到身边 | param 可减少（navi/jump 位、`actTypeOnFailedPath`） |
| 电梯（Limgrave→Mistwood 等） | 电梯到顶后同伴才出现 | 预判 warp（DLL）更顺 |
| 离开召唤区域 | 血条闪烁 → 消失 | `BuddyStoneParam.activateRange`（默认 100m）、`overwriteReturnRange` |
| 雾门 / 换区 | 强制消失 | 引擎硬规则；可 DLL 重新召唤 |
| Seamless Co-op 的 tiny pot | 「follow & warp」失效 | 已知 mod 冲突，无解 |

**新发现（param 层）**：`BuddyStoneParam.overwriteReturnRange`（バディ帰還距離上書き）就是「同伴归返/传送距离」的覆盖字段，默认 -1（用代码常量）。把它调大（如 60–120m）能显著减少「离远了就回来」；`activateRange` 控制召唤石允许范围。这比 v0.1 说的「纯代码常量」多了一个旋钮，但仍不能做到「永不传送」。

**运行时侧**：`SummonBuddyManager` / `SummonBuddyGroup`（字段 `follow_type`、`warp_requested`、`has_mount`）是 buddy 跟随/传送的管理器。DLL 可以读它来判断「这次 warp 是引擎主动要的」，也可以**试着在合适的时机主动触发/抑制 warp**——比写坐标更「顺着引擎」。这条也解释了 `pcFollowType` 的去向：它最终落到 `follow_type`。

### 1.4 三条技术路线对比
| 路线 | 能做到 | 代价 | 风险 |
|---|---|---|---|
| **P：param-only** | 减少 warp、走台阶/小落差、过梯（若动画 OK）、扩大召唤/归返范围 | 只改 `regulation.bin` | 梯子/电梯/大落差仍会 warp |
| **L：自定义 Lua AI 脚本** | 真正的「玩家式跟随」：过梯、跳、骑马、战斗节奏 | 需要 DSLuaDecompiler + 脚本 API + 加载方式 | 版本更新脚本会变；调试困难 |
| **D：DLL 位置/输入注入** | 位置跟随、强制 warp、驱动虚拟输入 | 需 RVA/调用点 | 版本脆弱、崩溃、被视为作弊 |
| **E：EMEVD** | 传送、修 dead zone、开关 | 低 | 没有 follow/buddy 指令，不能持续跟随 |

**推荐组合**：P（立刻见效）→ D（保底与预判 warp）→ L（Phase 4，追求「永不传送」）。

### 1.5 建议的跟随状态机（供 DLL/Lua 实现）
```
Follow     目标 = 玩家身后 2m；速度按距离分级（走/跑）
Wait       玩家在战斗外/攀爬中：在梯底或安全点等待（不 warp）
Climb      玩家上梯：同伴也上（若 navi+动画 OK），否则切 Wait → 玩家到顶后 warp
CatchUp    距离 > 15m：加速；> 25m 且路径失败 > 3s：预判 warp
Warp       仅当：路径失败 / block 变化 / 电梯 / 雾门 / 距离 > returnRange
Mounted    玩家骑马：切换骑乘形态（见 §2）或按马速追赶
```
关键原则：**warp 前先确认「玩家不在视线内」或「路径失败超过 N 秒」**，避免玩家眼睁睁看着同伴闪现。

### 1.6 实验清单（P 路线，1 天内可做完）
1. `enableNaviFlg_Ladder=1` + `enableJumpMove=1` + `disablePathMove=0` → 带去地下墓地（有梯子）测。
2. `BuddyStoneParam.overwriteReturnRange` 设 60/120/65535，测「离多远才回来」。
3. `actTypeOnFailedPath` 0/1/2/3 各跑一次，看失败时是「原地」还是「回家/瞬移」。
4. `pcFollowType` 0 vs 1：同一场景 A/B，确认语义（**目前无公开文档**）。
5. 换一个**有爬梯动画**的 NPC（如黑骑士 c3xxx）做 buddy，验证「动画决定能否爬」。

---

## 2. 骑乘：同伴能不能骑马

### 2.1 关键 ID
| 对象 | Chr ID | 备注 |
|---|---|---|
| 玩家 | `c0000` | 所有玩家/入侵者/泪滴同模型 |
| **Torrent** | **`c8000`**（另有资料称 `c2600`） | Smithbox Chr IDs 表写 `c8000 Torrent`，`ChrIns.npc_id` 文档举例「8000 for Torrent」；但一份调研指出游戏包内有 `chr/c2600.chrbnd` + `c2640.anibnd`。**两者冲突，需用 Smithbox 打开 `regulation.bin` 核对** |
| Torrent 的 NpcParam | `80000000`（社区 mod 文档） | 两个独立 mod 文档都这么标；**未逐行验证**。Torrent 无 CharaInitParam（不是捏脸角色） |
| 夜之骑兵马 | `c3160` | Night's Cavalry Horse（与骑手是两个实体、两条血条） |
| 骑士马 | `c4360`–`c4366` | Knight's / Godrick / Cuckoo / Leyndell / Redmane / Mausoleum |
| Leonard（马） | `c4740` | 参数里有、chr 不存在 |

### 2.2 骑乘是「数据驱动」的
`RideParam`（Paramdex `ER/Defs/RideParam.xml`）每行定义一对「乘る側 ↔ 乗られる側」：
| 字段 | 含义 |
|---|---|
| `atkChrId` | 骑手 Chr ID |
| `defChrId` | 被骑乘者 Chr ID |
| `atkChrAnimId` / `defChrAnimId` | 骑乘/被骑乘动画变量（对应 HAT 的 RideOn/RiddenOn 状态） |
| `defAdjustDmyId` / `defCheckDmyId` | 对齐/判定用 dummy poly（只在被骑乘方） |
| `diffAngMyToDef` / `dist` / `upperYRange` / `lowerYRange` / `diffAngMin/Max` | 上马判定：角度、距离、高度、方位 |
| `rideCamParamId` | 骑乘相机（**仅 PC 有效**） |

因为玩家就是 `c0000`，**`c0000 ↔ c8000` 的 RideParam 行必然已存在**（否则玩家骑不了 Torrent）。这意味着：数据层上，任何 c0000 NPC 骑 Torrent 的动画/判定都是现成的；缺的是「让 NPC 触发上马」的逻辑。

### 2.3 `BuddyParam` 原生支持「召唤即骑乘」
`BuddyParam` 有：
- `npcParamId` / `npcThinkParamId`：骑手
- `npcParamId_ridden` / `npcThinkParamId_ridden`：**被骑乘方（馬）**，注释写着「騎乗状態で召喚したいバディの場合、『乗られる側』の NPC パラメータ ID を設定します」

也就是说：**把 `npcParamId_ridden` 指向 Torrent/马 的 NpcParam 行，理论上召唤出来就是骑乘状态**。这是最省事的路线（纯 param，先测）。

- 引擎确有「组级」字段：`SummonBuddyGroup.has_mount`（"Whether this SummonBuddy has mount or not"），说明 buddy 系统内建坐骑支持。
- **已有玩家 mod 实证**：Latenna 召狼并「一出现就骑上去」（[Nexus 656](https://www.nexusmods.com/eldenring/mods/656)），以及 Latenna and Lobo（[Nexus 6467](https://www.nexusmods.com/eldenring/mods/6467)）。要点：坐骑 NpcParam + 不乱跑的 ThinkParam（常设 -1）+ 生成偏移贴近 + 坐骑有 500 挂点。原版行大概率为 -1（「引擎支持但官方没用」），jank 风险中等（上马动画、坐骑血量、warp 时人馬分离）。

### 2.4 动态上马（玩家上马 → 同伴也上马）
- 运行时对象：`PlayerGameData.mount_handle`、`CSChrRideModule`（`is_mounted` / `is_mounting` / `mount_data` / `last_mounted`），Torrent 侧 `is_ride_character=true`；`mount_data` **只在骑手端更新**。
- **Torrent 是玩家专属 mount 槽**：`PlayerGameData.mount_handle` 指向「玩家那只」，所有权与玩家绑定；让 NPC 去骑玩家那只**不可行**（会与玩家所有权冲突）。现实做法是**给同伴生成属于它自己的坐骑**。
- 引擎支持 NPC 动态上马：夜之骑兵的马与骑手是**两个独立实体、两条血条**，马死骑手落马，之后用「Remount」攻击**重新召马再骑**。所以「动态上马」不是引擎限制。
- 但 eldenring-rs **只暴露读取**（`has_ride_param` / `is_mounted` / `mount_data`），**没有 `mount()` API**；发起上马要逆向骑乘初始化函数，或复刻整套流程（Torrent of Ashes 已证明「下马后坐骑留下、像骨灰一样跟随」可行）。
- 触发方式候选：① 调用引擎「ride」初始化（RVA，需 RE）；② 给同伴一个「上马」AI goal（Lua）；③ 直接写 ride module 状态（脆）。

### 2.5 四条可选路线
| 路线 | 做法 | 可行性 | 风险 |
|---|---|---|---|
| **M1 召唤即骑乘（推荐先测）** | 复制 BuddyParam → `npcParamId_ridden` 指向**坐骑的** NpcParam（马/狼/Torrent） | 高（`has_mount` + Latenna 先例） | 坐骑要是「同伴自己的」，不能抢玩家那只；上马动画/血量/warp 分离 |
| **M2 DLL 生成马 + 挂载** | spawn `c8000`/`c4360`，设置 ride module / mount_handle | 中 | 需 RE；可能崩；多马性能 |
| **M3 幻影马** | 用 `c3160`/`c4360` + 白色 phantom shader，视觉上是「幽灵坐骑」 | 中 | 不是 Torrent，观感不同 |
| **M4 步行 + 提速/追赶** | 不骑马，给同伴加速或更积极的 warp | 高 | 玩家骑马时仍会掉队 |

> 推荐：**M1 先验证**（1 个 param 行即可）；不行再 M2；M3 作为美术兜底；M4 永远保留。

### 2.6 玩家上下马的联动（设计）
```
玩家上马 → 同伴若在 Follow：播放上马（或直接切到「骑乘形态」实体）
玩家下马 → 同伴可保持骑乘（省事）或下马（更真实，需下马逻辑）
进洞窟/室内（Torrent 禁用区）→ 同伴自动下马/切步行
```
注意：Torrent 在部分区域（洞窟、王城部分区域）不可召唤；同伴的坐骑同样应遵守，否则会出现「室内骑马」的违和/碰撞问题。

### 2.7 实验清单
1. 复制 Mimic Tear 的 `BuddyParam` → `npcParamId_ridden` 填 Torrent 的 NpcParam（大概率 `8000`，**待核实**）→ 召唤看是否骑马。
2. 若成功：换成 `c4360` 骑士马，看是否也能骑（验证「任意 rider↔mount」）。
3. 用 Cheat Engine/Debug Tool 找 `CSChrRideModule` 状态，手动把同伴设成骑乘，观察是否稳定。
4. 玩家骑马跑 100m，测同伴是「追上 / warp / 消失」。

---

## 3. 多召唤：一个骨灰出多个 / 多个骨灰并存

### 3.1 原版机制：`BuddyParam` 扇出
```
骨灰物品 → spEffect（triggerSpEffectId）
   → 引擎遍历所有 triggerSpEffectId == 该 spEffect 的 BuddyParam 行
   → 每行生成 1 个 NPC（npcParamId / npcThinkParamId / npcPlayerInitParamId 各自独立）
   → 用 x_offset / z_offset / y_angle 排开；appearOnAroundSekihi 控制从石碑周围冒出
```
所以 **Wandering Nobles = 5 行 BuddyParam 共用同一个 triggerSpEffectId**；`BuddyParam` 里**没有**「数量/组」字段（[libER 字段表](https://dasaav-dsv.github.io/libER/dd/d74/structfrom_1_1paramdef_1_1BUDDY__PARAM__ST.html)）。Nexus 教程也实证了「复制行 → 多出实体」「多个骨灰行共用 triggerSpEffectId → 一次施放出多种召唤」。

> 这就是「**一个骨灰召唤 3 个读不同存档的 AI**」的最干净实现：3 行 BuddyParam，各自不同 `npcParamId/npcThinkParamId`，共用触发 spEffect；每行的 profile 由 DLL 在召唤瞬间覆盖。

### 3.2 「只能一个骨灰」的限制在哪
| 层 | 是否限制 | 说明 |
|---|---|---|
| `BuddyParam` | 否 | 无数量字段 |
| UI（`CSFeSpiritAshDisplay`） | 否 | 原版 5 体各自独立血条，UI 天然支持 |
| 召唤石（`BuddyStoneParam`） | 部分 | `summonedEventFlagId`（已召唤）、`activateRange`、`buddyId`（特殊石可直接召唤指定 buddy） |
| 玩家状态（spEffect `203000` StateInfo 357 "Spirit Summon"） | 是 | 改掉就完全召不出 → 「能否召唤」是玩家状态 |
| **exe 逻辑（已存在 buddy 检查）** | **是** | 无公开字段；[Spirit Multiplier](https://www.nexusmods.com/eldenring/mods/11168) 用 DLL 补丁一次解掉「数量 / 区域 / 重召」 |

即：**「一次多体」是原生能力；「两次召唤 / 两个骨灰并存」要 DLL 补丁。**

### 3.3 现成参考
| 项目 | 机制 | 能同召不同骨灰 | 备注 |
|---|---|---|---|
| [Spirit Multiplier](https://www.nexusmods.com/eldenring/mods/11168)（DLL） | 每骨灰倍率/固定数、可同召多种、池外召唤、无需赐福重召 | **能** | 绑定 exe 版本；崩溃日志有 `eldenring.exe+0x1EBCEF9` 等地址 |
| [Nexus 混合召唤教程](https://forums.nexusmods.com/topic/13495284-simple-guide-to-increasemix-summons-in-elden-ring/)（纯参数） | 复制 BuddyParam 行 + 共用 triggerSpEffectId | 能（一次施放） | 作者警告「>10 体可能出问题」 |
| [Spirit Battler](https://www.nexusmods.com/eldenring/mods/3150) | 覆盖骨灰 → 自定义遭遇 | — | 自带上限 10 |
| [NPC Spawner](https://www.nexusmods.com/eldenring/mods/11612)（1.17.2） | DLL 按 NpcParam 生成，可选 Ally/Neutral/Hostile | — | 自建生成，不走骨灰路径 |
| [NPC Spawner and Control](https://www.nexusmods.com/eldenring/mods/11400) | ALLY 模式「follows you like a Spirit Ash，丢了会 warp」 | — | 已适配 1.17.2/2.7.2.0，最接近我们的「DLL 直接生成」 |
| [20 Mimic Tears](https://mein-mmo.de/en/elden-ring-player-sends-an-army-of-20-mimic-tears-into-battle-even-pulverizing-bosses,816281/) | 复制行 ×20 | 否（同一骨灰） | 娱乐向，性能差 |

### 3.4 性能
- 原版单骨灰最多 5 体；社区经验 **≤10 体**基本安全，Spirit Battler 直接设 10 上限。
- 每个 buddy 都是完整 c0000（AI + 动画 + 碰撞），Boss 战 10+ 体会掉帧、AI 互相卡位。
- **建议 3–6 体**（3 个「自己」正好）。

### 3.5 实验清单
1. 纯参数：复制 3 行 BuddyParam（不同 npcParamId），共用 triggerSpEffectId → 一次召唤出 3 个。
2. 把 3 行的 `x_offset/z_offset/y_angle` 调成三角站位，看是否围在玩家身边。
3. 用 DLL 在生成后把 3 个实体的 `ChrAsm` 改成不同装备，验证「一行一个 profile」。
4. 装 Spirit Multiplier（离线）测试「两次召唤 / 两个骨灰并存」的稳定性与冲突（它同时改了区域/重召，注意别和我们的补丁打架）。

---

## 4. 对路线图的修订

| 阶段 | 新增内容 | 验收 |
|---|---|---|
| **M1** | 追加：多行 BuddyParam 扇出（3 体）、`enableNaviFlg_Ladder`、`overwriteReturnRange` | 一次召唤 3 个 c0000，能跟、能过梯（有动画时） |
| **M1.5** | 骑乘实验：`npcParamId_ridden` → Torrent/马 | 召唤即骑乘，跟得上玩家马速 |
| **M2** | 载体克隆（不变）+ 3 个 profile 映射 | 3 个同伴外观/装备各自不同 |
| **M3** | 存档导入（不变） | 任意槽角色可召唤 |
| **M4** | LLM 权重（不变）+ 跟随状态机 | 权重生效；warp 只在兜底时发生 |
| **M5** | 自定义 Lua AI 脚本（可选，追求「永不传送」） | 过梯/骑马/战斗全原生 |

**风险更新**
| 风险 | 说明 | 缓解 |
|---|---|---|
| `pcFollowType` 语义未知 | 0/1 到底做什么没人写清楚 | 先 A/B 实测，不写死假设 |
| 梯子动画缺失 | c0000 有全套玩家动画，理论上最好；其他模型不一定 | 只用 c0000 做同伴 |
| Torrent 玩家专属 | NPC 骑 Torrent 可能被引擎拒绝 | 用 `c4360` 骑士马做备选 |
| 多体性能 | >10 体不稳 | 默认 3 体，上限 6 |
| DLL 补丁与 mod 冲突 | Spirit Multiplier 也改 exe | 二选一，或自己做兼容层 |
| Lua 脚本方案 | 需逆向 DSLua，版本更新易坏 | 放 Phase 4，非 MVP |

---

## 5. 参考
- Paramdex：[NpcThinkParam](https://github.com/soulsmods/Paramdex/blob/master/ER/Defs/NpcThinkParam.xml) · [BuddyParam](https://github.com/soulsmods/Paramdex/blob/master/ER/Defs/BuddyParam.xml) · [BuddyStoneParam](https://github.com/soulsmods/Paramdex/blob/master/ER/Defs/BuddyStoneParam.xml) · [RideParam](https://github.com/soulsmods/Paramdex/blob/master/ER/Defs/RideParam.xml)
- paramdef 注释：[NPC_THINK_PARAM_ST](https://dasaav-dsv.github.io/libER/de/dd2/structfrom_1_1paramdef_1_1NPC__THINK__PARAM__ST.html) · [BUDDY_PARAM_ST](https://dasaav-dsv.github.io/libER/dd/d74/structfrom_1_1paramdef_1_1BUDDY__PARAM__ST.html) · [BUDDY_STONE_PARAM_ST](https://dasaav-dsv.github.io/libER/d1/d13/structfrom_1_1paramdef_1_1BUDDY__STONE__PARAM__ST.html)
- Chr ID 表：[Smithbox Info - Chr IDs](https://github.com/vawser/smithbox/blob/master/Documentation/Game%20Information/ER/Info%20-%20Chr%20IDs.txt)（`c0000` 玩家、`c8000 Torrent`、`c4360-66` 骑士马）
- 骨灰行为改进：[Age of Spirits](https://www.nexusmods.com/eldenring/mods/5641) · [Better Spirit Ashes](https://www.nexusmods.com/eldenring/mods/3905)（作者：爬梯/跳跃需要动画，否则 warp） · [Spirit Tuning](https://www.nexusmods.com/eldenring/mods/9168)（电梯 warp 现象）
- 多召唤：[Spirit Multiplier](https://www.nexusmods.com/eldenring/mods/11168) · [Nexus 教程](https://forums.nexusmods.com/topic/13495284-simple-guide-to-increasemix-summons-in-elden-ring/) · [Spirit Battler](https://www.nexusmods.com/eldenring/mods/3150) · [NPC Spawner](https://www.nexusmods.com/eldenring/mods/11612) · [NPC Spawner and Control](https://www.nexusmods.com/eldenring/mods/11400)
- AI 结构：[Low-tech AI of Elden Ring](https://nega.tv/posts/low-tech-ai-of-elden-ring.html)（Lua goal 栈）· [DSLuaDecompiler](https://github.com/nex3/DSLuaDecompiler) · [EMEDF](https://soulsmods.github.io/emedf/er-emedf.html)（无 buddy/follow 指令）
- 爬梯实例：[Escapist 评测](https://www.escapistmagazine.com/elden-ring-ladder-fighting/) · [黑骑士骨灰（3DM）](https://mod.3dmgame.com/mod/218655)
- 骑乘：[RideParam](https://github.com/soulsmods/Paramdex/blob/master/ER/Defs/RideParam.xml) · [SummonBuddyGroup.has_mount](https://docs.rs/eldenring/0.14.0/eldenring/cs/struct.SummonBuddyGroup.html) · [CSChrRideModule](https://docs.rs/eldenring/0.14.0/eldenring/cs/struct.CSChrRideModule.html) · Latenna 骑狼：[Nexus 656](https://www.nexusmods.com/eldenring/mods/656) / [6467](https://www.nexusmods.com/eldenring/mods/6467) · [夜之骑兵 Remount](https://tarnished.app/enemies/night-s-cavalry) · [Torrent of Ashes](https://melty.gg/m/torrent-of-ashes) · [Ride Anywhere](https://www.nexusmods.com/eldenring/mods/10749)
- Companion 框架：[Un-Alone](https://www.nexusmods.com/eldenring/mods/8046) · [Tarnished Tool](https://github.com/borgCode/TarnishedTool)
