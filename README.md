# ER Echo（褪色残响）· 法环 AI 战友 MOD

> 召唤**你自己另一个存档里的角色**当同伴：外观/装备一致，战斗用**游戏原生 AI**，LLM 只当「战斗导演」调行为权重，骨灰式跟随、掉队才传送。

## 仓库

源码、文档与工具都在本仓库；构建产物与发布包**不提交**（见 `.gitignore`），随时可重新生成：

| 内容 | 位置 |
| --- | --- |
| 源码 / 文档 / 工具 | 仓库根目录 |
| Rust DLL 源码 | `mod/` |
| 第三方 crate 快照（构建必需） | `vendor/fromsoftware-rs-main/`（只保留 `eldenring` / `shared` 及许可证） |
| 构建产物 | `mod/target/`（`cargo build` 生成，已忽略） |
| Nexus 发布包 | `dist/nexus/`（`tools/package_nexus.ps1` 生成，已忽略） |

脚本不猜游戏目录，统一用 `tools/gamedir.ps1` / `tools/gamedir.py` 探测
（`-GameDir` 参数 → `$env:ER_ECHO_GAME_DIR` → 老布局 → 当前目录 → Steam 注册表/libraryfolders.vdf）：

```powershell
powershell -File tools\doctor.ps1 -Target "<Game>"        # 显式指定
$env:ER_ECHO_GAME_DIR = "<Game>"                          # 或者设环境变量
cd D:\Projects\ER-Echo; powershell -File tools\doctor.ps1  # 自动探测
```

## 状态

| 项 | 状态 |
|---|---|
| 技术调研（工具链/存档/AI/LLM） | ✅ 完成 |
| 追加调研（跟随/爬梯/骑乘/多召唤） | ✅ [docs/follow-mount-multi.md](docs/follow-mount-multi.md) |
| 设计文档 v0.2 | ✅ [docs/design.md](docs/design.md) |
| Python sidecar（LLM 导演 + 护栏） | ✅ 可跑（`--simulate` 自测通过） |
| Rust DLL | ✅ 已编译 + 进游戏加载 |
| 加载器 | ✅ ModEngine2 2.1.0 已装到游戏目录，config 指向 `er_echo.dll` |
| 授权召唤（骨灰 + 召唤石） | ✅ 实测：改 BuddyParam 行后召唤出人形克隆，可见、不透明 |
| 克隆体身份 | ✅ 实测是 `PlayerIns`（自带 `PlayerGameData`/`face_data`） |
| 召唤后注入（装备/脸/等级） | ✅ 实测：lv9、脸=目标档案、左手 31330000 / 右手 2000000，玩家完全不变 |
| 多存档同场（一召多体） | ✅ 实测：3 个克隆体等级 9/15/9（按 `i % n` 分配档案） |
| 跟随 | ✅ 原生骨灰跟随可用；距离日志用物理世界坐标；**掉队由骨灰行自己处理**（整行复制拟态本体 20700001 后实测 42 m → 1 m 自动拉回） |
| 零命令流程（`er_echo.ini`） | ✅ 进游戏自动加载档案 + 改骨灰行；**进游戏 / 坐火 / 传送 / 复活后自动召唤一队**（`summon_events=true`），F8 也可手动召；绕过区域/召唤石/冷却/「一次一队」（见 [§15](docs/implementation-log.md)） |
| 灵体特效 | ✅ 去掉 295000（NpcParam 常驻槽）+ 295190（召唤时挂的着色）；实测外观恢复正常、跟随不变 |
| 队友体型（身高/骨架/四肢） | ✅ 按档案的 `body_type` + 5 个体型滑条，在**出生时**从 `CharaInitParam → FACE_PARAM` 烘焙（1/2/3 号位各一行，见 [§28](docs/implementation-log.md)）；出生后改脸/装备不影响身体，改完要重召 |
| 同伴施法（法系队友） | ✅ 记忆法术 14 槽从存档导出（PGD `+0x93B4`）并注入克隆体 + 无限蓝；**另外把拟态 think 行的交战半径从 2 m 抬到 13/7 m**（出厂值贴脸才反应，法系根本没有射程，§17.1）；May lv6 `[4000, 4070]` 已在内存里就位，`bullet:` 日志实测一次 7 颗 |
| 权重 → AI（M4） | ✅ 可观察：`aggression` → 侦测/交战半径（6–20 m）、`spell_rate` → 记忆槽开几发（0/半/全）、`guard_rate` → 举盾、`target_switch` → 换目标；`combo/item/heal/spacing` 暂无可靠落点（§17.2） |
| 战斗验证台（不用真打） | ✅ `dummy` 把一只克隆体变敌对木桩 + `combat_probe`/`bullet_probe` 量化：掉血、TTK、子弹归属、克隆体血量 |
| 队友伤害修正 | ✅ 摘掉拟态泪滴行上的灵体削弱 spEffect `296000`（伤害 ×0.25 / 受伤 ×0.5 / 削韧 ×0.05）和 `20297000`（受伤削韧 ×0.5）：队友的伤害/受伤/削韧与玩家褪色者一致，**不动 SpEffectParam 行**，其它骨灰不受影响（`[clone] player_damage=true`） |
| 玩家升级 → 队友跟升 | ✅ 检测玩家等级/8 维属性/三围上限的增量，按同样的加点追给所有已加载档案，写回 profile JSON（`[clone] auto_level=true`）；场上克隆体立刻重写等级/属性 |
| 友伤开关 | ✅ 赐福「战友」二级菜单新增「友伤：开（20%）/关」：打开后 `AtkParam_Pc` 的 `friendlyTarget` 全开，玩家与同伴的攻击能命中对方，但只造成 **20%** 伤害（`[combat] friendly_fire_rate`；打普通敌人仍是 100%）；同伴队伍号/`isBuddyAI`/`team_attack_effectivity=0` 不变（不会把玩家当敌人），并钉住 `disable_lock_on`（不能被锁定）。状态持久化在 `er_echo_roster.json` |
| 战友模式·敌人生命补正 | ✅ 按当前**出场且活着**的战友人数补正敌人生命上限：0/1/2/3 人 = ×1.0/×1.5/×1.8/×2.0（`[balance] enemy_hp_scaling` + `enemy_hp_rates`）。运行时写每只敌人的 `CSChrDataModule { hp, max_hp, max_uncapped_hp, base_hp }`，**已经在打的 Boss 也立刻生效**，并按百分比保留已掉血量；收起战友/关闭功能恢复原上限（不写 `NpcParam`/`regulation.bin`）。`enemy_hp_status` 可看每只敌人的数值/跟踪状态 |
| 队友 AI（每号位） | ✅ 赐福「战友 → 队友 AI」三级菜单：**1/2/3 号位分别**点风格（默认 → 均衡 → 近战 → 法术 → 守护 → 激进），立刻写回该队友自己的 profile JSON `ai` 段（`preset` + 4 个数）。`aggression / guard_rate / target_switch` 落在每号位独立的 think 行（默认 `100000020/30/40`，运行时先从 `100000010` 整行复制、只覆盖差异字段，不借别的 AI 语义），**下次召唤**生效；`spell_rate` 直接改该克隆体的记忆槽数量，**立即**生效。没写 `ai` 的档案 = 跟随全局权重（和加功能前完全一样） |
| 状态/日志/恢复（M5） | ✅ `status`（F6 / 每 30 秒）+ 日志轮转（8 MB、带 `+Xs`）+ 心跳/上次操作（`er_echo_heartbeat.txt`）+ `safe_mode` + `resummon`/掉队保底 |
| 召唤区域限制 | ⚠️ 直接写召唤请求可绕过（已实测死区能召）；骨灰**物品**本身在死区仍不可用（引擎菜单层判定，见 §15.6） |
| 离线导出存档角色（不切号） | ✅ `export_profile_from_save.py` 直接解析 `.sl2`（明文 BND4）；实测召唤出旧存档的 Sirenix lv17 / Ludwig lv9 |
| 离线字段完整性 | ✅ 与运行时 dump 逐字段对照（`tools/diff_profile.py`）：等级/8 属性/22 槽装备/脸部 276B/HP·FP·耐力上限 全一致 |
| LLM 输入（战斗状态） | ✅ 每秒一条结构化 state：玩家三围/等级、克隆体（等级·血量·距离）、最近敌人、边沿事件 |
| LLM 工具调用（换装/加点） | ✅ `set_equipment`/`set_stats`/`rollback_equipment` 作用在**克隆体**上，带槽位白名单、参数存在性、±20% clamp、回滚点 |
| 游戏内 UI（原生） | ✅ 赐福根菜单「战友（n/m）」→ **二级菜单**（人数 / 1-3 号位 / 队友 AI（三级） / 立即重召 / 友伤 / 返回），运行时 EzState 注入；人数切换后「立即重新召唤」按新人数重召（1→3 / 3→1 实测）；消息钩子、F12 给装备（改内存档案，不写盘；没选中时恢复档案原样） |
| 多语言菜单 | ✅ `[i18n] language=en`（默认英文，`auto` 可跟系统）或 `zh-CN` / `zh-TW` / `ja`；`er_echo_i18n.ini` 可覆盖/新增语言（[docs/i18n.md](docs/i18n.md)） |
| 安装 / 跨机器 | ✅ [docs/INSTALL.md](docs/INSTALL.md)：版本/加载器/权限三道门槛、换机清单、症状对照；`tools/doctor.ps1` 预检、`tools/package_release.ps1` 打免存档发布包 |
| Nexus 发布素材 | ✅ [nexus/README.md](nexus/README.md)：页面文案/字段/权限/AI 披露/许可/上传清单；`tools/package_nexus.ps1` 出主包+可选 ESD 包；游戏内截图清单见 [nexus/shotlist.md](nexus/shotlist.md) |
| 可插拔安装 | ✅ [docs/PLUGIN.md](docs/PLUGIN.md)：整个 mod 收进 `mods\ER-Echo\`（DLL 读同目录 ini），不改 ME2 的 config/bat；**内置图形工具**（`Export-Profiles.bat` → 安装 / 导出 / 写 `profiles=`）；`tools/package_plugin.ps1` 打包，`reset_to_vanilla.ps1` / `install_plugin.ps1` 做纯净安装实验 |
| 一键安装器 | ✅ `ER-Echo-Setup.exe`（`tools/build_gui_exe.ps1`，payload 由 `tools/package_payload.ps1` 生成）：**只输入游戏路径**就自动装好——拷文件、导出存档角色、写 `profiles=`、改加载器配置（全带备份），卸载同页；exe 不用放进 Game 目录 |
| 参数表 dump | ✅ exe「安装 / 配置」页的「导出参数表」（或 `ER-Echo-Setup.exe --dump-tables <游戏路径>`）：走 DLL 的 IPC 让运行中的游戏写 `er_echo_equip.json` / `er_echo_magic.json`，导出器据此硬校验装备 id（混搭套装角色也能过）；Convergence 那套表已随包发布在 `payload\tables\convergence\` |
| Convergence 适配 | ✅ [docs/CONVERGENCE.md](docs/CONVERGENCE.md)：Convergence 3.x 走 me3，安装器改成往 `me3\convergence*.me3` 追加 `[[natives]]`；不覆盖它的 talk ESD；已实测 DLL 在 me3 下注入并挂上 EzState 钩子（`er_echo_npc.json` 2036415 字节 = Convergence 的 regulation） |

实现细节与复现步骤：[docs/implementation-log.md](docs/implementation-log.md)
安装 / 换机器 / 兼容性：[docs/INSTALL.md](docs/INSTALL.md)（English: [docs/INSTALL.en.md](docs/INSTALL.en.md)）
启动链排障（启动器崩溃 / 10 秒闪退 / 无 mod 也崩）：[docs/handoff-launch.md](docs/handoff-launch.md)
菜单多语言：[docs/i18n.md](docs/i18n.md)
日常使用（导出另一个存档、配置、召唤、LLM 调参）：[docs/usage.md](docs/usage.md)
启动链 / 发布排障（三个坑：launcher 崩溃、游戏本体崩、Steam 覆盖层导致 10 秒闪退）：[docs/handoff-launch.md](docs/handoff-launch.md)

## 现在能做什么

- **零命令使用**：`er_echo.ini` 配好 `profiles` + `buddy_rows` 后，进游戏直接用骨灰即可，
  召唤出来的就是目标存档的角色（外观/装备/等级），玩家自己不变；
- 注入后持续维护（每 15 帧重写），引擎变身/重招不会把外观刷回去；
- 多存档同场：`profiles=a.json,b.json` → 默认按名单顺序出场（`er_echo_roster.json`）；
- **赐福原生菜单**：最上面「战友（n/m）」，点进去是二级菜单：队伍人数 / 1-3 号位 / 队友 AI（三级菜单，每号位单独设风格） / 立即重新召唤 / 友伤开关（20%） / 返回
  （运行时 `EzState` 注入，不用改 ESD；`er_echo.ini` 的 `[ui] nested_menu` 可关，回退根列表版本）；
- **每个队友单独的 AI**：赐福「战友 → 队友 AI」里给 1/2/3 号位分别点 默认/均衡/近战/法术/守护/激进；
  点完立刻写回该队友 profile JSON 的 `ai` 段（`preset` + `aggression/spell_rate/guard_rate/target_switch`）。
  法术槽立即生效，交战半径/举盾/换目标在下一次召唤生效；没设置的档案跟随全局权重（详见 [usage.md](docs/usage.md)）；
- **队友体型按档案**：Buddy 在**出生时**按该号位档案的 `body_type` + 5 个体型滑条烘焙（1/2/3 号位各一行 init/FACE_PARAM，见 [§28](docs/implementation-log.md)）；出生后改脸/装备不影响身体，改完要重召；
- **F12 给队友装备**：置物包/装备菜单光标停在武器/防具/护符/法术上按 F12；没选中装备/法术时把队友的装备/法术恢复成档案原样（误按不会再复制玩家装备）；
- **战友模式·敌人生命补正**：按当前出战友人数提高敌人生命上限（1/2/3 人 = 1.5/1.8/2.0 倍），
  场上的 Boss 也立刻生效；`[balance]` 可关/可改倍率，`enemy_hp_status` 看跟踪详情（详见 [usage.md](docs/usage.md) §3.3）；
- **菜单多语言**：`er_echo.ini` 的 `[i18n] language=en`（默认英文；`auto` 跟随 Windows）或 `zh-CN` / `zh-TW` / `ja`，
  `auto` 跟 Windows 显示语言；自定义语言放 `er_echo_i18n.ini`（不用重编译，见 [docs/i18n.md](docs/i18n.md)）；
- 运行时导出 **BuddyParam / RideParam / NpcParam / NpcThinkParam / 玩家 profile** 为 JSON（不需要 Smithbox）；
- 运行时写 `NpcAiBehaviorProbability` / `NpcThinkParam` / `NpcParam`（LLM 权重通道）；
- 从当前角色一键导出档案：`python tools/dump_to_profile.py er_echo_profile.json -o profiles/me.json`；
- 手动命令（调试用）：`apply_to_clone`、`auto_apply`、`set_clone_profiles`、`equip_probe`、`clone_info`、
  `status`、`combat_probe`、`dummy`、`weights_probe`、`resummon`、`enemy_hp_status`、`enemy_hp_scale`；
- 热键：`F6` 状态、`F7` 收回、`F8` 召唤（旧流程也一样）、`F9` 重载 profile、`F10` 调试开关、`F11` 注入开关、`F12` 给队友选中项（没选中则恢复档案原样）。

## 快速开始（进游戏）

```powershell
# 0) 确认 config_eldenring.toml 里 [extension.mod_loader] 有：
#    mods = [ { enabled = true, name = "er-echo", path = "mod" } ]
#    空数组会导致 mod/script/talk 下的 ESD 完全不加载（坐火没有「战友」）。
# 0.5) 换机器 / 首次安装先自检（只读，游戏不用开）：
powershell -NoProfile -ExecutionPolicy Bypass -File tools\doctor.ps1

# 1) 启动（EAC 关闭、离线），自动点掉标题/断线提示并进入游戏
powershell -NoProfile -ExecutionPolicy Bypass -File tools\auto_start.ps1
# 进图后需要坐火时：
powershell -NoProfile -ExecutionPolicy Bypass -File tools\sit_grace.ps1

# 2) 进游戏后，另开一个终端 dump 数据
cd "D:\Projects\ER-Echo"
python tools\ipc_client.py dump_buddies
python tools\ipc_client.py dump_ride
python tools\ipc_client.py dump_profile

# 3) 从 dump 里挑到行 id 后，告诉 DLL（不用重编译）
python tools\ipc_client.py set_rows --behavior 0 --think 133200000 --npc 133201000
python tools\ipc_client.py set_weights --aggression 0.8 --dodge_rate 0.4

# 4) 召唤后注入：load_profile → 改骨灰行成人形 → 用骨灰 → 克隆体变成目标角色
python tools\ipc_client.py load_profile --path profiles\me.json   # 先导出你的角色
python tools\ipc_client.py set_buddy_row --id 23200000 --npc 100000010 --think 100000010 --init 26050 --follow 2
#    （在游戏里用「离群野狼」骨灰）
python tools\ipc_client.py clone_info          # 看 face_prefix / equip / level
python tools\ipc_client.py apply_to_clone --stats true

# 5) LLM 通道：看状态流 / 让它换装加点（工具调用只作用于克隆体）
python tools\watch_state.py --seconds 30
python tools\ipc_client.py set_equipment --args "{\"loadout\":{\"head\":630000}}"
python tools\ipc_client.py set_stats --args "{\"vigor\":12}"
python tools\ipc_client.py rollback_equipment
```

产物（在游戏根目录）：
- `er_echo.log`：DLL 日志（UTF-8，`Get-Content -Encoding utf8` 看）
- `er_echo_buddies.json`：所有骨灰召唤行（找 Mimic Tear）
- `er_echo_ride.json`：骑乘行（找 c0000 ↔ 坐骑）
- `er_echo_profile.json`：当前角色等级/属性/装备/脸缓冲
- `er_echo_roster.json`：赐福菜单里的出场人数 / 名单（0–3 人，`slots` 为 `profiles` 下标）

> 同一时间只能有一个 IPC 客户端；跑 `ipc_client.py` 前先停掉 `bridge/director.py`。

## 构建

前置：Windows + rustup `stable-x86_64-pc-windows-gnu` + MSYS2 binutils（提供 `as.exe`；
Rust 自带 dlltool 需要它）。细节见 [implementation-log.md](docs/implementation-log.md) §1。

```powershell
cd mod
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

产物：`mod/target/release/er_echo.dll`（`build.ps1` 若探测到游戏目录会顺手复制）。

## 打包 / 发布

```powershell
# Nexus 主包 + 可选 ESD fallback 包（发布到 Nexus 用这两个 zip）
powershell -NoProfile -ExecutionPolicy Bypass -File tools\package_nexus.ps1

# 可插拔插件包（mods\ER-Echo\，不改 ME2 配置）
powershell -NoProfile -ExecutionPolicy Bypass -File tools\package_plugin.ps1
```

Nexus 页面文案 / 字段 / 截图清单 / 上传检查表在 [nexus/](nexus/README.md)。
运行时不需要 Python；只有导出档案、IPC 调试、LLM 导演需要。

## 目录

```
ER-Echo/
├─ README.md
├─ LICENSE / LICENSE-MIT / LICENSE-APACHE
├─ docs/                         设计、安装、使用、排障、实现日志、文档配图（docs/images/）
├─ config/                       behavior_map.yaml / weights.schema.json
├─ bridge/                       Python sidecar（director / protocol / profile_reader）
├─ install/                      er_echo.ini 模板、ME2 配置片段、启动 bat 模板、参数表
├─ nexus/                        Nexus 发布素材（文案/字段/截图清单/上传清单/media）
├─ tools/                        doctor、gamedir、导出、IPC、打包、ESD 构建等
├─ ui/                           赐福菜单 ESD 资产（源 + 打包用的 out_vanilla / out_rootmenu）
├─ mod/                          Rust DLL（src + Cargo + build.ps1 + examples/offsets.rs）
└─ vendor/fromsoftware-rs-main/  上游 crate 快照（eldenring / shared，含 NON-AI 许可证）
```

常用命令：

```powershell
powershell -File tools\doctor.ps1                  # 安装预检
python tools\export_profile_from_save.py --list    # 列出存档角色
python tools\ipc_client.py status                  # 游戏内状态
python tools\ipc_send.py rebuild_clone --arg mode=model  # 通用 IPC（JSON 参数）
```

## 安全与合规

- **只离线**：EAC 关闭；带 mod 存档上线会被隔离/soft-ban。
- 改 `regulation.bin` / `.sl2` 前备份；本仓库不含游戏原始资源或他人存档。
- 本仓库代码 MIT OR Apache-2.0（见 [LICENSE](LICENSE) / [LICENSE-MIT](LICENSE-MIT) / [LICENSE-APACHE](LICENSE-APACHE)）；文档中的参数名来自 Paramdex / 社区逆向。
- `vendor/fromsoftware-rs-main` 使用 MIT-NON-AI / Apache-NON-AI，全文见该目录与 [nexus/THIRD-PARTY-LICENSES.txt](nexus/THIRD-PARTY-LICENSES.txt)。
