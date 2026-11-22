# 实现日志（2026-11-15）

> 目标：把「设计」变成可加载、可通信、可 dump 的真实 DLL，并把加载器装好。
> 结论：**DLL 已编译通过 + 冒烟测试通过（非游戏进程）**；ME2 已装好；剩「进游戏实测」这一步需要启动游戏。

---

> 说明（2026-11-22 源码整理）：日志里提到的 `tools/live_test*.ps1`、`restart_and_test*.ps1`、
> `_probe_magic*.py`、`tools/from_save*`、`tools/profile.*.json` 等一次性脚本与个人存档导出物
> 已从工作树移除（构建/发布不需要它们）；需要考古时看 git 历史。


## 1. 工具链（已完成）

| 项 | 结果 |
|---|---|
| rustup | 1.100.0（2026-11-09），`stable-x86_64-pc-windows-gnu` |
| rustc / cargo | 可用（`%USERPROFILE%\.cargo\bin`） |
| 链接器 | Rust 自带 `rust-lld` + self-contained MinGW（**无需 VS Build Tools**） |
| 缺失件 | gnu 工具链的 `dlltool` 需要 `as.exe`；Rust 未自带 |
| 解决 | MSYS2 `mingw-w64-x86_64-binutils 2.47` + 依赖 DLL（libintl-8 / libiconv-2 / zlib1 / libzstd），解压到 `%USERPROFILE%\er-tools\binutils` |

> crates.io 走了 `rsproxy.cn` 镜像（`~/.cargo/config.toml`），否则下载会卡。

复现：
```powershell
# 1) rustup（gnu 工具链）
rustup-init.exe -y --profile minimal --default-toolchain stable-x86_64-pc-windows-gnu --no-modify-path
# 2) binutils（见上，或直接把 as.exe 所在目录加进 PATH）
# 3) 构建
cd er-echo\mod
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

---

## 2. DLL（已编译 + 冒烟测试）

产物：`er-echo/mod/target/release/er_echo.dll`（**706 KB**），已复制到 `Game\er_echo.dll`。

PE 检查：
- 导出：`DllMain`
- 导入：仅系统 DLL（KERNEL32/msvcrt/ntdll/WS2_32/bcryptprimitives/…），**不依赖 libgcc/libwinpthread**，可直接注入。

模块：
| 文件 | 作用 |
|---|---|
| `lib.rs` | `DllMain` → 起线程 → `CSTaskImp::wait_for_instance` → `run_recurring(FrameBegin)`；热键、命令、状态上报、权重平滑 |
| `ipc.rs` | 127.0.0.1:7811 TCP **server**；hello/welcome、weights、command、ack；断线重连 |
| `params.rs` | `SoloParamRepository::get_mut` 写 `NpcAiBehaviorProbability`（30 个槽）、`NpcThinkParam`、`NpcParam` |
| `profile.rs` | `profile.json` 解析 + `ChrAsm.equipment_param_ids[22]` 写入 |
| `dump.rs` | 运行时导出 `BuddyParam` / `RideParam` / 玩家 profile 为 JSON（**不需要 Smithbox**） |

冒烟测试（把 DLL `LoadLibrary` 进 PowerShell，非游戏进程）：
```
[Info]  er_echo thread spawned; waiting for CSTaskImp (target exe 2.7.2.0)
[Error] wait_for_instance panicked（exe 名/版本不匹配）— DLL 保持空闲
[Info]  ipc connected to 127.0.0.1:7811
[Info]  ipc: weights seq=7 aggr=0.70 dodge=0.30 guard=0.60
[Info]  ipc: command dump_buddies
[Warn]  ipc disconnected
```
验证了：加载安全、panic 被捕获（**不会把宿主进程带崩**）、IPC 握手/收包/日志正常。
> 注意：`wait_for_instance` 会检查 exe 名（"elden ring"），所以只能在游戏里工作；这也证明版本门禁是生效的。

---

## 3. 加载器（已安装到游戏目录）

- Mod Engine 2 **2.1.0**（官方最后版本）已解压：`modengine2_launcher.exe` + `modengine2/` + `launchmod_eldenring.bat`。
- `Game\config_eldenring.toml`（已备份原文件为 `.bak`）：
```toml
[modengine]
debug = true
external_dlls = ["er_echo.dll"]

[extension.mod_loader]
enabled = true
loose_params = false
mods = []

[extension.scylla_hide]
enabled = false
```
- `mods = []`：先隔离测试，不加载 `mod/` 里已有的 loose 文件；确认 DLL 正常后再加。
- `er_echo.ini` 已复制到游戏根目录（DLL 从工作目录读）。

> ME2 2.1.0 对 1.17.2 的兼容性官方没声明；若启动失败，备选是 me3（Rust 版加载器）。

---

## 4. 现在能做什么

| 能力 | 状态 |
|---|---|
| 注入并附着到游戏 | ✅ 代码就绪（未在游戏内实测） |
| IPC 双向通信（weights/command/ack） | ✅ 冒烟测试通过 |
| LLM 权重写入 param | ✅ 代码就绪（行 id 待填） |
| dump BuddyParam/RideParam/玩家 profile | ✅ 代码就绪（进游戏即可产出 JSON） |
| 装备写入 `ChrAsm` | ✅ 代码就绪（`set_equipment` 命令） |
| 召唤克隆体 | 🚧 `summon()` 目前返回 "not implemented"（等 dump 出真实行 id 后接） |
| 多体扇出 / 骑乘 | 🚧 设计完成，等真实 param 行 |

---

## 5. 下一步（进游戏，10 分钟）

1. 双击 `Game\launchmod_eldenring.bat`（EAC 关闭、离线）。
2. 进游戏（主菜单即可先试），看 `Game\er_echo.log` 是否出现 `er_echo attached`。
3. 在另一个终端跑：
   ```powershell
   cd "D:\Program Files (x86)\Steam\steamapps\common\ELDEN RING\Game\er-echo"
   python tools\ipc_client.py dump_buddies
   python tools\ipc_client.py dump_ride
   python tools\ipc_client.py dump_profile
   ```
4. 产出 `Game\er_echo_buddies.json` / `er_echo_ride.json` / `er_echo_profile.json`。
5. 把行 id 告诉 DLL（**不用重编译**）：
   ```powershell
   python tools\ipc_client.py set_rows --behavior <行为表行> --think <think行> --npc <npc行>
   python tools\ipc_client.py set_weights --aggression 0.8 --dodge_rate 0.4
   ```
   然后按 `F10` 打开权重应用（热键），观察行为变化 / 日志。
6. `ride.json` 里 `atk_chr_id=0`（c0000）+ `def_chr_id=8000/…` 的行就是骑乘实验入口；`buddies.json` 里 `npc_param_id` 对应 Mimic Tear 的行 id 用于「载体克隆」。

---

## 7. 首次进游戏实测（2026-11-15 16:22）

版本坑：crates.io 的 `eldenring 0.14.0` 只支持 exe **2.6.2.0**，本机 2.7.2.0 → `wait_for_instance` panic。
修复：vendor 了 `fromsoftware-rs` main（`er-echo/vendor/fromsoftware-rs-main`，其 `rva.rs` 支持 2.7.2.0），Cargo 改 path 依赖，**编译通过**，进游戏后日志出现：

```
[Info] er_echo attached (target exe 2.7.2.0)
[Info] auto er_echo_buddies.json: 68153 bytes
[Info] auto er_echo_ride.json: 15908 bytes
```

### 实测到的关键数据

| 事实 | 值 |
|---|---|
| **Mimic Tear 的 BuddyParam 行** | `20700000` → `npc_param_id=133201000`、`think=133200000`、`pc_follow_type=2`、`trigger_sp_effect_id=207000` |
| 同组第二行 | `20700001` → `npc_param_id=100000010`、`npc_player_init_param_id=26050`（推测是「泪滴本体/变身」那一半） |
| `pc_follow_type` 分布 | 0:140 行 / 1:28 行 / **2:2 行**（不是只有 0/1） |
| `npc_param_id_ridden` | **全表 -1** → 原版从未用过「召唤即骑乘」，这条路要我们自己开 |
| **RideParam 里的 Torrent** | `atk_chr_id=0`（c0000 玩家）↔ `def_chr_id=8000`（Torrent），`dist=5.0`；另有 8002–8005 |
| 骑士马 | `3150↔3160`（夜之骑兵）、`4350↔4360` … `4356↔4366`，anim id 1/2/3 |
| 原版多体骨灰 | 大量 `trigger_sp_effect_id` 组有 2–5 行（如 `233200` 有 5 行）→ **扇出机制实测成立** |
| 玩家型 buddy | `npc_player_init_param_id` 非 -1 的行（26050/23342/…），对应入侵者/剧情 NPC 型 |

> 结论：`BuddyParam` 扇出、Mimic Tear 载体、Torrent=8000 都已在真实数据里确认；
> 「骑乘召唤」是空白区，正好是我们能做的差异化。

---

## 8. 下一步（进行中）

已加入 DLL 的新能力（已编译，等待下一次重启加载）：
- `summon`：备份玩家装备 → 套 profile（没有就用玩家自己）→ 给玩家 `apply_speffect(207000)` → 90 帧后还原；
- `set_speffect --id N --apply`：手动触发任意 spEffect（做实验用）；
- `dump_npc` / `dump_think`：导出全部 NpcParam/NpcThinkParam 关键字段（已加入自动 dump）。

测试脚本：`tools/restart_and_test.ps1` —— 等游戏退出 → 换 DLL → 启动 → 等 `er_echo_profile.json`（说明已读档）→ 自动发 `summon` → 打日志。

---

## 10. 调试记录：两条生成路线的现状（2026-11-15 17:00）

| 路线 | 结果 | 结论 |
|---|---|---|
| **Buddy 召唤**（`request_summon_speffect_id = 207000`） | 内存里稳定出现 `133201000`（史莱姆）+ `100000010`（本体），**用户肉眼看到过一次并摔死** | **唯一被肉眼确认渲染过的路线**；但不稳定，容易秒死/不可见 |
| **DLL 直接生成**（`WorldChrMan::spawn_debug_character`） | 内存里有实体（dist=0/2m，`npc_param_id` 正确），但**用户完全看不到出生**，随后死亡 | 该接口只创建了 ChrIns，缺少 block/event 注册或模型加载，**暂不可用** |

已排除/已确认：
- `spawn_debug_character` 的 `spawn_position` 用玩家 `chunk_position`（+dy）能对上 `dist`，位置不是问题；
- 给 `team=47` 强制 `tint_alpha_multiplier/opacity_keyframes_multiplier = 1.0` 没有让 debug 实体可见；
- `keep_summons`（每帧清 `disappear_requested` + 86400 延迟）能续命**召唤管理器里的实体**，但用户仍看不到（可能续的是不可见的“壳”）；
- 多脚本并行的重启流程会互相覆盖 DLL（已改成一次只跑一个脚本）。

**下一步（单变量）**：
1. 在**平坦地点**（教堂赐福）做纯净 summon：去掉 keep-alive 与 alpha 强制，只做 profile 替换 + `request_summon`，确认引擎原生流程能否稳定渲染出「史莱姆→变身」。
2. 能渲染后，再逐个加变量（先只加 `buddy_disappear_delay_sec`，再加 alpha，再加 `disappear_requested` 清除），定位到底是哪一步把它变成不可见/秒死。
3. `spawn_debug` 路线暂时搁置，等有时间再补 block/event 初始化。

### 追加结论（2026-11-15 17:12）

在**召唤石之外**的所有运行时生成都失败了，且失败方式一致：

| 尝试 | 结果 |
|---|---|
| `request_summon(207000)` → Mimic | 实体存在、坐标对，**模型没出来就死** |
| 覆写 BuddyParam 20700000 → Fia 参数（523220179/523220000/23221） | **Fia 也是「死在旁边、模型没出来」** |
| `spawn_debug_character`（Fia / Rogier / Mimic） | 实体存在、坐标对，**同样看不到出生** |
| `fix_clone` 把 block 改到玩家所在块 | 实体直接消失 |

结论：**不是 npc_param 的问题，也不是坐标/block 的问题**。运行时生成的 ChrIns 缺少「授权召唤上下文」（召唤石/区域），引擎会在模型加载前把它清理掉。三条伪造生成的路线全部撞在同一堵墙上。

**可行方向（改用引擎自己的授权路径）**：
1. 玩家在**召唤石/召唤区域**正常使用骨灰 → 引擎生成一个合法、可见的 buddy；
2. DLL 只做两件事：
   - 在玩家使用骨灰**之前**把玩家外观/装备换成目标存档档案（Mimic 会在生成瞬间复制）；
   - 生成完成后还原玩家。
3. 这样不伪造生成、不碰 `SummonBuddyManager`，绕开「模型没加载就被清理」。
4. 需要验证：玩家角色是否有可用骨灰、最近的召唤石位置；以及「使用骨灰」到「Mimic 复制」之间的时间窗（DLL 用 `request_summon_speffect_id` 变为非 0 作为触发信号）。

---

## 11. 突破：授权召唤路径成功（2026-11-15 17:25）

把**离群野狼**的 3 行 BuddyParam（`23200000/1/2`）运行时改成 Mimic 参数后，玩家在召唤石旁用骨灰：

```
spawned=True
chrs=[80020000/t10, 133201000/t47, 100000010/t47, 100000010/t47]
```

**用户确认：看到了人形克隆（可见、不透明）**。这证明：
- 引擎授权召唤路径（真实骨灰 + 召唤石）能正常渲染；
- 只要 BuddyParam 行指向 Mimic 参数，就能召唤出「人形克隆」；
- 问题确实出在「无召唤石的伪造生成」上，而不是 npc_param/坐标。

遗留问题：这次克隆**不是蓝皮肤**，而玩家在 prep 期间变成了蓝色 → **Mimic 复制发生在 prep 超时还原之后**。原因是 30 秒窗口太短（玩家走到召唤石时已超时）。
修复：`prep_clone` 窗口延长到 **180 秒**，并改为检测「buddy 集合里出现 133201000/100000010」来触发还原（不再依赖容易被同帧消费的 `request_summon_speffect_id`）。

---

## 9. 已知问题 / 注意

- `er_echo.log` 是 UTF-8（含中文）；PowerShell 5.1 的 `Get-Content` 默认按 ANSI 解码会显示成乱码，请用 `Get-Content -Encoding utf8` 或 VS Code 查看。
- `dump_*` 依赖 `SoloParamRepository`；如果主菜单取不到，先读档再试。
- 本工具链安装到了用户目录（`%USERPROFILE%\.cargo`、`%USERPROFILE%\er-tools`），不需要管理员权限。

---

## 12. 召唤后注入：不再改玩家外形（2026-11-15 17:5x）

### 12.1 结论（探针 `clone_info`）

泪滴本体（`npc_param_id = 100000010`）在 `summon_buddy_chr_set` 里是 **`PlayerIns`**：

```
chr_type=Npc, is_player_ins=true, level=20,
face_magic=FACE, face_size=288, face_prefix=000000006500000000000000,
equip=[110000 ×6, -1 ×6, 660000,660100,660200,660300, -1 ×6]
```

也就是说：它自带 `PlayerGameData`（`face_data` + `chr_asm` + 等级/属性）。
⇒ **「先改玩家、再让泪滴复制」不是必需的**；可以直接对克隆体写入。
⇒ 另一个意外收获：默认克隆体的脸是 `0x65...`（CharaInitParam 26050 的默认值），
   而玩家自己的脸是 `0x09...` —— 说明这次引擎**没有**把玩家的脸复制过去，
   正好可以用 `face_prefix` 区分「注入成功」和「还是默认脸」。

### 12.2 实现（`mod/src/kit.rs` + `lib.rs`）

| 命令 | 作用 |
|---|---|
| `apply_to_clone [--stats true]` | 手动把 `CLONE_PROFILES[0]` 写进所有 `PlayerIns` 克隆体 |
| `auto_apply --on true/false` | 每 15 帧持续注入（默认 **on**）——引擎变身/重招会覆盖数据，必须持续写 |
| `set_clone_profiles --paths a.json,b.json` | 多存档同场：第 i 个克隆体套第 `i % n` 个档案 |
| `apply_stats --on true` | 同时写 `level`/8 维属性/`effective_*`（HP 等派生值暂不重算） |
| `set_follow --dist 35` | 只改「跟丢判定日志」的阈值 |
| `load_profile --path ...` | 单档案，同时把它设成 `clone_profiles[0]` |

注入点与依据：
- 装备：`PlayerIns.chr_asm.equipment_param_ids[22]`（与改玩家时同一字段，已验证即时重绘）
- 脸：`PlayerGameData.face_data.face_data_buffer.buffer[276]`
  （= 存档 `FaceData` 块的 `[0x10..0x124]`）
- `dump_profile` 现在把 276 字节缓冲**补回 0x12F 自描述块**（marker + `FACE` + version + size + 尾 11 字节），
  配合 `tools/dump_to_profile.py` 可以「把当前角色一键导出成 profile」。

### 12.3 跟随：先测量，不硬写坐标

`follow_guard` 每 30 帧计算每个 buddy 到玩家的距离与区块一致性，超过阈值时每 5 秒打一条日志：

```
follow: far(>35)=2 other_block=0 dists=[100000010:12.3 100000010:41.7] (* = 不同区块)
```

**不写 `chunk_position`** 的原因：那是引擎每帧从物理侧回填的派生值，直接写会被覆盖；
早先 `fix_clone` 改 `block_id/block_origin` 导致实体消失，也是同一类问题。
骨灰原生跟随自带「掉队传送」，先用上面的日志验证它真的会拉近距离，再决定是否要自己接 warp。

### 12.4 测试脚本

- `tools/live_test17.ps1`：单档案注入（3 只狼全部改成泪滴人形）→ 期望
  `clone base face_prefix = 000000000900000000000000`、`equip[0]=31330000`、`level=9`
- `tools/live_test18.ps1` / `live_test18b.ps1`：双档案（lv9 + lv15）→ 期望 clone 等级序列 `9,15,9`
- `tools/restart_and_test17/18.ps1`：等游戏退出 → 换 `er_echo.new.dll` → 启动 → 等读档 → 跑测试

### 12.5 实测结果（2026-11-15 17:5x，第二轮）

三份「装备真相」同时写、同一帧回读，结果**全部保留**：

```
equip_probe[0]: chr_asm=[31330000, 2000000, 110000, 18000000, 110000, 110000]
                pgd_chr_asm=[31330000, 2000000, 110000, 18000000, 110000, 110000]
                entries_head=660000 gaitem0=GaitemHandle(213,0x8000d5,Weapon) idx0=5
```

`clone_info`（召唤后 3 分钟复查）依旧是 `level=9 / equip[0]=31330000 / equip[1]=2000000 / head=660000`，
说明这次**没有被引擎刷回**。第一轮失败的真实原因是 **`load_profile` 传了相对路径**
（DLL 的 CWD 是游戏根目录，不是 `er-echo/`）→ 档案没加载 → 一条都没写。
修复：`tools/ipc_client.py` 现在把 `--path/--paths` 解析成绝对路径再发给 DLL。

**玩家视角确认（本人）**：
- 3 个克隆体**就在身边**，会跟随、会战斗；
- 外观是目标档案（脸 + 右手武器），**玩家角色完全没变**。

⇒ 路线 A′ 全链路闭环：授权召唤 → 注入脸/装备/等级 → 原生 AI + 原生跟随。

### 12.6 坐标系坑：不要自己算距离

`follow_guard` 最初用 `main_player.chr_ins.chunk_position` 算距离，日志一直是 109–127 m，
但玩家看到克隆体就在脚边。实测同一帧：

```
player block_pos = -24.81, 91.94, 69.18     player chunk_pos = 40.0, -88.0, -80.0
clone  pos       = 21.34, 3.33, -13.88      （三个克隆体都在 19, 3.4, -13 附近）
```

`chunk_position` 对玩家和召唤物**不是同一套坐标**（玩家是 (40,−88,−80) 这种固定值，
召唤物是 block 局部坐标），任何组合算出来都是 100 m 级假距离。

正确做法：读引擎自己维护的「按到主角距离排序」的列表
`WorldChrMan.chr_inses_by_distance: DLVector<ChrInsDistanceEntry { chr_ins, distance }>`，
用 `ChrIns` 指针反查。这样拿到的就是引擎眼中的真实距离，也不需要自己 warp
（原生骨灰跟随本来就会在掉队时把召唤物传送回玩家身边）。

> 教训：`chunk_position` 是派生值，既不适合读来算距离，也不适合写（引擎每帧回填）。

### 12.7 多档案同场（实测）

同一会话里先 `set_clone_profiles`（lv9 测试档 + lv15 实时导出的档），再召一次骨灰：

```
clone[0] lv=9  vigor=15 eq0=31330000 eq1=2000000
clone[1] lv=15 vigor=21 eq0=31330000 eq1=2000000   ← 用的是第二个存档
clone[2] lv=9  vigor=15 eq0=31330000 eq1=2000000
```

等级序列 `9,15,9` 正好等于 `i % 2`，说明**按实例注入**成立：
一次召唤 3 个克隆体，可以分别读不同存档的等级/属性（外观数据也可以不同）。

### 12.8 配置驱动：零命令流程

`er_echo.ini` 现在支持进游戏自动准备（`apply_config_once`，读档后第 120 帧执行一次）：

```ini
[clone]
profiles=er-echo/tools/profile.test_face.json,er-echo/tools/profile.live_test.json
auto_apply=true
apply_stats=true

[summon]
buddy_rows=23200000,23200001,23200002
buddy_npc=100000010
buddy_think=100000010
buddy_init=26050
buddy_follow=0
```

效果：玩家只需要在游戏里**用骨灰**，不需要任何 Python 命令/热键。
（不想动原版骨灰时把 `buddy_rows` 留空。）

### 12.9 权重链路（部分验证）

`set_rows --think 100000010` + `set_weights` 后 `dump_think` 实测：

```
start_dist: 2 → 30, eye: 2 → 40, backhome: 9979 → 60, team_attack_effectivity: 100 → 0
```

- `set_weights` 每包只混合 15%（`Weights::blend`），且 **seq 必须递增** DLL 才会再次应用；
  `ipc_client.py` 新增 `--repeat N --seq-start S` 便于把权重推到目标值。
- 发现并修掉一个严重映射错误：`team_attack_effectivity = (1 - target_switch) * 100`
  在 `target_switch=0` 时会变成 100 → **召唤物会打队友（玩家）**。
  现在同伴固定写 `0`；`target_switch` 只映射到「忘记目标时间」。
- 仍未验证：`NpcAiBehaviorProbability` 是否真的驱动「玩家式 AI」（`PlayerIns.think_param` 私有，无访问器）。

### 12.11 视觉验证：装备注入确实驱动渲染

用户反馈「克隆体装备和脸跟玩家没区别」——原因是**两份测试档案就是从当前角色导出的**
（脸 payload 完全一致、同样是 660000 套甲），本来就应该长得一样。

为了排除「其实只是引擎复制了玩家」的可能，临时把所有槽写成 `-1`（空）：

```
clone_info: level=15 equip=[-1 × 22]
```

**用户确认：3 个克隆体当场变成裸体/空手** → 写 `chr_asm` / `equipment_entries` 真的会重绘，
不是引擎复制的假象。之后切回正常档案即恢复。

> 想看到「明显不同的外观」，需要一份和当前角色不同的档案：另一个存档（`dump_to_profile.py`）
> 或者从 `er_echo_equip.json`（新 `dump_equip` 命令）里挑别的套装 id，用
> `tools/make_profile.py --slot 12=... --slot 13=...` 派生。

### 12.12 剩余

- [x] 跟随距离：改用引擎的 `chr_inses_by_distance`（不再自己算坐标）
- [x] 多档案同场实测
- [x] 装备注入的视觉验证（裸体测试）
- [ ] `level/stats` 的派生值（HP/FP/攻击力）未重算，需要引擎函数或公式
- [ ] LLM 权重 → 克隆体动作频率的因果验证（需要录一段战斗观察）
- [ ] 「一召多体」目前靠骨灰自带的多行（野狼 3 行）；要更多/不同骨灰需要 Smithbox 加行
- [x] 真正「另一个存档」的端到端测试（见 §13，改为**离线解析 .sl2**，不用切号）

---

## 13. 离线解析 `.sl2` 导出角色（2026-11-15 18:2x）

需求：隔离/旧存档进不了游戏时，仍然要能导出角色。结论：**PC 版 `.sl2` 是明文 BND4，直接读**。

### 13.1 文件结构（实测 v1.17.2 + 2024 旧档都成立）

```
0x00 BND4
0x0C u32 entry 数 (12)
0x40 12 × 0x20 entry: u32 flags, u32 unk(-1), u64 size, u32 offset, u32 nameOffset, u64 pad
0x1C0 entry 名 UTF-16: USER_DATA000..011
槽 k(0..9) 数据 = file[offset+0x10 : offset+size]   # 跳过 0x10 MD5
```

### 13.2 槽内三块数据的定位（不硬编码绝对偏移）

| 数据 | 定位 |
|---|---|
| 等级/属性/名字 | 扫描 8×u32（1..99），要求 **`level == sum(stats) − 79`**（ER 全出身都满足：初始属性和 = 等级 + 79），再要求 `+0x60` 处是可打印非空 UTF-16 名 |
| FaceData | 扫描 `ff ff ff ff FACE` + `size == 0x120`，整块 0x12F |
| 装备 22 槽 | FaceData 前 `0xA8` 处的 22×i32；版本差异会偏，就近 ±0x20 搜索并用「防具槽落在 protector 区间、槽 6..11 为空」校验 |

> 旧档里个别角色（lvl 227 "Sanvenir"）装备表是另一种编码（值形如 `0x01ADB000`，疑似 <<8 的 gaitem 句柄），
> 校验不过 → 标记 `incomplete` 跳过，不瞎猜。

### 13.3 校验：与运行时 dump 逐字节对比

同一角色（slot 0 "Sv" lv15）：

```
level     15 == 15
stats     True
equip     True            # 22 槽完全一致
face      0x10..0x124 载荷 True
          仅尾部 11 字节不同（运行时 dump 清零了 FACE override，存档里是 01 01 01 ff…）
```

### 13.4 工具

`tools/export_profile_from_save.py`：

```powershell
python tools\export_profile_from_save.py --list
python tools\export_profile_from_save.py --save "...\ER0000.sl2" --list
python tools\export_profile_from_save.py --all -d tools\from_save
```

实测「隔离的旧存档」（`%APPDATA%\EldenRing\<SteamID> - 副本\ER0000.sl2`）：

```
slot 0: lv227 Sanvenir  runes=119276  (incomplete: equip=False)
slot 1: lv9   Samurai   runes=18006   wpn=[110000,2000000,…] armor=[660000,660100,660200,660300]
slot 2: lv17  Sirenix   runes=431     wpn=[31330000,3030000,…]
slot 3: lv9   Ludwig    runes=11      wpn=[31330000,2000000,110000,18000000,…]
```

导出到 `tools/from_save/`，直接填进 `er_echo.ini` 的 `profiles=` 即可召唤——全程没有切号。

### 13.5 端到端实测（离线档案 → 游戏内召唤）

把导出的两份档案热加载进正在运行的游戏（`set_clone_profiles`），用一次骨灰：

```
clone[0] lv=17 vit=21 eq0=31330000 eq1=3030000  eq3=110000    face=8200000008000000…
clone[1] lv=9  vit=15 eq0=31330000 eq1=2000000  eq3=18000000  face=8200000008000000…
clone[2] lv=17 vit=21 eq0=31330000 eq1=3030000  eq3=110000    face=8200000008000000…
```

- 等级/属性/武器与 `.sl2` 里解析出的值完全一致（Sirenix lv17 右手 3030000，Ludwig lv9 第三槽 18000000）；
- 脸 payload 前缀 `82000000 08000000…` 与玩家自己的 `00000000 09000000…` 明显不同；
- **全程没有切换存档/账号**，旧存档也从未被游戏加载过。

⇒ 「离线解析隔离存档 → 召唤成同伴」闭环完成。

### 13.6 账号目录下的多种存档（实测都能读）

| 文件 | 内容 | 解析 |
|---|---|---|
| `ER0000.sl2` | 主存档：Sv lv15、May lv6 | ✅ |
| `ER0000.sl2.bak` | 同上（自动备份） | ✅ |
| `ER0000.cnv` | Seamless Coop 存档：Sv lv13、Edr lv9 | ✅ |
| `ER0000.cnv.co2` | Coop 备份：SV lv137、V lv12 | ✅ |
| `ER0000.mod` | SV lv40 | 名字/等级/脸 ✅，装备表旧编码 ❌ |

用主存档导出的两份档案召唤实测（一次骨灰 3 体）：

```
clone[0] lv=15 vit=21 eq0=31330000 eq1=2000000 head=660000 body=660100 face=0000000009000000…
clone[1] lv=6  vit=9  eq0=30080000 eq1=33130000 head=630000 body=630100 face=0a00000067000000…
clone[2] lv=15 vit=21 eq0=31330000 eq1=2000000 head=660000 body=660100 face=0000000009000000…
```

和 `.sl2` 里解析出的字段逐项一致（May 的 630000 套装与玩家 660000 不同，一眼能区分）。

### 13.7 未解决：旧编码装备表

`ER0000.mod` 的 SV lv40 与副本存档的 `Sanvenir lv227` 用的是同一种旧编码（值形如 `0x01ADB000`，
疑似 `param<<8 | flags` 的 gaitem 句柄表）。当前会被标 `incomplete` 跳过。
真要支持需要拿「已知装备的角色」做一次对照反推。

### 13.8 登录 May 存档后的对照：还缺哪些解析（2026-11-15 18:3x）

**做法**：游戏里正好登录的是 May（slot 1），直接 `dump_profile` 拿运行时真值，
和离线导出的 `slot1_May.json` 逐项对。`tools/diff_profile.py` 就是这套对照。

```
OK  level: 6 vs 6
OK  stats 8/8
OK  equipment 22/22
OK  face payload 276B (block 303B)
OK  hp max: 396 vs 396
OK  fp max: 95 vs 95
OK  stamina max: 94 vs 94
ALL MATCH
```

⇒ **外观三要素（等级/属性、22 槽装备、脸部 276B）离线解析已经和运行时完全等价**，
May 与 Sv 用的是两套不同防具（630000 / 660000）、不同脸，所以「看起来是另一个角色」不是错觉。

同时把之前**没解析、或解析错了**的东西补上了：

| 字段 | 存档偏移（相对 PGD base） | 说明 |
|---|---|---|
| HP 当前/上限/基础 | `+0x08/0x0C/0x10` | `+0x0C` 是引擎算好的上限，直接抄 |
| FP | `+0x14/0x18/0x1C` | 同上 |
| 耐力 | `+0x24/0x28/0x2C` | `+0x20`/`+0x30` 是保留位，实测恒 0 |
| 七抗性 | `+0x70..+0x88` | 毒/腐败/出血/死亡/冻伤/睡眠/发狂 |
| 体型 / 出身 | `+0xB6` / `+0xB7` | Sv = 1/0、May = 0/4（4 与「占星者」初始属性吻合） |

四个角色的数值自洽（lv6→396/95/94、lv15→680/78/97、lv137→1144/270/125），
说明偏移是对的、不是巧合。

修掉的坑：

1. `summon_spirit_level` 之前是**硬编码 10**（假数据，导出器里写死的）。现已移除该字段，
   解析不到就不写，不再假装知道。
2. 装备表以前直接 `& 0x0FFFFFFF` 丢弃高位。现在把**原始 22×i32** 另存为 `equipment_raw` 留档
   —— 实测防具原始值是 `0x10099CF0`（高位 `0x1`），掩码后才是 630000，
   而运行时 `equipment_param_ids` 正好等于掩码后的值 ⇒ 掩码本身是对的。
3. 装备表里**不含强化等级**（May/Sv 的武器原始值就是 `+0` 的 param id）。
   `+N` 存在别处（inventory 的 gaitem 句柄 / `matching_weapon_level`），属下一步。

DLL 侧同步改了（等下次重启生效）：

- `apply_stats` 现在会写 `current/base_max_hp|fp|stamina` 和当前值
  —— 以前只写 level/属性，引擎**不会**因此重算上限，克隆体的血量池会是泪滴默认值；
- `dump_profile` 增加 `name`、`identity{player_id, character_id, gender, archetype, voice_type,
  starting_gift, unlocked_*_slots, spirit_ashes_level, weapon_level, flasks}`、
  `resistances`、`resistance_gauges`、`poise`、`discovery`、`max_equip_load`、
  `equipment_gaitem_handles`、`equipment_entries`、`equipment_item_idx_list`、`base_max_*`
  —— 用来在下次重启后把「存档偏移 ↔ 运行时字段」一次性钉死（尤其强化等级和 spirit level）。

兼容性：新增的 profile 键（`pools`/`resistances`/`equipment_raw`）都是 `#[serde(default)]`，
旧 DLL 读新 profile 不受影响（实测 `load_profile` 通过）。

工具：

- `tools/diff_profile.py` —— 运行时 dump ↔ 离线 profile 全字段对照，退出码 0/1，可直接当回归测试；
- `tools/probe_save_fields.py` / `probe_save_layout.py` —— 用运行时已知值反查存档偏移，
  新增字段时照这个套路验证（别凭猜测写偏移）。
- `tools/swap_dll_on_exit.ps1` —— **只**在游戏退出后换 DLL，不重启、不跑测试（避免抢占玩家的会话）。

### 13.9 主存档 slot 0 的装备表「异常」——已证伪（2026-11-15 19:5x）

对照 May 的过程中发现：游戏在 18:39:49 自动存档后，主存档 slot 0（Sv lv15）的
22 槽装备表里 **头部/手部** 是 `0x10002710 / 0x100027D8`（掩码后 10000 / 10200），
而身体/腿部是 `0x100A1284 / 0x100A134C`（660100 / 660300）。

当时的推测（**错的**）：以为 10000/10200 是占位值，因为 `660000-10000 == 660200-10200 == 650000`
看起来像「相对偏移」，而且同一份文件里 0x047a / 0x1aaf0 两处还留着完整的 660000..660300。

**证伪过程**（重新进游戏、并且切换到 Sv 存档后）：

```
dump_profile: name='Sv' lv15
equipment_param_ids = [31330000, 2000000, 110000, 110000, 110000, 110000, -1×6,
                       10000, 660100, 10200, 660300, -1×6]
```

运行时 `PlayerIns.chr_asm` 里就是这个值 ⇒ **存档没错，Sv 真的混搭：头 10000、手 10200、身/腿 骑士套**。
再用 `dump_equip` 导出参数表：`protectors` 共 838 条，`10000 / 10100 / 10200 / 10300` 恰好是一套
（stride 0x64，和 660000..660300 一样的成组规律）⇒ 10000/10200 是**真实存在的防具 id**。

教训与修正：

1. 之前加的「四件防具必须是一套」是**启发式**，会误杀混搭穿搭 —— 现在降级为**没有参数表时的兜底**；
2. 有 `er_echo_equip.json`（`dump_equip` 的产物）时，改用**硬校验**：
   `equip_ok()` 逐个检查「这个 id 是否真的在对应的 param 表里」（槽 0–11 → weapons、
   12–15 → protectors、17–21 → accessories）。错位表会因为 `1073744814` 这类值直接出局；
3. 之前那份「兜底」的 `slot0_Sv.json`（660000 套）已按存档真值重新导出，`diff_profile` 现在 8/8 ALL MATCH；
4. `merge_profile_fields.py` 保留（以后遇到真正读不出的槽还能用）。

> 这里也暴露了一个流程问题：**没有运行时对照就下结论**。以后凡是「存档里某字段奇怪」，
> 先 `dump_profile` + `dump_equip` 对照，再决定要不要动解析逻辑。

---

## 14. M4：LLM 闭环（2026-11-15 19:1x）

原计划里 M4 的两块短板补上了：**LLM 之前其实是「瞎的」**（状态只有玩家三围比例），
而且 §10.4 的换装/加点工具**根本没落到克隆体上**（`set_equipment` 写的是玩家的 `ChrAsm`）。

### 14.1 状态上报（DLL → sidecar）

`report_state()` 重写为结构化 JSON（`serde_json` 生成，不再手拼字符串），1 秒一条：

```json
{"v":1,"type":"state","seq":12,"frame":7200,
 "player":{"hp":0.72,"fp":0.55,"stam":0.9,"level":6,"runes":0,"blessing":0},
 "clones":[{"npc":100000010,"name":"May","level":6,"hp":0.95,"dist":4.2}],
 "enemy":{"npc":4090000,"team":1,"dist":6.3},
 "weights":{...},"strategy":"pressure",
 "events":["player_low_hp"]}
```

要点：

- 距离一律取 `WorldChrMan.chr_inses_by_distance`（按指针匹配，一次遍历同时服务克隆体/敌人）；
- `events` 是**边沿触发**：`player_low_hp`（<35%）、`player_dead`、`revive`、`enemy_engaged`、
  `enemy_dead`、`clone_summoned`、`clone_gone` —— 同一件事只报一次，不会把 LLM 刷屏；
- 敌人判定：`team_type` 既不等于玩家 team、也不是 47（同伴），且 `npc_param_id > 0`。

### 14.2 工具调用真正落到克隆体（`design.md` §10.4）

| 命令 | 参数 | 护栏 |
|---|---|---|
| `set_equipment` | `loadout{槽名: id}` 或 `slot`+`item_id`，可选 `upgrade`、`who` | 槽位白名单（名字或 0–21）、`ItemId::new` + `repo.get_equip_param` **存在性检查**、改前存回滚点 |
| `set_stats` | `level` / `vigor` … `arcane`，可选 `who` | 单步变化 clamp ±20%（1..713 / 1..99）；等级变了就按比例缩放存档里的三围上限 |
| `rollback_equipment` | — | 恢复上一次 `set_equipment` 之前的 22 槽 |

- `upgrade` 只对武器槽生效，做法是 **`id + N` 去参数表里查**，查不到就整包拒绝
  —— 不猜「+N 的编码规则」（design §11.3）。
- `who` 支持 `0/1/2…`（第几个档案）或省略（= 全部）。
- 写入的是 `CLONE_PROFILES`（内存档案）→ 立刻 `apply_to_clones()`，所以 `auto_apply` 之后
  每 15 帧重写时也会保持新装备，不会被引擎覆盖回旧值。

sidecar 侧 `director.py`：

- `SYSTEM_PROMPT` 补上状态结构 + `loadout`/`upgrade`/`stats`/`level`/`rollback` 的用法与克制原则；
- 新增 `--allow-tools`（默认关）：关了只发权重，开了才允许 LLM 换装/加点；
- `simulate` 的假状态改成和 DLL 完全相同的形状（`clones`/`enemy`/`events`），避免「仿真通过、实机字段对不上」。

### 14.3 修掉一个会让整条链路「看起来随机失败」的 bug：IPC 每 500 ms 断一次

`ipc.rs` 给 socket 设了 500 ms 读超时**为了不阻塞**，但用的是 `for line in reader.lines()`：
读超时会 yield 一个 `Err(WouldBlock/TimedOut)`，而旧代码 `Err(_) => break` —— 于是**空闲 500 ms 就断开**，
2 秒后重连。日志里成片的 `ipc connected/disconnected` 就是它。

后果：sidecar 只能在「连上那一瞬间」收到东西，state 大量丢失；命令能成只是因为
across 窗口里刚好塞进去了。这也是为什么之前 LLM 链路「时好时坏」。

现在把超时当作「暂无数据」继续读，只有真正的 EOF/错误才断线：

```rust
Some(Err(err)) if matches!(err.kind(), WouldBlock | TimedOut) => continue,
Some(Err(_)) | None => break,
```

### 14.4 新增观察工具

```powershell
# 只看状态流（不发权重/命令），确认 LLM 能看到战斗、克隆体距离与血量
python tools\watch_state.py --seconds 30
python tools\watch_state.py --seconds 30 --raw

# 换新 DLL 后的一键验收（dump_profile/diff、dump_equip 查 id、clone_info、10 秒 state 采样）
python tools\verify_after_restart.py

# 手动喂一条工具调用（--args 是通用入口，语义校验都在 DLL）
python tools\ipc_client.py set_equipment --args "{\"loadout\":{\"head\":630000}}"
python tools\ipc_client.py set_stats --args "{\"vigor\":12}"
python tools\ipc_client.py rollback_equipment

# LLM 导演（不连真模型先自测链路）
python bridge\director.py --simulate --llm mock
python bridge\director.py --llm ollama --model qwen2.5:7b --allow-tools
```

### 14.5 待实机验证（下次重启后跑 `verify_after_restart.py`）

1. `watch_state.py` 能收到 state，且 `clones[].dist` 与 `follow:` 日志里的引擎距离一致；
2. 召唤后克隆体 `hp` 是否接近档案里的 `pools.hp`（验证 `apply_stats` 写三围上限是否被引擎接受）；
3. 用 `set_equipment` 换成另一套甲 → 克隆体外观立即变化（等价于 §12.11 的裸体测试，但走工具链）；
4. `set_stats` 加点后 `clones[].level` 变化；
5. 权重因果：`set_weights --aggression 1 --repeat 8` 与 `--aggression 0` 各打一场，比较克隆体的攻击频率。

### 14.6 跟随/掉队：两次「自己传送」实测失败 → 真正的原因是骨灰行没复制对

**症状**：克隆体跟到 43–51 m 就不再回来，`follow:` 日志一直 `far(>35)=3`，二十多秒后消失。

**错误路线 1：写 `PlayerIns.block_position`**

```
recall: clone 100000010 (0.0,0.0,0.0) -> (-21.3,93.1,94.8)
```

克隆体的 `block_position` 一直是 `(0,0,0)`（它们是 NPC 型 `PlayerIns`，不用这个字段）。
写完之后它们从空中掉下去：`world_pos.y ≈ -400`、`hp [0, 680]`，直接死亡。

**错误路线 2：写 `ChrCtrl.physics_model_matrix.3` + `position_sync_requested = 1`**

同样坠落到 `y ≈ -400` 并死亡。那个矩阵是每帧从 `CSChrPhysicsModule::position` 重算出来的派生值，
直接改它不会建立碰撞/地面信息。真正该写的是 physics module 的 position（crate 未暴露），
或调用引擎的 warp 函数（需要额外逆向）。

**错误路线 3：解散 + 重召**

`request_summon`（spEffect 207000）单独调用**召不出任何东西**（0 个克隆体），
只有玩家使用骨灰时 `request_summon_speffect_id` 才会被引擎消费。所以 DLL 没法自己重召。

**真正的修复：把「拟态泪滴本体」那一行 BuddyParam 整行复制过去**

`dump_buddies` 里对比就能看出来：

```
20700001  npc=100000010 think=100000010 init=26050 follow=0  trigger=207000   ← 拟态本体
23200000  npc=140700000 think=140700000 init=-1     follow=0  trigger=232000   ← 离群野狼（借的壳）
```

我们之前只改了 `npc/think/init/follow` 四个字段，`x_offset/z_offset/y_angle/
disable_pc_target_share/appear_on_around_sekihi` 还是狼的，`follow` 还被我按经验写成了 2
（本体是 0）。新增 `params::copy_buddy_row` + `[summon] buddy_copy_from=20700001`：

```
config: BuddyParam 23200000 -> ... follow=0
config: BuddyParam 23200001 -> ... follow=0
config: BuddyParam 23200002 -> ... follow=0
config: buddy_copy_from=20700001 applied to 3 row(s)
```

**复测（同一局，玩家正常跑开）**：

```
follow: far(>35)=3  dists=[42.5 40.1 40.9]
follow: far(>35)=2  dists=[36.9 34.5 35.2]
follow: far(>35)=0  dists=[0.9 2.5 1.1]      ← 自己回来了
...
follow: far(>35)=0  dists=[2.9 2.9 3.1]
```

⇒ 掉队后引擎自己把它们拉回来了，**不需要我们自己写传送**。用户的原话是对的：
跟随/传送本来就是骨灰行在管，DLL 只要让召唤体真的复刻「骨灰本体那一行」。

保留的东西：

- `recall` 命令现在直接返回错误并说明原因（防止有人再踩）；
- `[tuning] auto_recall=false`：打开只打告警；
- `keep_close --dist N`：把 `backhome_dist` 压到 N 米以内（比权重里的默认值更“贴身”），
  想更紧的跟随可以用它。

## 15. 召唤限制绕过 + 灵体外观（2026-11-15 20:4x）

诉求：骨灰不要受区域/次数限制；召唤体不要灵体特效。

### 15.1 「能不能召唤」到底卡在哪

`SummonBuddyManager`（`WorldChrMan + 0x1e538`）里与召唤有关的门禁（crate 已给的布局）：

| 偏移 | 字段 | 作用 |
| --- | --- | --- |
| `0x28` | `disappear_requested` | 已被请求消失 → 召不出来 |
| `0x90` | `item_use_cooldown_timer` | 刚用过骨灰的冷却 |
| `0x98` | `player_has_alive_summon` | 「已经有一队」→ 不允许再用骨灰 |
| `0xb5..0xb8` | `is_within_activation_range` / `prev` / `is_within_warn_range` / `prev` | 玩家是否在**召唤石**范围内 |

- 召唤石是 `BuddyStoneParam`：304 行，半径字段 `activate_range` 实测 **35..999**。
  玩家落在所有石头半径之外 = 社区说的 **dead zone**（不是 bug，是这张图就这么放的）。
- FromSoft 还在地图脚本里写了「禁召区」：**即使把 `activate_range` 抬到 9999 也没用**，
  因为这些地方**根本没有石头实体** —— 实测死区里 `buddy_stone_entity_id = 0`。

### 15.2 四条路线，实测结果

| 做法 | 结果 |
| --- | --- |
| 304 行 `activate_range` → 9999 | 有石头的区域全覆盖；无石头区域无效 |
| 每帧把 `0xb5..0xb8` + 冷却置真 | **无效**：管理器每帧自己重算会覆盖；物品可用性看到的是重算后的值 |
| 清 `player_has_alive_summon` | 有效：可以在已有召唤物时再召 |
| **直接写 `request_summon_speffect_id`** | **有效，且绕过前面所有判定** |

⇒ 骨灰**物品**能不能用是引擎在菜单/物品使用层判定的（还依赖石头实体存在），DLL 改不动；
而**召唤请求这一层没有区域概念** —— 写进去就生成。所以入口从「用骨灰」改成「直接写请求」。

### 15.3 现在的召唤入口（不需要骨灰物品）

```
F8  → summon() → summon_force()
   ├ bypass_summon_gates()       范围/冷却/消失请求置真
   ├ clear_alive_summon_flag()   清 player_has_alive_summon（可反复召）
   ├ spawn_origin = 玩家物理坐标（否则是上次残留值，克隆体会生成在几百米外再 warp 回来）
   └ request_summon_speffect_id = <buddy_rows 第一行的 trigger，默认 232000>
F7  → 收回（disappear_requested + delay 0）
IPC: summon_force / request_summon {"id":232000}
```

实测（就在用户「按骨灰没反应」的那个位置，`buddy_stone_entity_id = 0`）：

```
request_summon {id:232000}
  100000010 lv15 hp[680/680] dist 2.8 m
  100000010 lv6  hp[396/396] dist 2.7 m
  100000010 lv15 hp[680/680] dist 2.6 m
follow: far(>35)=0 resolved=3/3 dists=[1.1 0.6 1.1]
```

### 15.4 灵体外观：不是 PhantomParam，是 spEffect

- `NpcParam(100000010).phantom_shader_id = -1`，`133201000` 同样 → **PhantomParam 那条线已证伪**。
- 真正的来源：
  - `NpcParam` 常驻 spEffect 槽 **#26 = 295000**（普通骨灰白雾）；
  - 召唤时引擎另外挂 **295190**（灵体着色）。只去掉 295000 仍然有蓝白虚影；
    再摘掉 295190 立刻正常（用户确认「外观正常的」）。
- 实现（都不动 `regulation.bin`）：
  - 启动时把 `NpcParam` 常驻槽里的 295000 改成 -1（影响**之后**的召唤）；
  - 每 15 帧对在场克隆体 `ChrIns::remove_speffect()` 摘 295000/295200/295190（管重挂/重生）；
  - 配置 `no_spirit_glow=true`、`glow_speffects=295000,295200,295190`；
  - 备用路线（未用上）：`phantom_set` / `phantom_override` 改 `PHANTOM_PARAM_ST` 行。

### 15.5 闪退复盘（0xc0000005，faulting module = er_echo.dll）

`bypass_summon_gates` 在读档那几帧解引用了**空**的 `summon_buddy_manager`。反汇编崩溃点：

```
mov 0x1e538(%rax),%rax      ; WorldChrMan.summon_buddy_manager
movl $0x1010101,0xb5(%rax)  ; 4 个 bool 一次写 —— 崩在这里（rax = 0）
movl $0x0,0x90(%rax)        ; item_use_cooldown_timer
movb $0x0,0x28(%rax)        ; disappear_requested
```

修法：所有管理器访问走 `spirit::manager()/manager_mut()` 判空，并且只在
`main_player.is_some()` 时写。教训：`OwnedPtr` 在读档/过场/回标题时都会被置空，
**每次解引用都要判**（`keep_summons`、`request_summon`、`dismiss` 也一并改了）。

另外加了状态追踪（每 30 帧比对一次，变化才打）：

```
summon state: request -1->-1 active -1->232000 alive false in_range true->true chrs 1->4
```

有了它就能区分「按键根本没被接受（request 不动）」和「接受了但没生成（chrs 不动）」。

### 15.6 篝火（赐福）集成：不能塞菜单项，但能挂到「休息」流程

赐福菜单是 **ESD + 前端（Scaleform）** 驱动的：菜单项来自脚本/前端数据，DLL 运行时
拿不到「往菜单里加一行」的接口（`CSMenuManImp` 只暴露 UI 状态、`popup_messages`、
`display_status_message`，都是显示用的）。要真的加菜单项得改 ESD/前端资源并打包，
属于另一套离线 mod 工程。

但引擎把「坐在赐福上」的动画状态放在 `CSLuaEventMan` 的 proxy 里：

```
CSLuaEventMan  →  lua_event_proxy  →  control_flags (LuaEventControlFlags)
    bit5 bonfire_loop_begin_requested   坐下动画开始
    bit7 bonfire_sitting_loop_active    ← 正在坐（休息中）
    bit8 bonfire_stand_up_in_progress   起身中
```

所以这里不做「常驻维持」（用户明确否掉了：队伍掉了就自动补会很吵），而是**只在四个事件之后召**：

| 事件 | 判定依据 | 延迟 |
| --- | --- | --- |
| **坐火** | `bonfire_sitting_loop_active` **上升沿（坐下那一刻）** | 150 帧 |
| 传送 / 世界重置 | `CSNowLoadingHelper.menu_load_counter` +1，或 player `block_id` 变化 | 240 帧 |
| 复活 | `PlayerGameData.current_hp` 由 0 变 >0 | 120 帧 |
| **重进游戏（读档）** | `main_player` 由 None 变 Some（`SEEN_PLAYER` 边沿；回标题会复位） | 360 帧 |

**关键修正（用户实测指出）**：世界刷新/敌人重生是在**坐下那一刻**做的，不是起身。
第一版把召唤挂在「起身」边沿，而且执行时「还坐着就往后推」——等于永远等在世界刷新之后，
结果坐火永远召不出来。现在改成坐下即排 150 帧后执行，坐着不推后。

另外还有一条旁证信号：坐火期间如果克隆体从 >0 被清成 0（世界刷新确实发生了），
立刻排 90 帧后召唤。

执行时只在「玩家已死 / 刚进过加载画面 30 帧内」才推后；场上已有克隆体则跳过
（走路跨 block 也走同一个事件，不该叠一队）。事件召唤后 240 帧验证一次，
仍为 0 才重试，最多 2 次（不是常驻轮询）。

- 配置 `[summon] summon_events=true`；
- 诊断命令 `event_probe`：打印 `sitting / hp / block / load_counter / 已排队帧 / 克隆数`；
- 日志里 `event flags changed: LuaEventControlFlags { ... }` 会在**任意控制位变化**时打一条，
  排查「坐火到底哪一位在动」非常直接；
- 手动召唤仍是 F8，F7 收回。

### 15.7 还没做

- 让**骨灰物品**在死区也能按：需要找出引擎那个可用性判定函数并打补丁（AOB 逆向，风险高）；
- 召唤/受击/死亡的紫雾（另一批 spEffect，用户没要求）；
- FP 消耗：未改（lv15 的 78 FP 够用）；
- 「使用次数」：骨灰本身不消耗，真正的限制是「一次一队」，已由 `multi_summon` 解除。


---

## 16. 同伴施法：占星师为什么只会平砍（2026-11-15 22:0x）

### 16.1 先证伪「AI 权重不够」

占星师档案（`May`, lv6, int16）召唤出来只平砍。第一直觉是行为权重
（`NpcAiBehaviorProbability` 的 spell 槽 13/14/20..28、`spell_rate`），
但把这些槽拉满也没用 —— 因为克隆体**根本没有法术可放**。

### 16.2 根因：法术列表是「每个 PlayerIns 自己一份」

`PlayerGameData.equipment.equip_magic_data` 是个独立结构：

```rust
pub struct EquipMagicData {
    pub equip_game_data: NonNull<EquipGameData>,
    pub entries: [EquipMagicItem; 14],   // { param_id, charges }
    pub selected_slot: i32,
}
```

`npc_param_id = 100000010`（拟态泪滴本体）的 think（`100000010`）**本身就会施法**
（原版拟态泪滴会照抄玩家的法术放），但它读的是**自己**的 `entries`。
我们造克隆体时只注入了装备 22 槽 / 属性 / 脸，14 个记忆槽全是 `-1`：

```
[magic_probe] player Sv  lv15 int9  fp78/78  slots=(空)
              clone      lv6  int16 fp95/95  slots=(空)   ← 没法术可放
```

### 16.3 记忆槽在存档的哪（v1.17.2 实测）

定位办法：先用 `dump_magic` 把 317 行 `Magic` id 导出来（法术 id 是
`4000..53912` 与 `2004300..2050090` 两段 + 一行 `999999999` 占位），
再拿这张表当**真值表**回存档里扫 14 槽结构。

结论：`PlayerGameData` 起点 **+0x93B4**，14 × `(param_id: i32, charges: i32)`，
空槽 `(-1, 0)`、装了法术 `(id, -1)`。两个角色都精确命中，且和运行时对得上：

| 角色 | 存档 +0x93B4 | 运行时 `magic_probe` |
|---|---|---|
| Sv (lv15, int9) | `[-1 × 14]` | 空 |
| May (lv6, int16) | `[4000, 4070, -1 × 12]` | `[4000, 4070]` |

`4000` = Glintstone Pebble（mp 7 / int 10），`4070` = 占星师初始的另一发 —— 正好是
职业初始配置，说明读到的就是「记忆槽」本身。

顺带纠正两处早期猜测（`design.md` §7.2）：

- 「记忆法术 14 槽 = +0x74」**是错的**，+0x74 落在抗性区；真实偏移是 +0x93B4；
- 存档里装备/道具 id 带 flag：`0x10000000 | id`（武器/防具）、`0x40000000 | id`（道具/法术），
  归一化一律 `& 0x0FFFFFFF`。

### 16.4 注入（`mod/src/ai.rs`）

- 只写 `entries` / `selected_slot` / `unlocked_magic_slots`，**不碰** `equip_game_data`
  回指指针（引擎靠它找背包，写错会崩）；
- `equip_magic_data` 是 `OwnedPtr`（内部 `NonNull`），拿它必须先按原始 `usize` 读，
  再做 `== 0` 判断（§15.5 的 UB 教训）；
- `charges` 写 `-1`：写成 `0/1` 会让引擎把槽当「已耗尽」，放一次就再也不放；
- 持续注入：`auto_apply` 每 15 帧重跑（变身/重招会覆盖 PGD）。

导出侧 `tools/export_profile_from_save.py` 增加 `magic`（14 个 id，`-1` = 空）与
`unlocked_magic_slots`，并新增 `--magic-ids er_echo_magic.json`（默认自动找）；
固定偏移校验不过时会在「装备表前 0x400」范围扫一遍兜底。

### 16.5 无限蓝（`infinite_fp`）

法术要 FP；克隆体的 FP 只减不增，放两下就干了，然后 AI 退化成纯平砍 ——
现象和「不会施法」一模一样。`keep_clone_fp()` 每帧把 `current_fp` 顶回上限，
`[ai] infinite_fp=false` 可关。

### 16.6 怎么确认它真的放了法术

不看画面也能确认：施法会生成 bullet，`CSBulletIns.targeting_owner.owner_chr_handle`
就是施法者。每 15 帧扫一遍 `CSBulletManager.bullets()`，克隆体（team 47）名下有弹就记：

```
[Info] bullet: clone=2 other=0 samples=["npc=100000010 team=47", ...]
```

手动查：`ipc_client.py bullet_probe`（附带 `max_seen`）。

### 16.7 新命令

| 命令 | 作用 |
|---|---|
| `magic_probe` | 玩家 + 克隆体的记忆槽 → `er_echo_magic_probe.json` |
| `magic_copy` | 把玩家的法术整份抄给克隆体（验证「有法术就会放」的兜底） |
| `magic_set {"ids":[4000,4070]}` | 显式指定（LLM 调法术的入口） |
| `infinite_fp on/off` | 无限蓝开关 |
| `bullet_probe` | 场上子弹按施法者归类 |
| `dump_magic` | 全部 `Magic` 行（id / 耗蓝 / 需求 / behavior） |

### 16.8 还没做

- 战技、喝药（estus）的权重仍是「社区槽位」，没有逐条实测；
- **法术选择策略**（按耗蓝/距离/敌人抗性挑法术）没做，完全交给原生 AI；
- LLM 改法术只写内存（`magic_set`），还没回写存档；
- 队友骑马（用户同意暂缓）。

---

## 17. M4/M5：权重真正落地 + 战斗验证台 + 打磨（2026-11-15 22:2x）

> 这一节把「M4 = 权重能观察」和「M5 = 打磨」推进到可验收：
> 不再需要用户参战，DLL 自己能造一个可量化的战斗场景。

### 17.1 占星师不施法的**第二层**原因：她根本没进入战斗

§16 修的是「没法术」。修完之后仍然常常看不到施法，根因在**拟态泪滴 think 行的出厂值**：

| 字段 | 出厂值 | 含义 |
|---|---|---|
| `eye_dist` | **2 m** | 只有贴脸才「看见」敌人 |
| `search_eye_dist` | 2 m | 搜索半径同样为 2 m |
| `battle_start_dist` | **2 m** | 只有贴脸才进入战斗 |
| `backhome_dist` | 9979 m | 不设「回家」绳长 |

所以法系同伴永远在「跟随」状态里平砍 —— 不是她不想放法术，是她的射程只有 2 米。

实测（同一位置、同一个 10 m 外的敌人）：

```
think.eye_dist = 2   → 20 s 内 0 发子弹，克隆体始终在玩家身边 2.7 m
think.eye_dist = 28  → 2 s 内 bullet: clone=7（一次 7 颗同时在飞）
```

修法：`apply_config_once` 里**立刻把默认权重写一次** think 行（不等 LLM）：

```
[Info] config: default weights -> think 100000010 (aggr=0.50: eye=13m battle_start=7m)
```

映射收窄成「跟随友好」的区间（旧版 aggression 1.0 = 40 m 太远，会为追怪离开玩家）：

| 权重 | 落点 | 范围 |
|---|---|---|
| `aggression` | `eye_dist` / `search_eye_dist` | 6–20 m |
| | `battle_start_dist` | 3–12 m |
| | `battle_eye_update_dist` | 4–12 m |
| `guard_rate` | `is_guard_act` + `NpcParam.guard_angle / phys_guard_cut_rate` | — |
| `target_switch` | `search_target_lv1/lv2_forget_time` | 1–20 s / 1–30 s |
| `spell_rate` | **记忆槽里开几发法术**（见 17.2） | 0 / 半 / 全 |
| `backhome_dist` | 只在 `keep_close` 显式给了绳长时才写 | 默认不碰（9979） |

`team_attack_effectivity` 依旧写死 0（拉高会让召唤物误伤玩家，§14.2）。

### 17.2 `spell_rate` 唯一可行的落点：记忆槽数量

`NPC_THINK_PARAM_ST` 里**没有**「施法概率」这种字段（全部字段名扫过一遍：
`logic_id / battle_goal_id / ranged_attack_id / eye_dist / …`），`NpcAiBehaviorProbability`
的槽位对 player 型 AI 又不生效（§16.1）。所以「法术倾向」改成直接控制**开几发**：

```text
spell_rate < 0.1     → 清空记忆槽（纯近战）
spell_rate = 0.5     → 只开 ceil(0.5 * 2) = 1 发（May 只剩 4000）
spell_rate = 1.0     → 全开（May = [4000, 4070]）
```

实测（`auto_apply` 每 15 帧重写，所以切换是即时的）：

```
spell_rate=0.50 → auto_apply: ... spells=1/2   status magic=[4000]
spell_rate=0.00 → status magic=[] [] []         + 敌人在 6 m：12 s 内 bullet_probe max_seen=0
spell_rate=1.00 → status magic=[4000,4070]      + 敌人在 6 m：bullet_probe total=2 clone=2
```

这是目前**唯一**能「LLM 说别放法术就真不放」的开关，也是 M4 的验收证据之一。

### 17.3 平滑与部分更新

- DLL 侧 `Weights::blend(prev, next, 0.15, 0.03)`：一包只走 15%（实测 0.5 → 0.65），
  `|Δ| < 0.03` 直接丢弃（防抖）；sidecar 的 `Guard` 是同一套参数（`--max-delta/--hysteresis`）。
- **修掉一个会误导判断的坑**：`WeightsIn` 以前是 `f32` + `#[serde(default)]`，
  只发 `{"aggression":0.9}` 会把其余 8 个权重**静默清零**。实测时 `spell_rate` 被清零
  但克隆体照样施法，差点写成「施法权重无效」。现在字段全是 `Option<f32>`，
  没发的沿用上一轮（`WeightsIn::merged`），日志也会打印合并后的值。

### 17.4 战斗验证台：不用用户参战也能量

**（a）`spawn_debug` 的坐标 bug**：`ChrDebugSpawnRequest` 要的是**世界坐标**
（physics matrix 那套），旧代码传的是 `chunk_position`（block 内局部坐标，玩家在
`40,-88,-80`），于是「日志说生成了、场上什么都没有」。修好后可以把敌人放在指定距离：

```
spawn_debug at (5.5,4.9,1.8) npc=30600000 think=30600000 chara=-1 dist=10.0
dump_chrs: 30000000 team 6 dist 22.6 pos [15.9,5.0,10.4]
```

顺带确认：`chara_init_param_id = -1` 对普通敌人是可用的（`ChrInitParam` 是出生装备表，
敌人不需要）。

**（b）`dummy`：把一只克隆体临时改成敌对队**

`ChrIns.team_type` 是运行时字段（克隆体本来就是 team 47 的 PlayerIns），
改成 6 之后另外两只克隆体会把它当敌人打；`dummy {"on":false}` 还原。

```
dummy: clone #2 team 47->6, hp 680x680 (test target)
combat: dummy=595 dmg=85 ...        ← 30 s 打掉 85 血（可量化）
dummy off: 1 chr restored to team 47
```

**改不动的部分**：`current_max_hp` 每帧被引擎按属性重算（写 30000，下一帧回 680），
所以指标从「打掉我灌的假血」改成「掉血速度 / 多久打死（TTK）」。
`auto_apply` 现在只作用于 team 47，不会再给木桩重写档案（之前会把 HP 上限写回去）。

**（c）新探针**

| 命令 | 作用 |
|---|---|
| `combat_probe` | 木桩血量/掉血 + 克隆体血量/距离 + 子弹归属 → `er_echo_combat.json` + 一行日志 |
| `weights_probe` | 读回 think/behavior 行里被权重写过的字段（验证「写进去了没有」） |
| `status` | 克隆体（等级/血量/FP/距离/法术）+ 木桩 + 最近敌人 + 权重 + 开关 → `er_echo_status.json` |

### 17.5 M5 打磨

| 项 | 做法 | 状态 |
|---|---|---|
| 状态面板 | `status` 命令 + F6 热键 + 每 30 秒自动打一条（`[debug] auto_status`） | ✅ |
| 敌人判定 | `team_type` 0（中立/Torrent）与 1（玩家自己）不再算敌人（之前 556 个「敌人」） | ✅ |
| 日志 | 轮转（>8 MB → `.1` → `.2`）+ 每行带 `+Xs`（相对进程启动，便于对帧号） | ✅ |
| 崩溃取证 | 每 60 帧写 `er_echo_heartbeat.txt`（帧号 + 最后一个高危操作），下次启动第一条日志就报 | ✅ 实测报出 `previous session heartbeat: frame=12720 op=spawn_debug` |
| 安全模式 | `[debug] safe_mode` / `safe_mode` 命令：关掉事件召唤 / 灵体摘除 / 木桩 / 调试生成 | ✅ 实测 `dummy` 返回 `safe_mode on: dummy disabled` |
| 热键 | F6 状态、F7 收回、F8 召唤、F9 重读档案、F10 调试、F11 注入开关 | ✅ |
| 掉队保底 | `[tuning] lost_resummon`：全体 >`lost_distance`(150 m) 持续 `lost_seconds`(15 s) → 解散重召 | ⚠️ 代码就位，未实测触发 |
| 重召 | `resummon`：解散 → 等 manager 清干净 → 再请求；引擎忽略 `disappear_requested` 时退化为「补一队」 | ⚠️ 部分 |

**重召的坑（实测）**：`summon_anywhere` 每帧把 `disappear_requested` 置回 false，
所以「解散」要先停掉门禁绕过（`DISMISS_AT`）。即便如此，引擎在多数状态下**直接忽略**
消失请求（8 秒 `dismiss: timeout (3 left)`），然后也不接受第二次召唤请求 ——
因为管理器的 `active_summon_speffect_id` 还停在 232000，「已经在召」时写 request 会被丢掉：

```
resummon: dismiss requested; summon in 300 frames
dismiss: timeout (3 left) — stopping dismiss
resummon: previous squad still alive (3 clone) — dismiss ignored, summoning an extra squad
resummon: request sent (settled=false)
status: clones=3   ← 请求发了，但引擎没生成
```

**结论**：DLL 侧能可靠做到的只有「不卡死 + 如实报错」；真正解散/重召要靠引擎自己
（读档/传送/坐火时 `active_summon_speffect_id` 才会归 -1，这正是事件召唤能工作的原因）。
所以 `lost_resummon` 目前只是「告警 + 尝试」，不能保证把队友拉回来。
另外克隆体出场时会掉一点血（实测 680 → 522，疑似召唤落地的坠落伤害），不影响功能。

### 17.6 命令表（新增）

| 命令 | 作用 |
|---|---|
| `status` | 一行紧凑状态 + `er_echo_status.json` |
| `combat_probe` | 战斗采样（木桩/克隆体/子弹） |
| `dummy {"on":true,"who":0,"team":6}` | 把第 N 只克隆体变成敌对木桩（可逆） |
| `weights_probe` | 读回 think/behavior 行 |
| `resummon` | 解散 + 重召（引擎不配合时补一队） |
| `safe_mode {"on":true}` | 关掉高风险特性 |
| `magic_player {"ids":[...]}` | 临时给**玩家**写记忆槽（只改内存，用于对照实验） |

### 17.7 还没做

- `NpcAiBehaviorProbability` 的槽位语义仍未证实 → 默认 `behavior_row=0` 不写；
- `combo_rate / item_rate / heal_priority / spacing` 还没有可靠落点（只有 think 行里
  那几个距离/防御字段是真起作用的）；
- `lost_resummon` 的真实触发（需要把克隆体丢到 150 m 外）没测；1 小时稳定性没测；
- 法术选择策略、LLM 改法术回写存档、队友骑马 — 同 §16.8。

## 18. 游戏内 UI：赐福菜单 + 置物包给装备（2026-11-15）

### 18.1 选型：不用 ImGui

需求是「在篝火处选人数/名单」「在置物包里把装备/法术给队友」。两者都能用原版 UI 完成：

* **篝火菜单** = ESD（`t000001000`）里的 `AddTalkListData` / `GetTalkListEntryResult`，菜单项和二级菜单都是原生 Scaleform；
* **文字** = 挂 `CSMsgRepository::LookupEntry`，对自定义 ID 返回 UTF-16 字符串（transmog / erdGameTools 同款做法）；
* **DLL 通信** = 菜单只写事件标志，DLL 每帧读、清零、执行。

这样没有额外窗口、没有 ImGui，手柄/键鼠、分辨率、语言都跟着游戏走。

### 18.2 ESD：赐福菜单里加「战友」

修改的是 `script/talk/m00_00_00_00.talkesdbnd.dcx` 里的 `t000001000`（赐福对话脚本）。
流程（工具链见 `er-echo/ui/README.md`）：

```text
Data0.bhd/bdt --(extract_game_file.py)--> m00_00_00_00.talkesdbnd.dcx
  --(esdtool -writepy)--> t000001000.py
  --(patch_grace_esd.py)--> t000001000.py（加 x900/x901）
  --(esdtool -writebnd)--> m00_00_00_00.talkesdbnd
  --(pack_talk_esd.py)--> m00_00_00_00.talkesdbnd.dcx（KRAK DCX）
  --(复制)--> mod/script/talk/
```

**ME2 必须真的加载 `mod/`**：`config_eldenring.toml` 的 `[extension.mod_loader] mods` 不能是
`[]`，否则 ME2 不碰 `mod/script/talk`，文件在磁盘上但游戏根本没读到（坐火看不到「战友」，
2026-11-16 实测）。正确写法：

```toml
mods = [ { enabled = true, name = "er-echo", path = "mod" } ]
```

另外根选项放在**赐福列表最上面**（`ClearTalkListData()` 之后的第一条），不要放在
「整理木箱」后面：列表一屏只显示前 6–7 项，放后面会被挤出可视区。

子菜单函数第一行必须是 **`CloseShopMessage()`**（vanilla `x78`/`x87` 都这样）。
少了它时选「战友」会把父菜单关掉又回到原列表 / 没有新选单（2026-11-16 实测）。

菜单结构（最终采用：根列表 5 项，无二级菜单）：

```text
赐福菜单（最上面 5 项）
├─ 队伍人数：2（点击切换）   ← 69100001，0→1→2→3→0
├─ 1号位：May（点击切换）    ← 69100002
├─ 2号位：May（点击切换）    ← 69100003
├─ 3号位：May（点击切换）    ← 69100004
├─ 立即重新召唤              ← 69100005
├─ （原版：消磨时间 / 升级 / 圣杯瓶 / 记忆 / 整理木箱 / 离去）
```

> **2026-11-16 二级菜单尝试记录（失败）：**
> 1. `x900` 所有 `if GetTalkListEntryResult()` 分支都 `return 0` → ESDLANG 把
>    `ClearTalkListData/AddTalkListData/ShowShopMessage` 编进 `Unused` 状态 →
>    点「战友」后**空菜单、HUD 消失**。
> 2. 改成 vanilla `x78` 形状（`CloseShopMessage` + `while True`，选项分支不 return）→
>    点「战友」后**立刻返回一级菜单**。
> 3. 去掉 `CloseShopMessage` → 仍然立刻返回。
> 结论：离线 ESD 重编译这条路走不通。参考 mod（erdGameTools / transmog）能做二级菜单，
> 是因为它们用 C++ 在**运行时**往 live talk machine 注入 `er::ezstate` 状态
> （`CloseShopMessage`/`AddTalkListData`/`ShowShopMessage` 事件序列），不是改 ESD 文件。
> 移植那套需要定义 `state/transition/expression` 结构并 hook `EzState::EnterState`，
> 是独立工程；目前保留已验证可用的根列表版本。

ESD 只做一件事：`SetEventFlag(6720..6728)`；菜单刷新/列表重建由游戏自己完成。
**不要**用 69031xxx 这类大号标志：`CSEventFlagMan` 的 group 表只有 14667 个 holder
（group = id/1000），69031 组不存在，`get/set` 静默失败，菜单点了等于没点（§18.6 实测）。
6720 段是社区自定义菜单常用段（Chat-with-Melina 用 6700-6703）。

### 18.3 消息钩子

`CSMsgRepository::LookupEntry` 是叶子函数：

```asm
3B 51 10          cmp edx, [rcx+0x10]   ; bnd < count
73 29             jae  +0x29             ; -> xor eax,eax; ret
44 3B 41 14       cmp r8d, [rcx+0x14]   ; msg < count?
73 23             jae  +0x23
48 8B 41 08       mov rax, [rcx+8]
...
```

我们的 ID（69100000+）比原版 FMG 条目大，**不能**在检查之后挂钩；必须在函数入口接住。
入口 15 字节正好是 5 条完整指令，没有栈帧：

* 入口写 15 字节绝对跳转（`FF 25 00 00 00 00` + u64 + 3×NOP）；
* trampoline 复制这 15 字节，fallthrough 跳回 `target+15`；
* 两条 `jae` 都跳到 `target+0x2e`（`xor eax,eax; ret`），所以在 trampoline 的 `+0x2e`
  放一个绝对跳转，语义完全一致。

目标地址由 AOB `8B DA 44 8B CA 33 D2 48 8B F9 44 8D 42 6F`（thunk）解析 `call rel32`
得到；1.17.2 实测 `rva 0x2671370`。钩子装好后 `msg_test` 不打开任何菜单就能验证：

```text
msg_test: id=69100000 -> "战友（2/2）"
msg_test: id=15000395 -> "整理木箱"   ← 原版 ID 走 trampoline，证明参数顺序/回跳都正确
```

参数顺序是 **`(this, language, bnd, msg)`**：rdx 是语言/表索引，r8 是 bundle，r9 是 msg。
一开始按 `(this, bnd, msg, lang)` 写，`msg_test` 传 `(repo, 33, 69100000, 0)` 也能“碰巧”
命中自定义 ID，但游戏真实调用 `(repo, 0, 33, 69100000)` 时匹配不到，菜单文字会全空。
用原版 `15000395` 走通 trampoline 才确认了正确顺序。

### 18.4 人数 / 名单

`er_echo_roster.json`：

```json
{ "v": 1, "count": 2, "slots": [0, 1, 0] }
```

* `count` 0..3；`slots[i]` 是 `er_echo.ini` `[clone] profiles` 列表里的下标；
* 启动时若没有该文件，按 profiles 数量生成默认值（count=min(3,n)）；
* 第 i 个克隆体用 `slots[i]` 的档案，`auto_apply_clones` 每 15 帧按它重写；
* 人数落到载体骨灰行：`BuddyParam.trigger_sp_effect_id` 第 4 个以后改 `-1`
  （`params::apply_buddy_count`），实测 `count=2` 时只生成 2 个克隆体。

菜单标志 → DLL（`roster.rs`）：

| 标志 | 含义 |
|---|---|
| 6720..6723 | 人数 = 0/1/2/3（保留，旧版直接选项用） |
| 6724..6726 | 1/2/3 号位切到下一个档案 |
| 6727 | 立即解散重召 |
| 6728 | 人数循环 0→1→2→3→0（赐福根列表用） |

实测：

```text
flag_test: id=6722 group=6 before=false after_set=true
roster: count -> 2 (slots=[0, 1, 0])
menu: companion count -> 2
ui: menu texts rebuilt (profiles=2, count=2, slots=[0, 1, 0])
```

### 18.5 置物包给队友（F12）

`F12` / `give_selected`：

1. 读 `CSMenuManImp.player_menu_ctrl.selected_goods_item` / `selected_magic_item`；
2. 选中武器 → 写槽 **1（右手当前武器）**，不碰 3/5（待切换）；
   选中防具 → 按 `EquipParamProtector.protector_category` 写 12..15（直接替换）；
   选中护符 → 17；选中法术 → `magic.insert(0, …)` 插到记忆列表**最前面**（`kit::apply`
   按 `spell_rate` 只取前 N 发，追加到末尾在低施法率下不生效）；
3. **改档案而不是改克隆体**：`auto_apply` 每 15 帧按档案重写，直接写克隆体会被覆盖；
4. 改完 `apply_to_clones(false)` 立即生效。

如果菜单没有选中项（`selected_* == NONE`），退化成「复制玩家当前装备」：
右手武器 + 头/身/手/腿。实测：

```text
give: current gear -> [(1, 2000000), (12, 10000), (13, 660100), (14, 10200), (15, 660300)]
      to 2 companion(s), 10 profile edit(s)
```

`clone_info` 回读确认槽 1 已变 2000000、防具四个槽已替换，且 5 秒后没有被 auto_apply 刷回去。

> **2026-11-22 更新**：没选中项时**不再**走上面这条「复制玩家当前装备」的旧路径，改为把队友
> 恢复成档案原样（§22）；旧日志留作历史记录。

### 18.6 限制 / 风险

* ~~**菜单视觉未自动实测**~~：已用 `tools/shot.ps1` 截图 + 键盘方向键/E 自动走位实测（见 §18.8）。
* `selected_goods_item` 是否真的等于「置物包光标」尚未验证；F12 的落点（武器槽 1 / 防具
  12–15 / 护符 17 / 法术最前）已验证。
* 武器只写 param id，**强化等级/质变**没有一起写（需要 gaitem handle 里的强化信息）。
* ESD 文件跟游戏版本绑定：升级后要按 `ui/README.md` 重新抽/反编译/编译。
* 6720..6727 是社区常用段，可能和别的 mod 撞；撞了改 `roster.rs` + ESD 两处。
* 标志会写进存档（DLL 读完立刻清零；`roster::clear_flags` 启动时再清一次）。

### 18.7 新增命令

| 命令 | 用途 |
|---|---|
| `msg_test` / `--args '{"id":69100000}'` | 直接调 `LookupEntry`，验证自定义/原版文本（不打开菜单） |
| `flag_test` / `--args '{"id":6722,"keep":true}'` | 读写事件标志并打印 holder 信息；`keep=true` 可模拟 ESD 菜单置位 |
| `give_selected` | 等价于 F12：选中项给当前出场队友；没选中则恢复档案原样；改的是内存档案 |

## 19. 二级菜单：运行时 EzState 注入（2026-11-16 22:5x）

§18 的根列表 5 项是 fallback。用户要的是「赐福 → 战友 → 人数/名单/重召/返回」。
离线 ESD 试过三版都失败（handoff §3），这次按 handoff 的路线 1 移植参考 mod 的
运行时注入，**成功**。

实现全文见 [submenu-runtime-injection.md](submenu-runtime-injection.md)，要点：

1. `EzState::EnterState`（1.17.2 RVA `0x208be00`）用调用点 AOB 定位，
   入口 15 字节绝对跳转 + trampoline（prologue 无 RIP 相对寻址）；
2. machine 的 `state_group` 在 **+0x28**（运行时扫描确认）；用
   「entry_events 里有 `AddTalkListData(_, 15000395, _)`」认赐福 group；
3. 根菜单项插在 BFS 找到的**第一个加菜单项的 state**（x31/state 2，id 2）的
   entry_events 开头 → 排在赐福时间行之后的第一项；结果分支插在
   `GetTalkListEntryResult() == 6 → OpenRepository` 那条 transition 之前；
4. 二级菜单 state：`CloseShopMessage / ClearTalkListData / 6×AddTalkListData /
   ShowShopMessage(Regular)`；关闭后进 branch，按结果去 5 个
   `SetEventFlag` callback（6728/6724..6726/6727）或「返回」→ 根菜单循环入口
   （清空列表那个 state；跳 initial_state 不会重开菜单，实测会直接消失）；
5. callback 用 `GetCurrentStateElapsedTime() > 0.25` 等 DLL 刷完文字再回菜单
   （直接回会用旧文本建列表，实测「人数 2→3」显示 2）。

实测日志（1.17.2）：

```text
ezstate: EnterState hook installed at 0x7ff65e56be00 (rva 0x208be00, call site 0x7ff65e56a582)
ezstate: machine->state_group found at +0x28 (group=0x7ff476ec07c8, x31, 1 plausible candidate(s))
ezstate: patched grace group x31: item at state ...c490 (id 2) event[0],
         transition at state ...c640 [5], initial=...c400, events 2 -> 3, transitions 17 -> 18
menu: companion count -> 3 (cycle)
```

截图验证：根菜单第一项「战友（n/m）」→ 二级菜单 6 项 → 人数 0→1→2→3 循环并刷新、
号位切换、返回根菜单；HUD 正常、不空白。

部署变化：`mod/script/talk` 现在是**原版** ESD（`ui/out_vanilla`），根列表补丁版
留在 `ui/out_rootmenu`，用 `tools/switch_menu_mode.ps1 -Mode root|nested` 切换；
`er_echo.ini` 加 `[ui] nested_menu`。

命令：`menu_status` / `menu_dump` / `menu_reset` / `menu_enable --args '{"on":false}'`。

顺带修复：`mod/build.ps1` 是无 BOM 的 UTF-8，PowerShell 5.1 按 GBK 读中文注释时
会把下一行吞掉（`$live = ...` 整行变成注释），导致 DLL 从来没被复制到游戏目录；
已改为 UTF-8 with BOM。

## 20. 人数/重召修复 + 坐火卡顿（2026-11-17 00:1x）

用户反馈两件事：1）坐火严重卡顿；2）切换人数后点「立即重新召唤」没用，还是 3 人。

### 20.1 卡顿根因：EzState 钩子在非赐福机器上做全量扫描

`grace_group_of` 原本每次 `EnterState` 都扫 `+0x08..+0x200` 的每个偏移，并对
「长得像 state_group」的指针跑 `group_is_grace`（遍历 states/events）。提示类
talk machine 每秒会进很多次 EnterState，实测 **191 次调用累计 48 秒、单帧卡 30 秒**
（perf 日志：`max frame gap 30043ms, ezstate 191 calls/48158896us`）。

修复（`mod/src/ezstate.rs`）：

1. 首次在 `machine+0x28` 校验到合法 group 后置 `LAYOUT_OK`，之后热路径**只裸读一个指针**；
2. 只试已知偏移 `+0x28`，不再扫整段（版本变了就 passive，不卡游戏）；
3. `group_is_grace` 先比 group id（x31 = `0x7fffffff-31`），再限 states/events 上限；
4. 非赐福 group 负缓存，同一个 group 只查一次；
5. 注入完成后 detour 直接返回（`PATCHED_GROUP != 0`）。

修复后：perf 从 48s/191 calls 降到一次性 ~0.3s（而且主要是游戏自己的坐火世界重置）；
注入后 `ezstate 0 calls`（快速返回）。加的诊断：每 5 秒统计最大帧间隔和钩子耗时，
>400ms 或钩子累计 >20ms 才 warn（坐火/传送的正常 100~300ms 卡顿不报警）。

### 20.2 人数不生效根因：trigger→BuddyParam 映射是加载时建的

`SummonBuddyManager.trigger_speffect_to_buddy_map` 是**世界加载时**从
`BuddyParam.trigger_sp_effect_id` 建的 `ChainingMap`。运行时改 trigger 不会更新它：
实测人数=1、`buddy count: 1/3 active`，但引擎仍按旧映射把 3 行全召出来
（`auto_apply: 3 clone(s)`、`chrs 1->4`）。`summon_groups` dump 证实
`232000 -> [23200000, 23200001, 23200002]`。

修复（`mod/src/spirit.rs` + `params.rs` + `lib.rs`）：

1. `sync_trigger_chain`：人数变化 / 召唤前，把 trigger 链**截断或重连**到
   `rows[..count]`。桶项一直在 `ChainingMap.buckets` 数组里，只改 `next` 指针，
   不分配不释放。实测人数 1→3 后 dump 显示 `232000 -> 23200000`（截断成功）。
2. `trim_extra_buddy_groups`：召唤后按 `SummonBuddyGroup.buddy_param_id` 保留最多
   `count` 个组，其余置 `disappear_requested=true` + `disappear_delay_sec=0`
   （全局 `disappear_requested` 引擎经常忽略；逐组 delay=0 才真的走）。
3. `apply_buddy_count` 永远保留第 0 行的 trigger：全改成 -1 会把 map 的键删掉，
   之后 0→1 人时引擎找不到可召的行。
4. `summon_groups` 诊断命令：打印 groups（buddy id、disappear flag/delay、raw bytes）
   和 trigger_map。

实测：

* 1 人 → 菜单切到 3 → 立即重召 → `clones=3`；
* 3 人 → 菜单切到 1 → 立即重召 → `clones=1`（`status` 确认，不再多召）；
* 坐火不再出现几十秒冻结，perf 最大帧间隔回到游戏正常的 ~100–300ms（世界重置）。



## 21. 多语言 + 跨机器安装（2026-11-20）

### 21.1 菜单文案本地化（`mod/src/i18n.rs`）

游戏内可见文字只有赐福菜单那几行（`ui.rs` 的 `refresh_texts`），所以没做通用 i18n 框架，
只做「模板表 + 命名占位符」：

* 内置 `zh-CN` / `zh-TW` / `en` / `ja`；缺键回退 `en`，再缺原样返回 key（能看出拼写错误）；
* `language=auto`（默认）读 Windows 显示语言（`GetUserDefaultUILanguage`，LANGID
  0x04 简/繁、0x11 日，其他英文）——**没法**可靠地用游戏自己的语言：`CSMsgRepository`
  的 `lang` 参数没有公开的「索引 → 语言」映射；
* `er_echo_i18n.ini`（可选，游戏根目录）按 `[语言]` 段覆盖/新增语言，
  值里 `{count}` `{n}` `{i}` `{name}` `{level}` 由 `render()` 替换；UTF-8（BOM 也认）；
* 运行时也能切：`ipc_client.py set_language --args "{\"lang\":\"ja\"}"`。

注意点：

* 菜单用**游戏当前语言的字体图集**渲染，语言和游戏文本不一致会出现方块——
  `INSTALL.md` / `i18n.md` 都写了；
* ESD 的幂等判断靠 `ROOT_MSG`（69100000）而不是文字，所以换语言不影响注入；
* 日志里加了一行 `i18n: language=... (..., override file loaded/absent, builtin: ...)`，
  排障先看这行；`status` 的 `ui.language` 也是实际生效值。

测试：`cargo test --release --lib` 8 个用例（渲染 / 语言归一化 / 覆盖文件解析 /
四语言齐全性 / 逐语言拼装）。

### 21.2 可移植性审计（能不能在别人机器上生效）

结论：**能，但版本、加载器、写权限是硬门槛**（详见 `docs/INSTALL.md`）。证据：

* `er_echo.dll` 导入表只有系统 DLL：`kernel32 / msvcrt / ntdll / oleaut32 / user32 /
  ws2_32 / bcryptprimitives / api-ms-win-core-synch-l1-2-0` → 不需要 VC++/Python；
  架构 `0x8664`（x64 PE32+）；
* `vendor/.../eldenring/src/rva.rs` 只注册 `(EN, 2.7.2.0)` 与 `(JP, 2.7.2.1)`，
  其他版本 `rva::get()` 直接 panic；AOB 也是 1.17.2 逐字节匹配；
* 赐福菜单依赖版本绑定的 `mod/script/talk/m00_00_00_00.talkesdbnd.dcx`；
* 工具里原来写死 `D:\...\Game` 的 `swap_dll_on_exit.ps1` 改成按 `$PSScriptRoot` 推根目录；
  其余调试脚本（`live_test*` / `restart_and_test*` / `_probe_magic*`）维持在仓库里，但
  发布包已排除；
* 游戏目录写权限：DLL 要在 CWD 写 `er_echo.log` 等；装在 `Program Files` 下没授权时
  看起来就是「mod 没反应」。

### 21.3 两个新工具

* `tools/doctor.ps1`：只读预检（游戏版本 / ME2 两处配置 / DLL 架构+依赖 / ini 的
  profiles+language / ESD / 写权限 / Python），也能对发布目录跑（没有 exe 时自动降级）；
* `tools/package_release.ps1`：打 `dist/ER-Echo-<日期>.zip`，只收运行必需文件 + 工具 +
  文档；排除作者存档导出物、调试脚本、`mod/src|target`；自动关 ME2 debug、把 profiles
  指向示例、去掉作者 SteamID、给 `.ps1` 补 UTF-8 BOM（PS 5.1 读无 BOM 中文会乱码）。

### 21.4 验证

* `cargo build --release` 通过；`er_echo.dll` 落在游戏根目录（SHA256 见打包输出）；
* `cargo test --release --lib` 8/8；
* 对游戏目录跑 `doctor.ps1`：0 阻断（2 条警告：ME2 `debug=true`、IPC token 默认值）；
* 对发布目录跑 doctor：0 阻断；zip 0.86 MB / 58 个文件。
* 脱离游戏的冒烟测试（同一个 DLL，用 LoadLibrary 注入普通 PowerShell 进程）：
  - `language=auto` → `i18n: language=zh-CN`；
  - `language=ko` + `er_echo_i18n.ini` → `language=ko ... override file loaded`；
  - `language=zz-ZZ` → 保留自定义代码、回退英文；
  - 没有游戏时 `wait_for_instance` panic 被 `catch_unwind` 接住，进程不崩；
  说明 DLL 的依赖、配置解析、i18n 初始化在「干净机器」上就能跑通。

## 22. F12 没选中时恢复档案原样（2026-11-22）

**问题**：`selected_goods_item` 并不总能拿到置物包光标（§18.6 一直未验证）。旧逻辑在没选中时
「复制玩家当前整套装备」——按错一次 F12 就把玩家装备糊到队友档案上，且没有任何提示。

**改法**（`mod/src/lib.rs`）：

1. 新增 `ORIGINAL_PROFILES` 快照，装档案统一走 `install_profiles()`：四个来源都会同时更新快照 ——
   `reload_profile()`（F9 / 环境变量 `ER_ECHO_PROFILE`）、IPC `load_profile`、
   IPC `set_clone_profiles`、`apply_config_once()`（ini 的 `profiles=`）；
   `set_equipment` / `set_stats` / `rollback_equipment` 只改当前档案，不动快照；
2. `give_selected()` 在 `selected_goods_item` / `selected_magic_item` 都为空时，不再读玩家
   `chr_asm`，改为按 `roster::active_count` + `slot_for_clone` 遍历出场队友，把
   `equipment_param_ids` 和 `magic` 拷回快照值，再 `apply_to_clones(false)`；
3. 恢复范围**只有** F12 能改的东西（22 个装备槽 + 法术列表）；等级/属性/外观/脸不动
   （那是 `set_stats` / F9 重载档案的事）；
4. 日志：`give: restore original gear for N companion(s), K field(s) reverted`；
   IPC `give_selected` 返回 `give: restore original -> N companion(s)`；
5. 名单人数为 0 时仍报 `no active companion (summon first)`；没加载档案报
   `no clone profiles loaded`。

**文档同步**：`docs/usage.md` 的给装备流程与排障表、`README.md` 能力表/热键、
`nexus/changelog.md`（Unreleased）、`nexus/description.bbcode`、`docs/design.md` 的 M6 说明；
顺手改正 §18.5 的「法术 → 第一个空位」（代码实际是 `insert(0, …)`）。

**验证**：`cargo build --release` + `cargo test --release --lib` 8/8 通过。**没在游戏里实测**
（这台机器上没法合成输入）；游戏内可用 IPC 验证：先用 F12 改掉队友装备，再在菜单外按 F12，
日志应出现 `restore original gear`，`clone_info` 回读应回到档案值。

## 23. 队友伤害修正 / 升级跟随 / 友伤（2026-11-22）

### 23.1 找到「骨灰伤害修正」到底在哪

用离线解密 + BND4/Param 解析（`regulation.bin` = AES-256-CBC → DCX/ZSTD → BND4）核对
1.17.2 的拟态泪滴行，确认：

* `NpcParam` **100000010**（人形泪滴）/ **133201000**（史莱姆）的常驻 spEffect 槽里都有
  **`296000`**，其字段正好是社区说的「骨灰削弱」：
  - `atkPlayer/atkEnemyDmgCorrectRate_*` = **0.25**（造成伤害 ×0.25）；
  - `defPlayer/defEnemyDmgCorrectRate_*` = **0.5**（受到伤害 ×0.5）；
  - `saAttackPowerRate` = **0.05**（削韧伤害 ×0.05）。
* 另有 **`20297000`**：`saReceiveDamageRate` = 0.5（受到削韧 ×0.5）。
* `5400/5401`（灵体基础）、`290200..290210`（骨灰强化 doping）、`90000/90010` 等
  的伤害/削韧倍率都是 1.0 —— 它们不是「队友伤害只有玩家四分之一」的来源。

**改法**（`mod/src/spirit.rs` + `lib.rs`）：

1. `SUMMON_CORRECTION_SPEFFECTS = [296000, 20297000]`；
2. `apply_config_once()` 里用 `strip_npc_speffect_slots()` 把这两个 id 从
   **100000010 / 133201000 的 NpcParam 常驻槽**改成 `-1`（只影响拟态泪滴，之后的召唤不再挂削弱）；
3. tick 每 15 帧用 `strip_speffects()` 从场上克隆体身上摘掉（兜底「已在场 / 变身 / 重招」）；
4. 没有改 `SpEffectParam` 行本身：玩家用其它骨灰召出来的灵体保持原版数值；
5. ini `[clone] player_damage=false` 可关；`damage_probe` 输出 NpcParam 常驻槽和每只克隆体的
   spEffect 列表/`has_correction`/`disable_lock_on`。

### 23.2 玩家升级 → 队友跟升 + 写回 profile

* `PlayerLevelSnapshot { level, stats[8], hp/fp/stamina = base_max_* }` 存在
  `PLAYER_LEVEL_BASE`，每 30 帧采一次；
* 等级上升时才计算增量：`dlevel` + 8 个属性差值 + 三围上限差值；
* `Profile::apply_level_up()` 把同样的加点追给**所有已加载档案**（不是只追当前出场的），
  等级封顶 713、属性 1..99、`pools` 有值才加；
* `ORIGINAL_PROFILES`（F12 恢复快照）同步跟升，避免两份档案等级不一致；
* 档案来源路径新增 `CLONE_PROFILE_PATHS`（`install_profiles(profiles, paths)` 统一写入）：
  `apply_config_once`（ini）、`load_profile` / `set_clone_profiles`（IPC）、`reload_profile`
  （F9）都会带路径；自动升级后用 `save_profile()`（`.json.tmp` → rename）写回；
* 场上克隆体立刻 `kit::apply_stats()` 重写 `level/stats/pools`（不碰装备/外观/法术）；
* 读档/切号（等级下降）只重设基线，不追升；`[clone] auto_level=false` 可关；
  `level_status` 输出基线 + 每份档案的 `level/path`。

### 23.3 赐福菜单「友伤」

* 菜单：`ezstate.rs` 的二级菜单从 6 项变 7 项（新增 `MSG_FRIENDLY = 69100007`、
  callback `FLAG_FRIENDLY_FIRE = 6729`），文案 `friendly_fire_on/off` 四语言；
* 状态存 `er_echo_roster.json.friendly_fire`（旧 roster 没这个字段时用 ini 默认值）；
* 打开：`AtkParam_Pc` 全表 `friendlyTarget = 1`（只改 PC 表，`AtkParam_Npc` 不动），
  于是玩家和克隆体（都是 `PlayerIns`）的攻击能命中友军；
* 同伴仍是 `team_type=47`、`isBuddyAI=1`、`team_attack_effectivity=0`，AI 不会把玩家当敌人；
* 每 15 帧给克隆体钉 `ChrCtrlModifierActionFlags::disable_lock_on = true`
  并清 `is_locked_on`；关闭友伤时还原；
* 记录 `FRIENDLY_PATCHED`：关闭时只还原「原本不是 friendlyTarget」的行，不覆盖原版/其它 mod；
* IPC：`friendly_fire --args '{"on":true}'`、`friendly_fire_status`。

### 23.4 验证

* `cargo check --release` 通过；`cargo test --release --lib` **12/12** 通过
  （新增 4 个 `Profile::apply_level_up` 测试；i18n 四语言键表齐全）；
* 离线核对依据：regulation.bin 1.17.2 的 `NpcParam` 100000010/133201000 常驻槽、
  `SpEffectParam` 296000/20297000 字段值（见 §23.1）；
* **未在游戏内实测**：本机没法合成输入。游戏内建议按顺序验证：
  1. `damage_probe` → `has_correction=false`、NpcParam 常驻槽里没有 296000/20297000；
  2. 坐火升 1 级 → `level_status` 档案等级 +1、日志 `levelup: ... wrote [...]`，
     `clone_info` 回读场上克隆体等级 +1；
  3. 菜单「友伤：开」→ `friendly_fire_status` 的 `friendly_target_rows` 明显上升，
     用武器砍队友/让队友砍自己都能掉血；`damage_probe` 的 `disable_lock_on=true`，
     准星不能锁队友。

## 24. 安装器 GUI 设置持久化 + 默认英文（2026-11-22）

**问题**：`ER-Echo-Setup.exe` 每次打开都把游戏路径/存档/输出目录/`er_echo.ini` 重置成自动探测值；
语言默认 `system_lang()`（中文系统就是中文）。

**改法**（`tools/profile_export_gui.py`）：

1. 统一用 `QSettings("ER-Echo", "ProfileExport")`（Windows 注册表
   `HKCU\Software\ER-Echo\ProfileExport`）保存：
   `lang`、`save_path`、`out_dir`、`ini_path`、`setup_path`、`setup_save`、`tab`、`geometry`；
2. 所有 `QLineEdit.textChanged` + 页签切换接 500ms 防抖 `QTimer`，关闭窗口时
   `closeEvent` 强制 `_save_settings()`（含 `QSettings.sync()`），不会因为没点按钮而丢；
3. 启动时 `_restore_settings()` 优先用保存值；路径字段为空才走
   `pick_default_save()` / `find_inis()` / `setup_autostart()`；
   窗口位置/页签也在 `_restore_window_state()` 恢复；
4. **默认英文**：没有显式选择时 `lang="en"`；`--lang auto` 仍可跟系统。
   旧版只存了 `lang`，没有 `lang_explicit`；其中 `lang=zh` 可能只是当年的默认值，
   所以启动时忽略它并按 `en` 启动。用户真正从下拉框选过语言会写
   `lang_explicit=true`，之后继续沿用（实测 `lang=zh` + 无 flag → `en`；
   `lang=zh` + flag=true → `zh`）；
5. `er_echo_setup.py` 的 `INI_TEMPLATE` 改为 `[i18n] language=en`，
   并补上 `player_damage=true`、`auto_level=true`、`[combat] friendly_fire=false`
   （新安装的默认值；DLL 侧 `Config` 的 `language` 兜底也从 `auto` 改为 `en`）。

**验证**（实际运行重新打包的 exe，offscreen）：

* 清空 QSettings、只写旧 `lang=zh` → 启动后写回 `lang=en`，并保存
  `save_path / out_dir / ini_path / setup_path / setup_save / tab / geometry`；
* `lang=zh` + `lang_explicit=true` → 启动后仍是 `zh`（保存的显式选择不被覆盖）；
* 测试完已删除测试用注册表键，用户下次打开按默认英文 + 自动探测，随后正常记忆。

**打包**：`tools/build_gui_exe.ps1 -SkipInstall -SkipPayload -SkipIcon` 重新生成
`dist\tools\ER-Echo-Setup\` 和 `ER-Echo-Setup-0.2.0.zip`；payload DLL 仍是
`D45AD955…3468CE`，`--selftest-setup` errors=0。文档同步到
`docs/INSTALL.md`、`usage.md`、`i18n.md`、`INSTALL.en.md`、`nexus/changelog.md`。

## 25. 友伤倍率降到 20%（2026-11-22）

**问题**：上一版友伤只是把 `AtkParam_Pc.friendlyTarget` 打开，友伤是 100% 武器伤害；用户要
「20% 左右」。

**不能直接改 AtkParam**：`AtkParam_Pc.atkPhys/atkMag/...` 是玩家打**所有**目标的伤害，
改 20% 会让打敌人也只剩 20%。因此改为给**克隆体**挂一条临时 spEffect：

* `atkPlayerDmgCorrectRate_*` = 克隆体打**玩家类目标**的伤害倍率（克隆体→玩家）；
* `defPlayerDmgCorrectRate_*` = 克隆体受到**玩家类攻击**的伤害倍率（玩家→克隆体）；
* `atkEnemy/defEnemy/defObj = 1`：克隆体打/受普通敌人的伤害都不变；
* **只挂克隆体，不挂玩家**。第一版把玩家也挂了，用户实测「敌人打玩家的伤害也变低」；
  现在玩家本体完全没有该 effect，所以敌人→玩家、玩家→敌人都保持原伤害。

**实现**：

1. 选一条在 regulation 其它 param 表里**没有任何引用**的高 id SpEffect
   **`20011466`**（原字段 `def* = 0`，像调试/占位行）；
2. `params::patch_friendly_damage_effect(rate)` 把它改成
   `effect_endurance=-1`、`atkPlayer*=rate`、`defPlayer*=rate`、`atkEnemy*=1`、`defEnemy/defObj=1`，
   并保存原 22 个字段；`restore_friendly_damage_effect()` 关闭时原样写回；
3. `FRIENDLY_EFFECT_READY` 守卫：patch 失败时**绝不**把原行（`def*=0` = 无敌）挂到角色上；
4. `spirit::set_friendly_damage_effect()` 只给 `is_clone()` 挂/摘（不含 `main_player`）；
   tick 每 15 帧重挂（死亡/重载后恢复），关闭时先摘 effect 再还原行；
5. 倍率可配：`[combat] friendly_fire_rate=0.2`（clamp 0.01–1.0）；
   IPC `friendly_fire --args '{"on":true,"rate":0.15}'`；菜单文案显示 `20%`；
6. POISE/削韧不缩放（只缩放 HP 伤害）；`friendly_fire_status` 输出 `damage_rate/effect_id/effect_ready`。

**验证**：`cargo check --release` + `cargo test --release --lib` 29/29 通过；离线核对
`20011466` 在 regulation 其它表无引用、字段为空。**未在游戏内实测**：
游戏内开友伤后看 `friendly_fire_status`（`effect_ready=true`、`damage_rate=0.2`），
`damage_probe` 里克隆体的 `speffects` 应包含 `20011466`，玩家 `player_has_effect=false`；
用武器互相打应约为原伤害的 20%，
打普通敌人仍是原伤害。payload DLL `E8CE6719…FD5663E`。

## 26. 赐福菜单：每个队友单独的 AI（2026-11-22）

**需求**：赐福菜单里能**分别**调每个队友的 AI，并且调完要**持久化写回各自的 profile**。

### 26.1 为什么不能直接改共享 think 行

三个克隆体都是 `npc_param_id = 100000010` 的 `PlayerIns`，think 行也全是
`NpcThinkParam 100000010`。`params::apply_weights()` 写的是**这一行**，改一个人等于改三个人
（§17.1 的 aggression → 交战半径就是这么落的）。要做「分别调」，必须让每个号位有**自己的行**。

可行点：引擎在**生成那一刻**按 `BuddyParam.npc_think_param_id` 取 think 行，而载体骨灰正好是
3 行（`23200000..2`）。所以：

* 三个号位各指一行 `NpcThinkParam`；
* 每次同步时先把全局行（`think_row`，默认 100000010，已含 LLM/全局权重）**整行按字节复制**过去，
  再只覆盖该号位预设的 4 个字段 —— 不依赖借来的行原本是什么 AI；
* `clone_think_row()` 用 `size_of::<NPC_THINK_PARAM_ST>()` 做原始字节复制（同表同结构体，
  行内存连续、行里没有 id 字段；id 在 row descriptor 里，不在结构体里）；
* 借的行默认 `100000020 / 100000030 / 100000040`：1.17.2 的 think dump 里它们和 100000010
  的 `logic_id=10000 / battle_goal_id=29999 / is_buddy_ai=1 / eye=2 / backhome=9979` 完全一致
  （拟态泪滴家族），只是 id 不同；就算改动前它们被原版内容用过，行为也和基准一样，不会串 AI；
* 这些行**只在当前这局内存里改**，重启游戏从 regulation 重新读回；行不存在 / 填 0 时该号位
  自动退回共享 `think_row`（日志 `assigned` 里会显示 100000010）。

### 26.2 哪些旋钮能按人分开

| 旋钮 | 落点 | 生效时机 |
|---|---|---|
| `aggression` | 该号位 think 行的 `eye_dist / search_eye_dist / battle_start_dist / battle_eye_update_dist` | 下次召唤 |
| `guard_rate` | 该号位 think 行的 `is_guard_act`（`NpcParam` 的防御角度/减伤仍是共享行，跟全局） | 下次召唤 |
| `target_switch` | 该号位 think 行的 `search_target_lv1/lv2_forget_time` | 下次召唤 |
| `spell_rate` | **该克隆体自己的记忆槽开几发**（`kit::apply`，§17.2） | 立即（`auto_apply` / 菜单点击时重写） |

没进预设的 `dodge_rate / combo_rate / heal_priority / item_rate / spacing` 没有按实体区分的落点
（behavior 表共享且槽位语义未证实），所以菜单里不提供，避免给出无效选项。

### 26.3 预设与 profile 持久化

`ai.rs` 新增 `AiPreset`（`balanced / melee / caster / guardian / aggressive`）与
`AiProfile { preset, aggression, spell_rate, guard_rate, target_switch }`：

| 预设 | aggression | spell_rate | guard_rate | target_switch |
|---|---|---|---|---|
| `balanced` | 0.50 | 0.50 | 0.50 | 0.50 |
| `melee` | 0.75 | 0.00 | 0.25 | 0.50 |
| `caster` | 0.50 | 1.00 | 0.20 | 0.60 |
| `guardian` | 0.25 | 0.30 | 1.00 | 0.25 |
| `aggressive` | 1.00 | 0.50 | 0.15 | 0.90 |

`Profile` 新增 `#[serde(default, skip_serializing_if = "Option::is_none")] ai: Option<AiProfile>`：

* **写在档案里**（不是 roster）：换 `profiles=` / 换号时 AI 跟着角色走；两个号位选中同一份档案则共享；
* 没设置 = `None` = 跟随全局权重，**不碰**独立 think 行 —— 谁都没点过菜单时行为和加功能前完全一样；
* 菜单点一次 → 改内存档案 + `save_profile()`（`.json.tmp` → rename）写回源文件；
  没路径（IPC 临时加载）只改内存并 warn；写盘失败只 warn，菜单里的状态仍然生效；
* 手改数字（不等于预设值）→ 菜单显示「自定义」（`AiProfile::label_key()`）。

### 26.4 菜单 / 标志 / 文案

* 二级菜单从 7 项变 8 项：`队友 AI（点击进入）`（`MSG_AI_MENU = 69100008`，插在 3 号位与
  「立即重新召唤」之间）；
* 三级菜单 4 项：1/2/3 号位（`69100020..69100022`）+ 返回（复用 69100006）；
  点号位 → `SetEventFlag(6730/6731/6732)` → 0.25 秒后回三级菜单（可连续调几个人），
  「返回」→ 二级菜单 state；
* `roster::FLAG_AI_SLOT = [6730, 6731, 6732]`，`ALL_FLAGS` 从 10 个变 13 个（启动/读完后清）；
* `ui::refresh_texts()` 每行显示「{i}号位 {name}：{预设}」；`inherit` 显示「默认」、
  手改数字显示「自定义」；
* i18n 新增 9 个键 × 4 语言：`ai_menu / ai_slot / ai_default / ai_custom / ai_balanced /
  ai_melee / ai_caster / ai_guardian / ai_aggressive`（`er_echo_i18n.ini` 可覆盖）。

### 26.5 同步时机与 IPC

`sync_teammate_ai()`（`lib.rs`）：读每个号位的档案 → 算合并权重 → `clone_think_row` +
`write_think_weights` → `BuddyParam.npc_think_param_id`。调用点：

* `apply_config_once()`（第一次召唤之前；用已有 repo，不重入 `params::repo()`）；
* 菜单改人数 / 号位 / AI（`poll_roster_flags`）；
* LLM `set_weights` 生效后（每号位行从新的全局行重新复制）；
* `load_profile` / `set_clone_profiles` / F9 重载；
* tick 每 600 帧（20 s）兜底一次。

新命令：

| 命令 | 作用 |
|---|---|
| `teammate_ai_status` | 每号位档案/AI/think 行 + 载体行当前 think id，另写 `er_echo_teammate_ai.json` |
| `set_teammate_ai {"slot":0,"preset":"caster"}` | 等价于菜单点 1 号位；`preset` 可换 `aggression/spell_rate/guard_rate/target_switch` 手调 |
| `set_teammate_ai {"slot":0,"inherit":true}` | 删掉 `ai` 段，回到跟随全局 |
| `teammate_think_rows {"rows":[100000020,100000030,100000040]}` | 运行时换借的行（下次召唤生效） |

`status` 的 `roster` 里新增 `ai / ai_think_rows / buddy_think`，一行状态里显示 `roster(... ai=[...])`；
LLM state 的 `clones[]` 每只也带 `ai`（`inherit` / 预设名）。

### 26.6 验证

* `cargo check --release` 通过；`cargo test --release --lib` 全部通过（本次新增 9 个用例：
  预设循环 / 预设数值范围 / profile 缺省与 JSON round-trip / 手改数字→自定义 /
  `AiPreset::parse` 别名 / 老 profile 无 `ai` 字段 / 未知预设回退）；
* 离线核对：1.17.2 `er_echo_think.json` 里 100000010 / 100000020 / 100000030 / 100000040
  的 logic/goal/buddy/距离字段一致（都是拟态泪滴家族），所以把它们当基准副本用不会串 AI；
* 离线加载冒烟：把新 DLL `LoadLibrary` 进普通 PowerShell 进程，日志正常出现
  `i18n: language=zh-CN`，随后按预期报 `wait_for_instance panicked`（非游戏进程）并保持空闲，
  没有 DllMain/配置解析崩溃；
* **未在游戏内实测**（本机有 1.17.2 游戏安装，但当前没有安装这个 mod，也没有可靠的输入合成）。
  游戏内建议按顺序验证：
  1. 坐火 →「战友 → 队友 AI」→ 1 号位点到「法术」：日志应有
     `ai: slot 1 profile[i] '...' -> caster ... write_back=true` 和
     `ai: think row per slot [100000020, 100000010, 100000010] ...`；
  2. 看该 profile JSON 多了 `ai` 段；重启游戏（reload）后菜单仍显示「法术」；
  3. 起身/重召 → `teammate_ai_status`：`buddy_think` 第 1 位应是 100000020；
     1 号位法系角色的记忆槽应为全开（`status` 的 `magic=[...]`），交战半径更大；
  4. 把 1 号位设成「近战」→ `status` 里该克隆体 `magic=[]`（法术槽立即清空）；
  5. 两个号位设不同预设（如 1 号位近战、2 号位法术）→ 两只的距离/举盾/施法应不同。

**文档同步**：`README.md`（能力表 + 菜单）、`docs/usage.md`（菜单/INI/IPC/排障）、
`docs/i18n.md`（9 个新键 × 4 语言）、`docs/submenu-runtime-injection.md`（三级菜单结构）、
`install/er_echo_i18n.example.ini`、`nexus/changelog.md`。

---

## 27. 战友模式：按出战友人数补正敌人生命值（2026-11-22）

### 27.1 需求 / 规则

开启战友模式（有同伴出场）时，敌人生命值按**当前出场且还活着**的战友数量补正：

| 战友人数 | 敌人生命上限 |
|---|---|
| 0 | ×1.0（不补正） |
| 1 | ×1.5 |
| 2 | ×1.8 |
| 3 | ×2.0 |

倍率可在 `er_echo.ini` 的 `[balance] enemy_hp_rates=1.5,1.8,2.0` 改；`enemy_hp_scaling=false` 关闭。

### 27.2 落点：为什么写 `CSChrDataModule`，不写 `NpcParam`

`NpcParam.hp` 是生成时读一次的（i16，后期 Boss 翻倍还会溢出）。玩家通常进 Boss 房之后
才召唤战友，此时 Boss 已经生成，改 param 行影响不到它。所以直接写每个敌人自己的
`CSChrDataModule { hp, max_hp, max_uncapped_hp, base_hp }`：

* `max_hp` 是血条/受击/死亡判定读的值；
* `base_hp` 一并按倍率写 —— 引擎因 spEffect / 阶段变化重算上限时仍带着倍率；
* `hp` 在倍率变化时按当前百分比缩放（满血仍满血，半血仍半血）。

`balance::tick()` 每 15 帧跑一次（约 0.25 s 内生效）：

1. 数当前活着的克隆体（`summon_buddy_chr_set` + `spirit::is_clone` + HP > 0）；
2. 遍历 `world.chr_sets` 里的敌对 NPC（跳过玩家/中立/team 47/我们的克隆体/`PlayerIns`）；
3. 第一次见到：记录原始四件套 + 写入 `原始值 × 倍率`；
4. 人数变化：按当前 HP 百分比换算到新上限；
5. 引擎把上限改回原值（阶段/重算）：下一次 tick 检测 `max_hp` 与上次写入值不一致，重新补；
6. 收起战友 / `enemy_hp_scaling=false`：按当前 HP 百分比写回原始四件套（不借机回血）。

### 27.3 配置 / IPC / 诊断

* `[balance] enemy_hp_scaling` / `enemy_hp_rates`（`install/er_echo.ini.template` 已加注释）；
* `enemy_hp_status`：当前人数/倍率/跟踪数/`consistent_live`，以及最近 16 只敌人的
  `hp / max_hp / max_uncapped_hp / base_hp / tracked / scale`，另写 `er_echo_enemy_hp.json`；
* `enemy_hp_scale {"on":false}` / `{"rates":[1.5,2.0,2.5]}`：运行时临时改；
* `status` 行新增 `flags(... ehp=2.00 ...)`；人数/倍率变化日志：
  `enemy_hp: comrades 3 -> 2, enemy max HP x2.00 -> x1.80`。

### 27.4 验证

* `cargo build --release` 通过；`cargo test --release --lib` **29/29** 通过
  （新增 8 个：倍率表 / clamp / 满血保持 / 半血按比例 / 降倍率按比例 / 收起战友按百分比还原 /
  0 与负值 / 近似相等容差）；
* **未在游戏内实测**（本机游戏目录当前没装 DLL/ME2 配置，且 Program Files 不可写）。
  游戏内建议按顺序验证：
  1. 进游戏、召唤 3 个战友 → 日志出现 `enemy_hp: comrades 0 -> 3, enemy max HP x1.00 -> x2.00`；
  2. 找一只敌人（或进 Boss 房）→ `enemy_hp_status`：`multiplier=2.0`、`tracked_live>0`、
     `consistent_live` 应等于 `tracked_live`；`samples[].max_hp ≈ base_hp × 2`；
  3. 打掉 Boss 一截血，再切人数（菜单 3→2 人）→ **百分比应保持**、上限变为 ×1.8；
  4. 收回全部战友（F7 / 菜单人数 0）→ 上限回到原值；`enemy_hp_status` 的 `tracked` 归零；
  5. 若 `consistent_live` 一直是 0，说明引擎两次 tick 之间重算了上限，需要改走
     spEffect `max_hp_rate` 方案（备选路线，见 `SP_EFFECT_PARAM_ST::max_hp_rate`）。

---

## 28. 队友体型：为什么「和玩家一样」，以及 spawn 种子（2026-11-22）

### 28.1 症状

召唤出的队友脸 / 装备 / 等级都对，但**体型**（身高、骨架、四肢粗细）跟玩家一样，不跟档案。

### 28.2 排查结论

* `PlayerGameData.face_data` 里确实有体型数据：
  * 276B 缓冲（存档 `FaceData` 块 `[0x10..0x124]`）在 `0xB0..0xB4`：头 / 胸 / 腹 / 臂 / 腿；
  * 引擎解析出的 7 个 `f32` 在 `FaceData + 0x130`（头 / 胸 / 腹 / 右臂 / 右腿 / 左臂 / 左腿），
    映射 `f = (byte - 127.5) / 127.5`；
  * `PlayerIns + 0x650` 还有一份同步副本。
* **只改这些不改变渲染**：模型在出生时就按 `CharaInitParam -> FACE_PARAM` 烘焙好了；
  出生后写 PGD / FaceData 只影响脸（脸是动态的），改不了身体。
* 直接调 `ChrIns` vtable 的 `initialize_model_resources` 会**闪退**（实测，崩溃在调用后的下一帧）。
  不要再走这条「强制重建模型」的路。
* 真正的种子链：
  `BuddyParam.npc_player_init_param_id`(26050) → `CharaInitParam.npc_player_face_gen_id`(1)
  → `FACE_PARAM_ST.chr_body_scale_*` + `CharaInitParam.npc_player_sex`。
* 实证：把 `FACE_PARAM` 1 的 body 从 `[255,255,255,255,255]` 改成 `[0,0,0,0,0]`、再 `resummon`，
  裸体克隆体明显变瘦变小 —— 这条链就是体型的唯一落点。

### 28.3 修复

* `params::setup_teammate_bodies()`：
  1. 给 1/2/3 号位各复制一行 `CharaInitParam`（源 26050）和一行 `FACE_PARAM`（源 1）；
  2. 按**该号位档案**写 5 个体型滑条 + `npc_player_sex = body_type`；
  3. 把 3 行载体骨灰的 `npc_player_init_param_id` 指到各自的 init 行。
* 在 `sync_teammate_ai_with()` 里自动跑（配置初始化 / 菜单改人数·号位 / profile 重载 / 20s 兜底），
  用 FNV 签名去重，只在「号位→档案/体型/载体行」变化时重做。
* `kit::apply()` 仍然写 `gender` + 7 个 `f32` + `PlayerIns+0x650`（数据一致；引擎日后若重读也有值）。
* **下次召唤生效**（和每号位 AI 的 think 行同节奏）：菜单「立即重新召唤」/ F8 / 进图自动召唤。

### 28.4 验证

* 自动日志：
  `bodies: {"init_rows":[2999999,2049902,2049901],"face_rows":[91009,91008,91007],...}`
  `slots=[{profile:"Rio", body:[128,123,120,114,95]}, {profile:"Cina", body:[128,128,128,128,128]}, {profile:"Lilis", body:[88,128,138,128,128]}]`
* 裸体 A/B：FaceParam body `255 -> 0` 后 `resummon`，用户确认「变瘦/变小」。
* 最终验收（2026-11-22 20:5x）：干净启动 → 自动建 3 组行并召唤，卸装后用户确认
  「三只体型各不同，脸/肤色也匹配」。
* 注意：换过 `profiles=` 列表后 `slot_for_clone(i, n)` 会按 `slot % n` 重映射；
  已在场的克隆体身体是**旧映射**烘焙的，必须重召才会和新脸/肤色一致。

### 28.5 诊断命令

| 命令 | 作用 |
|---|---|
| `init_probe` | 列出 `CharaInitParam` / `FACE_PARAM` 行数、26050 的字段、它指向的 face 行体型值 |
| `setup_bodies` | 手动重做一遍每号位 spawn 参数（排障用；正常由 sync 自动跑） |
| `face_row_body {"profile":N}` | 把 profiles[N] 的体型写进 26050 当前指向的共享 face 行（A/B 验证用，会给所有号位用同一个体型） |

备用行选择：从 `CharaInitParam` / `FACE_PARAM` 里挑**没有被任何 BuddyParam 引用**的高 id 行
（当前实测 init=`2999999/2049902/2049901`、face=`2024510/2024500/99992`）；第一次建好后这 3 行会被
载体骨灰引用，之后改人数/档案都复用它们，不再吃新行。若将来和别的 mod 抢行，可改成 ini 指定。

研究工具（只读）：
* `mod/examples/offsets.rs`：`cargo run --example offsets` 打印运行时结构偏移；
* `tools/probe_face_memory.py`：扫描游戏进程里的 `FACE` + 0x120 结构，打印 `FaceData.unk130` 的体型 float；
* `tools/ipc_send.py <cmd> --arg k=v`：避开 PowerShell 引号传 JSON 的通用 IPC 客户端。
