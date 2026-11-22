//! 游戏内可见文字的本地化（赐福菜单那几行）。
//!
//! 整个 mod 里真正显示在游戏里的字符串只有 `ui.rs` 的菜单文案，所以这里做的不是
//! 通用 i18n 框架，而是「模板表 + 命名占位符」：
//!
//! * 内置 `zh-CN` / `zh-TW` / `en` / `ja`；缺键一律回退 `en`，再缺就原样返回 key；
//! * `er_echo_i18n.ini`（游戏根目录，可选）可以覆盖内置文案，也可以新增语言，
//!   新增语言只要在 `er_echo.ini` 里写 `[i18n] language=ko` 就行；
//! * `language=auto`（默认）读 Windows 显示语言，认不出来用英文。
//!
//! 为什么不用游戏自己的语言设置：`CSMsgRepository` 的查找函数只在菜单打开时才被
//! 调用，而且传进来的 `lang` 索引没有公开的 0..n → 语言名映射；Windows 显示语言
//! 是最稳的近似值，实在不准就让玩家显式写 `language=`。
//!
//! 注意：文字最终由游戏的字体图集渲染，**菜单语言最好和游戏文本语言一致**，
//! 否则可能出现方块（游戏只加载当前语言的字体）。

use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

/// 可选的外部翻译文件（相对游戏根目录，或 DLL 同目录）。
pub const OVERRIDE_FILE: &str = "er_echo_i18n.ini";

/// 覆盖文件的实际路径：DLL 同目录优先，其次 CWD。
pub fn override_path() -> std::path::PathBuf {
    crate::data_file(OVERRIDE_FILE)
}

/// 内置语言代码。顺序无关，仅用于文档/日志。
pub const BUILTIN_LANGS: &[&str] = &["zh-CN", "zh-TW", "en", "ja"];

/// 当前语言代码；`None` = 还没 `configure`，按 auto 现算。
static LANG: Mutex<Option<String>> = Mutex::new(None);
/// `"<lang>\u{1}<key>"` → 文案。
static OVERRIDES: OnceLock<HashMap<String, String>> = OnceLock::new();

#[link(name = "kernel32")]
unsafe extern "system" {
    fn GetUserDefaultUILanguage() -> u16;
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

/// 设置语言（`auto` / `zh-CN` / `en` / 自定义）。返回实际生效的语言代码。
pub fn configure(spec: &str) -> String {
    let code = canonical_code(spec).unwrap_or_else(detect_os);
    if let Ok(mut g) = LANG.lock() {
        *g = Some(code.clone());
    }
    // 预热覆盖表：没有文件也是一次空表，之后不再碰磁盘。
    let _ = OVERRIDES.get_or_init(load_overrides);
    code
}

/// 当前生效的语言代码。
pub fn current() -> String {
    if let Some(code) = LANG.lock().ok().and_then(|g| g.clone()) {
        return code;
    }
    let code = detect_os();
    if let Ok(mut g) = LANG.lock() {
        *g = Some(code.clone());
    }
    code
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
