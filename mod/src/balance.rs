//! 战友模式：按当前出场的战友人数补正**敌人**的生命值上限。
//!
//! 规则（默认，`[balance] enemy_hp_rates=` 可改）：
//!
//! | 战友人数 | 敌人生命上限 |
//! |---|---|
//! | 0 | ×1.0（不补正） |
//! | 1 | ×1.5 |
//! | 2 | ×1.8 |
//! | 3 | ×2.0 |
//!
//! ## 为什么改 `CSChrDataModule`，不改 `NpcParam`
//!
//! `NpcParam.hp` 只在**生成时**读一次。玩家通常是在 Boss 房里（Boss 已经生成）
//! 才用骨灰召唤战友的，改 param 行影响不到场上的 Boss；而且 `NpcParam.hp` 是
//! `i16`，后期 Boss 翻倍会溢出。这里直接改角色自己的
//! `CSChrDataModule { hp, max_hp, max_uncapped_hp, base_hp }`：
//!
//! * `max_hp` 是血条/受击/死亡判定读的值；
//! * `base_hp` 一并按倍率写，这样引擎因 spEffect/阶段变化重算上限时仍然带着倍率；
//! * `hp` 在**倍率变化时**按当前百分比缩放（满血 Boss 补正后仍满血，半血仍半血）。
//!
//! 每 15 帧重新钉一次；引擎若在两次之间把上限改回去（阶段切换 / 重新读档），
//! 下一次 tick 会检测到并重新补正。战友全收起 / 功能关闭时按当前血量百分比写回
//! 原始值（不会借机回血）。

use eldenring::cs::{CSChrDataModule, ChrIns, FieldInsHandle, PlayerIns, WorldChrMan};
use fromsoftware_shared::Superclass;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::atomic::{AtomicBool, AtomicU32, AtomicU64, Ordering};
use std::sync::{Mutex, OnceLock};

/// 战友人数上限（和 `roster::MAX_SLOTS` / 骨灰载体行数一致）。
pub const MAX_COMRADES: usize = 3;

/// 默认倍率：1 / 2 / 3 号位战友。
pub const DEFAULT_RATES: [f32; MAX_COMRADES] = [1.5, 1.8, 2.0];

static ENABLED: AtomicBool = AtomicBool::new(true);
static RATES: Mutex<[f32; MAX_COMRADES]> = Mutex::new(DEFAULT_RATES);
/// 上一次 tick 的战友人数 / 倍率（只在变化时打日志）。
static LAST_COUNT: AtomicU32 = AtomicU32::new(u32::MAX);
static LAST_MULT_BITS: AtomicU32 = AtomicU32::new(1.0f32.to_bits());
static LAST_APPLY_FRAME: AtomicU64 = AtomicU64::new(0);
static APPLIED_TOTAL: AtomicU64 = AtomicU64::new(0);
static RESTORED_TOTAL: AtomicU64 = AtomicU64::new(0);

/// 一个角色的 HP 四件套（读出来 / 写回去都用它）。
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct HpSnapshot {
    hp: i32,
    max_hp: i32,
    max_uncapped_hp: i32,
    base_hp: i32,
}

impl HpSnapshot {
    fn read(data: &CSChrDataModule) -> Self {
        HpSnapshot {
            hp: data.hp,
            max_hp: data.max_hp,
            max_uncapped_hp: data.max_uncapped_hp,
            base_hp: data.base_hp,
        }
    }

    fn write(&self, data: &mut CSChrDataModule) {
        data.max_hp = self.max_hp;
        data.max_uncapped_hp = self.max_uncapped_hp;
        data.base_hp = self.base_hp;
        data.hp = self.hp.clamp(0, data.max_hp.max(0));
    }
}

/// 跟踪状态：原始值 + 我们写进去的值 + 当时用的倍率。
#[derive(Clone, Copy, Debug)]
struct Tracked {
    /// 第一次看到它时的原始值（未补正）。
    baseline: HpSnapshot,
    /// 上一次实际写进去的值（检测引擎有没有覆盖）。
    applied: HpSnapshot,
    scale: f32,
    /// 最后一次在 chr_sets 里看到它的帧（清理用）。
    last_seen: u64,
}

/// 用 `FieldInsHandle + npc + character_id` 当键：世界重载后即使地址复用，
/// 至少 npc / character_id 对不上时不会误写。
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
struct Key {
    handle: FieldInsHandle,
    npc: i32,
    character: u32,
}

fn tracked() -> &'static Mutex<HashMap<Key, Tracked>> {
    static TRACKED: OnceLock<Mutex<HashMap<Key, Tracked>>> = OnceLock::new();
    TRACKED.get_or_init(|| Mutex::new(HashMap::new()))
}

// ---------------------------------------------------------------- 配置

pub fn enabled() -> bool {
    ENABLED.load(Ordering::Acquire)
}

pub fn set_enabled(on: bool) {
    ENABLED.store(on, Ordering::Release);
}

pub fn rates() -> [f32; MAX_COMRADES] {
    RATES.lock().map(|g| *g).unwrap_or(DEFAULT_RATES)
}

/// 上一次 tick 统计到的活战友数（只用于状态显示；还没跑过 tick 时是 0）。
pub fn last_count() -> usize {
    match LAST_COUNT.load(Ordering::Relaxed) {
        u32::MAX => 0,
        v => v as usize,
    }
}

/// 设置 1/2/3 人倍率；不足 3 个用当前值补齐，返回 clamp 后的实际值。
///
/// 倍率限制在 `0.1..=20.0`：`1.0` 以下也允许（调试/做「战友模式反而简单」的实验），
/// 但默认是只加不减。
pub fn set_rates(values: &[f32]) -> [f32; MAX_COMRADES] {
    let mut out = rates();
    for (dst, src) in out.iter_mut().zip(values.iter()) {
        if src.is_finite() {
            *dst = src.clamp(0.1, 20.0);
        }
    }
    if let Ok(mut g) = RATES.lock() {
        *g = out;
    }
    out
}

/// 当前战友人数对应的敌人生命倍率。
pub fn multiplier_for(count: usize) -> f32 {
    if count == 0 {
        return 1.0;
    }
    rates()[count.min(MAX_COMRADES) - 1]
}

fn desired_multiplier(count: usize) -> f32 {
    if enabled() {
        multiplier_for(count)
    } else {
        1.0
    }
}

// ---------------------------------------------------------------- 数值计算

fn scale_int(value: i32, scale: f32) -> i32 {
    if value <= 0 {
        return value;
    }
    (value as f64 * scale as f64)
        .round()
        .clamp(1.0, i32::MAX as f64) as i32
}

/// 按 `baseline` 计算补正后的四件套；`current` 只用来取“现在剩的百分比”。
fn scaled(baseline: &HpSnapshot, scale: f32, current: &HpSnapshot) -> HpSnapshot {
    let max_hp = scale_int(baseline.max_hp, scale).max(1);
    let uncapped_base = baseline.max_uncapped_hp.max(baseline.max_hp);
    let ratio = if current.max_hp > 0 {
        (current.hp as f64 / current.max_hp as f64).clamp(0.0, 1.0)
    } else {
        1.0
    };
    HpSnapshot {
        hp: (ratio * max_hp as f64).round().clamp(0.0, max_hp as f64) as i32,
        max_hp,
        max_uncapped_hp: scale_int(uncapped_base, scale).max(max_hp),
        base_hp: scale_int(baseline.base_hp, scale).max(0),
    }
}

/// 还原：把当前 HP 百分比投回原始上限（不能直接 min(current_hp, 原上限)，
/// 否则 80% 血的敌人在收起战友时会被“治疗”到 100%）。
fn restore_snapshot(baseline: &HpSnapshot, current: &HpSnapshot) -> HpSnapshot {
    let ratio = if current.max_hp > 0 {
        (current.hp as f64 / current.max_hp as f64).clamp(0.0, 1.0)
    } else {
        0.0
    };
    HpSnapshot {
        hp: (ratio * baseline.max_hp as f64).round() as i32,
        ..*baseline
    }
}

/// 整数近似相等（引擎重算可能差 1 点）。
fn close_int(a: i32, b: i32) -> bool {
    if a == b {
        return true;
    }
    let tolerance = (a.abs().max(b.abs()) / 100).max(1);
    (a - b).abs() <= tolerance
}

fn close_f32(a: f32, b: f32) -> bool {
    (a - b).abs() <= 0.001
}

// ---------------------------------------------------------------- 角色筛选

fn key_of(chr: &ChrIns) -> Key {
    Key {
        handle: chr.field_ins_handle,
        npc: chr.npc_param_id,
        character: chr.character_id,
    }
}

/// 只看敌对 NPC：跳过玩家/中立/同伴队伍、我们自己的克隆体、以及 PlayerIns
/// （入侵者/其他玩家的 HP 在 `PlayerGameData` 里，不在 `CSChrDataModule`）。
fn is_target(chr: &ChrIns, player_team: u8) -> bool {
    if matches!(chr.team_type, 0 | 1 | 47) || chr.team_type == player_team {
        return false;
    }
    if chr.npc_param_id <= 0 {
        return false;
    }
    if crate::spirit::CLONE_NPCS.contains(&(chr.npc_param_id as u32)) {
        return false;
    }
    // 不碰 PlayerIns：它们是入侵者/其他玩家（以及变身中的克隆体），
    // 上限由 PlayerGameData 每帧重算，写 data_module 没有意义。
    if chr.as_subclass::<PlayerIns>().is_some() {
        return false;
    }
    true
}

/// 取 `chr.modules.data`，并对裸指针判空（读档瞬间模块可能还没建好）。
fn data_mut(chr: &mut ChrIns) -> Option<&mut CSChrDataModule> {
    let modules = chr.modules.as_ptr();
    if modules.is_null() {
        return None;
    }
    let data = unsafe { (*modules).data.as_ptr() };
    if data.is_null() {
        return None;
    }
    Some(unsafe { &mut *data })
}

fn data_ref(chr: &ChrIns) -> Option<&CSChrDataModule> {
    let modules = chr.modules.as_ptr();
    if modules.is_null() {
        return None;
    }
    let data = unsafe { (*modules).data.as_ptr() };
    if data.is_null() {
        return None;
    }
    Some(unsafe { &*data })
}

/// 当前**活着**的战友数量（同伴队伍 + 拟态 NPC，排除已经倒下的）。
fn alive_comrades(world: &mut WorldChrMan) -> usize {
    world
        .summon_buddy_chr_set
        .characters()
        .filter(|chr| crate::spirit::is_clone(chr))
        .filter(|chr| match chr.as_subclass::<PlayerIns>() {
            Some(p) => unsafe { p.player_game_data.as_ref() }.current_hp > 0,
            None => true,
        })
        .count()
}

// ---------------------------------------------------------------- 主循环

/// 每 15 帧调用一次：按战友人数补正场上所有敌人的 HP 上限，并处理还原。
pub fn tick(world: &mut WorldChrMan) {
    let count = alive_comrades(world);
    let desired = desired_multiplier(count);
    let frame = crate::frame();

    let prev_count = LAST_COUNT.swap(count as u32, Ordering::Relaxed);
    let prev_mult = f32::from_bits(LAST_MULT_BITS.swap(desired.to_bits(), Ordering::Relaxed));
    if prev_count != u32::MAX && (prev_count != count as u32 || !close_f32(prev_mult, desired)) {
        log::info!(
            "enemy_hp: comrades {} -> {count}, enemy max HP x{prev_mult:.2} -> x{desired:.2}",
            if prev_count == u32::MAX {
                0
            } else {
                prev_count
            }
        );
    }

    let Ok(mut map) = tracked().lock() else {
        return;
    };
    let player_team = world
        .main_player
        .as_ref()
        .map(|p| p.chr_ins.team_type)
        .unwrap_or(1);
    let restoring = close_f32(desired, 1.0);
    let mut applied = 0usize;
    let mut restored = 0usize;
    let mut seen = 0usize;

    for set in world.chr_sets.iter_mut() {
        let Some(set) = set.as_mut() else { continue };
        for chr in set.characters() {
            if !is_target(chr, player_team) {
                continue;
            }
            let key = key_of(chr);
            let Some(data) = data_mut(chr) else { continue };
            let current = HpSnapshot::read(data);
            seen += 1;

            if restoring {
                // 收起战友 / 关功能：还原我们改过的值。只还原“还是我们写的那组数”的角色；
                // 引擎中途换过阶段/重算过就不要再按旧 baseline 写回去。
                if let Some(state) = map.remove(&key) {
                    let still_ours = if state.applied.base_hp > 0 {
                        close_int(current.base_hp, state.applied.base_hp)
                    } else {
                        // 有些行 base_hp 是 0（引擎不用它），改看 max_hp。
                        close_int(current.max_hp, state.applied.max_hp)
                    };
                    if still_ours {
                        restore_snapshot(&state.baseline, &current).write(data);
                        restored += 1;
                    }
                }
                continue;
            }

            if current.hp <= 0 || current.max_hp <= 0 {
                continue;
            }

            match map.get_mut(&key) {
                None => {
                    let next = scaled(&current, desired, &current);
                    next.write(data);
                    map.insert(
                        key,
                        Tracked {
                            baseline: current,
                            applied: next,
                            scale: desired,
                            last_seen: frame,
                        },
                    );
                    applied += 1;
                }
                Some(state) => {
                    if !close_f32(state.scale, desired) {
                        // 人数变了：按当前血量百分比换算到新上限（满血仍满血）。
                        let next = scaled(&state.baseline, desired, &current);
                        next.write(data);
                        state.applied = next;
                        state.scale = desired;
                        state.last_seen = frame;
                        applied += 1;
                    } else if !close_int(current.max_hp, state.applied.max_hp) {
                        if state.applied.base_hp == 0 {
                            // base_hp 不可用（有些行是 0）：没有“引擎用的是原始 base
                            // 还是我们改过的 base”这个信号，只能按原始值重钉一次。
                            let next = scaled(&state.baseline, desired, &current);
                            next.write(data);
                            state.applied = next;
                            state.last_seen = frame;
                            applied += 1;
                        } else if close_int(current.base_hp, state.baseline.base_hp) {
                            // 引擎把上限写回了原值：重新补正（保留当前百分比）。
                            let next = scaled(&state.baseline, desired, &current);
                            next.write(data);
                            state.applied = next;
                            state.last_seen = frame;
                            applied += 1;
                        } else if close_int(current.base_hp, state.applied.base_hp) {
                            // 引擎基于我们改过的 base 重算了上限（比如挂了个 +10% 的
                            // spEffect）：接受它的新上限，别再乘一次。
                            state.applied.max_hp = current.max_hp;
                            state.applied.max_uncapped_hp = current.max_uncapped_hp;
                            state.applied.hp = current.hp;
                            state.last_seen = frame;
                        } else {
                            // 阶段切换 / 换了一行 NpcParam：把当前值当成新的未补正基线。
                            let next = scaled(&current, desired, &current);
                            next.write(data);
                            state.baseline = current;
                            state.applied = next;
                            state.last_seen = frame;
                            applied += 1;
                        }
                    } else {
                        state.last_seen = frame;
                    }
                }
            }
        }
    }

    // 清理已经不在场上的角色：保留 10 秒（敌人可能暂时离开 chr_sets / 切镜头）。
    // 世界重载后即使 handle 复用也不会误写：还原前会核对 applied 那组数。
    let cutoff = frame.saturating_sub(600);
    map.retain(|_, state| state.last_seen >= cutoff);

    if applied > 0 || restored > 0 {
        LAST_APPLY_FRAME.store(frame, Ordering::Relaxed);
        APPLIED_TOTAL.fetch_add(applied as u64, Ordering::Relaxed);
        RESTORED_TOTAL.fetch_add(restored as u64, Ordering::Relaxed);
        log::debug!(
            "enemy_hp: x{desired:.2}, applied={applied}, restored={restored}, tracked={}, seen={seen}",
            map.len()
        );
    }
}

// ---------------------------------------------------------------- 诊断

/// `enemy_hp_status` 的 JSON 快照（不修改游戏状态）。
pub fn status(world: &mut WorldChrMan) -> Value {
    let count = alive_comrades(world);
    let desired = desired_multiplier(count);
    let player_pos = world
        .main_player
        .as_ref()
        .and_then(|p| crate::world_pos(&p.chr_ins));
    let player_team = world
        .main_player
        .as_ref()
        .map(|p| p.chr_ins.team_type)
        .unwrap_or(1);
    let map = tracked().lock().ok();
    let mut samples: Vec<Value> = Vec::new();
    let mut tracked_live = 0usize;
    let mut consistent_live = 0usize;

    for set in world.chr_sets.iter() {
        let Some(set) = set.as_ref() else { continue };
        for chr in set.characters() {
            if !is_target(chr, player_team) {
                continue;
            }
            let Some(data) = data_ref(chr) else { continue };
            let key = key_of(chr);
            let dist = match (player_pos, crate::world_pos(chr)) {
                (Some(a), Some(b)) => {
                    ((a.0 - b.0).powi(2) + (a.1 - b.1).powi(2) + (a.2 - b.2).powi(2)).sqrt()
                }
                _ => f32::INFINITY,
            };
            let (tracked_scale, is_tracked, consistent) =
                match map.as_ref().and_then(|m| m.get(&key)) {
                    Some(state) => {
                        tracked_live += 1;
                        let ok = close_int(data.max_hp, state.applied.max_hp)
                            && close_int(data.base_hp, state.applied.base_hp);
                        if ok {
                            consistent_live += 1;
                        }
                        (state.scale, true, ok)
                    }
                    None => (1.0, false, false),
                };
            if samples.len() < 256 {
                samples.push(json!({
                    "npc": chr.npc_param_id,
                    "npc_id": chr.npc_id,
                    "team": chr.team_type,
                    "dist": if dist.is_finite() { json!((dist * 10.0).round() / 10.0) } else { Value::Null },
                    "hp": data.hp,
                    "max_hp": data.max_hp,
                    "max_uncapped_hp": data.max_uncapped_hp,
                    "base_hp": data.base_hp,
                    "tracked": is_tracked,
                    "scale": tracked_scale,
                    "consistent": consistent,
                }));
            }
        }
    }
    samples.sort_by(|a, b| {
        let da = a["dist"].as_f64().unwrap_or(f64::MAX);
        let db = b["dist"].as_f64().unwrap_or(f64::MAX);
        da.partial_cmp(&db).unwrap_or(std::cmp::Ordering::Equal)
    });
    samples.truncate(16);

    json!({
        "enabled": enabled(),
        "rates": rates(),
        "comrades": count,
        "multiplier": desired,
        "tracked": map.as_ref().map(|m| m.len()).unwrap_or(0),
        "tracked_live": tracked_live,
        "consistent_live": consistent_live,
        "last_apply_frame": LAST_APPLY_FRAME.load(Ordering::Relaxed),
        "applied_total": APPLIED_TOTAL.load(Ordering::Relaxed),
        "restored_total": RESTORED_TOTAL.load(Ordering::Relaxed),
        "samples": samples,
    })
}

// ---------------------------------------------------------------- tests

#[cfg(test)]
mod tests {
    use super::*;

    /// 两个测试都会改全局 RATES；Rust 测试默认并行，必须串行化。
    static RATE_TEST_LOCK: Mutex<()> = Mutex::new(());

    fn snap(hp: i32, max_hp: i32, uncapped: i32, base: i32) -> HpSnapshot {
        HpSnapshot {
            hp,
            max_hp,
            max_uncapped_hp: uncapped,
            base_hp: base,
        }
    }

    #[test]
    fn multiplier_table() {
        let _guard = RATE_TEST_LOCK.lock().unwrap();
        // 默认表：0 人不变，1/2/3 人 -> 1.5/1.8/2.0，超过 3 人仍按 3 人。
        let saved = rates();
        set_rates(&DEFAULT_RATES);
        assert_eq!(multiplier_for(0), 1.0);
        assert_eq!(multiplier_for(1), 1.5);
        assert_eq!(multiplier_for(2), 1.8);
        assert_eq!(multiplier_for(3), 2.0);
        assert_eq!(multiplier_for(4), 2.0);
        set_rates(&saved);
    }

    #[test]
    fn rates_are_clamped_and_partial_rates_keep_current() {
        let _guard = RATE_TEST_LOCK.lock().unwrap();
        let saved = rates();
        set_rates(&DEFAULT_RATES);
        let out = set_rates(&[0.0, 30.0]);
        assert_eq!(out[0], 0.1);
        assert_eq!(out[1], 20.0);
        assert_eq!(out[2], 2.0, "没给的倍率沿用当前值");
        set_rates(&saved);
    }

    #[test]
    fn scaling_keeps_full_hp_full() {
        let base = snap(1000, 1000, 1000, 1000);
        let out = scaled(&base, 1.5, &base);
        assert_eq!(out.max_hp, 1500);
        assert_eq!(out.max_uncapped_hp, 1500);
        assert_eq!(out.base_hp, 1500);
        assert_eq!(out.hp, 1500);
    }

    #[test]
    fn scaling_keeps_percentage() {
        let base = snap(2000, 2000, 2000, 2000);
        let current = snap(500, 2000, 2000, 2000); // 25%
        let out = scaled(&base, 2.0, &current);
        assert_eq!(out.max_hp, 4000);
        assert_eq!(out.hp, 1000, "25% of 4000");
    }

    #[test]
    fn scaling_down_keeps_percentage() {
        let base = snap(1000, 1000, 1000, 1000);
        let current = snap(1350, 1800, 1800, 1800); // 补正到 1.8 后掉了 25%
        let out = scaled(&base, 1.5, &current);
        assert_eq!(out.max_hp, 1500);
        assert_eq!(out.hp, 1125, "75% of 1500");
    }

    #[test]
    fn restore_keeps_percentage_instead_of_healing() {
        let base = snap(1000, 1000, 1000, 1000);
        // 补正到 2.0 后仍是 80%：1200/1500。收起战友应回到 800/1000（不是 1000/1000）。
        let current = snap(1200, 1500, 1500, 1500);
        let out = restore_snapshot(&base, &current);
        assert_eq!(out.max_hp, 1000);
        assert_eq!(out.hp, 800);
    }

    #[test]
    fn zero_or_negative_values_stay_at_zero() {
        assert_eq!(scale_int(0, 2.0), 0);
        assert_eq!(scale_int(-5, 2.0), -5);
    }

    #[test]
    fn close_int_tolerates_rounding_but_not_rewrites() {
        assert!(close_int(1000, 1001));
        assert!(close_int(1000, 1010));
        assert!(!close_int(1000, 1100));
    }
}
