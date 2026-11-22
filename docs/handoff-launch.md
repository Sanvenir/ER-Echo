# Handoff：启动链 & 发布排障（2026-11-21）

> **状态：✅ 本机已可正常游玩（管理员启动）；发布方案已定。**
>
> 这次连续踩到**三个互相独立**的坑，排查时千万别混在一起。按「WER 里的出错模块 + 崩溃偏移」就能一眼分开：
>
> | # | 是谁崩的 | 指纹 | 一句话处理 |
> |---|---|---|---|
> | 1 | `modengine2_launcher.exe` | `0xC0000409`，`ucrtbase.dll +0xa527e` | bat 里加 `-p ".\eldenring.exe"` |
> | 2 | `eldenring.exe`（**不带 mod 也崩**） | `0xC0000005` @ `0x1EBCEF9` | 本机是系统组件损坏 / EAC 坏 → DISM + 重装游戏 |
> | 3 | `eldenring.exe`（**只有 ME2 注入时崩**） | `0xC0000005` @ `0x1EBCEF9`，dump 里有 `DLUserInputManagerImpl_win32.cpp(98)` | 管理员启动（或关掉 Steam 覆盖层） |
>
> 现役文件：`launchmod_eldenring.bat`（普通）+ `launchmod_eldenring_admin.bat`（自提权）
> 相关文档：[INSTALL.md](INSTALL.md) §3、[INSTALL.en.md](INSTALL.en.md) §3
> **这台机器必须用 admin 版**（或先关掉 Steam 覆盖层），普通版会 10 秒崩。

---

## 1. 一句话结论（给未来的自己）

1. **启动器崩溃（坑 1）是 ME2 自身缺陷**，跟机器关系不大 → 发布版 bat 永远带 `-p`，对所有人无副作用。
2. **游戏本体自杀（坑 2）不是 mod 的锅**，是玩家机器的系统组件 / 反作弊环境坏 → 文档里要写「先保证不带 mod 能进标题」。
3. **ME2 注入后 10 秒自杀（坑 3）是环境相关的小概率坑**（同一套文件本机 11-17 还不提权能跑）→ 默认**不**强制提权，另附 admin 版 bat + 覆盖层替代方案。

---

## 2. 三个坑的详情

> 小节按**实际排查顺序**排列（先坑 1、再坑 3、最后证实坑 2）；小节号沿用上面的坑号，方便对照。

### 2.1 坑 1：双击 bat 后命令窗一闪就没（launcher `0xC0000409`）

**现象**
事件查看器 → Windows 日志 → 应用程序，`Application Error 1000`：

```
Faulting application name: modengine2_launcher.exe, version: 0.0.0.0
Faulting module name: ucrtbase.dll
Exception code: 0xc0000409        ← abort()，即未捕获的 C++ 异常
Fault offset: 0x00000000000a527e
```

**根因**
ME2 2.1.0 的 `-t er` 会去走「Steam 安装路径自动探测」（读注册表 + 解析 `libraryfolders.vdf`，
dump 里能看到 `winreg` / `tyti::vdf` 的 RTTI）。这段在本机抛未捕获异常 → 直接 abort。

**证据（当时的参数矩阵）**

| 命令 | 结果 |
|---|---|
| `-t er -c config` | ❌ `0xC0000409` |
| `-t ds3 -c config` / `-t 2` / `--launch-target er` | ❌ 一样崩 |
| `-t er -c config -p .\eldenring.exe` | ✅ 正常 |
| 只给 `-c`（不给 `-t`）/ 无参数 | ✅ 正常 |

**处理**
bat 固定成：

```bat
.\modengine2_launcher.exe -t er -c ".\config_eldenring.toml" -p ".\eldenring.exe"
```

`-p` 直接给本地 exe 路径 → 跳过自动探测。**这一条对所有玩家都安全**，所以进了发布版。

---

### 2.2 坑 3（发布相关，重点）：ME2 注入后约 10 秒闪退

**现象**
不提权启动：游戏窗口能出，约 8~15 秒后消失；WER 里 `eldenring.exe`、`0xc0000005`、
**偏移恒为 `0x1EBCEF9`**。

**崩溃点是什么（从 exe 里静态挖出来的）**
`0x1EBCEF9` 处指令是 `C7 04 25 … BA AD DE 00` = `mov dword ptr [0], 0xDEADBA`，
是**故意写空指针**的 fatal 分支；同函数附近引用的字符串是：

```
DL_PANIC is invoking Debugger...
DL_PANIC is firing core dump...
```

**真正的原因（从 dump 内存里挖出来的）**

```
[Dantelion2 Panic] ..\..\Source\detail\Spec\Win32\DLUserInputManagerImpl_win32.cpp(98)
```

即 FromSoft 的 `DL_PANIC` 断言，位置在**用户输入管理器（Raw Input / XInput / DirectInput）**。

**排除过程（为什么确定是「ME2 钩子 × Steam 覆盖层」）**

| 实验 | 结果 | 说明 |
|---|---|---|
| 直接启动 `eldenring.exe`（无 ME2） | ✅ 存活 70 s+ | 游戏本体没问题 |
| 直启后**注入一个无害的已签名 DLL**（`version.dll`） | ✅ 存活 50 s | 游戏**不检测**「注入」本身 |
| ME2 + **完全没有 mod**（`external_dlls=[]`、`mod_loader=false`） | ❌ 仍崩 | 与 er_echo 无关 |
| ME2 + `scylla_hide=true` | ❌ 仍崩 | 不是「隐藏注入模块」能解决 |
| ME2 `-s false`（不挂起启动） | ❌ 仍崩 | 不是挂起/注入时序 |
| `base` 扩展也关掉（只剩 1 个钩子） | ❌ 仍崩 | 触发点极靠前 |
| ME2 文件与官方 `ModEngine-2.1.0.0-win64.zip` 逐文件比对 | ✅ 304 个文件全一致（只差自己的 config/bat） | 不是文件损坏 |
| ME2 的 AOB 偏移 vs 11-17 日志 | ✅ `0x-1e2a722` / `0x57171b1` 完全相同 | 不是游戏版本变了 |
| **管理员启动** | ✅ 正常进游戏、mod 全生效 | 决定性 |

**机制**
不提权时，Steam 的游戏内覆盖层 `gameoverlayrenderer64.dll` 会被注入进游戏进程
（dump 的模块列表里可以看到它），它和 ME2 的钩子撞在**输入层**，触发输入管理器的断言。
提权后进程完整性级别更高，**Steam 无法把覆盖层注入进去**，冲突消失。

**代价**：游戏内没有 Steam 覆盖层（好友/截图/内嵌浏览器）。成就与云存档**未验证**，下次发布前值得确认。
**替代方案**：Steam → 设置 → 游戏中 → 取消「启用 Steam 界面」，然后普通 bat 也能跑（本机尚未验证）。

---

### 2.3 坑 2：不带 mod 也会 10 秒崩（游戏/系统层）

**现象**：同一偏移 `0x1EBCEF9`，但 dump 里**没有** `modengine2.dll` / `er_echo.dll`。

**本机查到并修过的两件事（供以后参考，不是 mod 的问题）**

1. **系统组件存储损坏**：`DISM /Online /Cleanup-Image /RestoreHealth` 报

   ```
   CSI Payload Corruption: 1496 / Total Repaired Corruption: 3604
   All WCP store corruptions were fixed
   ```

2. **EAC（EasyAntiCheat_EOS）是坏的**（本机特有，玩家侧也可能遇到）：
   - 服务 `EasyAntiCheat_EOS` 注册了但 `sc start` 秒退（`0x57` ERROR_INVALID_PARAMETER）
   - `%APPDATA%\EasyAntiCheat\773d3a68…`（ER 的产品数据）不存在，只剩 Nightreign 的
   - `HKLM\SOFTWARE\WOW6432Node\EasyAntiCheat_EOS\ProductsInstalled` 里挂着 ER 的 productid →
     setup 一直打印 `ProductId already marked as installed, no action needed.` **秒成功但什么都没装**
   - 官方引导器 `start_protected_game.exe` 弹「**启动错误 (30001)**」
   - 对照实验：同引擎同 EAC-EOS 的 **Nightreign 能正常启动**（EAC 服务本身没问题）

**最终解法**：**Steam 卸载 → 重装游戏**。重装后 vanilla 直启 70 s+ 正常，坑 2 消失。

**发布文档要写的**：装 mod 之前先确认「不带 mod 能正常进标题界面」；只离线；版本必须 1.17.2。

---

## 3. 发布清单（每次打包前逐项过）

- [ ] `er_echo.dll` 用当前源码重编译，版本匹配 1.17.2（exe `2.7.2.0` 全球 / `2.7.2.1` 日版）
- [ ] `config_eldenring.toml`：`debug = false`、`external_dlls = ["er_echo.dll"]`、`mods` **非空**
- [ ] `er_echo.ini`：`profiles=` 指向 `profiles/profile.example.json`（打包脚本会自动改）
- [ ] 两个 bat 都在，且都是 **CRLF**：
      `launchmod_eldenring.bat`（普通，带 `-p`）+ `launchmod_eldenring_admin.bat`（自提权）
- [ ] `mod\script\talk\m00_00_00_00.talkesdbnd.dcx` 在包里
- [ ] `powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\doctor.ps1` 全绿
- [ ] 生成 README 里含「约 10 秒闪退 → admin 版 / 关覆盖层」这一条
- [ ] **在另一台/干净环境实测两条路径**：普通 bat（不提权）×1、admin bat（提权）×1
- [ ] Nexus 描述写清：只离线 / 版本 1.17.2 / 先确认无 mod 能进标题 / 闪退看 INSTALL §3

打包命令（用 `pwsh` 7，脚本是 UTF-8 无 BOM）：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\package_release.ps1
```

打包脚本已改成会**一并带上** `launchmod_eldenring_admin.bat`，并在 README 里加提示。

---

## 4. 可复用的诊断手法（下次 10 分钟定位）

### 4.1 第一步：读 WER（模块 + 偏移是主线）

```powershell
Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000; StartTime=(Get-Date).AddHours(-2)} |
  Where-Object { $_.Message -match 'eldenring|modengine' } |
  ForEach-Object { $l = $_.Message -split "`n"; "$($_.TimeCreated) | $($l[0]) | $($l[3])" }
```

- 出错模块是 `modengine2_launcher.exe` → 坑 1（加 `-p`）
- 出错模块是 `eldenring.exe` → 进 4.2

### 4.2 第二步：分清「游戏本体崩」还是「ME2 注入崩」

```powershell
# (a) 纯直启，不经过 ME2 —— 活过 60 秒说明游戏本体 OK
Start-Process .\eldenring.exe -WorkingDirectory (Get-Location)

# (b) 纯 ME2，不加载任何 mod —— 仍然崩说明和 er_echo 无关
@'
[modengine]
debug = false
external_dlls = []
[extension.mod_loader]
enabled = false
'@ | Set-Content .\config_test_pureme2.toml -Encoding utf8
.\modengine2_launcher.exe -t er -c .\config_test_pureme2.toml -p .\eldenring.exe
```

### 4.3 第三步：从 dump 里挖 panic 原因（这次靠它翻盘）

```powershell
$d = Get-ChildItem "$env:LOCALAPPDATA\CrashDumps\eldenring*.dmp" |
     Sort-Object LastWriteTime -Descending | Select-Object -First 1
$s = [Text.Encoding]::GetEncoding(28591).GetString([IO.File]::ReadAllBytes($d.FullName))
[regex]::Matches($s, 'Dantelion2 Panic[^\x00]{0,140}|DL_PANIC[^\x00]{0,60}') |
  ForEach-Object { $_.Value } | Select-Object -Unique
```

会直接打印 `[Dantelion2 Panic] …文件(行号)`——这就是断言现场。
dump 的模块列表里还能看出有没有 `gameoverlayrenderer64.dll`（Steam 覆盖层）、
`modengine2.dll`、`scylla`/`ViGEm` 之类。

### 4.4 第四步：确认 ME2 本身没坏

```powershell
# 与官方 release 逐文件比对（2023-09-01 的 2.1.0 是最后一版）
# 下载：https://github.com/soulsmods/ModEngine2/releases/download/release-2.1.0/ModEngine-2.1.0.0-win64.zip
Select-String .\modengine2\logs\modengine_*.log -Pattern 'Jump offset' | Select-Object -First 6
# 和 11-17 的日志比：0x-1e2a722 / 0x57171b1 相同 → exe 没变、钩子位置没变
```

### 4.5 第五步：确认 EAC 状态（玩家侧常见）

```powershell
(Get-Service EasyAntiCheat_EOS).Status                       # Stopped + sc start 报 0x57 = 坏
(Get-ItemProperty 'HKLM:\SOFTWARE\WOW6432Node\EasyAntiCheat_EOS').ProductsInstalled
dir "$env:APPDATA\EasyAntiCheat" -Recurse -Depth 2            # 有没有本作 productid 目录
```

坏了的修法（按代价从低到高）：Steam 校验文件 → 管理员跑 `EasyAntiCheat\install_easyanticheat_eos_setup.bat`
→ 删 `ProductsInstalled` 里本作 id 再装 → 重装游戏。

---

## 5. 本机环境快照（复现参考）

| 项 | 值 |
|---|---|
| 游戏 | `eldenring.exe` 2.7.2.0（1.17.2），全新重装于 2026-11-21 14:01 |
| ModEngine2 | 2.1.0（`2.1.0-0924ab36…`），文件与官方 release **逐字节一致** |
| 系统 | Windows 11 `10.0.26200.9974`；HVCI/VBS **开**；Smart App Control **关** |
| 反作弊 | EAC-EOS（`EasyAntiCheat_EOS` 服务），本机曾损坏后随游戏重装修复 |
| 输入 | **ViGEmBus 已安装**（er_echo 的 `vpad` 工具），USB 里有 XInput 设备 |
| 覆盖层 | Steam 覆盖层开；NVIDIA App 覆盖层（`NvCamera64`/`nvspcap64`）在跑 |
| 其他常驻 | McAfee、Clash for Windows、UU 加速器、Razer Cortex、N.E.K.O.、ASUS HDR 工具 |
| 关键时间线 | 11-17 不提权可玩 → 11-20 起崩 → 11-21 重装游戏后 vanilla 正常、ME2 需提权 |

> 注意：**11-17 同一套文件不提权能跑**，说明坑 3 是环境相关、不是必然。
> 别把「必须提权」写进 mod 的硬性要求，只作为排障手段。

---

## 6. 本次改动清单

| 文件 | 改动 |
|---|---|
| `launchmod_eldenring.bat` | 普通版，带 `-p` + `cd /d "%~dp0"` + 失败提示；头注释写了坑 1/坑 3 的处理入口 |
| `launchmod_eldenring_admin.bat` | **新增**：自检高完整性 SID（`S-1-16-12288`），否则 `Start-Process -Verb RunAs` 重新拉起自己 |
| `er-echo/docs/INSTALL.md` | §3 加两行（10 秒闪退 / launcher `0xC0000409`）；第 5 步加「闪退 → admin 版 / 关覆盖层」 |
| `er-echo/docs/INSTALL.en.md` | §3 加对应两行 |
| `er-echo/tools/package_release.ps1` | 打包时带上 admin bat；生成 README 加「10 秒闪退」提示 |
| `er-echo/dist/ER-Echo-20261120/` | 同步两个 bat |
| 备份 | `launchmod_eldenring.bat.bak-20261120`（最原始的 ME2 版本，172 B） |

**本机额外动作（与 mod 无关，但要知道）**
- 重装过一次游戏（坑 2 的解法），`mods/`、`SeamlessCoop/` 被清掉
- EAC 目录 `C:\Program Files (x86)\EasyAntiCheat_EOS` 被清空重装过一次（驱动缺失）
- 清空过 NVIDIA `DXCache`（32 GB）与 `D3DSCache`（5.4 GB）
- Steam `loginusers.vdf` 的 `SkipOfflineModeWarning` 改成了 `1`（`WantsOfflineMode` 原本就是 `1`）

---

## 7. 遗留 TODO / 观察点

1. **未验证**：admin 模式下 Steam 成就、云存档是否正常（发布前最好确认一次，并在 README 说明）。
2. **未验证**：关掉 Steam 覆盖层后，本机普通 bat 是否能跑（能跑就省掉每次 UAC）。
3. **可加**：`doctor.ps1` 增加一条自检——当前是否管理员 / 建议用哪个 bat（玩家一跑自检就知道）。
4. **可加**：`auto_start.ps1`、`enter_game.ps1`、`restart_and_test*.ps1` 统一加「先自检提权」，
   否则这些脚本现在每次调用 bat 都会弹 UAC。
5. **未解释**：为什么 11-17→11-20 环境会变（怀疑系统组件损坏 + 覆盖层/驱动状态），
   DISM 修好 1496 个 payload 后 vanilla 才正常；若再遇到，优先跑 DISM + 重装游戏，别先怀疑 mod。
