//! 篝火菜单的队伍配置（人数 + 出场名单）。
//!
//! 菜单本身是原生 ESD（`t000001000` 的赐福对话菜单），它只负责把选择写成
//! 事件标志；这里保存配置、把「第 i 个克隆体用哪个档案」算出来，并把人数
//! 落到 `BuddyParam.trigger_sp_effect_id` 上（= 让第 4 个以后的行不再被召唤）。

use fromsoftware_shared::FromStatic;
use serde::{Deserialize, Serialize};
use std::sync::Mutex;

pub const MAX_SLOTS: usize = 3;
const ROSTER_FILE: &str = "er_echo_roster.json";

/// 菜单 → DLL 的事件标志（ESD 只置位，DLL 读完立刻清零）。
///
/// 必须用**真实存在的事件标志组**：`CSEventFlagMan` 只认识
/// `flag_block_descriptors` 里有的 group（group = id / 1000）。
/// 之前用的 69031xxx（group 69031）超出范围，`set/get` 静默失败，
/// 菜单点了等于没点。6700 段是社区常用的自定义菜单标志（Chat-with-Melina
/// 用 6700-6703），这里取 6720-6727。
pub const FLAG_COUNT_0: u32 = 6720;
pub const FLAG_COUNT_1: u32 = 6721;
pub const FLAG_COUNT_2: u32 = 6722;
pub const FLAG_COUNT_3: u32 = 6723;
pub const FLAG_SLOT_0: u32 = 6724;
pub const FLAG_SLOT_1: u32 = 6725;
pub const FLAG_SLOT_2: u32 = 6726;
pub const FLAG_SLOT: [u32; MAX_SLOTS] = [FLAG_SLOT_0, FLAG_SLOT_1, FLAG_SLOT_2];
pub const FLAG_APPLY: u32 = 6727;
/// 赐福列表里的「队伍人数」项：点一次 0→1→2→3→0。
pub const FLAG_COUNT_CYCLE: u32 = 6728;
/// 「友伤」开关项：点一次开/关。
pub const FLAG_FRIENDLY_FIRE: u32 = 6729;
/// 三级菜单「队友 AI」：1/2/3 号位各一个，点一次切到下一个预设。
pub const FLAG_AI_SLOT: [u32; MAX_SLOTS] = [6730, 6731, 6732];

pub const ALL_FLAGS: [u32; 13] = [
    FLAG_COUNT_0,
    FLAG_COUNT_1,
    FLAG_COUNT_2,
    FLAG_COUNT_3,
    FLAG_SLOT[0],
    FLAG_SLOT[1],
    FLAG_SLOT[2],
    FLAG_APPLY,
    FLAG_COUNT_CYCLE,
    FLAG_FRIENDLY_FIRE,
    FLAG_AI_SLOT[0],
    FLAG_AI_SLOT[1],
    FLAG_AI_SLOT[2],
];

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Roster {
    pub v: u32,
    /// 出场人数 0..=3（0 = 不召唤）
    pub count: u8,
    /// 每个位置用 `CLONE_PROFILES` 里的第几个档案；-1 = 空
    pub slots: [i32; MAX_SLOTS],
    /// 玩家与同伴互相能打中（赐福菜单「友伤」项，持久化到这里）
    #[serde(default)]
    pub friendly_fire: bool,
}

impl Default for Roster {
    fn default() -> Self {
        Self {
            v: 1,
            count: 0,
            slots: [-1; MAX_SLOTS],
            friendly_fire: false,
        }
    }
}

static ROSTER: Mutex<Option<Roster>> = Mutex::new(None);

fn normalize(mut r: Roster, profile_count: usize) -> Roster {
    r.v = 1;
    r.count = r.count.min(MAX_SLOTS as u8);
    for slot in &mut r.slots {
        if *slot < 0 || *slot as usize >= profile_count {
            *slot = -1;
        }
    }
    // 默认把前 count 个位置填上档案，避免菜单里全是「—」
    if profile_count > 0 {
        for i in 0..r.count as usize {
            if r.slots[i] < 0 {
                r.slots[i] = i.min(profile_count - 1) as i32;
            }
        }
    }
    r
}

/// 读 roster，同时告诉调用方「文件里有没有写过 `friendly_fire`」。
///
/// 旧版本的 `er_echo_roster.json` 没有这个字段；这时应该用 ini 里的默认值，
/// 而不是把 serde 的 `false` 当成玩家显式关掉了友伤。
fn load_file_with_meta() -> Option<(Roster, bool)> {
    let text = std::fs::read_to_string(ROSTER_FILE).ok()?;
    let value: serde_json::Value = serde_json::from_str(&text).ok()?;
    let has_field = value.get("friendly_fire").is_some();
    let roster = serde_json::from_value(value).ok()?;
    Some((roster, has_field))
}

pub fn save_file(r: &Roster) {
    if let Ok(text) = serde_json::to_string_pretty(r) {
        let _ = std::fs::write(ROSTER_FILE, text);
    }
}

/// 启动时初始化：有 `er_echo_roster.json` 就用它，否则按 ini 档案数生成默认值。
///
/// `default_friendly_fire` 只在**没有 roster 文件**或旧文件里没有该字段时生效；
/// 文件里已有开关状态时以文件为准（玩家在赐福菜单里点过的状态不会被 ini 每次启动覆盖）。
pub fn init(profile_count: usize, default_friendly_fire: bool) -> Roster {
    let loaded = load_file_with_meta();
    let has_friendly_field = loaded.as_ref().map(|(_, has)| *has).unwrap_or(false);
    let mut r = loaded.map(|(r, _)| r).unwrap_or_else(|| Roster {
        v: 1,
        count: profile_count.min(MAX_SLOTS) as u8,
        slots: [0, if profile_count > 1 { 1 } else { 0 }, if profile_count > 2 { 2 } else { 0 }],
        friendly_fire: default_friendly_fire,
    });
    if !has_friendly_field {
        // 老 roster 文件没有这个字段：用 ini 的默认值补上并写回。
        r.friendly_fire = default_friendly_fire;
    }
    r = normalize(r, profile_count);
    save_file(&r);
    if let Ok(mut g) = ROSTER.lock() {
        *g = Some(r.clone());
    }
    log::info!(
        "roster: count={} slots={:?} friendly_fire={} (profiles={profile_count})",
        r.count,
        r.slots,
        r.friendly_fire
    );
    r
}

pub fn get() -> Roster {
    ROSTER
        .lock()
        .ok()
        .and_then(|g| g.clone())
        .unwrap_or_default()
}

pub fn set_count(count: u8, profile_count: usize) {
    let mut r = get();
    r.count = count.min(MAX_SLOTS as u8);
    r = normalize(r, profile_count);
    save_file(&r);
    if let Ok(mut g) = ROSTER.lock() {
        *g = Some(r.clone());
    }
    log::info!("roster: count -> {} (slots={:?})", r.count, r.slots);
}

pub fn cycle_slot(slot: usize, profile_count: usize) -> i32 {
    if slot >= MAX_SLOTS || profile_count == 0 {
        return -1;
    }
    let mut r = get();
    let cur = r.slots[slot];
    let next = if cur < 0 || cur as usize + 1 >= profile_count {
        0
    } else {
        cur + 1
    };
    r.slots[slot] = next;
    save_file(&r);
    if let Ok(mut g) = ROSTER.lock() {
        *g = Some(r.clone());
    }
    log::info!("roster: slot {} -> profile {} (slots={:?})", slot + 1, next, r.slots);
    next
}

/// 赐福菜单「友伤」项：翻转开关并持久化，返回新状态。
pub fn toggle_friendly_fire() -> bool {
    let mut r = get();
    r.friendly_fire = !r.friendly_fire;
    save_file(&r);
    if let Ok(mut g) = ROSTER.lock() {
        *g = Some(r.clone());
    }
    log::info!("roster: friendly_fire -> {}", r.friendly_fire);
    r.friendly_fire
}

/// 显式设置友伤开关（IPC 用），持久化。
pub fn set_friendly_fire(on: bool) {
    let mut r = get();
    if r.friendly_fire == on {
        return;
    }
    r.friendly_fire = on;
    save_file(&r);
    if let Ok(mut g) = ROSTER.lock() {
        *g = Some(r.clone());
    }
    log::info!("roster: friendly_fire -> {on}");
}

/// 第 `i` 个克隆体用哪个档案（`-1` = 没有可用档案）。
pub fn slot_for_clone(i: usize, profile_count: usize) -> i32 {
    if profile_count == 0 {
        return -1;
    }
    let r = get();
    if i >= r.count as usize {
        return -1;
    }
    let slot = r.slots[i.min(MAX_SLOTS - 1)];
    if slot < 0 {
        (i % profile_count) as i32
    } else {
        (slot as usize % profile_count) as i32
    }
}

/// 当前实际要召唤几个。
pub fn active_count(profile_count: usize) -> usize {
    if profile_count == 0 {
        return 0;
    }
    (get().count as usize).min(MAX_SLOTS)
}

/// 清除菜单标志（上一局崩溃可能留下置位的标志）。
pub unsafe fn clear_flags() {
    if let Ok(man) = eldenring::cs::CSEventFlagMan::instance_mut() {
        for flag in ALL_FLAGS {
            man.virtual_memory_flag.set_flag(flag, false);
        }
    }
}

/// 有任意一个菜单标志被置位 → 返回它（并清零）。
pub unsafe fn take_flag() -> Option<u32> {
    let man = eldenring::cs::CSEventFlagMan::instance_mut().ok()?;
    for flag in ALL_FLAGS {
        if man.virtual_memory_flag.get_flag(flag) {
            man.virtual_memory_flag.set_flag(flag, false);
            return Some(flag);
        }
    }
    None
}
