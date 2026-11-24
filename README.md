# ER Echo锛堣お鑹叉畫鍝嶏級

> 鍙敜**浣犺嚜宸卞彟涓€涓瓨妗ｉ噷鐨勮鑹?*褰撳悓浼达細澶栬銆佷綋鍨嬨€佽澶囥€佺瓑绾с€佹硶鏈叏閮ㄤ竴鑷达紱鎴樻枟鐢?*娓告垙鍘熺敓 AI**锛?> 楠ㄧ伆寮忚窡闅忥紝鎺夐槦鑷姩鎷夊洖锛涜祼绂忚彍鍗曢噷鎹汉鏁般€佸彿浣嶃€侀槦鍙?AI銆佸紑鍏冲弸浼ゃ€?*鍙绾夸娇鐢ㄣ€?*

![ER Echo](nexus/media/00-banner-1400x400.jpg)

[English quick start](#english-quick-start) 路 [涓嬭浇瀹夎](#download) 路 [浠庢簮鐮佹瀯寤篯(#build-from-source) 路
[椤圭洰缁撴瀯](#project-structure) 路 [鏂囨。绱㈠紩](#docs) 路 [鍙戝竷娴佺▼](#release)

---

## 杩欐槸浠€涔?
ER Echo 鏄?**ELDEN RING 1.17.2** 鐨?DLL mod锛圧ust锛岃繍琛屽湪 Mod Engine 2 / me3 涓嬶級銆傚畠鎶婃父鎴忛噷鐨?銆岄鐏般€嶆崲鎴愪竴涓粠**浣犺嚜宸辩殑瀛樻。**瀵煎嚭鐨勮鑹诧紝骞朵繚鐣欓鐏板師鐢熺殑璺熼殢銆佽拷鍑汇€佷紶閫併€佹柦娉曡涓恒€?
| 鑳藉姏 | 璇存槑 |
|---|---|
| 鑷繁鐨勮鑹?| 浠?`.sl2` 瀵煎嚭锛氳劯銆佷綋鍨嬨€?2 涓澶囨Ы銆佺瓑绾с€? 缁村睘鎬с€佽蹇嗘硶鏈?|
| 1鈥? 鍚嶅悓浼?| 姣忎釜鍙蜂綅涓€浠芥。妗堬紝鍙悓鍦猴紱鍙敜涓嶇湅鍖哄煙/鍙敜鐭?鍐峰嵈 |
| 鍘熺敓 AI | 璺熼殢銆佹帀闃熶紶閫併€佺储鏁屻€佷妇鐩俱€佹柦娉曪紱涓嶆敼 `regulation.bin`銆佷笉鍐欎綘鐨?`.sl2` |
| 璧愮銆屾垬鍙嬨€嶈彍鍗?| 浜烘暟 / 1鈥? 鍙蜂綅 / 闃熷弸 AI锛堜笁绾э級/ 绔嬪嵆閲嶅彫 / 鍙嬩激 / 杩斿洖 |
| 骞宠　涓庝究鍒?| 闃熷弸浼ゅ淇涓庣帺瀹朵竴鑷淬€佸崌绾ц窡闅忋€佹晫浜?HP 鎸夊嚭鎴樺弸浜烘暟琛ユ銆乣F12` 缁欒澶?|
| 澶氳瑷€鑿滃崟 | 榛樿璺熼殢娓告垙鏂囨湰璇█锛堣嫳 / 绠€涓唴缃紝鍙嚜瀹氫箟锛?|
| 瀹夎鏂瑰紡 | 涓€閿畨瑁呭櫒锛堟帹鑽愶級鎴栨墜鍔ㄨВ鍘嬶紱涓嶆墦鍖呫€佷笉鍒嗗彂鍔犺浇鍣?|
| 鍙€?| Python LLM銆屾垬鏂楀婕斻€嶏紝榛樿 mock 绂荤嚎 |

> 鈿狅笍 **鍙绾?*锛氬叧 EAC 鍚姩锛屽甫 mod 鐨勫瓨妗ｄ笉瑕佷笂绾匡紙浼?soft-ban锛夈€傛敼妗ｅ墠鍏堝浠?`ER0000.sl2`銆?
---

## English quick start

ER Echo summons **characters from your own save files** as Spirit Ash companions: same face, body,
gear, level and spells, driven by the game's native AI. Offline only.

- **Requires:** ELDEN RING **1.17.2** (exe 2.7.2.0 / 2.7.2.1), Windows 10/11 x64, Mod Engine 2
  (tested 2.1.0) or me3 (standalone, or bundled with The Convergence 3.x).
- **Install:** download `ER-Echo-Setup-0.1.0.zip`, extract anywhere, run `ER-Echo-Setup.exe`, pick the
  game folder + loader, **Install**, then **Launch game**. No manual config editing.
- **Manual install:** `ER-Echo-0.1.0.zip` (no `.exe`) 鈫?unzip into `...\ELDEN RING\Game`, follow its
  `README.txt`.
- **In game:** Site of Grace 鈫?first entry **Comrades (n/m)**; `F8` summons directly.
- **Build from source:** see [Build from source](#build-from-source); one command is
  `powershell -File tools\build_all.ps1`.
- Loaders are **not** bundled or redistributed. Nothing is sent over the network; the DLL only opens
  a loopback socket `127.0.0.1:7811` for local tools.

---

<a id="download" name="download"></a>
## 涓嬭浇涓庡畨瑁?
| 娓犻亾 | 鎷夸粈涔?|
|---|---|
| **Nexus Mods**锛堜富鍙戝竷椤碉級 | 涓绘枃浠?`ER-Echo-Setup-0.1.0.zip`锛涘彲閫夛細鎵嬪姩鍖呫€丒SD fallback 鍖?|
| **GitHub Releases** | 鍚屾牱涓変釜 zip + `release-checksums.txt`锛堝鐢ㄤ笅杞?/ 鏍稿 hash锛?|

涓変釜鍖呯殑鍒嗗伐锛?
| 鏂囦欢 | 鐢ㄩ€?|
|---|---|
| `ER-Echo-Setup-0.1.0.zip` | **鎺ㄨ崘**銆備竴閿畨瑁呭櫒锛氭嫹鏂囦欢銆佸鍑哄瓨妗ｈ鑹层€佸啓 `profiles=`銆佹敼鍔犺浇鍣ㄩ厤缃紙鍏ㄥ甫澶囦唤锛夈€佸悓椤靛嵏杞斤紝骞舵湁涓€閿惎鍔ㄣ€?|
| `ER-Echo-0.1.0.zip` | 鎵嬪姩瀹夎锛氳В鍘嬪埌 `...\ELDEN RING\Game`锛屾寜鍖呭唴 `README.txt` 鑷繁鍔?`external_dlls` / `mod_loader`銆?*涓嶅惈 exe**銆?|
| `ER-Echo-0.1.0-ESD-fallback.zip` | 鍙€夈€傚彧鍦ㄨ繍琛屾椂娉ㄥ叆鐨勩€屾垬鍙嬨€嶅叆鍙ｅ缁堜笉鍑虹幇鏃剁敤锛屼細鏇挎崲 talk ESD銆?|

瀹夎鍓嶆彁锛?
1. 姝ｇ増 ELDEN RING **1.17.2**锛岃兘**涓嶅甫 mod**杩涙爣棰樺苟绋冲畾涓€鍒嗛挓锛堝惁鍒欏厛淇父鎴?EAC锛夈€?2. 瑁呭ソ鍔犺浇鍣細鍘熺増 鈫?[Mod Engine 2](https://github.com/soulsmods/ModEngine2/releases)锛?   鍘熺増 + me3 鎴?The Convergence 3.x 鈫?[me3](https://github.com/garyttierney/me3/releases)銆?3. 澶囦唤 `%APPDATA%\EldenRing\<SteamID>\ER0000.sl2`銆?
> 瀹夎鍣ㄤ笉甯?ME2 / me3 / Convergence 鐨勬枃浠讹紝鍙啓閰嶇疆寮曠敤锛涢〉闈㈤噷缁欎簡瀹樻柟閾炬帴鍜屽畨瑁呮楠ゃ€?> 瀹夎鍣ㄦ湭鍋氫唬鐮佺鍚嶏紝涓埆鏉€杞? VirusTotal 寮曟搸锛堝吀鍨嬫槸 Elastic锛変細鎶?PyInstaller 鍖呰鎶ヤ负鎭舵剰锛?> 婧愮爜銆佹瀯寤鸿剼鏈拰姣忔鍙戝竷鐨?SHA-256 閮藉湪鏈粨搴擄紝浠嬫剰鐨勮瘽鐢ㄦ墜鍔ㄥ寘鎴栬嚜琛屾瀯寤恒€?
---

<a id="build-from-source" name="build-from-source"></a>
## 浠庢簮鐮佹瀯寤?
### 1. 宸ュ叿閾撅紙涓€娆℃€э級

| 缁勪欢 | 瑕佹眰 | 鐢ㄩ€?|
|---|---|---|
| Windows | 10/11 x64 | 鍏ㄩ儴 |
| Rust | `rustup` + `stable-x86_64-pc-windows-gnu` 宸ュ叿閾?| 缂栬瘧 `er_echo.dll` |
| MSYS2 binutils | 瑙ｅ帇鍒?`%USERPROFILE%\er-tools\binutils`锛堟彁渚?`mingw64\bin\as.exe`锛?| Rust 鐨?gnu 閾炬帴 |
| Python | 3.11锛坄python` 鍦?PATH锛?| 瀹夎鍣?/ 瀵煎嚭宸ュ叿 |
| Python 鍖?| `PySide6`銆乣PyInstaller`銆乣Pillow` | 鏋勫缓瀹夎鍣紱鑴氭湰浼氳嚜鍔ㄨ鍒?`build\pydeps`锛屼笉鍔ㄧ郴缁?Python |
| 娓告垙鏈綋 | 1.17.2锛堝彲閫夛級 | `doctor.ps1` 瀹炴祴銆佹瀯寤哄悗椤烘墜鎷?DLL |

> Rust 鐢?gnu 宸ュ叿閾炬槸鍥犱负閾炬帴鍣ㄨ嚜甯?`rust-lld`+MinGW锛?*涓嶉渶瑕?* Visual Studio Build Tools锛?> 浣?gnu 宸ュ叿閾剧己 `as.exe`锛屾墍浠ラ渶瑕?MSYS2 binutils銆?
### 2. 涓€鏉″懡浠ゆ瀯寤哄叏閮?
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_all.ps1
```

瀹冩寜椤哄簭鎵ц涓嬮潰鍥涙锛屾渶鍚庢墦鍗颁笁涓?zip 鐨勮矾寰?/ 澶у皬锛屽苟鏇存柊 `nexus\release-checksums.txt`銆?
### 3. 鍒嗘鏋勫缓锛堟帓鏌ユ椂鐢級

```powershell
# 1) Rust DLL -> mod\target\release\er_echo.dll锛堟帰鍒版父鎴忕洰褰曚細椤烘墜鎷疯繃鍘伙級
powershell -NoProfile -ExecutionPolicy Bypass -File mod\build.ps1

# 2) 瀹夎鍣?payload -> build\payload锛圖LL + 鏂囨。 + 鍚姩 bat + talk ESD + 璁稿彲锛?powershell -NoProfile -ExecutionPolicy Bypass -File tools\package_payload.ps1 -SkipBuild

# 3) 瀹夎鍣?-> dist\tools\ER-Echo-Setup\锛坥nedir锛岄娆′細鑷姩瑁?PySide6/PyInstaller/Pillow锛?powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_gui_exe.ps1 -SkipPayload

# 4) 涓変釜鍙戝竷 zip -> dist\nexus\锛屽苟鍐?nexus\release-checksums.txt
powershell -NoProfile -ExecutionPolicy Bypass -File tools\package_nexus.ps1 -SkipBuild
```

浜х墿锛?
| 浜х墿 | 浣嶇疆 | 璇存槑 |
|---|---|---|
| `er_echo.dll` | `mod\target\release\` | Rust DLL锛岀害 1.6 MB |
| payload | `build\payload\` | 瀹夎鍣ㄥ唴宓屽唴瀹癸紙47 涓枃浠讹級 |
| `ER-Echo-Setup.exe` + `_internal\` | `dist\tools\ER-Echo-Setup\` | onedir锛岀害 73 MB锛?*鏁翠釜鏂囦欢澶逛竴璧峰垎鍙?* |
| `ER-Echo-Setup-<ver>.zip` | `dist\nexus\` | 涓绘枃浠讹紝绾?28 MB |
| `ER-Echo-<ver>.zip` | `dist\nexus\` | 鎵嬪姩鍖咃紝绾?1 MB |
| `ER-Echo-<ver>-ESD-fallback.zip` | `dist\nexus\` | 鍙€?ESD 鍙樹綋 |
| `release-checksums.txt` | `nexus\` | 涓変釜 zip + DLL 鐨?SHA-256 |

### 4. 鏋勫缓娉ㄦ剰浜嬮」

- **PowerShell 5.1 璇?UTF-8**锛歚.ps1` 閲屾湁涓枃灏卞繀椤诲瓨鎴?**UTF-8 with BOM**锛屽惁鍒欎細琚綋 ANSI(GBK)
  璇汇€佹妸涓嬩竴琛屽悶杩涙敞閲娿€備粨搴撻噷鐨?`.ps1` 閮藉甫 BOM锛屾敼瀹岃妫€鏌?`[IO.File]::ReadAllBytes` 鍓嶄笁瀛楄妭銆?- **`as.exe` 鎵句笉鍒?*锛氱‘璁?`%USERPROFILE%\er-tools\binutils\mingw64\bin\as.exe` 瀛樺湪锛?  `mod\build.ps1` 浼氭妸瀹冨拰 `%USERPROFILE%\.cargo\bin` 涓存椂鍔犺繘 PATH銆?- **pip 鎱?瓒呮椂**锛氬畨瑁呭櫒鏋勫缓璧版竻鍗庨暅鍍忥紙`tools\build_gui_exe.ps1` 閲岀殑 `-i`锛夛紱绂荤嚎鏃跺厛鎵嬪姩鎶?  `PySide6` / `pyinstaller` / `pillow` 瑁呰繘 `build\pydeps`銆?- **瀹夎鍣?GUI 渚濊禆**锛?*涓嶈**鎹㈠洖 PyQt5锛圙PLv3/鍟嗕笟鍙岃鍙紝浼氭妸瀹夎鍣ㄥ彉鎴?GPL 浣滃搧锛夛紱
  鐜板湪鐢?PySide6锛圠GPLv3锛夛紝鏋勫缓鑴氭湰浼氳嚜鍔ㄨ骞惰鍓棤鐢?Qt 妯″潡銆?- **鏉€杞鎶?*锛氭湭绛惧悕 + PyInstaller + 娉ㄥ叆娓告垙鐨?DLL 鏄父瑙佸惎鍙戝紡鐩爣锛涙瀯寤?鍙戝竷鍓嶅彲鍙傝€?  `nexus\false-positive-report.md`銆傛瀯寤虹敤 `--onedir`銆乣--noupx`锛堣剼鏈凡鍥哄畾锛夈€?- **鏋勫缓浜х墿涓嶅叆搴?*锛歚mod/target/`銆乣build/`銆乣dist/` 閮藉湪 `.gitignore` 閲岋紝闅忔椂鍙噸寤恒€?
---

<a id="project-structure" name="project-structure"></a>
## 椤圭洰缁撴瀯

```
ER-Echo/
鈹溾攢 mod/                        Rust DLL锛坈dylib锛?鈹? 鈹溾攢 src/                     lib.rs / ezstate.rs / i18n.rs / balance.rs / spirit.rs / ui.rs / ipc.rs ...
鈹? 鈹溾攢 Cargo.toml               鐗堟湰鍙凤紙鍙戝竷鏃朵笌鏂囦欢鍚嶃€侀〉闈繚鎸佷竴鑷达級
鈹? 鈹溾攢 build.ps1                鏋勫缓 DLL锛堣 PATH銆乧argo build --release锛?鈹? 鈹斺攢 examples/offsets.rs      鍋忕Щ閲忔帰娴嬪皬宸ュ叿
鈹溾攢 vendor/fromsoftware-rs-main/  涓婃父 crate 蹇収锛坋ldenring / shared锛屽惈 NON-AI 璁稿彲璇佸叏鏂囷級
鈹溾攢 tools/                      鏋勫缓 + 杩愯鏃跺伐鍏?鈹? 鈹溾攢 build_all.ps1            涓€鏉″懡浠ゆ瀯寤哄叏閮?鈹? 鈹溾攢 package_payload.ps1      鐢熸垚瀹夎鍣?payload
鈹? 鈹溾攢 build_gui_exe.ps1        PyInstaller 鎵撳寘 ER-Echo-Setup.exe
鈹? 鈹溾攢 package_nexus.ps1        鐢熸垚涓変釜鍙戝竷 zip + 鏍￠獙娓呭崟
鈹? 鈹溾攢 publish_github_release.ps1  鍙戝竷鍒?GitHub Releases
鈹? 鈹溾攢 er_echo_setup.py         瀹夎/鍗歌浇/鍔犺浇鍣?鍚姩/鍙傛暟琛紙鏃?Qt 渚濊禆鐨勬牳蹇冿級
鈹? 鈹溾攢 profile_export_gui.py    Qt 鐣岄潰锛堝畨瑁呫€佸鍑恒€佽缃級
鈹? 鈹溾攢 doctor.ps1               瀹夎棰勬锛堢増鏈?鍔犺浇鍣?渚濊禆/鏉冮檺/鎻愭潈/bat 鍙傛暟锛?鈹? 鈹溾攢 gamedir.ps1 / .py        娓告垙鐩綍鎺㈡祴
鈹? 鈹溾攢 export_profile_from_save.py  浠?.sl2 瀵煎嚭瑙掕壊
鈹? 鈹溾攢 ipc_client.py / ipc_send.py  DLL 鏈湴 IPC 宸ュ叿
鈹? 鈹斺攢 switch_menu_mode.ps1 / reset_to_vanilla.ps1 ...
鈹溾攢 bridge/                     鍙€?Python sidecar锛圠LM 鎴樻枟瀵兼紨锛岄粯璁?mock锛?鈹溾攢 config/                     behavior_map.yaml / weights.schema.json
鈹溾攢 install/                    er_echo.ini 妯℃澘銆丮E2 閰嶇疆鐗囨銆佸惎鍔?bat 妯℃澘銆佸唴缃。妗堛€丆onvergence 鍙傛暟琛?鈹溾攢 ui/                         璧愮鑿滃崟 ESD 璧勪骇锛坆ase 妯℃澘 / esd 鑴氭湰 / out_vanilla / out_rootmenu锛?鈹溾攢 docs/                       瀹夎銆佷娇鐢ㄣ€佹彃浠躲€丆onvergence銆乮18n銆佽璁°€佸疄鐜版棩蹇椼€佸彂甯?鈹溾攢 nexus/                      Nexus 鍙戝竷鏉愭枡锛堟枃妗?瀛楁/娓呭崟/鎴浘/璁稿彲/鏍￠獙/鐢宠瘔妯℃澘锛?鈹溾攢 dist/                       锛堝拷鐣ワ級鏋勫缓浜х墿
鈹斺攢 build/                      锛堝拷鐣ワ級涓棿鏂囦欢銆丳yInstaller 渚濊禆
```

鍏抽敭鏂囦欢锛?
| 璺緞 | 浣滅敤 |
|---|---|
| `mod/src/lib.rs` | DLL 鍏ュ彛銆佺儹閿€両PC 鍛戒护銆侀厤缃В鏋愩€佸彫鍞?娉ㄥ叆涓绘祦绋?|
| `mod/src/ezstate.rs` | 璧愮鑿滃崟 EzState 杩愯鏃舵敞鍏ワ紙鍚洖鏍囬/璇绘。鍚庨噸鎵撹ˉ涓侊級 |
| `mod/src/i18n.rs` | 鑿滃崟鏂囨涓庛€岃窡闅忔父鎴忚瑷€銆嶈В鏋?|
| `tools/package_nexus.ps1` | 鍙戝竷鍖呯殑**鍞竴**鍑哄彛锛氫笁涓?zip + 鍝堝笇 |
| `install/er_echo.ini.template` | 閰嶇疆榛樿鍊硷紙`profiles`銆佸弸浼ゃ€佸钩琛°€丄I銆乮18n锛?|
| `nexus/checklist.md` | 鍙戝竷褰撳ぉ鐨勬搷浣滄竻鍗?|
| `docs/RELEASING.md` | GitHub Release 鐨勪笁绉嶅彂甯冩柟寮?|

---

<a id="docs" name="docs"></a>
## 鏂囨。绱㈠紩

| 鏂囨。 | 鍐呭 |
|---|---|
| [docs/INSTALL.md](docs/INSTALL.md) 路 [INSTALL.en.md](docs/INSTALL.en.md) | 浠庨浂瀹夎銆佹崲鏈恒€佺棁鐘跺鐓?|
| [docs/usage.md](docs/usage.md) | 鍏ㄩ儴閰嶇疆椤广€佽彍鍗曘€佺儹閿€両PC 鍛戒护銆佹帓闅?|
| [docs/PLUGIN.md](docs/PLUGIN.md) | 鍙彃鎷斿畨瑁咃紙`mods\ER-Echo\`锛変笌鍗歌浇 |
| [docs/CONVERGENCE.md](docs/CONVERGENCE.md) | Convergence 3.x + me3 閫傞厤 |
| [docs/i18n.md](docs/i18n.md) | 鑿滃崟璇█瑙ｆ瀽涓庤嚜瀹氫箟鏂囨 |
| [docs/design.md](docs/design.md) | 璁捐鏂囨。锛堟満鍒躲€佽皟鐮斻€佸彇鑸嶏級 |
| [docs/implementation-log.md](docs/implementation-log.md) | 閫愭棩瀹炵幇鏃ュ織涓庤俯鍧戣褰?|
| [docs/RELEASING.md](docs/RELEASING.md) | 鍙戝竷鍒?GitHub Releases |
| [nexus/](nexus/README.md) | Nexus 椤甸潰鏂囨銆佸瓧娈点€佹埅鍥俱€佷笂浼犳竻鍗?|

甯哥敤鍛戒护锛?
```powershell
powershell -File tools\doctor.ps1                     # 瀹夎棰勬
python tools\export_profile_from_save.py --list       # 鍒楀嚭瀛樻。瑙掕壊
python tools\ipc_client.py status                     # 娓告垙鍐呯姸鎬?python tools\ipc_send.py rebuild_clone --arg mode=model
```

---

<a id="release" name="release"></a>
## 鍙戝竷娴佺▼

1. 鏀圭増鏈彿锛歚mod/Cargo.toml`锛屽苟纭椤甸潰/鏂囦欢鍚嶄竴鑷淬€?2. 鏋勫缓锛歚powershell -File tools\build_all.ps1`銆?3. 鏍稿锛歚nexus\release-checksums.txt`銆?4. **Nexus**锛氭寜 [nexus/checklist.md](nexus/checklist.md) 涓婁紶锛涜 quarantine 鏃剁敤
   [nexus/nexus-quarantine-appeal.md](nexus/nexus-quarantine-appeal.md)銆?5. **GitHub**锛歚powershell -File tools\publish_github_release.ps1 -DryRun` 鐪嬭鍒掞紝鍘绘帀 `-DryRun`
   姝ｅ紡鍙戯紙鎴栨寜 [docs/RELEASING.md](docs/RELEASING.md) 鐢ㄧ綉椤?/ `gh`锛夈€?
---

## 鍏煎鎬т笌宸茬煡闄愬埗

- **鐗堟湰閿佸畾**锛氬彧鏀寔 1.17.2锛坋xe 2.7.2.0 / 2.7.2.1锛夛紱娓告垙鏇存柊鍚庤閲嶆槧灏勫亸绉诲苟閲嶆柊缂栬瘧銆?- **鍐茬獊**锛氭敼鍚屼竴鎵瑰弬鏁拌锛圔uddyParam / NpcParam / NpcThinkParam / BuddyStoneParam锛夋垨鍚屼竴浠?  talk ESD 鐨?mod 鍙兘鍐茬獊锛涘厛鍙鏈?mod 鍐嶉€愪釜鍔犲洖銆?- **楠ㄧ伆閫夋嫨**锛氶粯璁ゆ敼銆屽鐙奸鐏般€嶈锛屽叾瀹冮鐏拌鍦?`er_echo.ini` 鐨?`buddy_rows` 閲屾槧灏勩€?- **beta**锛氭牳蹇冩祦绋嬪凡鍦?1.17.2 瀹炴祴锛屼絾浠嶆槸 0.x锛涗繚鐣欏共鍑€瀛樻。鍜屽浠姐€?
---

## 璁稿彲涓庣涓夋柟

- 鏈粨搴撲唬鐮侊細**MIT OR Apache-2.0**锛圼LICENSE](LICENSE) / [LICENSE-MIT](LICENSE-MIT) /
  [LICENSE-APACHE](LICENSE-APACHE)锛夈€?- `vendor/fromsoftware-rs-main`锛?*MIT-NON-AI / Apache-2.0-NON-AI**锛屽叏鏂囬殢浠撳簱鍜屽彂甯冨寘鍒嗗彂
  锛圼nexus/THIRD-PARTY-LICENSES.txt](nexus/THIRD-PARTY-LICENSES.txt)锛夛紝涓嶅緱鐢ㄤ簬璁粌 ML 妯″瀷銆?- 瀹夎鍣ㄨ繍琛屾椂锛歈t 6 / PySide6锛圠GPLv3锛夈€丆Python锛圥SF锛夈€丱penSSL锛圓pache-2.0锛夈€乴ibffi锛圡IT锛夈€?  PyInstaller锛圙PLv2+渚嬪锛夛紱鍏ㄦ枃鍦ㄥ彂甯冨寘鐨?`LICENSES\`銆?- 鍙戝竷鍖呭惈涓€浠?*鏀硅繃鐨?* vanilla talk ESD锛堣祼绂忚彍鍗曟寕杞界偣蹇呴渶锛夛紝涓嶅惈 `regulation.bin`锛屼笉鍚粬浜哄瓨妗ｏ紱
  `ui/base` 鍙槸閲嶆墦鍖呮ā鏉匡紝涓嶉殢鍖呭垎鍙戙€?- 鏈粨搴撲笉鍖呭惈 ME2 / me3 / Convergence 鐨勬枃浠躲€?
ELDEN RING 鏄?FromSoftware / Bandai Namco 鐨勫晢鏍囷紱鏈」鐩槸闈炲畼鏂?fan work锛屼笌涓ゅ鍏徃鏃犲叧銆?