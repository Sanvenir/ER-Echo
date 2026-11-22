//! 游戏内可见文字的本地化（赐福菜单那几行）。
//!
//! 整个 mod 里真正显示在游戏里的字符串只有 `ui.rs` 的菜单文案，所以这里做的不是
//! 通用 i18n 框架，而是「模板表 + 命名占位符」：
//!
//! * 内置 `zh-CN` / `zh-TW` / `en` / `ja`；缺键一律回退 `en`，再缺就原样返回 key；
//! * `er_echo_i18n.ini`（游戏根目录，可选）可以覆盖内置文案，也可以新增语言，
//!   新增语言只要在 `er_echo.ini` 里写 `[i18n] language=ko` 就行；
//! * `language=game`（推荐，安装器默认）**直接跟游戏自己的文本语言**；
//! * `language=auto` 读 Windows 显示语言；也有人写死 `zh-CN` / `en` / …。
//!
//! 游戏文本语言从哪来：Elden Ring 自己没有「游戏内语言」开关，它读的是 Steam
//! 的 per-game 语言（`ISteamApps::GetCurrentGameLanguage`，用户没选过时回退
//! Steam 界面语言）。所以这里按下面顺序取，拿到就停：
//!
//! 1. 进程里的 `steam_api64.dll` → `SteamAPI_ISteamApps_GetCurrentGameLanguage`
//!    （和游戏读的是同一个值；Goldberg 之类模拟器也实现这个接口）；
//! 2. `<库>\steamapps\appmanifest_1245620.acf` 的 `UserConfig` → `MountedConfig`；
//! 3. Goldberg / SteamEmu 的 `settings\language` 或 `steam_settings\configs.user.ini`；
//! 4. 都不行才退回 Windows 显示语言（等同于 `auto`）。
//!
//! 注意：文字最终由游戏的字体图集渲染，**菜单语言要和游戏文本语言一致**，
//! 否则可能出现方块（游戏只加载当前语言的字体）——这正是 `game` 模式要解决的问题。

use std::collections::HashMap;
use std::os::windows::ffi::OsStringExt;
use std::sync::{Mutex, OnceLock};

/// 可选的外部翻译文件（相对游戏根目录，或 DLL 同目录）。
pub const OVERRIDE_FILE: &str = "er_echo_i18n.ini";

/// 覆盖文件的实际路径：DLL 同目录优先，其次 CWD。
pub fn override_path() -> std::path::PathBuf {
    crate::data_file(OVERRIDE_FILE)
}

/// 内置语言代码。顺序无关，仅用于文档/日志。
pub const BUILTIN_LANGS: &[&str] = &["zh-CN", "zh-TW", "en", "ja"];

/// Elden Ring 的 Steam AppID（`appmanifest_1245620.acf`）。
const STEAM_APP_MANIFEST: &str = "appmanifest_1245620.acf";
/// Goldberg / SteamEmu 的全局语言文件。
const EMU_LANG_FILE: &str = r"Goldberg SteamEmu Saves\settings\language";
/// Goldberg 的 per-user 配置（新版）。
const EMU_USER_CONFIG: &str = r"Goldberg SteamEmu Saves\settings\configs.user.ini";
/// 游戏目录里的模拟器配置（`<Game>\steam_settings\configs.user.ini`）。
const EMU_GAME_CONFIG: &str = r"steam_settings\configs.user.ini";

/// 语言来源（`er_echo.ini` 里 `[i18n] language=` 的写法）。
#[derive(Clone, Copy, PartialEq, Eq)]
enum Mode {
    /// 写死的语言代码
    Fixed,
    /// `game`：跟随游戏文本语言
    Game,
    /// `auto`：跟 Windows 显示语言
    Os,
}

struct State {
    mode: Mode,
    /// 当前生效的语言代码
    code: String,
    /// 这个代码从哪来的（日志 / status 用）
    source: &'static str,
    /// `game` 模式是否已经从进程内 Steam 接口读到过语言（读到前每次取值都重试）
    steam_ok: bool,
}

/// 当前状态；`None` = 还没 `configure`，按 auto 现算。
static STATE: Mutex<Option<State>> = Mutex::new(None);
/// `"<lang>\u{1}<key>"` → 文案。
static OVERRIDES: OnceLock<HashMap<String, String>> = OnceLock::new();

#[link(name = "kernel32")]
unsafe extern "system" {
    fn GetUserDefaultUILanguage() -> u16;
    fn GetModuleHandleA(name: *const u8) -> *mut std::ffi::c_void;
    fn GetProcAddress(module: *mut std::ffi::c_void, name: *const u8) -> *mut std::ffi::c_void;
    fn GetModuleFileNameW(module: *mut std::ffi::c_void, buf: *mut u16, len: u32) -> u32;
}

/// 把用户写的语言名归一化成语言代码。`None` 表示 "auto"/空。
fn canonical_code(spec: &str) -> Option<String> {
    let s = spec.trim().to_ascii_lowercase().replace('_', "-");
    Some(match s.as_str() {
        "" | "auto" => return None,
        "zh" | "zh-cn" | "zh-hans" | "chs" | "cn" | "zh-sg" => "zh-CN".into(),
        "zh-tw" | "zh-hk" | "zh-mo" | "zh-hant" | "cht" | "tw" => "zh-TW".into(),
        "en" | "en-us" | "en-gb" => "en".into(),
        "ja" | "jp" | "ja-jp" => "ja".into(),
        other
            if !other.is_empty()
                && other
                    .chars()
                    .all(|c| c.is_ascii_alphanumeric() || c == '-') =>
        {
            other.to_string()
        }
        _ => "en".into(),
    })
}

/// Windows 显示语言 → 语言代码。
fn detect_os() -> String {
    let id = unsafe { GetUserDefaultUILanguage() };
    let primary = id & 0x03ff;
    let sub = (id >> 10) & 0x3f;
    match primary {
        // 0x04 = LANG_CHINESE；0x02 简体、0x04 新加坡 = 简体，其余（TW/HK/MO）= 繁体
        0x04 if sub == 0x02 || sub == 0x04 => "zh-CN".into(),
        0x04 => "zh-TW".into(),
        // 0x11 = LANG_JAPANESE
        0x11 => "ja".into(),
        _ => "en".into(),
    }
}

/// `language=` 写 `game` 时表示「跟随游戏文本语言」（这些别名都认）。
fn is_game_spec(spec: &str) -> bool {
    matches!(
        spec.trim().to_ascii_lowercase().as_str(),
        "game" | "steam" | "follow" | "follow-game" | "game-language"
    )
}

/// Steam 的语言名 → 我们的语言代码（Steam 的 `GetCurrentGameLanguage` 返回值）。
///
/// 只认 Steamworks 支持的语言名；认不出来返回 `None`（调用方继续走兜底）。
fn steam_name_to_code(name: &str) -> Option<String> {
    let name = name.trim().to_ascii_lowercase().replace('_', "-");
    let code = match name.as_str() {
        "english" => "en",
        "schinese" => "zh-CN",
        "tchinese" => "zh-TW",
        "japanese" => "ja",
        "koreana" => "ko",
        "brazilian" => "pt-BR",
        "portuguese" => "pt",
        "latam" => "es-419",
        "spanish" => "es",
        "french" => "fr",
        "german" => "de",
        "italian" => "it",
        "polish" => "pl",
        "russian" => "ru",
        "ukrainian" => "uk",
        "turkish" => "tr",
        "czech" => "cs",
        "danish" => "da",
        "dutch" => "nl",
        "finnish" => "fi",
        "norwegian" => "no",
        "romanian" => "ro",
        "swedish" => "sv",
        "hungarian" => "hu",
        "greek" => "el",
        "bulgarian" => "bg",
        "thai" => "th",
        "vietnamese" => "vi",
        "arabic" => "ar",
        _ => return None,
    };
    Some(code.to_string())
}

/// 配置/模拟器文件里的一种写法 → 语言代码：先按 Steam 语言名认，再按代码认。
///
/// 只接受像代码的值（字母数字/`-`/`_`），避免把 `auto` 或垃圾值误判成英文。
fn language_value(value: &str) -> Option<String> {
    let value = value.trim();
    if value.is_empty() || value.eq_ignore_ascii_case("auto") {
        return None;
    }
    if let Some(code) = steam_name_to_code(value) {
        return Some(code);
    }
    let looks_like_code = value.len() <= 12
        && value
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_');
    if looks_like_code {
        canonical_code(value)
    } else {
        None
    }
}

/// 当前进程 exe 所在目录（用来往上找 `steamapps`）。
fn exe_dir() -> Option<std::path::PathBuf> {
    unsafe {
        let mut buf = vec![0u16; 1024];
        let n = GetModuleFileNameW(std::ptr::null_mut(), buf.as_mut_ptr(), buf.len() as u32) as usize;
        if n == 0 || n >= buf.len() {
            return None;
        }
        let s = std::ffi::OsString::from_wide(&buf[..n]);
        std::path::Path::new(&s).parent().map(|p| p.to_path_buf())
    }
}

/// 进程内问 Steam：游戏自己读的就是这个值。
///
/// 三个导出都要在，而且 `SteamAPI_Init` 已经跑完（`GetHSteamUser` 非 0）才敢调
/// 接口——否则 steam_api 自己的上下文还没建好，调了会崩。
unsafe fn steam_language() -> Option<String> {
    let module = GetModuleHandleA(b"steam_api64.dll\0".as_ptr());
    if module.is_null() {
        return None;
    }
    let user_fn = GetProcAddress(module, b"SteamAPI_GetHSteamUser\0".as_ptr());
    let apps_fn = GetProcAddress(module, b"SteamAPI_SteamApps_v008\0".as_ptr());
    let lang_fn = GetProcAddress(
        module,
        b"SteamAPI_ISteamApps_GetCurrentGameLanguage\0".as_ptr(),
    );
    if user_fn.is_null() || apps_fn.is_null() || lang_fn.is_null() {
        return None;
    }
    let get_user: unsafe extern "C" fn() -> u32 = std::mem::transmute(user_fn);
    if get_user() == 0 {
        return None;
    }
    let get_apps: unsafe extern "C" fn() -> *mut std::ffi::c_void = std::mem::transmute(apps_fn);
    let apps = get_apps();
    if apps.is_null() {
        return None;
    }
    let get_lang: unsafe extern "C" fn(*mut std::ffi::c_void) -> *const u8 =
        std::mem::transmute(lang_fn);
    let p = get_lang(apps);
    if p.is_null() {
        return None;
    }
    // 防御：只接受短的、可打印的 ASCII
    let mut len = 0usize;
    while len < 32 && *p.add(len) != 0 {
        len += 1;
    }
    let bytes = std::slice::from_raw_parts(p, len);
    if !bytes.iter().all(|b| b.is_ascii_graphic() || *b == b' ') {
        return None;
    }
    let name = std::str::from_utf8(bytes).ok()?.trim();
    steam_name_to_code(name)
}

/// 在 VDF 块里找 `"language" "xxx"`。
fn vdf_language(block: &str) -> Option<String> {
    let mut rest = block;
    while let Some(i) = rest.find("\"language\"") {
        rest = &rest[i + "\"language\"".len()..];
        let Some(open) = rest.find('"') else { return None };
        let after = &rest[open + 1..];
        let Some(close) = after.find('"') else { return None };
        if let Some(code) = language_value(&after[..close]) {
            return Some(code);
        }
    }
    None
}

/// 解析 `appmanifest_<appid>.acf`：先 `UserConfig`（玩家在 Steam 属性里选的），
/// 再 `MountedConfig`（上次安装时的语言）。
fn manifest_language(text: &str) -> Option<String> {
    for section in ["UserConfig", "MountedConfig"] {
        let Some(start) = text.find(&format!("\"{section}\"")) else {
            continue;
        };
        let rest = &text[start..];
        let end = rest.find('}').unwrap_or(rest.len());
        if let Some(code) = vdf_language(&rest[..end]) {
            return Some(code);
        }
    }
    None
}

/// Steam 库根目录（`...\steamapps`` 的父目录）：从 exe 目录往上找 manifest。
fn steam_manifest_language() -> Option<String> {
    let dir = exe_dir()?;
    for anc in dir.ancestors().take(6) {
        let manifest = anc.join("steamapps").join(STEAM_APP_MANIFEST);
        if let Ok(text) = std::fs::read_to_string(&manifest) {
            return manifest_language(&text);
        }
    }
    None
}

/// `key=value` 形式的模拟器配置里取 `language=`。
fn language_from_config_text(text: &str) -> Option<String> {
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with([';', '#', '[']) {
            continue;
        }
        let Some((key, value)) = line.split_once('=') else {
            continue;
        };
        if key.trim().eq_ignore_ascii_case("language") {
            if let Some(code) = language_value(value) {
                return Some(code);
            }
        }
    }
    None
}

fn language_from_plain_file(path: &std::path::Path) -> Option<String> {
    let raw = std::fs::read_to_string(path).ok()?;
    language_value(&raw)
}

fn language_from_config_file(path: &std::path::Path) -> Option<String> {
    let raw = std::fs::read_to_string(path).ok()?;
    language_from_config_text(&raw)
}

/// Goldberg / SteamEmu：`settings\language` 纯文本，或 `configs.user.ini` 的 `language=`。
fn emu_language() -> Option<String> {
    let mut roots: Vec<std::path::PathBuf> = Vec::new();
    if let Some(dir) = exe_dir() {
        roots.push(dir);
    }
    if let Ok(cwd) = std::env::current_dir() {
        roots.push(cwd);
    }
    for root in &roots {
        if let Some(code) = language_from_config_file(&root.join(EMU_GAME_CONFIG)) {
            return Some(code);
        }
    }
    if let Some(appdata) = std::env::var_os("APPDATA") {
        let base = std::path::PathBuf::from(appdata);
        if let Some(code) = language_from_plain_file(&base.join(EMU_LANG_FILE)) {
            return Some(code);
        }
        if let Some(code) = language_from_config_file(&base.join(EMU_USER_CONFIG)) {
            return Some(code);
        }
    }
    None
}

/// `game` 模式的第一轮解析：进程内 Steam → Steam manifest → 模拟器文件 → Windows。
fn detect_game_initial() -> (String, &'static str) {
    if let Some(code) = unsafe { steam_language() } {
        return (code, "steam");
    }
    if let Some(code) = steam_manifest_language() {
        return (code, "manifest");
    }
    if let Some(code) = emu_language() {
        return (code, "goldberg");
    }
    (detect_os(), "windows")
}

/// 设置语言（`game` / `auto` / `zh-CN` / `en` / 自定义）。返回实际生效的语言代码。
pub fn configure(spec: &str) -> String {
    let (mode, code, source) = if is_game_spec(spec) {
        let (code, source) = detect_game_initial();
        (Mode::Game, code, source)
    } else if let Some(code) = canonical_code(spec) {
        (Mode::Fixed, code, "config")
    } else {
        (Mode::Os, detect_os(), "windows")
    };
    if let Ok(mut g) = STATE.lock() {
        *g = Some(State {
            mode,
            code: code.clone(),
            source,
            steam_ok: false,
        });
    }
    // 预热覆盖表：没有文件也是一次空表，之后不再碰磁盘。
    let _ = OVERRIDES.get_or_init(load_overrides);
    code
}

/// 当前生效的语言代码。
///
/// `game` 模式在第一次成功读到进程内 Steam 语言之前，每次取值都会重试
/// （DLL 启动时 `SteamAPI_Init` 可能还没跑完，那时只能靠 manifest/系统语言兜底）；
/// 读到就换掉兜底值并打一行日志。
pub fn current() -> String {
    let mut changed: Option<(String, String)> = None;
    let code = {
        let mut guard = match STATE.lock() {
            Ok(g) => g,
            Err(_) => return detect_os(),
        };
        if guard.is_none() {
            let code = detect_os();
            *guard = Some(State {
                mode: Mode::Os,
                code: code.clone(),
                source: "windows",
                steam_ok: false,
            });
            return code;
        }
        let st = guard.as_mut().expect("state just checked");
        if st.mode == Mode::Game && !st.steam_ok {
            if let Some(code) = unsafe { steam_language() } {
                st.steam_ok = true;
                if code != st.code {
                    changed = Some((st.code.clone(), code.clone()));
                    st.code = code;
                }
                st.source = "steam";
            }
        }
        st.code.clone()
    };
    if let Some((old, new)) = changed {
        log::info!("i18n: language=game -> {new} (steam_api；之前 {old} 来自 manifest/系统)");
    }
    code
}

/// 当前语言代码是从哪来的：`steam` / `manifest` / `goldberg` / `windows` / `config`。
pub fn source() -> String {
    let _ = current();
    STATE
        .lock()
        .ok()
        .and_then(|g| g.as_ref().map(|s| s.source.to_string()))
        .unwrap_or_else(|| "windows".into())
}

fn overrides() -> &'static HashMap<String, String> {
    OVERRIDES.get_or_init(load_overrides)
}

fn override_for(code: &str, key: &str) -> Option<String> {
    overrides()
        .get(&format!("{code}\u{1}{key}"))
        .cloned()
}

fn load_overrides() -> HashMap<String, String> {
    let Ok(raw) = std::fs::read_to_string(override_path()) else {
        return HashMap::new();
    };
    parse_overrides(&raw)
}

/// 解析 `er_echo_i18n.ini`：`[语言]` 段 + `key=value`，`;`/`#` 注释，值里可以有 `=`。
fn parse_overrides(raw: &str) -> HashMap<String, String> {
    let mut map = HashMap::new();
    let text = raw.strip_prefix('\u{feff}').unwrap_or(raw);
    let mut section = String::new();
    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with([';', '#']) {
            continue;
        }
        if line.starts_with('[') && line.ends_with(']') {
            let name = &line[1..line.len() - 1];
            section = canonical_code(name).unwrap_or_else(|| name.trim().to_string());
            continue;
        }
        let Some((key, value)) = line.split_once('=') else {
            continue;
        };
        if section.is_empty() || key.trim().is_empty() {
            continue;
        }
        map.insert(
            format!("{}\u{1}{}", section, key.trim()),
            value.trim().to_string(),
        );
    }
    map
}

/// 内置文案表：`(语言, key, 模板)`。模板里的 `{name}` 由 [`text`] 的实参替换。
const TABLE: &[(&str, &str, &str)] = &[
    // ---- 简体中文（原版，保持逐字不变） ----
    ("zh-CN", "root", "战友（{count}/{n}）"),
    ("zh-CN", "count_row", "队伍人数：{count}（点击切换）"),
    ("zh-CN", "slot", "{i}号位：{name}（点击切换）"),
    ("zh-CN", "resummon", "立即重新召唤"),
    ("zh-CN", "friendly_fire_on", "友伤：开（{rate}%，点击关闭）"),
    ("zh-CN", "friendly_fire_off", "友伤：关（点击开启）"),
    ("zh-CN", "back", "返回"),
    ("zh-CN", "count_none", "不召唤"),
    ("zh-CN", "count_n", "{count} 人"),
    ("zh-CN", "profile", "{name}  Lv{level}"),
    ("zh-CN", "ai_menu", "队友 AI（点击进入）"),
    ("zh-CN", "ai_slot", "{i}号位 {name}：{preset}（点击切换）"),
    ("zh-CN", "ai_default", "默认"),
    ("zh-CN", "ai_custom", "自定义"),
    ("zh-CN", "ai_balanced", "均衡"),
    ("zh-CN", "ai_melee", "近战"),
    ("zh-CN", "ai_caster", "法术"),
    ("zh-CN", "ai_guardian", "守护"),
    ("zh-CN", "ai_aggressive", "激进"),
    // ---- 繁體中文 ----
    ("zh-TW", "root", "戰友（{count}/{n}）"),
    ("zh-TW", "count_row", "隊伍人數：{count}（點擊切換）"),
    ("zh-TW", "slot", "{i}號位：{name}（點擊切換）"),
    ("zh-TW", "resummon", "立即重新召喚"),
    ("zh-TW", "friendly_fire_on", "友傷：開（{rate}%，點擊關閉）"),
    ("zh-TW", "friendly_fire_off", "友傷：關（點擊開啟）"),
    ("zh-TW", "back", "返回"),
    ("zh-TW", "count_none", "不召喚"),
    ("zh-TW", "count_n", "{count} 人"),
    ("zh-TW", "profile", "{name}  Lv{level}"),
    ("zh-TW", "ai_menu", "隊友 AI（點擊進入）"),
    ("zh-TW", "ai_slot", "{i}號位 {name}：{preset}（點擊切換）"),
    ("zh-TW", "ai_default", "預設"),
    ("zh-TW", "ai_custom", "自訂"),
    ("zh-TW", "ai_balanced", "均衡"),
    ("zh-TW", "ai_melee", "近戰"),
    ("zh-TW", "ai_caster", "法術"),
    ("zh-TW", "ai_guardian", "守護"),
    ("zh-TW", "ai_aggressive", "激進"),
    // ---- English ----
    ("en", "root", "Comrades ({count}/{n})"),
    ("en", "count_row", "Party size: {count} (click to change)"),
    ("en", "slot", "Slot {i}: {name} (click to change)"),
    ("en", "resummon", "Resummon now"),
    ("en", "friendly_fire_on", "Friendly fire: ON ({rate}% damage, click to disable)"),
    ("en", "friendly_fire_off", "Friendly fire: OFF (click to enable)"),
    ("en", "back", "Back"),
    ("en", "count_none", "Don't summon"),
    ("en", "count_n", "{count} party member(s)"),
    ("en", "profile", "{name}  Lv{level}"),
    ("en", "ai_menu", "Companion AI (click to open)"),
    ("en", "ai_slot", "Slot {i} {name}: {preset} (click to change)"),
    ("en", "ai_default", "Default"),
    ("en", "ai_custom", "Custom"),
    ("en", "ai_balanced", "Balanced"),
    ("en", "ai_melee", "Melee"),
    ("en", "ai_caster", "Caster"),
    ("en", "ai_guardian", "Guardian"),
    ("en", "ai_aggressive", "Aggressive"),
    // ---- 日本語 ----
    ("ja", "root", "戦友（{count}/{n}）"),
    ("ja", "count_row", "人数：{count}（クリックで変更）"),
    ("ja", "slot", "{i}番：{name}（クリックで変更）"),
    ("ja", "resummon", "いますぐ再召喚"),
    ("ja", "friendly_fire_on", "同士討ち：オン（{rate}%ダメージ，クリックで解除）"),
    ("ja", "friendly_fire_off", "同士討ち：オフ（クリックで有効）"),
    ("ja", "back", "戻る"),
    ("ja", "count_none", "召喚しない"),
    ("ja", "count_n", "{count} 人"),
    ("ja", "profile", "{name}  Lv{level}"),
    ("ja", "ai_menu", "戦友 AI（クリックで開く）"),
    ("ja", "ai_slot", "{i}番 {name}：{preset}（クリックで変更）"),
    ("ja", "ai_default", "既定"),
    ("ja", "ai_custom", "カスタム"),
    ("ja", "ai_balanced", "バランス"),
    ("ja", "ai_melee", "近接"),
    ("ja", "ai_caster", "魔法"),
    ("ja", "ai_guardian", "守護"),
    ("ja", "ai_aggressive", "積極"),
];

fn builtin(code: &str, key: &str) -> Option<&'static str> {
    TABLE
        .iter()
        .find(|(lang, k, _)| *lang == code && *k == key)
        .map(|(_, _, text)| *text)
}

/// 取一条文案：外部覆盖 → 当前语言内置 → 英文内置 → key 本身。
pub fn text(key: &str, args: &[(&str, &str)]) -> String {
    let code = current();
    let template = match override_for(&code, key) {
        Some(custom) => custom,
        None => builtin(&code, key)
            .or_else(|| builtin("en", key))
            .unwrap_or(key)
            .to_string(),
    };
    render(&template, args)
}

/// 把模板里的 `{name}` 换成实参；不认识的占位符原样保留（方便发现拼写错误）。
fn render(template: &str, args: &[(&str, &str)]) -> String {
    if !template.contains('{') {
        return template.to_string();
    }
    let mut out = String::with_capacity(template.len() + 16);
    let mut rest = template;
    while let Some(open) = rest.find('{') {
        out.push_str(&rest[..open]);
        let after = &rest[open + 1..];
        let Some(close) = after.find('}') else {
            out.push('{');
            rest = after;
            continue;
        };
        let name = &after[..close];
        match args.iter().find(|(k, _)| *k == name) {
            Some((_, value)) => out.push_str(value),
            None => {
                out.push('{');
                out.push_str(name);
                out.push('}');
            }
        }
        rest = &after[close + 1..];
    }
    out.push_str(rest);
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn render_replaces_named_args() {
        let got = render("战友（{count}/{n}）", &[("count", "2"), ("n", "3")]);
        assert_eq!(got, "战友（2/3）");
    }

    #[test]
    fn render_keeps_unknown_placeholder() {
        assert_eq!(render("hi {who}", &[]), "hi {who}");
    }

    #[test]
    fn render_without_placeholder_is_unchanged() {
        assert_eq!(render("返回", &[("x", "1")]), "返回");
    }

    #[test]
    fn canonical_accepts_common_aliases() {
        assert_eq!(canonical_code("auto"), None);
        assert_eq!(canonical_code(""), None);
        assert_eq!(canonical_code("zh_CN").as_deref(), Some("zh-CN"));
        assert_eq!(canonical_code("CHS").as_deref(), Some("zh-CN"));
        assert_eq!(canonical_code("zh-Hant").as_deref(), Some("zh-TW"));
        assert_eq!(canonical_code("en-US").as_deref(), Some("en"));
        assert_eq!(canonical_code("jp").as_deref(), Some("ja"));
        assert_eq!(canonical_code("ko").as_deref(), Some("ko"));
        assert_eq!(canonical_code("bad lang!").as_deref(), Some("en"));
    }

    #[test]
    fn game_spec_aliases_are_recognised() {
        for spec in ["game", " GAME ", "steam", "follow", "game-language"] {
            assert!(is_game_spec(spec), "{spec} 应识别为 game 模式");
        }
        for spec in ["auto", "zh-CN", "en", "", "gamers"] {
            assert!(!is_game_spec(spec), "{spec} 不应识别为 game 模式");
        }
    }

    #[test]
    fn steam_language_names_map_to_codes() {
        assert_eq!(steam_name_to_code("schinese").as_deref(), Some("zh-CN"));
        assert_eq!(steam_name_to_code("tchinese").as_deref(), Some("zh-TW"));
        assert_eq!(steam_name_to_code("english").as_deref(), Some("en"));
        assert_eq!(steam_name_to_code("japanese").as_deref(), Some("ja"));
        assert_eq!(steam_name_to_code("brazilian").as_deref(), Some("pt-BR"));
        assert_eq!(steam_name_to_code("klingon"), None);
    }

    #[test]
    fn language_value_rejects_auto_and_junk() {
        assert_eq!(language_value("schinese").as_deref(), Some("zh-CN"));
        assert_eq!(language_value("zh_TW").as_deref(), Some("zh-TW"));
        assert_eq!(language_value("auto"), None);
        assert_eq!(language_value(""), None);
        assert_eq!(language_value("bad lang!"), None);
    }

    #[test]
    fn manifest_prefers_user_config_then_mounted() {
        let both = "\"AppState\"\n{\n\t\"UserConfig\"\n\t{\n\t\t\"language\"\t\t\"schinese\"\n\t}\n\t\"MountedConfig\"\n\t{\n\t\t\"language\"\t\t\"tchinese\"\n\t}\n}\n";
        assert_eq!(manifest_language(both).as_deref(), Some("zh-CN"));

        let mounted_only = "\"AppState\"\n{\n\t\"MountedConfig\"\n\t{\n\t\t\"language\"\t\t\"japanese\"\n\t}\n}\n";
        assert_eq!(manifest_language(mounted_only).as_deref(), Some("ja"));
        assert_eq!(manifest_language("\"AppState\"\n{\n}\n"), None);
    }

    #[test]
    fn emu_config_reads_language_line() {
        assert_eq!(
            language_from_config_text("[user::general]\nlanguage=schinese\n").as_deref(),
            Some("zh-CN")
        );
        assert_eq!(
            language_from_config_text("language = zh_TW\n").as_deref(),
            Some("zh-TW")
        );
        // 模拟器里写 auto 等于没选，不能当成英文
        assert_eq!(language_from_config_text("language=auto\n"), None);
    }

    #[test]
    fn game_detection_reports_a_known_source() {
        let (code, source) = detect_game_initial();
        assert!(!code.is_empty(), "game 模式必须给出一个代码");
        assert!(
            ["steam", "manifest", "goldberg", "windows"].contains(&source),
            "unexpected language source {source}"
        );
    }    #[test]
    fn text_assembles_for_each_builtin_language() {
        let cases = [
            ("zh-CN", "战友（2/3）"),
            ("zh-TW", "戰友（2/3）"),
            ("en", "Comrades (2/3)"),
            ("ja", "戦友（2/3）"),
        ];
        for (code, expected) in cases {
            configure(code);
            assert_eq!(text("root", &[("count", "2"), ("n", "3")]), expected);
            assert_eq!(text("back", &[]), text("back", &[]));
        }
    }

    #[test]
    fn parse_overrides_handles_sections_and_comments() {
        let map = parse_overrides(
            "\u{feff}; 注释\n[ko]\nroot=동료 ({count}/{n})\n\n# 另一个注释\n[en]\nback = Back\nmath=1+1=2\n",
        );
        assert_eq!(map.get("ko\u{1}root").map(String::as_str), Some("동료 ({count}/{n})"));
        assert_eq!(map.get("en\u{1}back").map(String::as_str), Some("Back"));
        assert_eq!(map.get("en\u{1}math").map(String::as_str), Some("1+1=2"));
    }

    #[test]
    fn parse_overrides_normalizes_section_codes() {
        let map = parse_overrides("[zh_CN]\nback=返回\n");
        assert!(map.contains_key("zh-CN\u{1}back"));
    }

    #[test]
    fn every_builtin_language_covers_every_key() {
        let keys = [
            "root",
            "count_row",
            "slot",
            "resummon",
            "friendly_fire_on",
            "friendly_fire_off",
            "back",
            "count_none",
            "count_n",
            "profile",
            "ai_menu",
            "ai_slot",
            "ai_default",
            "ai_custom",
            "ai_balanced",
            "ai_melee",
            "ai_caster",
            "ai_guardian",
            "ai_aggressive",
        ];
        for lang in BUILTIN_LANGS {
            for key in keys {
                assert!(
                    builtin(lang, key).is_some(),
                    "missing {lang}/{key}"
                );
            }
        }
    }
}
