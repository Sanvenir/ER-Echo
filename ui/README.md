# 游戏内 UI：赐福菜单（运行时注入 + ESD fallback）

现在有**两种**可切换的实现：

| 模式 | 部署的 ESD | 菜单怎么来 |
|---|---|---|
| `nested`（默认） | `out_vanilla/`（**原版** `t000001000`） | `er_echo.dll` 运行时往 live `EzState` 注入「战友」→ 6 项二级菜单（`mod/src/ezstate.rs`） |
| `root`（fallback） | `out_rootmenu/`（根列表 5 项补丁） | 离线 ESD 直接挂 5 项，DLL 不注入（`nested_menu=false`） |

切换（会同时换 ESD + ini，重启游戏生效）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\switch_menu_mode.ps1 -Mode root
powershell -NoProfile -ExecutionPolicy Bypass -File er-echo\tools\switch_menu_mode.ps1 -Mode nested
```

原理/字节码/anchors 详见 [../docs/submenu-runtime-injection.md](../docs/submenu-runtime-injection.md)。

## 文件

```
ui/
├─ talk/
│  ├─ m00_00_00_00.raw.dcx       从 Data0 抽出的原始 DCX（KRAK）
│  └─ m00_00_00_00.talkesdbnd.dcx  已解压的 BND4（374 KB）
├─ base/
│  └─ m00_00_00_00.talkesdbnd    给 esdtool 当模板的 BND4（= 上面的解压结果）
├─ esd/py/                         esdtool -writepy 反编译出的 .py（原始）
├─ esd/edit/                       patch_grace_esd.py 生成的补丁版 .py
└─ out_bnd/
   ├─ m00_00_00_00.talkesdbnd      esdtool -writebnd 重新打包的 BND4
   └─ m00_00_00_00.talkesdbnd.dcx  pack_talk_esd.py 包回 KRAK DCX（最终）
```

## 依赖

* Python 3.11（`extract_game_file.py` / `patch_grace_esd.py` / `pack_talk_esd.py`）
* [ESDLang `esdtool`](https://github.com/thefifthmatt/ESDLang/releases) v0.5.1（解压到任意目录，
  下面的 `$esdtool` 指 `esdtool.exe` 所在目录）
* 游戏自带的 `oo2core_6_win64.dll`（Oodle KRAK 压缩/解压，脚本会从游戏根目录加载）

## 重建（游戏升级后）

在游戏根目录（`...\ELDEN RING\Game`）执行：

```powershell
# 0) 抽原始 DCX（Data0.bhd/bdt 是 RSA + AES 加密的，脚本会处理）
python er-echo\tools\extract_game_file.py extract-raw `
  /script/talk/m00_00_00_00.talkesdbnd.dcx `
  er-echo\ui\talk\m00_00_00_00.raw.dcx

# 1) 解压成 BND4（pack 脚本要复用 raw.dcx 的 76 字节头）
python er-echo\tools\extract_game_file.py extract `
  /script/talk/m00_00_00_00.talkesdbnd.dcx `
  er-echo\ui\talk\m00_00_00_00.talkesdbnd.dcx

# 2) 解压 BND4（extract_game_file.py 默认已经解压；确认文件头是 BND4）
#    然后把它作为 esdtool 的模板
Copy-Item er-echo\ui\talk\m00_00_00_00.talkesdbnd.dcx `
          er-echo\ui\base\m00_00_00_00.talkesdbnd -Force

# 3) 反编译（只反编译 t000001000 也行，-noannotate 避免依赖 msg/param）
& "$esdtool\esdtool.exe" -er -noannotate `
  -i "er-echo\ui\base\m00_00_00_00.talkesdbnd" `
  -writepy "er-echo\ui\esd\py\%e.py"

# 4) 加「战友」菜单
python er-echo\tools\patch_grace_esd.py

# 5) 重新编译 + 打包
& "$esdtool\esdtool.exe" -er -noannotate `
  -esddir "er-echo\ui\base" -f t000001000 `
  -i "er-echo\ui\esd\edit\t000001000.py" `
  -writebnd "er-echo\ui\out_bnd"
python er-echo\tools\pack_talk_esd.py

# 6) 部署
Copy-Item er-echo\ui\out_bnd\m00_00_00_00.talkesdbnd.dcx `
          mod\script\talk\m00_00_00_00.talkesdbnd.dcx -Force

# 7) 确认 config_eldenring.toml 的 mod_loader 真的加载 mod/：
#    mods = [ { enabled = true, name = "er-echo", path = "mod" } ]
#    mods = [] 时 ME2 不会读 mod/script/talk，游戏里看不到任何改动。
```

> `pack_talk_esd.py` 会把 `out_bnd\m00_00_00_00.talkesdbnd` 用 Oodle KRAK 压回 DCX，
> 并做一次解压回读校验；输出应在 30 KB 左右。

## 菜单 / 文本 / 标志

| 用途 | 文本 ID | ESD 结果 | 事件标志 |
|---|---|---|---|
| 根选项「战友（x/y）」 | 69100000 | — | — |
| 人数标签 | 69100001 | — | — |
| 1/2/3 号位 | 69100002..04 | — | — |
| 立即重召 | 69100005 | — | 6727 |
| 返回 | 69100006 | — | — |
| 友伤开关 | 69100007 | — | 6729 |
| 「队友 AI」入口（二级菜单） | 69100008 | — | — |
| 队友 AI 1/2/3 号位（三级） | 69100020..22 | — | 6730..6732 |
| 人数 0/1/2/3 | 69100010..13 | — | 6720..6723 |
| 1/2/3 号位循环 | — | — | 6724..6726 |
| 档案名（最多 16 个） | 69100100+ | — | — |

> 三级「队友 AI」菜单是 DLL 运行时注入的（`ezstate.rs` 的 `build_inject`），不需要 ESD；
> 根列表 fallback 版本没有这一项。

* 文本由 `er_echo.dll` 的 `LookupEntry` 钩子返回（bnd 33 `event_text_for_talk`）；
* 菜单只写标志，DLL 每帧读并清零；标志会进存档，所以 DLL 读完立刻 `set_flag(false)`，
  `roster::clear_flags()` 启动时再清一次；
* **不要**把标志改成 69031xxx：group 69031 不在 `CSEventFlagMan` 的 holder 表里（§18.6）。

## 注意

* `talkesdbnd` 是版本绑定的；游戏升级后必须重新抽/反编译/编译。
* 如果你的 mod 也改 `m00_00_00_00.talkesdbnd.dcx`，需要把两份 ESD 改动合并，不能直接覆盖。
* `esdtool -writebnd` 输出的是**未压缩** BND4；必须再跑 `pack_talk_esd.py` 才是游戏要的 `.dcx`。
