# 褪色残响 · ER Echo
## 艾尔登法环「跨存档 AI 战友」MOD 技术方案 v0.2

> 目标：召唤**你自己另一个存档里的角色**作为同伴，外观/装备/属性一致；战斗由**游戏原生 AI** 驱动（不用 LLM 逐帧操控），LLM 只做「战斗导演」——每 1–3 秒调一次行为权重、偶尔换装/加点；跟随行为参考骨灰，掉队就传送到主角身边。
>
> 本文件是**研究 + 设计**，不是已跑通的成品。文中所有「已验证 / 待验证 / 不确定」都按调研证据标注；代码骨架未经编译验证。

---

## 0. 一页结论

| 问题 | 结论 |
|---|---|
| 技术上能不能做？ | **能**，而且比预想简单：法环的「骨灰」本身就是「召唤一个 c0000（玩家模型）NPC + 跟随 AI + 传送」的现成系统。 |
| 最难的三个点 | ① 把**任意存档**的外观（FaceData 0x12F）与装备灌进 NPC；② 把 LLM 的「权重」映射到**真实存在的 AI 参数**上；③ 跨区域常驻跟随（引擎会在非召唤区解散骨灰）。 |
| 最省事的 MVP | **拟态泪滴（Mimic Tear）当载体**：先让玩家角色的运行时外观/装备临时变成目标存档角色 → 召唤泪滴（它会完整复制）→ 立刻还原玩家。得到「目标角色外观 + 装备 + 原生玩家式 AI + 骨灰跟随」的同伴，几乎不用碰未公开函数。 |
| 一次能召几个 | **原生就能一个骨灰出多个**：N 行 `BuddyParam` 共用同一个 `triggerSpEffectId`，每行生成一个 NPC（Wandering Nobles 5 体就是这么做的）。「两个骨灰同时存在」才需要 DLL 补丁。 |
| 能骑马吗 | **数据层可行**：`BuddyParam.npcParamId_ridden` 就是「被骑乘方」；Torrent = `c8000`，`RideParam` 定义骑手↔坐骑的动画/判定，玩家↔Torrent 的行已存在。先测「召唤即骑乘」。 |
| 跟随会不会总传送 | 原生 buddy AI 在「路径失败/电梯/大落差/换区/雾门」时 warp；`BuddyStoneParam.overwriteReturnRange` 可调归返距离，但**「永不传送」只能靠自定义 Lua AI 或 DLL**。详见 [follow-mount-multi.md](follow-mount-multi.md)。 |
| LLM 怎么调权重 | 法环有 **`NpcAiBehaviorProbability`（约 200 个 int16 槽，按情境给动作打分）** 和 **`AiOddsParam`（act0..act99 动作比率）**，这就是天然的「行为权重表」；再叠加 `NpcThinkParam`（感知/交战距离/回巢）与 `NpcParam`（喝药概率等）。运行时用 `SoloParamRepository::get_mut` 直接写，**数字类参数即时生效**。 |
| 主技术栈 | **Rust + [`eldenring` crate 0.14](https://docs.rs/eldenring/0.14.0/eldenring/) + me3/ModEngine2 加载**。该 crate 的 `rva.rs` 明确只接受 `exe 2.7.2.0`（= 1.17.2），与本机版本**完全一致**。 |
| 本机现状 | 游戏 1.17.2（`eldenring.exe` 2.7.2.0）+ 全 DLC；`modengine2/` 2.1.0 残留但 `bin/` 为空；有 Seamless Co-op 存档痕迹；**没有 C++/Rust 编译器**（需要先装）。 |
| 合规红线 | **只能离线**（EAC 关闭）。带 mod 存档上线 = 隔离匹配池/soft-ban。任何情况下不要把改过的 `.sl2` 同步到线上。 |

---

## 1. 需求 → 能力拆解

| 需求 | 游戏内对应机制 | 实现手段 | 难度 |
|---|---|---|---|
| 召唤另一个存档的角色 | `c0000` 玩家模型 + `NpcParam`/`CharaInitParam` + `BuddyParam` | DLL 注入 + param 行 | 中 |
| 外观一致 | `FaceData`（0x12F 自描述块）+ 召唤瞬间复制 | 离线读档 + 运行时覆盖 | 中高 |
| 装备一致 | `ChrAsm.equipment_param_ids[22]` | DLL 写入 | 低 |
| 属性/等级 | `NpcParam.hp/def_*` 或 `PlayerGameData` | DLL 写入 | 中 |
| 不用 LLM 驱动作 | 原生 AI 输出「虚拟手柄输入」：`NpcAiActionParam`（moveDir/keys/hold） | 直接复用 | 零（白送） |
| LLM 实时调权重 | `NpcAiBehaviorProbability` / `AiOddsParam` / `NpcThinkParam` | 运行期写 param | 中 |
| 骨灰式跟随 | `BuddyParam.pcFollowType` + `NpcThinkParam.isBuddyAI=1` + `teamType=47` | param + DLL | 低 |
| 过远传送 | ✅ 引擎自带（前提：召唤体复刻骨灰本体行） | 距离检测 + 告警 | 低 |
| LLM 换装/加点 | `ChrAsm` / `NpcParam` | 工具调用白名单 | 低 |

> 一句话：**把「骨灰」当外壳，把「拟态泪滴」当复制器，把「NpcAiBehaviorProbability」当调音台，把 LLM 当调音师。**

---

## 2. 本机环境事实（2026-11-15 实测）

| 项 | 值 |
|---|---|
| 游戏路径 | `D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game` |
| exe | `eldenring.exe` ProductVersion **2.7.2.0**（= 1.17.2，含 SotE） |
| 数据 | `Data0-3.bdt`、`DLC.bdt`、`sd/`（约 78 GB） |
| 加载器 | **ModEngine2 2.1.0 已安装**（2026-11-15）：`modengine2_launcher.exe` + `modengine2/` + `launchmod_eldenring.bat`；`config_eldenring.toml` 已指向 `er_echo.dll`（`debug=true`，`mods=[]` 先隔离测试） |
| 反作弊 | `toggle_anti_cheat.exe` + `start_game_in_offline_mode.exe`；`start_protected_game.exe.original` 有备份 |
| 存档 | `%APPDATA%\EldenRing\<SteamID>\ER0000.sl2`（28,967,888 B）+ `.co2`（Seamless）+ `.mod`/`.cnv` 变体 |
| 工具链 | **Rust 1.100.0（`stable-x86_64-pc-windows-gnu`）已装**；MSYS2 binutils 2.47（补 `as.exe`，Rust 的 dlltool 需要）在 `%USERPROFILE%\er-tools\binutils`；Python 3.11 / .NET 8 运行时 / Git / Node 有；无 MSVC/CMake |

> 结论（2026-11-15 更新）：Rust 工具链已打通，`er_echo.dll` 已编译（706 KB）+ 冒烟测试通过；剩「进游戏实测」一步。构建脚本 `mod/build.ps1`，细节见 [implementation-log.md](implementation-log.md)。

---

## 3. 法环 MOD 的五种手段（先搞清「能改什么」）

### 3.1 文件替换（最普遍）
把解包后的文件按目录结构放进 `mod/`，加载器拦截读取。ER 的容器是 `Data0.bdt`…`DLC.bdt`（BHD/BDF 索引 + BDT 数据），解包工具：
- **UXM** / **WitchyBND**（解包/重打包 BND、DCX）
- **Smithbox**（[vawser/Smithbox](https://github.com/vawser/Smithbox)，DSMapStudio 的继任者，C#/GPL-3.0）：地图、param、EMEVD、文本一把梭
- **Yabber**（老一代，仍可用）

### 3.2 Param 编辑（改数值/行为）
`regulation.bin` 是全部 param 表的打包。两条路：
1. **静态**：改 `regulation.bin` → 放进 `mod/` 覆盖。适合「一劳永逸」的数值/权重预设。
2. **运行时**：DLL 里通过 `SoloParamRepository` 直接读写内存中的行，**适合 LLM 实时调参**。

> 注意：ModEngine2 的 `loose_params`（把 param 拆成单个文件）**对 ER 不生效**（官方配置里写明 Not currently supported for Elden Ring，代码也只对 DS3 注册）。ER 只能整包 `regulation.bin` 或运行时改。

Paramdex（[soulsmods/Paramdex](https://github.com/soulsmods/Paramdex)，`ER/Defs/*.xml`）给出每张表的字段名/类型/范围/说明，是主要字典；`NpcAiBehaviorProbability` 这类没有 Paramdex XML 的表，字段名取自 eldenring-rs / libER 的 paramdef 生成。

### 3.3 EMEVD / ESD（事件脚本）
地图事件、Boss 演出、NPC 对话状态机。工具 **DarkScript3**（[AinTunez/DarkScript3](https://github.com/AinTunez/DarkScript3)，JS 方言编译成 EMEVD）与 Smithbox 内置编辑器。
- EMEVD **不能**直接调用你自己的 DLL 代码（指令只按 function id 调引擎函数），但可以**置事件旗标**让 DLL 轮询，或让 DLL 触发事件。
- 本方案：MVP 不需要写 EMEVD；召唤走「物品 → spEffect → BuddyParam」原生链。

### 3.4 原生 DLL（本方案主战场）
- **Mod Engine 2**（[soulsmods/ModEngine2](https://github.com/soulsmods/ModEngine2)，MIT，C++）：`config_eldenring.toml` 里 `[modengine] external_dlls = ["xxx.dll"]`；`launchmod_eldenring.bat` 启动（绕过 `start_protected_game.exe`，EAC 根本不注入）。**官方已停止开发**（最后 release 2.1.0，2023-09），但在 1.17.2 上仍被大量 mod 使用（未官方声明兼容）。
- **me3**（[garyttierney/me3](https://github.com/garyttierney/me3)，Rust，活跃，v0.13.x）：profile TOML，可指定独立 `savefile`、默认阻止官方匹配连接（`start_online`），更适合「mod 专用存档」。
- 注入库：**[eldenring-rs](https://github.com/vswarte/fromsoftware-rs)**（crate `eldenring` 0.14.0，MIT/Apache-2.0）。它不是 AOB 扫描，而是 **RTTI 单例 + 按 exe 版本的 RVA 表**；`rva.rs` 里 `from_lang_version` 只接受 `(EN, "2.7.2.0")` / `(JP, "2.7.2.1")`——**正好是本机版本**。
- C++ 备选：**libER**（[Dasaav-dsv/libER](https://github.com/Dasaav-dsv/libER)，Apache-2.0 with LLVM exception，按版本符号表 + 自带 updater）。

### 3.5 外部进程（不改游戏）
Cheat Engine 表、**Elden Ring Debug Tool**（Nordgaren，C#）、Smithbox 的 live 模式。适合**做实验**（手动改 ChrAsm、改 param 行看效果），不适合做产品（脆、需要点击）。

### 3.6 选型
```
静态内容（新骨灰/新 param 行/新外观预设） → Smithbox 改 regulation.bin
实时逻辑（LLM 权重/装备/跟随保底）        → Rust DLL + eldenring-rs + me3/ME2
召唤链（物品→spEffect→Buddy）             → param 行（静态）
事件（可选，剧情/入场）                    → DarkScript3
```

---

## 4. 目标系统的技术地图

### 4.1 角色对象
`ChrIns` 是所有角色基类（NPC、敌人、玩家、骨灰、幻影都继承）。玩家是 `PlayerIns`，包含：
- `chr_ins`（位置/朝向/队伍/状态）
- `player_game_data`（等级、8 维属性、HP/FP/耐力、装备、`face_data`）
- `chr_asm`（**22 个装备槽**：`equipment_param_ids[22]` + `gaitem_handles[22]`）

`ChrAsm` 的 22 槽顺序（与存档 PGD+0x58 表一致）：
`0 左手1 / 1 右手1 / 2 左手2 / 3 右手2 / 4 左手3 / 5 右手3 / 6 箭1 / 7 弩1 / 8 箭2 / 9 弩2 / 10 箭3 / 11 弩3 / 12-15 头/身/手/腿 / 16 hair(未用) / 17-21 护符1-5`

> `equipment_param_ids` 直接写就能**即时改变外观与攻击**（这是 Cheat Engine「换装」的原理），但武器强化等级是**另一套 item id**（+0…+25），不是独立字段。

### 4.2 召唤链（骨灰的本质）
```
使用骨灰物品
  → 玩家获得 triggerSpEffectId（BuddyParam.triggerSpEffectId 匹配）
  → 引擎按 BuddyParam 行生成 NPC：
       npcParamId            → NpcParam（HP/防御/掉率/喝药概率/幻影着色器）
       npcThinkParamId       → NpcThinkParam（感知/交战/回巢/是否 BuddyAI）
       npcPlayerInitParamId  → 玩家型 buddy 的初始参数（泪滴用）
       pcFollowType          → PC 跟随 & 传送类型（0/1）
       dopingSpEffect_lv0..10→ 骨灰 +0…+10 强化
  → 设 teamType（社区值 47 = 灵体召唤）
  → AI 侧 isBuddyAI=1 → 走跟随逻辑
```
关键点：**`NpcParam` 里没有 `npcThinkParamId`**（常见误解）。think 参数由 **MSB Part** 或 **BuddyParam** 指定。所以「做一个新骨灰」= 新 `BuddyParam` 行 + `NpcParam` 行 + `NpcThinkParam` 行 + 一个触发物品/spEffect。

**扇出（一次召唤多个）**：引擎会遍历**所有** `triggerSpEffectId` 等于该 spEffect 的 `BuddyParam` 行，每行生成一个 NPC，用 `x_offset`/`z_offset`/`y_angle` 排开。这就是 Wandering Nobles（5 体）的实现方式——`BuddyParam` 里**没有**数量/组字段。所以「一个骨灰召唤 3 个不同存档的自己」= 3 行 `BuddyParam`（各自不同 `npcParamId/npcThinkParamId`）+ 同一个触发 spEffect，不需要 EMEVD。

### 4.3 跟随与传送
- `BuddyParam.pcFollowType`：「PC 追従＆ワープタイプ」，只有 0/1 两档；**0/1 的具体语义没有公开文档**，必须游戏内 A/B 实测。
- `NpcThinkParam.isBuddyAI`：Buddy 专用思考，必开。
- **归返/传送距离有 param 旋钮**：`BuddyStoneParam.overwriteReturnRange`（バディ帰還距離上書き，默认 -1=代码常量）、`activateRange`（默认 100m），以及 `summonedEventFlagId` / `overwriteActivateRegionEntityId`。调大 returnRange 能显著减少「离远就回来」。
- **爬梯不是引擎禁止**：敌人会爬梯追人；`enableNaviFlg_Ladder`（默认 0）+ 该 NPC 的爬梯动画 + 导航网格三者齐全就能过梯。c0000 自带全套玩家动画，是最有希望过梯的模型；缺动画的骨灰会「退化为 warp」。
- warp 的原生触发：路径失败 / 大落差 / 电梯 / 离开召唤区 / 雾门 / 换区。**所以「永不传送」靠 param 做不到**，需要 DLL 位置跟随或自定义 Lua AI（`logicId` 可指向自加载脚本）。
- **别自己写坐标**（2026-11-15 实测）：写 `PlayerIns.block_position`（克隆体这字段恒为 `(0,0,0)`）
  或 `ChrCtrl.physics_model_matrix` 都会让实体掉出世界（`y≈-400`、血量归零）。
  真正能改的是 `CSChrPhysicsModule::position`（crate 未暴露）或引擎 warp 函数。
- **正确做法是让召唤体完全复刻「骨灰本体行」**：`[summon] buddy_copy_from=20700001`
  把拟态泪滴那行 `BuddyParam` 整行复制到载体行（保留各自 trigger spEffect）。
  实测复制前掉队 42 m 后卡住不回，复制后引擎自己拉回到 1 m。详见 implementation-log §14.6。
- 想要更贴身的跟随：`keep_close --dist 15`（压 `NpcThinkParam.backhome_dist`），
  或调 `BuddyStoneParam.overwriteReturnRange`。状态机与实验清单见 [follow-mount-multi.md](follow-mount-multi.md) §1。

### 4.4 AI：原生驱动 + 权重表
法环 NPC AI 的**输出是「虚拟手柄输入」**——`NpcAiActionParam` 每行就是 `moveDir + key1/2/3 + 长按标记 + 手势`。所以「玩家式战斗」（翻滚、喝药、战技、法术）不是靠 LLM 生成动作，而是靠**行为表 + 装备**。

权重在三层：

| 层 | 表 | 作用 | 实时性 |
|---|---|---|---|
| 情境动作打分 | **`NpcAiBehaviorProbability`**（约 200 个 int16，如 `param000..param199`；社区常用标注只覆盖前 ~130） | 每个情境下各动作的分数：连段/翻滚/防御/喝药/施法/接近 | **每次决策读取，最可能即时** |
| 动作比率 | **`AiOddsParam`**（`act0..act99`，0–100） | 动作池的比率 | 即时 |
| 感知/交战 | `NpcThinkParam`（eye/searchEye/BattleStartDist/backhome/TeamAttackEffectivity…） | 索敌、开战、追击、围攻人数 | 角色初始化时建立，**已有个体可能不刷新**（待实测） |
| 数值/喝药 | `NpcParam`（hp/def/`estusFlaskLotPoint`/`guardAngle`…） | 数值与喝药概率 | 即时 |

### 4.5 外观：FaceData
`face_data` 是 **0x12F 自描述块**（`marker=-1` + magic `FACE` + size `0x120`）：
```
0x00 marker(-1) | 0x04 'FACE' | 0x0C size(0x120)
0x10  8 × 模型 id（脸/发/眼/眉/须/饰品/贴花/睫毛）
0x30  64 B 五官结构滑条
0x70  64 B FaceGen 参数（创建界面不暴露）
0xB0  7 B 体型缩放（头/胸/腹/左右臂/左右腿）
0xB7  91 B 颜色（肤/妆/纹身/体毛/眼/发/须/眉/睫毛/饰品）
0x112 1 B 眼效果（255=癫火）
0x124 override 开关 + 2×int32（癫火 81000 / Varre 81001 …）
```
它是**可整块移植**的（自带 magic+size，无指针耦合）——所有外观 copier 都这么干。

### 4.6 骑乘（同伴骑马）
- **Torrent 身份有冲突资料**：Smithbox Chr IDs 写 `c8000 Torrent`、`ChrIns.npc_id` 文档举例「8000 for Torrent」；另有调研称游戏包内是 `chr/c2600.chrbnd` + `c2640.anibnd`。NpcParam 社区多标 `80000000`。**用 Smithbox 打开 `regulation.bin` 核对**。马匹另有 `c3160`（夜之骑兵马）、`c4360`–`c4366`（各骑士马）。
- **骑乘是数据驱动的**：`RideParam` 每行定义 `atkChrId`（骑手）↔ `defChrId`（坐骑）、双方动画变量、对齐/判定 dummy poly、距离/角度/高度容差。玩家就是 `c0000`，所以 `c0000 ↔ Torrent` 的行已存在——**c0000 NPC 骑同类坐骑的动画与判定是现成的**。
- **`BuddyParam` 原生支持「召唤即骑乘」**：`npcParamId_ridden` / `npcThinkParamId_ridden` 是「被骑乘方（坐骑）」。引擎还有群组级 `SummonBuddyGroup.has_mount`，且玩家 mod 已实证（Latenna 召狼并骑上）。关键：给同伴生成**它自己的**坐骑，不能抢玩家那只。
- **动态上马**：Torrent 是玩家专属 mount 槽（`PlayerGameData.mount_handle`），NPC 骑玩家那只不可行；夜之骑兵「马死落马 → Remount 重新召马」证明引擎支持 NPC 动态上马。但 eldenring-rs 只有只读的 `is_mounted/mount_data`，没有 `mount()` API，发起上马要逆向或走 Lua goal。
- 细节与四条路线（召唤即骑乘 / DLL 生成马 / 幻影马 / 步行提速）见 [follow-mount-multi.md](follow-mount-multi.md) §2。

---

## 5. 总体架构

```
┌───────────────────────────── 离线（Python/C#，游戏外） ─────────────────────────────┐
│  ER0000.sl2  ──解析──►  profile.json                                                 │
│                          { name, level, stats[8], equip[22], face_b64(0x12F), ... }   │
└───────────────────────────────────┬──────────────────────────────────────────────────┘
                                    │ 读取
┌───────────────────────────────────▼──────────────────────────────────────────────────┐
│  Python Sidecar（director.py）                                                        │
│   ├─ StateCompactor：把游戏状态压成 <400 token JSON                                   │
│   ├─ Scheduler：1–3 s tick + 事件触发；单飞（in-flight=1）；状态哈希去重               │
│   ├─ LLMClient：本地 Ollama/llama.cpp 或 OpenAI 兼容 API                              │
│   ├─ Guardrails：JSON Schema → clamp → 变化率上限 → 白名单 → 迟滞                     │
│   └─ 工具：set_weights / set_equipment / set_stats / set_strategy（全部白名单）        │
└───────────────────────────────────┬──────────────────────────────────────────────────┘
                                    │ NDJSON over TCP 127.0.0.1:7811（带 token）
┌───────────────────────────────────▼──────────────────────────────────────────────────┐
│  er_echo.dll（Rust，me3/ME2 注入，运行在游戏主线程 hook 上）                            │
│   ├─ IPC：非阻塞收包 → 原子变量存最新 weights                                          │
│   ├─ CloneManager：召唤/销毁/找回载体                                                  │
│   ├─ ProfileApplier：ChrAsm 22 槽、PlayerGameData 属性、FaceData 缓冲                  │
│   ├─ ParamTuner：SoloParamRepository::get_mut → 写 NpcAiBehaviorProbability/NpcThink...│
│   ├─ FollowGuard：距离/区块检测 → 保底 warp                                           │
│   └─ Telemetry：HP/距离/事件 → 回传 sidecar                                            │
└───────────────────────────────────┬──────────────────────────────────────────────────┘
                                    │ eldenring-rs（RTTI + 版本 RVA）
                              ELDENRING.exe（EAC off，离线）
```

**双环原则**：快环 = 游戏原生 AI（60 fps，零延迟）；慢环 = LLM（1–3 s，只调「旋钮」）。**任何情况下不在帧循环里等网络**。

---

## 6. 实现路线（按风险/成本排序）

### 路线 A′：骨灰授权召唤 + 召唤后注入（**已实测，推荐**）
思路：玩家正常用骨灰（引擎授权召唤），DLL 在 `summon_buddy_chr_set` 里找到人形克隆体，
**直接往克隆体自己的 `PlayerGameData` / `ChrAsm` 里写档案**。

```
1) 运行时把骨灰的 BuddyParam 行指向 Mimic 人形参数（npc=100000010, init=26050, follow=2）
2) 玩家在召唤石旁用骨灰 → 引擎生成授权召唤物（渲染/权限/跟随全部原生）
3) DLL 每 15 帧扫描 buddy 集合里的 PlayerIns → 写 face(276B) + ChrAsm(22 槽) [+ level/stats]
4) 多档案：第 i 个克隆体套第 i % n 个 profile（set_clone_profiles）
```

实测依据（`clone_info`）：`100000010` 的 `is_player_ins=true`，自带 `FACE` 缓冲与 `chr_asm`；
默认脸是 `0x65...`（CharaInit 默认），与玩家自己的 `0x09...` 不同 ⇒ 注入可验证。

优点：**完全不改玩家**（无闪烁/无还原风险）；可以按实例区分存档；不需要模型重建函数。
缺点：仍要玩家用一次骨灰（授权召唤）；引擎变身/重招可能覆盖，需要持续注入（已实现 15 帧一次）。

### 路线 A：拟态泪滴载体 + 运行时覆盖（旧方案，保留作 fallback）
思路：利用「泪滴在召唤瞬间完整复制玩家外观/装备/属性」这一原生特例。

```
1) DLL 保存玩家当前 profile（ChrAsm + PlayerGameData + FaceData buffer）
2) DLL 把玩家运行时数据覆盖为目标存档 profile
3) 触发召唤 Mimic Tear（原生物品/事件；或复用其 BuddyParam 行）
4) 泪滴生成 → 复制完成
5) DLL 立刻把玩家数据还原（1 帧内，玩家只会闪一下）
6) 对泪滴实体做收尾：teamType=47、phantomShaderId=白灵、名字 roleNameId、跟随参数
```
优点：完全绕开「给 NPC 应用脸部数据」的未公开函数；泪滴自带玩家式 AI + 骨灰跟随；MVP 一周内可见。
缺点：依赖泪滴这个特例（版本更新可能变）；玩家外观会闪 1 帧；「先改玩家再还原」在异常退出时有风险 → 必须先备份 + 写前校验。

> 存档侧配合：如果不想动运行时 FaceData，可先把目标外观写进**当前活跃槽**（离线、可回滚），进游戏召唤后再还原存档。savefmt 调研认为这是「目前唯一不依赖未公开函数的可靠组合」。

### 路线 B：自定义 BuddyParam + 骨灰召唤链（param-only 验证）
```
复制 Mimic Tear 的 BuddyParam 行 → 指向自定义 NpcParam（复制 c0000 行）
  → npcThinkParamId 指向自定义 NpcThinkParam（isBuddyAI=1）
  → 绑一个新物品/spEffect 触发
```
优点：零 DLL 就能验证「c0000 + 跟随 + 战斗」是否成立；也是最终产品的**召唤外壳**。
缺点：外观/装备是静态的（无法读别的存档），只能验证机制。

### 路线 C：DLL 直接生成 c0000 + 全字段注入（终态）
用 `CSDebugChrCreator`/生成请求直接创建一个 c0000 NPC，然后：
- 写 `ChrAsm` 22 槽（装备）
- 写 `PlayerGameData`（等级/属性/HP）
- 写 `FaceDataBuffer`（外观）→ **需要触发模型重建**（未公开，需 RE）
- 设 `teamType`、`phantomShaderId`、`BuddyParam` 关联

优点：不依赖泪滴、可多克隆、可跨区域常驻。
缺点：脸部写入 + 模型重建是唯一没被公开验证的一环，RE 成本高；`CSDebugChrCreator` 是调试路径，稳定性未知。

| | A′ 召唤后注入 | A 泪滴载体 | B param 骨灰 | C 直接生成 |
|---|---|---|---|---|
| 改玩家外观 | ❌ 不用 | ✅ 要（+还原） | ❌ | ❌ |
| 读别的存档外观 | ✅ | ✅（借复制） | ❌ | ✅ |
| 原生 AI | ✅ | ✅ | ✅ | ✅ |
| 跟随/传送 | ✅ 原生 | ✅ | ✅ | 需自己接 |
| 多存档同场 | ✅（按实例注入） | ❌（复制的是玩家） | ❌ | ✅ |
| 工作量 | 低（已实现） | 中 | 低 | 高 |
| 版本脆弱性 | 低 | 中 | 低 | 高 |
| 建议 | **已用** | 备用 | 验证用 | 后做 |

### 路线 B+：多行 BuddyParam 扇出（一次召唤 3 个）
```
3 行 BuddyParam，共用同一个 triggerSpEffectId
  行1: npcParamId=c0000_echo_a / npcThinkParamId=think_a / x_offset=-1.5
  行2: npcParamId=c0000_echo_b / npcThinkParamId=think_b / x_offset= 0
  行3: npcParamId=c0000_echo_c / npcThinkParamId=think_c / x_offset=+1.5
```
- 纯参数即可「一次召唤多个」；每行独立 `NpcParam/NpcThinkParam`，互不干扰（解决 v0.1 说的「共享行冲突」）。
- 想按存档区分：DLL 在生成后把每个实例的 `ChrAsm`/`FaceData` 覆盖成对应 profile（行只是「槽位」，profile 是运行时数据）。
- 想「多个骨灰并存」：需要 DLL 补丁（参考 [Spirit Multiplier](https://www.nexusmods.com/eldenring/mods/11168)），或自己绕过 exe 的「已有 buddy」检查。

### 路线 D：DLL 直接生成（NPC Spawner 式）
参考 [NPC Spawner](https://www.nexusmods.com/eldenring/mods/11612)（支持 1.17.2）与 [NPC Spawner and Control](https://www.nexusmods.com/eldenring/mods/11400)（ALLY 模式、跟随、丢了会 warp）。优点是不依赖骨灰物品/召唤区；缺点是没有骨灰血条、死亡/换区清理要自己做、`teamType`/`pcFollowType` 要手动接。适合做「常驻同伴」而不是「骨灰」。

---

## 7. 存档 → 角色档案（离线）

### 7.1 `.sl2` 真实结构（v1.17.2）
| 偏移 | 内容 |
|---|---|
| `0x00` | BND4 头（12 entries，数据起点 `0x300`） |
| `0x40` | 12 × 0x20 entry 表 |
| `0x1C0` | entry 名 UTF-16：`USER_DATA000`…`USER_DATA011`（**无下划线**） |
| `0x300 + k·0x280010` | 槽 k（k=0..9）：`0x10` MD5 + `0x280000` 角色数据 |

- `USER_DATA010`（0x60010）：全局（Settings、`MenuSystemSaveLoad` 内 **15 个外观预设** `0xFACE`、`ProfileSummary`、按键等）
- `USER_DATA011`（0x240020）：regulation 快照（DCX 压缩）
- 校验：每槽**只有 MD5**（覆盖其后 0x280000），另有 `PlayerGameDataHash`（Adler-32 变体，只覆盖 level/8 属性/职业/vow/runes/装备 id，**不含脸**）
- **PC 端 `.sl2` 实际未加密**（明文 BND4）。流传的 `99 AD 2D 50…` 是 DS3/Nightreign 的 key，不要误用。

> 结论：**读档不需要破解**，只需要正确的偏移链；难点在 `gaitem_map` 变长表之后的动态偏移，**不要硬编码绝对偏移**。

### 7.2 要抽取的字段
| 字段 | 位置（相对 `player_game_data`） |
|---|---|
| 8 维属性 | `+0x34..0x50`（Vig/Mind/End/Str/Dex/Int/Fai/Arc，u32） |
| 等级 / 卢恩 / 记忆 | `+0x60` / `+0x64` / `+0x68` |
| 角色名 | `+0x94`，32 B UTF-16LE |
| 体型 / 出身 / 骨灰强化 | `+0xB6` / `+0xB7` / `+0xBF` |
| 幽影树 / 灵灰祝福 | `+0xF4` / `+0xF5` |
| 装备 22 槽 | `+0x58` 表（见 4.1 顺序） |
| 背包/仓库 | `+0x9010` / `+0x6010`（12 B 记录：handle+qty+index） |
| 记忆法术 14 槽 | `+0x93B4`：14 × `(param_id: i32, charges: i32)`，空槽 `(-1, 0)`、已装备 `(id, -1)`（v1.17.2 实测，见 implementation-log §16；早期写的 `+0x74` 是错的） |
| 外观 | 沿 `滴露(+0x0C)` 之后继续走，`face_data` 在**相对上一段的 +0x12F 处**（不是 PGD 绝对偏移，必须顺序 walk） |

### 7.3 FaceData 可移植性
整块 0x12F 拷贝即可（自带 magic/size）。需要同步：
1. `body_type`（0xB6）与预设头部模型 0x09 一致；
2. 重算目标槽 MD5；
3. 想让读盘界面也对，还要改 `USER_DATA010.ProfileSummary` 的 face 副本（`+0x36`，0x124 B）。
改脸**不需要**重算 `PlayerGameDataHash`。

### 7.4 工具链
| 工具 | 语言 | 用途 |
|---|---|---|
| [ER-Save-Lib](https://github.com/ClayAmore/ER-Save-Lib) | Rust | 最完整的社区解析库（可当参考/依赖） |
| [er-save-manager](https://github.com/Hapfel1/er-save-manager) | Python | 解析/重序列化/hash/`.sl2↔.co2`/`.erc` 角色导出 |
| [ER Save Manager (Soar Qin)](https://www.nexusmods.com/eldenring/mods/9571) | 闭源 | 图形化槽导入导出、face data 15 槽、NPC 脸预设、明确支持 1.17.1/1.17.2 |
| [Elden Ring Appearance Copier](https://www.nexusmods.com/eldenring/mods/11076) | 闭源 | 外观复制 + `eldenblingsliders` JSON |
| [soulsformatsNEXT](https://github.com/soulsmods/soulsformatsnext) | C# | 只能拆 BND4/DCX/PARAM，**不含存档语义** |

**建议**：MVP 阶段别自己写解析器——用 `er-save-manager` 导出 `.erc`/JSON，或直接复用 ER-Save-Lib；自己写只做「读 0x12F + 装备表」的最小 walker。

### 7.5 风险
- 槽版本（slot version 261/262）随版本变化；写回前校验。
- `ProfileSummary` 不同步 → 读盘界面显示旧脸（不影响进游戏）。
- 备份/原子写（tmp + rename）；`.co2` 单独处理，别把 Seamless 专属物品写回 `.sl2`。

---

## 8. 召唤与跟随

### 8.1 召唤（路线 B 的 param 清单）
最小可验证改动（只改 `regulation.bin`）：
1. 复制 Mimic Tear 的 `NpcParam`（社区值 `133201000`，**待核实**）→ 新行 `c0000_echo`
2. 复制 `NpcThinkParam`（`133200000`）→ 新行，改 `isBuddyAI=1`、`BattleStartDist`、`TeamAttackEffectivity`、`backhome*`
3. 复制 `BuddyParam` 行 → `npcParamId`/`npcThinkParamId` 指向新行，`pcFollowType=1`
4. 用 Smithbox 把它挂到一个不用的骨灰物品（或复制物品行 + `refId`）
5. 进游戏召唤 → 观察：是否 c0000、是否跟随、是否用武器/战技、是否会 warp

### 8.2 跟随/传送（v0.2：传送降级为兜底）
- 原生：`pcFollowType=1` + `isBuddyAI=1` + `teamType=47`；引擎负责跟随 + 失败回退。
- param 层减少 warp：`enableNaviFlg_Ladder/Door/Hole=1`、`enableJumpMove=1`、`disablePathMove=0`、`actTypeOnFailedPath` 调成「原地等待」、`BuddyStoneParam.overwriteReturnRange` 调大（60–120）、`activateRange` 调大。
- **状态机**（DLL/Lua 实现）：
  ```
  Follow   目标 = 玩家身后 2m，按距离分级速度
  Wait     玩家战斗外/攀爬中：梯底等待，不 warp
  Climb    玩家上梯：navi+动画允许则跟；否则 Wait 到玩家到顶再 warp
  CatchUp  距离 > 15m 加速；> 25m 且路径失败 > 3s：预判 warp
  Warp     仅当：路径失败 / block 变化 / 电梯 / 雾门 / 距离 > returnRange
  Mounted  玩家骑马：切骑乘形态（§8.4）
  ```
- 铁律：**warp 前确认玩家不在看它**（或在读图），避免「眼睁睁闪现」。
- warp 实现优先级：① 引擎 warp 函数（RVA，需 RE）；② 写 `ChrIns` 坐标/`block_id` 后触发重定位（eldenring-rs 暴露字段）；③ EMEVD `WarpCharacterAndSetFloor`（仅适合脚本化传送点）。
- 跨区域：骨灰在非召唤区会消散（雾门强制消失）。常驻方案 = 路线 D（DLL 自建实体），不绑区域，但要自己处理死亡/换区/血条。

### 8.3 死亡/消散/重召
- 监听 `ChrIns` HP/死亡事件 → 播放消散特效 → 可选择冷却后重召。
- 重召 = 重新执行路线 A/B 的召唤流程；确保旧实体的 `ChrAsm`/param 覆盖被清理。

### 8.4 骑乘（同伴骑马）
- **先做 M1（纯 param）**：复制 BuddyParam → `npcParamId_ridden` 指向**坐骑**的 NpcParam（Torrent 社区标 `80000000`，待 Smithbox 核对；也可先用 `c4360` 骑士马），坐骑 ThinkParam 设 -1、生成偏移贴近；召唤看是否「人马一体」。
- 有 Latenna 骑狼先例（Nexus 656/6467）+ 引擎 `SummonBuddyGroup.has_mount`，可行但 jank 风险中等（上马动画、坐骑血量、warp 时分离）。
- 失败则 M2（DLL 生成**同伴自己的**坐骑 + 逆向骑乘初始化）或 M3（幻影马：`c4360` + 白 phantom shader）。
- 玩家上下马联动：上马 → 同伴切骑乘形态；下马 → 可保持骑乘；进洞窟/禁马区 → 自动下马。
- 细节见 [follow-mount-multi.md](follow-mount-multi.md) §2。

### 8.5 多召唤（一个骨灰出多个）
- 原生扇出：N 行 BuddyParam 共用 `triggerSpEffectId`（§4.2），每行独立 `NpcParam/NpcThinkParam`；用 `x_offset/z_offset/y_angle` 站位。
- 「两个骨灰并存」：exe 检查，需 DLL 补丁（Spirit Multiplier 先例）；不推荐与其它改 exe 的 mod 叠加。
- 性能：3–6 体为宜，>10 体不稳定（每个都是完整 c0000）。
- 细节见 [follow-mount-multi.md](follow-mount-multi.md) §3。

---

## 9. 战斗 AI 与 LLM 权重

### 9.1 为什么不让 LLM 驱动作
- 延迟：本地 7B 端到端 500–800 ms，云 300–600 ms；游戏帧 16 ms。
- 稳定性：LLM 输出抖动 → 角色抽搐。
- 成本：每秒 1 次调用，一小时 3600 次。
- 结论：**LLM 只做「慢环」策略/权重**，动作由原生 AI 以 60 fps 执行。

### 9.2 权重维度（10 维，0–100）
| 维度 | 含义 | 主要落点 |
|---|---|---|
| `aggression` | 主动开战/追击 | `NpcThinkParam.BattleStartDist`、`eye_dist`、`backhomeDist` |
| `dodge_rate` | 翻滚/侧移频率 | `NpcAiBehaviorProbability` 101/102/103/110/111/116/120/121 |
| `guard_rate` | 举盾/防御 | `isGuard_Act`、105/112/113/118、`guardAngle` |
| `combo_rate` | 连段倾向 | 000/001/115 |
| `heal_priority` | 喝药/回血 | 023/097 + `NpcParam.estusFlaskLotPoint` |
| `spell_rate` | 法术使用 | 013/014/020–028 |
| `item_rate` | 道具使用 | `NpcParam.estusFlask*LotPoint` + goods |
| `spacing` | 保持距离/拉扯 | 126、010/011、`BattleStartDist` |
| `target_switch` | 换目标 | `TeamAttackEffectivity`、`searchTargetLv*ForgetTime`、`disablePCTargetShare` |
| `follow_distance` | 跟随紧密度 | **无 param，需 DLL** |

> 槽位编号来自社区对 `NpcAiBehaviorProbability` 的标注（Parrytime/Damaged/Guard/Estus/R1 combo 等），**必须逐条实测**；本方案把它们放在 `config/behavior_map.yaml` 里，方便校准。

### 9.3 写入策略
```
新值 = clamp(target, min, max)
新值 = prev + clamp(新值 - prev, -max_delta, +max_delta)   # 变化率 ≤ 15%/tick
if |新值 - prev| < 3: 不写（迟滞，避免抖动）
每 3 个 tick 才允许切换 strategy（防抖）
```
- **per-instance 冲突**：param 行是全局共享的。如果同时存在两个克隆体，改同一行会互相影响。解决：为每个克隆体分配**独立的 param 行**（预生成 N 份副本），或只在单克隆时使用。
  > **2026-11-22 落地**：三个号位各借一行 `NpcThinkParam`（默认 `100000020/30/40`），
  > 同步时把全局行（`think_row`）整行按字节复制过去、再只覆盖该号位的
  > `aggression / guard_rate / target_switch` 字段（`params::clone_think_row` +
  > `write_think_weights`）—— 就是「预生成 N 份副本」的运行时版本。
  > `spell_rate` 仍落在每个克隆体自己的记忆槽上，所以它立即生效。见 implementation-log §26。
- `NpcThinkParam` 的 think 实例在角色初始化时建立，**对已存在个体可能不刷新** → 感知类权重需要「重召生效」，或改成 hook。
- 每次写入记日志（旧值/新值/来源），方便回滚与调参。

### 9.4 没有对应参数的维度
- `follow_distance`：DLL 自己控制（距离阈值 + warp）。
- 精确的「攻击欲望/技能选择」：Phase 3 用 hook 拦截 AI 决策函数，或在 `NpcAiBehaviorProbability` 上做映射实验。

---

## 10. LLM 接入

### 10.1 双环与节奏
```
每 0.5 s：DLL 采样状态（HP/距离/敌人/事件）→ 环形缓冲
每 1–3 s：sidecar 取最新状态 → 压缩 → LLM → 权重
每 tick：DLL 读原子变量 → 平滑写入
事件触发（玩家 HP<30%、敌人死亡、进入 Boss 房）：立即插队一次
```

### 10.2 协议（NDJSON over TCP）
- `127.0.0.1:7811`，启动时随机 token，握手校验；只 bind loopback；消息 ≤ 64 KB。
- 心跳 2 s；断线 → DLL 用 last-known-good 权重继续。
- 消息示例：
```json
{"v":1,"type":"state","seq":42,"t":1731.4,
 "player":{"hp":0.62,"stam":0.31,"flask":3},
 "enemy":{"id":"margit","hp":0.44,"poise":0.8,"dist":3.2},
 "events":["hit_taken","guard_broken"],
 "last":{"aggression":0.5,"dodge_rate":0.4}}
```
```json
{"v":1,"type":"weights","seq":42,
 "weights":{"aggression":0.62,"dodge_rate":0.55,"heal_priority":0.7},
 "strategy":"punish_after_combo","reason":"player low stamina","confidence":0.71}
```

### 10.3 Prompt（战斗导演）
- 系统提示：角色设定（同伴姓名/性格）、可用旋钮及范围、约束（只输出 JSON）、禁止事项。
- 用户消息：压缩状态 + 最近 8 条事件 + 上次权重 + 时间。
- 输出：`weights`（0–1 浮点）+ `strategy`（枚举）+ 可选 `loadout`（白名单 id）+ `say`（一句短台词，可选）。
- 稳定性：temperature 0.2–0.4；JSON Schema 强约束；拒绝自由文本指令。

### 10.4 工具调用（装备/加点）
| 工具 | 参数 | 约束 |
|---|---|---|
| `set_equipment` | `slot`, `item_id`, `upgrade` | 白名单 + 槽位枚举 + 存在性检查 |
| `set_stats` | `hp/def/attack` 或 `level` | clamp 到目标角色 ±20% |
| `set_strategy` | 枚举 | 枚举表 |
| `resummon` | - | 冷却 30 s |

每次工具调用都要有 **dry-run** 与 **回滚点**（保存旧的 `ChrAsm`/param 值）。

### 10.5 延迟预算
| 段 | 时间 |
|---|---|
| 状态序列化 + IPC | ~3 ms |
| prompt 组装 | ~5 ms |
| prefill 400 tok（本地 7B） | 150–400 ms |
| decode 24 tok | 200–400 ms |
| 校验/应用 | ~2 ms |
| **合计 p50** | **0.5–0.9 s** |
| p95 | 1.2 s（超时用 last-known-good） |

> 要 <300 ms 只能上 3B 以下 + 固定前缀 KV cache + 输出 ≤12 token，或云 mini 模型；更稳的做法是「轻反应 300 ms、重决策 1–3 s」。

### 10.6 兜底
- LLM 超时/报错 → 保持上次权重 + 规则 fallback（低血→提高 heal/guard，被围→提高 dodge）。
- 连续 N 次无变化 → 降低 tick 频率省 token。
- 权重越界/NaN → 丢弃整包。

---

## 11. 装备与「升级」

### 11.1 运行时换装
`ChrAsm.equipment_param_ids[i] = item_id`，然后让模型刷新（`ChrIns` 的 model ins 重建；换武器一般自动刷新，换护甲可能需要重载）。风险：非法 id/未持有物品可能导致 T-pose 或崩溃 → 白名单 + 存在性检查。

### 11.2 「升级」两种做法
| 做法 | 实现 | 优点 | 缺点 |
|---|---|---|---|
| 数值型 | 改 `NpcParam.hp/def_*/attack` 或 `PlayerGameData` 属性 | 简单、即时 | 没有「等级」概念，曲线不真实 |
| 等级型 | 写 `PlayerGameData.level/stats`（仅玩家型 NPC 有 PGD） | 显示真实等级、影响武器补正 | 需要重算派生值，且 c0000 NPC 是否有完整 PGD 待验证 |

MVP 用「数值型 + UI 显示虚拟等级」；后续再试等级型。

> **v0.3 已实现（2026-11-22）**：克隆体是 `PlayerIns`，等级型可用。DLL 每 30 帧对比玩家
> `PlayerGameData.level` 与 8 维基础属性、HP/FP/耐力 `base_max_*`；检测到等级上升时，把
> 本次增量按同样的加点追给所有已加载档案（保留各档案原有等级差），写回 profile JSON，
> 并立刻重写场上克隆体的 `level/stats/pools`。见 [usage.md §3.2](usage.md) 与
> [implementation-log.md](implementation-log.md) §23。

### 11.3 武器强化/战灰/法术
- 强化：直接选 `+N` 的 item id（武器 id 段内偏移）。
- 战灰：`EquipParamWeapon` 的 `gemMountType`/`refId` 关联，或直接给带战灰的武器 id。
- 法术：`ChrAsm` 的记忆槽 + `MagicParam`；NPC 用魔法还需要 `NpcThinkParam`/行为表允许施法。

---

## 12. 工程结构

```
er-echo/
├─ README.md
├─ docs/design.md                  ← 本文件
├─ config/
│  ├─ behavior_map.yaml            ← 权重 → 参数/槽位（可校准）
│  └─ weights.schema.json          ← LLM 输出 JSON Schema
├─ bridge/                         ← Python sidecar（无需编译）
│  ├─ director.py                  ← 调度 + LLM + 兜底
│  ├─ protocol.py                  ← NDJSON 帧 + 校验
│  └─ profile_reader.py            ← 读 profile.json（.sl2 解析见 tools/）
├─ tools/
│  └─ export_profile.md            ← 用现成工具导出 .erc/JSON 的步骤
└─ mod/                            ← Rust DLL（需 rustup + MSVC）
   ├─ Cargo.toml
   └─ src/
      ├─ lib.rs                    ← DllMain + 初始化 + 主循环
      ├─ ipc.rs                    ← TCP/NDJSON 客户端
      ├─ params.rs                 ← param 读写封装
      └─ profile.rs                ← profile 结构与 ChrAsm 应用
```

构建（Rust）：
```powershell
rustup target add x86_64-pc-windows-msvc
cargo build --release --target x86_64-pc-windows-msvc
# 产物 target/.../er_echo.dll → 放进 ME2 的 external_dlls 或 me3 的 [[natives]]
```

---

## 13. 里程碑

| 阶段 | 内容 | 验收 | 预估 |
|---|---|---|---|
| **M0 环境** | 装 rustup + VS Build Tools；跑通 [`fromsoftware-rs` apply-speffect 示例](https://github.com/vswarte/fromsoftware-rs/tree/main/examples) | 游戏内出现 buff + 日志 | 0.5–1 天 |
| **M1 param 验证** | Smithbox 做「自定义 BuddyParam + c0000 骨灰」；3 行扇出；打开 navi/jump 位；调 `overwriteReturnRange` | 一次召唤 3 个 c0000；能跟、能打；有动画时能过梯 | 2–3 天 |
| **M1.5 骑乘** | `npcParamId_ridden` → Torrent/马；失败则幻影马 | 召唤即骑乘，跟得上玩家马速 | 1–2 天 |
| **M2 载体克隆** | 路线 A：临时覆盖玩家 → 召唤泪滴 → 还原 | 同伴外观/装备 = 指定 profile | 2–4 天 |
| **M3 存档导入** | 离线解析 `.sl2` → `profile.json` → M2 | 任意槽角色可召唤 | 2–3 天 |
| **M4 LLM 权重** | sidecar + param 写入 + 平滑 | 战斗中权重变化可观察、不抽搐 | 3–5 天 |
| **M5 打磨** | 装备/加点工具、跟随保底、UI/热键、日志、崩溃恢复 | 连续 1 小时稳定 | 1 周 |
| **M6 游戏内 UI** | 原生 ESD 赐福菜单「战友」（人数/名单/重召）+ `LookupEntry` 消息钩子 + 置物包 F12 给装备（没选中时恢复档案原样） | 菜单能开、文字/人数/名单/给装备全链路 | 2–3 天 |

> **M4/M5 实测进度（2026-11-15）**：M4 的「可观察」已达成 —— `aggression` → 侦测/交战半径、
> `spell_rate` → 记忆槽开几发、`guard_rate` → 举盾、`target_switch` → 换目标，都有实机证据；
> 行为概率表对 player 型 AI 不生效，`combo/item/heal/spacing` 暂无落点。
> M5 已完成状态面板/日志轮转/心跳取证/安全模式/热键/重召与掉队保底；
> 待测：`lost_resummon` 真实触发、连续 1 小时稳定性。详见 implementation-log §17。
>
> **M6 进度（2026-11-15）**：`m00_00_00_00.talkesdbnd.dcx` 的 `t000001000` 已加入「战友」菜单
> （人数/名单/重召），文字由 `LookupEntry` 钩子按自定义 ID 返回（`msg_test` 实测
> `69100000 -> "战友（2/2）"`），标志 6720..6727 实测能驱动人数/名单（`flag_test`）。
> 置物包 F12 给装备已实测可写入档案（内存 profile，不写盘）并躲过 `auto_apply` 回写（`give` / `clone_info`
> 回读）；2026-11-22 起没选中项时改为恢复档案原样（见 implementation-log §22）。
> **未自动实测**：菜单视觉（合成输入打不开赐福菜单），需人工确认。详见 §18。

**风险登记**
| 风险 | 影响 | 缓解 |
|---|---|---|
| ME2 已停更，1.17.2 兼容性 | 加载失败 | 优先 me3；保留 ME2 回退 |
| 泪滴复制是版本特例 | 更新后失效 | 抽象 `CloneBackend`，可切路线 C |
| FaceData 写入崩溃 | 闪退/坏档 | 先备份、校验 0x12F、失败回滚 |
| param 共享行冲突 | 多克隆互相干扰 | 预生成独立行 |
| LLM 抖动 | 行为怪异 | clamp/迟滞/平滑/超时兜底 |
| 在线封号 | 账号风险 | 只离线；me3 `start_online=false`；不改线上档 |

---

## 14. 合规与安全
- **只离线**：EAC 关闭，`start_protected_game.exe` 被绕过；带 mod 存档上线会被隔离/soft-ban。
- **备份**：改 `regulation.bin`/`.sl2` 前必备份；写档用 tmp+rename。
- **不发布他人存档内容**：外观数据属于个人信息，分发 mod 时不要打包别人的脸。
- **不绕过在线校验**：不接官方匹配、不改 NetMan。

---

## 15. 先做这 9 个实验（按顺序，成本递增）
1. **c0000 骨灰**：Smithbox 复制 Mimic Tear 的 `NpcParam/NpcThinkParam/BuddyParam` → 挂到闲置骨灰物品 → 召唤，确认「c0000 + 跟随 + 战斗」。
2. **权重表生效**：把 `NpcAiBehaviorProbability` 的翻滚槽改 0 / 改 100，进游戏对比行为；再试 `AiOddsParam`。
3. **运行时换装**：用 Debug Tool/CE 改玩家 `ChrAsm` 槽，确认即时生效、崩溃边界。
4. **DLL 注入**：跑 `fromsoftware-rs` 示例，确认 `SoloParamRepository::get_mut` 能改行并生效。
5. **泪滴复制**：离线把另一个槽的 face 写进当前槽 → 召唤泪滴 → 看是否复刻（再还原存档）。
6. **多体扇出**：复制 3 行 BuddyParam（不同 npcParamId）共用 `triggerSpEffectId` → 一次召唤出 3 个，调 `x_offset/z_offset` 站位。
7. **爬梯**：`enableNaviFlg_Ladder=1` + `enableJumpMove=1` + `disablePathMove=0` → 地下墓地跟玩家上梯；再换一个没动画的 NPC 对比（应回退 warp）。
8. **骑乘**：`npcParamId_ridden` 填 Torrent 的 NpcParam → 召唤看是否骑马；再试 `c4360` 骑士马（见 [follow-mount-multi.md](follow-mount-multi.md) §2）。
9. **pcFollowType A/B**：同一场景 0 vs 1，记录跟随/传送差异（目前无公开文档）。

---

## 16. 参考资料
- Paramdex ER 定义：[NpcThinkParam](https://github.com/soulsmods/Paramdex/blob/master/ER/Defs/NpcThinkParam.xml) · [NpcParam](https://github.com/soulsmods/Paramdex/blob/master/ER/Defs/NpcParam.xml) · [BuddyParam](https://github.com/soulsmods/Paramdex/blob/master/ER/Defs/BuddyParam.xml) · [BuddyStoneParam](https://github.com/soulsmods/Paramdex/blob/master/ER/Defs/BuddyStoneParam.xml) · [RideParam](https://github.com/soulsmods/Paramdex/blob/master/ER/Defs/RideParam.xml) · [BehaviorParam](https://github.com/soulsmods/Paramdex/blob/master/ER/Defs/BehaviorParam.xml) · [AiOddsParam](https://github.com/soulsmods/Paramdex/blob/master/ER/Defs/AiOddsParam.xml) · [NpcAiActionParam](https://github.com/soulsmods/Paramdex/blob/master/ER/Defs/NpcAiActionParam.xml)
- 追加研究（跟随/爬梯/骑乘/多召唤）：[follow-mount-multi.md](follow-mount-multi.md)
- Chr ID（c0000 玩家 / c8000 Torrent / c4360-66 马）：[Smithbox Info - Chr IDs](https://github.com/vawser/smithbox/blob/master/Documentation/Game%20Information/ER/Info%20-%20Chr%20IDs.txt)
- 多召唤/跟随类 mod：[Spirit Multiplier](https://www.nexusmods.com/eldenring/mods/11168) · [Age of Spirits](https://www.nexusmods.com/eldenring/mods/5641) · [Better Spirit Ashes](https://www.nexusmods.com/eldenring/mods/3905) · [Spirit Battler](https://www.nexusmods.com/eldenring/mods/3150) · [NPC Spawner](https://www.nexusmods.com/eldenring/mods/11612) · [NPC Spawner and Control](https://www.nexusmods.com/eldenring/mods/11400) · [Un-Alone](https://www.nexusmods.com/eldenring/mods/8046)
- AI 结构：[Low-tech AI of Elden Ring](https://nega.tv/posts/low-tech-ai-of-elden-ring.html) · [DSLuaDecompiler](https://github.com/nex3/DSLuaDecompiler) · [EMEDF](https://soulsmods.github.io/emedf/er-emedf.html)
- eldenring-rs：[crate 文档](https://docs.rs/eldenring/0.14.0/eldenring/) · [repo](https://github.com/vswarte/fromsoftware-rs) · `ChrAsm` / `PlayerIns` / `SoloParamRepository` / `CSDebugChrCreator`
- 加载器：[ModEngine2](https://github.com/soulsmods/ModEngine2) · [me3](https://github.com/garyttierney/me3)
- 编辑器：[Smithbox](https://github.com/vawser/Smithbox) · [DarkScript3](https://github.com/AinTunez/DarkScript3) · [libER](https://github.com/Dasaav-dsv/libER)
- 存档：[er-save-manager 技术文档](https://elden-ring-save-manager.readthedocs.io/en/main/technical/save-file-structure/) · [ER-Save-Lib](https://github.com/ClayAmore/ER-Save-Lib)
- 社区现象参考：骨灰 warp/区域解散（日本 wiki「霊体」）、[Age of Spirits](https://www.nexusmods.com/eldenring/mods/5641)、[Better Spirit Ashes](https://www.nexusmods.com/eldenring/mods/3905)、[Aggression Mod](https://www.nexusmods.com/eldenring/mods/2361)、[Immersive Enemy AI](https://www.nexusmods.com/eldenring/mods/5274)
- 实体/参数对照（看 c0000 NPC 实例）：[soulsmods data › ER entities](https://soulsmods.github.io/data/er/entities.html)
