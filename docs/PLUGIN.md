# 可插拔安装（plugin layout）

目标：**不动 Mod Engine 2 的任何文件**——不覆盖 `config_eldenring.toml`、不改
`launchmod_eldenring.bat`、不碰 `modengine2\`。装=解压，卸=删目录。

> **更省事的方式**：`ER-Echo-Setup.exe`（安装包里的那个 exe）会把下面的步骤全自动做完——
> 输入/自动检测游戏路径 → 拷文件 → 导出你自己的角色 → 写好 `profiles=` → 改配置（带备份），
> 还支持直接装到 Convergence（me3）。本文留作手动安装和排查时的参考。
> Convergence 的细节见 [CONVERGENCE.md](CONVERGENCE.md)。

## 1. 目录

```
<ELDEN RING>\Game\
├─ eldenring.exe
├─ config-er-echo.toml          ← 本 mod 自己的 ME2 配置（唯一新增的根目录文件）
├─ mods\
│  └─ ER-Echo\                   ← 插件本体，删掉=卸载
│     ├─ er_echo.dll
│     ├─ er_echo.ini             ← DLL 优先读自己同目录的配置
│     ├─ er_echo_i18n.example.ini
│     ├─ launch-er-echo.bat      ← 普通启动（cd 到游戏根 + 自己的 -c）
│     ├─ launch-er-echo-admin.bat ← 自提权（10 秒闪退时用）
│     ├─ Export-Profiles.bat      ← 图形导出工具（选存档 → 导出 → 自动写 ini）
│     ├─ mod\script\talk\...dcx   ← 赐福菜单必需（实测不挂载则不出现「战友」）
│     ├─ profiles\builtin_sanvenir.json  ← 内置角色 Sanvenir（彩蛋 / 备用）
│     ├─ profiles\profile.example.json   ← 格式示例
│     ├─ tools\Setup\             ← 上面那个 bat 打开的 onedir GUI（exe + _internal + payload）
│     ├─ tools\ bridge\ docs\ install\
│     └─ LICENSES\ THIRD-PARTY-LICENSES.txt
├─ config_eldenring.toml        ← 完全没动
├─ launchmod_eldenring.bat      ← 完全没动
└─ modengine2\                  ← 完全没动
```

`config-er-echo.toml` 内容：

```toml
[modengine]
debug = false
external_dlls = ["mods/ER-Echo/er_echo.dll"]

[extension.mod_loader]
enabled = true
loose_params = false
mods = [ { enabled = true, name = "er-echo", path = "mods/ER-Echo/mod" } ]
```

启动器做的事：

```bat
cd /d "%~dp0..\.."                                    :: 回到游戏根目录
.\modengine2_launcher.exe -t er -c ".\config-er-echo.toml" -p ".\eldenring.exe"
```

`-c` 指向自己的配置，`-p` 跳过 ME2 2.1.0 的 Steam 路径探测（`0xC0000409`）。

## 2. 为什么 DLL 能读到自己同目录的 ini

以前 `er_echo.dll` 用 CWD 找 `er_echo.ini`，所以配置必须放游戏根目录。现在改成：

1. 先找 **DLL 所在目录** 的 `er_echo.ini` / `er_echo_i18n.ini`；
2. 没有再退回 CWD（兼容老的平铺安装）。

所以插件可以整包待在 `mods\ER-Echo\` 里。注意 `er_echo.ini` 里的 **profiles 路径仍以
游戏根目录为基准**，要写成 `mods/ER-Echo/profiles/xxx.json`。

运行期产物（`er_echo.log`、`er_echo_*.json`、`er_echo_heartbeat.txt`）仍然写在
**游戏根目录**（DLL 的 CWD），卸载时一起删即可。

## 3. 安装 / 卸载

安装（解压到游戏根目录即可）：

1. 确认 `modengine2_launcher.exe` 在游戏根目录；
2. 把 `ER-Echo-Plugin-<版本>.zip` 解到游戏根目录；
3. **首次使用**：
   - 双击 `mods\ER-Echo\Export-Profiles.bat` → 自动列出你存档里的角色 →
     选一个 →「导出选中」→ 弹窗选「是」写进 `er_echo.ini`（自动备份）；
   - 双击 `mods\ER-Echo\launch-er-echo-admin.bat` 进游戏；
4. （推荐）先跑 `powershell -File mods\ER-Echo\tools\doctor.ps1 -Target <Game>`。

不导出也能直接玩：名单里固定带内置角色 **Sanvenir**（Lv1，彩蛋 / 备用）。
要「自己另一个存档的角色」，走一次 `Export-Profiles.bat`（或命令行导出）；
工具只会写 `slot<N>_*.json` 并保留内置档案条目，不会把它覆盖掉。

卸载：

```
删 mods\ER-Echo\
删 config-er-echo.toml
删游戏根目录的 er_echo.log* / er_echo_*.json / er_echo_heartbeat.txt
```

原版 `config_eldenring.toml`、`launchmod_eldenring.bat` 一直没被改过，所以不需要恢复。

## 4. 和别的 mod 共存

插件用的是**独立配置文件**，因此：

* 用 `launch-er-echo.bat` 启动 → 只加载 ER Echo（+ 它自己的配置）；
* 用原来的 `launchmod_eldenring.bat` 启动 → 只加载你 `config_eldenring.toml` 里的东西，
  **不会**加载 ER Echo；
* 想让两者同时生效：把 `"mods/ER-Echo/er_echo.dll"` 加进 `config_eldenring.toml` 的
  `external_dlls`，然后用原版 bat 启动（这时就回到「共享配置」模式了，插件仍可整目录删除）。

## 5. 纯净安装实验（本机流程）

> 这一节是开发机上的实验：`install_plugin.ps1` 只放在仓库里，**发布包不带**。
> 发布包里装插件用安装器（或手动解压）。

```powershell
# 0) 退出游戏
# 1) 恢复到干净状态（自动备份到 %USERPROFILE%\ER-Echo-Backups）
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\reset_to_vanilla.ps1

# 2) 基线验证：直接跑 eldenring.exe，能进标题并稳定 1 分钟
#    （若这一步就崩，先修游戏/EAC，别装 mod）

# 3) 干净安装 + 自检
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\install_plugin.ps1 `
    -Package er-echo\dist\plugin\ER-Echo-Plugin-0.1.0.zip

# 4) 带启动验证（等日志出现 attached）
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\install_plugin.ps1 `
    -Package er-echo\dist\plugin\ER-Echo-Plugin-0.1.0.zip -Launch

# 5) 进游戏：坐赐福看 Comrades (n/m)，F8 召唤；然后卸载再验证一次干净
```

## 6. 和完整包 / Nexus 包的关系

| 包 | 布局 | 改 ME2 文件 | 用途 |
|---|---|---|---|
| `dist/ER-Echo-<日期>` | 平铺（根目录 dll/ini/bat/config） | 是（替换 config + bat） | 本机日常玩 |
| `dist/nexus/ER-Echo-0.1.0` | 平铺 + 自带 bat | 部分（只加 external_dlls，bat 可选替换） | Nexus 发布 |
| `dist/plugin/ER-Echo-Plugin-0.1.0` | **mods\ER-Echo\ 插件** | **否** | 干净安装实验 / 多 mod 共存 |

三种包共用同一份 DLL 和 `er_echo.ini`，只是摆放位置不同。

## 7. 验证记录（2026-11-21）

完整记录见 [EXPERIMENT-20261121.md](EXPERIMENT-20261121.md)。要点：

* 从干净目录装插件 → doctor 通过；
* ME2 日志确认从子目录加载：
  `Loaded external DLL ...\Game\mods/ER-Echo/er_echo.dll`；
* **赐福菜单必须挂载 ESD**（`mods/ER-Echo/mod`）：实测不挂载时日志报
  `ezstate: cannot find grace root list start state`，菜单不出现；挂载后日志出现
  `ezstate: patched grace group x31 ... events 2 -> 3`，截图确认「战友（1/2）」在菜单第一项；
* 档案：把 `profiles` 指向两份真实导出（`Sv` lv15 / `May` lv6）后，
  日志 `config profile[0/2] 'Sv'`、`auto_apply: 1 clone(s) -> equip=1 face=1`，克隆体血量 680；
* **本机（当前环境）不提权会在 ~15 秒闪退，连 vanilla 也一样**（Steam 覆盖层触发输入管理器
  panic，`0x1EBCEF9`）；提权后稳定。所以本机日常用 `launch-er-echo-admin.bat`。
