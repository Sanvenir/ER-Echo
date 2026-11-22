//! Param 读写：把「权重」落到真实存在的 param 行上。
//!
//! API 事实（eldenring 0.14）：
//!  - `SoloParamRepository::get_mut::<Marker>(id: u32) -> Option<&mut Marker::StructType>`；
//!    Marker 在 `eldenring::cs`（如 `NpcThinkParam`），StructType 在 `eldenring::param`
//!    （如 `NPC_THINK_PARAM_ST`），字段私有，必须用 `set_xxx()` 访问器。
//!  - `NpcAiBehaviorProbability` 对应 `NPC_AI_BEHAVIOR_PROBABILITY_PARAM_ST`，
//!    200 个 `set_param000..set_param199`。
//!  - 行 id 是**占位值**：在 Smithbox 建好 `c0000_echo_*` 后填进 `rows`。

use eldenring::cs::{
    AtkParam_Pc, BuddyParam, CharaInitParam, FaceParam, NpcAiBehaviorProbability, NpcParam,
    NpcThinkParam, SoloParam, SoloParamRepository, SpEffectParam,
};
use eldenring::param::{
    NPC_AI_BEHAVIOR_PROBABILITY_PARAM_ST, NPC_PARAM_ST, NPC_THINK_PARAM_ST, SP_EFFECT_PARAM_ST,
};
use fromsoftware_shared::FromStatic;
use std::sync::atomic::{AtomicBool, AtomicU32, AtomicUsize, Ordering};
use std::sync::Mutex;

/// 目标克隆体用的 param 行（运行时可通过 `set_rows` 命令改，不必重编译）
pub mod rows {
    use std::sync::atomic::{AtomicU32, Ordering};
    pub static BEHAVIOR: AtomicU32 = AtomicU32::new(0);
    pub static THINK: AtomicU32 = AtomicU32::new(0);
    pub static NPC: AtomicU32 = AtomicU32::new(0);

    pub fn set(behavior: u32, think: u32, npc: u32) {
        BEHAVIOR.store(behavior, Ordering::Relaxed);
        THINK.store(think, Ordering::Relaxed);
        NPC.store(npc, Ordering::Relaxed);
    }

    pub fn get() -> (u32, u32, u32) {
        (
            BEHAVIOR.load(Ordering::Relaxed),
            THINK.load(Ordering::Relaxed),
            NPC.load(Ordering::Relaxed),
        )
    }
}

pub const BEHAVIOR_SLOT_COUNT: usize = 200;

#[derive(Debug, Clone, Copy, Default)]
pub struct Weights {
    pub aggression: f32,
    pub dodge_rate: f32,
    pub guard_rate: f32,
    pub combo_rate: f32,
    pub heal_priority: f32,
    pub spell_rate: f32,
    pub item_rate: f32,
    pub spacing: f32,
    pub target_switch: f32,
}

impl Weights {
    /// 上一帧 → 这一帧的平滑（变化率上限 + 迟滞）。
    pub fn blend(prev: &Weights, next: &Weights, max_delta: f32, hysteresis: f32) -> Weights {
        fn one(p: f32, n: f32, max_delta: f32, hyst: f32) -> f32 {
            let d = (n - p).clamp(-max_delta, max_delta);
            let v = (p + d).clamp(0.0, 1.0);
            if (v - p).abs() < hyst { p } else { v }
        }
        Weights {
            aggression: one(prev.aggression, next.aggression, max_delta, hysteresis),
            dodge_rate: one(prev.dodge_rate, next.dodge_rate, max_delta, hysteresis),
            guard_rate: one(prev.guard_rate, next.guard_rate, max_delta, hysteresis),
            combo_rate: one(prev.combo_rate, next.combo_rate, max_delta, hysteresis),
            heal_priority: one(prev.heal_priority, next.heal_priority, max_delta, hysteresis),
            spell_rate: one(prev.spell_rate, next.spell_rate, max_delta, hysteresis),
            item_rate: one(prev.item_rate, next.item_rate, max_delta, hysteresis),
            spacing: one(prev.spacing, next.spacing, max_delta, hysteresis),
            target_switch: one(prev.target_switch, next.target_switch, max_delta, hysteresis),
        }
    }
}

/// 取全局 param 仓库。
///
/// SAFETY: 只能在主线程（FrameBegin/FrameEnd 任务）调用。
pub unsafe fn repo() -> Option<&'static mut SoloParamRepository> {
    SoloParamRepository::instance_mut().ok()
}

fn set_behavior_slot(row: &mut NPC_AI_BEHAVIOR_PROBABILITY_PARAM_ST, slot: usize, value: i16) -> bool {
    match slot {
        0 => row.set_param000(value),
        1 => row.set_param001(value),
        13 => row.set_param013(value),
        14 => row.set_param014(value),
        20 => row.set_param020(value),
        21 => row.set_param021(value),
        22 => row.set_param022(value),
        23 => row.set_param023(value),
        24 => row.set_param024(value),
        25 => row.set_param025(value),
        26 => row.set_param026(value),
        27 => row.set_param027(value),
        28 => row.set_param028(value),
        97 => row.set_param097(value),
        101 => row.set_param101(value),
        102 => row.set_param102(value),
        103 => row.set_param103(value),
        105 => row.set_param105(value),
        110 => row.set_param110(value),
        111 => row.set_param111(value),
        115 => row.set_param115(value),
        116 => row.set_param116(value),
        118 => row.set_param118(value),
        120 => row.set_param120(value),
        121 => row.set_param121(value),
        126 => row.set_param126(value),
        130 => row.set_param130(value),
        131 => row.set_param131(value),
        _ => return false,
    }
    true
}

/// 直接写 `NpcAiBehaviorProbability` 的某个槽。
///
/// SAFETY: `slot` 必须 < BEHAVIOR_SLOT_COUNT；行必须存在；只能在主线程调用。
pub unsafe fn write_behavior_slot(
    repo: &mut SoloParamRepository,
    row: u32,
    slot: usize,
    value: i16,
) -> bool {
    if slot >= BEHAVIOR_SLOT_COUNT {
        return false;
    }
    let Some(entry) = repo.get_mut::<NpcAiBehaviorProbability>(row) else {
        return false;
    };
    set_behavior_slot(entry, slot, value)
}

/// 批量写 behavior slots：`(slot, value)`。
pub unsafe fn write_behavior_slots(
    repo: &mut SoloParamRepository,
    row: u32,
    slots: &[(usize, i16)],
) -> usize {
    slots
        .iter()
        .filter(|(slot, value)| write_behavior_slot(repo, row, *slot, *value))
        .count()
}

/// 改 `NpcThinkParam`（感知/交战）。注意：对已存在实体可能不刷新。
pub unsafe fn with_think(
    repo: &mut SoloParamRepository,
    row: u32,
    f: impl FnOnce(&mut NPC_THINK_PARAM_ST),
) -> bool {
    match repo.get_mut::<NpcThinkParam>(row) {
        Some(think) => {
            f(think);
            true
        }
        None => false,
    }
}

/// 改 `NpcParam`（数值/队伍/防御）。即时生效。
pub unsafe fn with_npc(
    repo: &mut SoloParamRepository,
    row: u32,
    f: impl FnOnce(&mut NPC_PARAM_ST),
) -> bool {
    match repo.get_mut::<NpcParam>(row) {
        Some(npc) => {
            f(npc);
            true
        }
        None => false,
    }
}

// ---------------------------------------------------------------- friendly fire

/// 被我们打开过 `friendlyTarget` 的 `AtkParam_Pc` 行（关掉友伤时只还原这些）。
static FRIENDLY_PATCHED: Mutex<Vec<u32>> = Mutex::new(Vec::new());
/// 诊断：上一次扫描到的 PC 攻击行总数 / 原本就允许打友军的行数。
static LAST_SCAN: AtomicUsize = AtomicUsize::new(0);
static LAST_ALREADY: AtomicUsize = AtomicUsize::new(0);

/// 打开/关闭「玩家与同伴互相能打中」。
///
/// 引擎命中判定 = 攻击行 `ATK_PARAM_ST` 的 target 位 × 双方队伍关系：
/// - 同伴是 team 47（友军），玩家自己的攻击行只有 `opposeTarget`，所以打不到同伴；
/// - 把 **`AtkParam_Pc`**（玩家/PlayerIns 用的攻击表）的 `friendlyTarget` 全部打开，
///   玩家和克隆体（也是 PlayerIns）的攻击就能命中友军。
///
/// 只动 PC 表，不动 `AtkParam_Npc`：敌人的攻击仍然不会误伤自己人。
/// 原本就 `friendlyTarget=1` 的行不记入回滚表，关闭时保持原样。
///
/// 返回 `(本次改动/还原行数, PC 表总数, 原本就允许友军的行数)`。
pub unsafe fn set_friendly_fire(on: bool) -> Result<(usize, usize, usize), String> {
    let repo = repo().ok_or("no SoloParamRepository")?;
    set_friendly_fire_with(repo, on)
}

/// 同 [`set_friendly_fire`]，但复用调用方已经拿到的 repo（避免同时持有两个 `&mut`）。
pub unsafe fn set_friendly_fire_with(
    repo: &mut SoloParamRepository,
    on: bool,
) -> Result<(usize, usize, usize), String> {
    let mut patched = FRIENDLY_PATCHED.lock().map_err(|_| "friendly lock")?;
    let total = repo.rows::<AtkParam_Pc>().count();
    LAST_SCAN.store(total, Ordering::Relaxed);

    if on {
        let mut already = 0usize;
        let mut changed = 0usize;
        for (id, row) in repo.rows_mut::<AtkParam_Pc>() {
            if row.friendly_target() {
                already += 1;
                continue;
            }
            row.set_friendly_target(true);
            patched.push(id);
            changed += 1;
        }
        LAST_ALREADY.store(already, Ordering::Relaxed);
        Ok((changed, total, already))
    } else {
        let mut restored = 0usize;
        for id in patched.drain(..) {
            if let Some(row) = repo.get_mut::<AtkParam_Pc>(id) {
                // 只还原我们写过的行；写入后若被别的 mod 再次改成 true，这里会覆盖回 false。
                // 这是可接受的：友伤开关的语义就是「我来决定」。
                row.set_friendly_target(false);
                restored += 1;
            }
        }
        Ok((restored, total, LAST_ALREADY.load(Ordering::Relaxed)))
    }
}

/// 友伤诊断：PC 表行数 / 当前 `friendlyTarget=1` 行数 / 我们改过的行数。
pub unsafe fn friendly_fire_stats() -> serde_json::Value {
    let Some(repo) = repo() else {
        return serde_json::json!({ "error": "no SoloParamRepository" });
    };
    let total = repo.rows::<AtkParam_Pc>().count();
    let mut friendly = 0usize;
    for (_id, row) in repo.rows::<AtkParam_Pc>() {
        if row.friendly_target() {
            friendly += 1;
        }
    }
    let patched = FRIENDLY_PATCHED.lock().map(|g| g.len()).unwrap_or(0);
    serde_json::json!({
        "pc_rows": total,
        "friendly_target_rows": friendly,
        "patched_by_us": patched,
        "damage_rate": friendly_rate(),
        "effect_id": FRIENDLY_FIRE_SPEFFECT,
        "effect_ready": friendly_effect_ready(),
        "last_scan": LAST_SCAN.load(Ordering::Relaxed),
        "last_already": LAST_ALREADY.load(Ordering::Relaxed),
    })
}

// ---------------------------------------------------------------- friendly fire damage

/// 友伤倍率用的 spEffect。
///
/// 原版行 `20011466` 在 regulation 的其它参数表里**没有任何引用**，字段基本是空的
/// （只有 `def* = 0`，原用途像调试/占位）。友伤开启时把它临时改成：
/// * `atkPlayerDmgCorrectRate_* = rate`：克隆体打「玩家类目标」的伤害倍率（克隆体→玩家）；
/// * `defPlayerDmgCorrectRate_* = rate`：克隆体受到「玩家类攻击」的伤害倍率（玩家→克隆体）；
/// * `atkEnemy/defEnemy/defObj = 1`：打普通敌人 / 受到普通敌人伤害都不变。
///
/// **只挂到克隆体身上**，不挂玩家：玩家被敌人打、玩家打敌人都不受影响。
/// 关闭友伤时从克隆体身上摘掉并把原字段写回去。
pub const FRIENDLY_FIRE_SPEFFECT: u32 = 20011466;
const FR_FIELD_COUNT: usize = 22;
/// 友伤倍率（0.2 = 20%）。配置/IPC 可改，运行时 patch 读这个值。
static FRIENDLY_RATE_BITS: AtomicU32 = AtomicU32::new(0.2f32.to_bits());
/// effect 行是否已经成功改成「友伤 20%」的安全版本；没改成时**绝不能**挂到角色身上
/// （原行 `def* = 0`，挂上去会变成无敌）。
static FRIENDLY_EFFECT_READY: AtomicBool = AtomicBool::new(false);
/// 原字段（effect_endurance + 5 atkPlayer + 5 atkEnemy + 5 defPlayer + 5 defEnemy + defObj）
static FRIENDLY_EFFECT_ORIGINAL: Mutex<Option<[f32; FR_FIELD_COUNT]>> = Mutex::new(None);

/// 友伤 effect 行是否已安全 patch。
pub fn friendly_effect_ready() -> bool {
    FRIENDLY_EFFECT_READY.load(Ordering::Acquire)
}

/// 设置友伤倍率并返回 clamp 后的值。
pub fn set_friendly_rate(rate: f32) -> f32 {
    let rate = rate.clamp(0.01, 1.0);
    FRIENDLY_RATE_BITS.store(rate.to_bits(), Ordering::Relaxed);
    rate
}

/// 当前友伤倍率（0.2 = 20%）。
pub fn friendly_rate() -> f32 {
    f32::from_bits(FRIENDLY_RATE_BITS.load(Ordering::Relaxed))
}

fn read_friendly_effect(row: &SP_EFFECT_PARAM_ST) -> [f32; FR_FIELD_COUNT] {
    [
        row.effect_endurance(),
        row.atk_player_dmg_correct_rate_physics(),
        row.atk_player_dmg_correct_rate_magic(),
        row.atk_player_dmg_correct_rate_fire(),
        row.atk_player_dmg_correct_rate_thunder(),
        row.atk_player_dmg_correct_rate_dark(),
        row.atk_enemy_dmg_correct_rate_physics(),
        row.atk_enemy_dmg_correct_rate_magic(),
        row.atk_enemy_dmg_correct_rate_fire(),
        row.atk_enemy_dmg_correct_rate_thunder(),
        row.atk_enemy_dmg_correct_rate_dark(),
        row.def_player_dmg_correct_rate_physics(),
        row.def_player_dmg_correct_rate_magic(),
        row.def_player_dmg_correct_rate_fire(),
        row.def_player_dmg_correct_rate_thunder(),
        row.def_player_dmg_correct_rate_dark(),
        row.def_enemy_dmg_correct_rate_physics(),
        row.def_enemy_dmg_correct_rate_magic(),
        row.def_enemy_dmg_correct_rate_fire(),
        row.def_enemy_dmg_correct_rate_thunder(),
        row.def_enemy_dmg_correct_rate_dark(),
        row.def_obj_dmg_correct_rate(),
    ]
}

fn write_friendly_effect(row: &mut SP_EFFECT_PARAM_ST, v: &[f32; FR_FIELD_COUNT]) {
    row.set_effect_endurance(v[0]);
    row.set_atk_player_dmg_correct_rate_physics(v[1]);
    row.set_atk_player_dmg_correct_rate_magic(v[2]);
    row.set_atk_player_dmg_correct_rate_fire(v[3]);
    row.set_atk_player_dmg_correct_rate_thunder(v[4]);
    row.set_atk_player_dmg_correct_rate_dark(v[5]);
    row.set_atk_enemy_dmg_correct_rate_physics(v[6]);
    row.set_atk_enemy_dmg_correct_rate_magic(v[7]);
    row.set_atk_enemy_dmg_correct_rate_fire(v[8]);
    row.set_atk_enemy_dmg_correct_rate_thunder(v[9]);
    row.set_atk_enemy_dmg_correct_rate_dark(v[10]);
    row.set_def_player_dmg_correct_rate_physics(v[11]);
    row.set_def_player_dmg_correct_rate_magic(v[12]);
    row.set_def_player_dmg_correct_rate_fire(v[13]);
    row.set_def_player_dmg_correct_rate_thunder(v[14]);
    row.set_def_player_dmg_correct_rate_dark(v[15]);
    row.set_def_enemy_dmg_correct_rate_physics(v[16]);
    row.set_def_enemy_dmg_correct_rate_magic(v[17]);
    row.set_def_enemy_dmg_correct_rate_fire(v[18]);
    row.set_def_enemy_dmg_correct_rate_thunder(v[19]);
    row.set_def_enemy_dmg_correct_rate_dark(v[20]);
    row.set_def_obj_dmg_correct_rate(v[21]);
}

/// 把友伤 effect 改成「只把对玩家类目标的伤害压到 `rate`」，返回实际使用的倍率。
pub unsafe fn patch_friendly_damage_effect(rate: f32) -> Result<f32, String> {
    let repo = repo().ok_or("no SoloParamRepository")?;
    patch_friendly_damage_effect_with(repo, rate)
}

/// 同 [`patch_friendly_damage_effect`]，复用调用方的 repo。
pub unsafe fn patch_friendly_damage_effect_with(
    repo: &mut SoloParamRepository,
    rate: f32,
) -> Result<f32, String> {
    // 先标记未就绪：中途失败时调用方绝不能把原行（def*=0）挂到角色身上。
    FRIENDLY_EFFECT_READY.store(false, Ordering::Release);
    let row = repo
        .get_mut::<SpEffectParam>(FRIENDLY_FIRE_SPEFFECT)
        .ok_or_else(|| format!("SpEffectParam {} not found", FRIENDLY_FIRE_SPEFFECT))?;
    let mut original = FRIENDLY_EFFECT_ORIGINAL
        .lock()
        .map_err(|_| "friendly effect lock")?;
    if original.is_none() {
        *original = Some(read_friendly_effect(row));
    }
    let rate = rate.clamp(0.01, 1.0);
    row.set_effect_endurance(-1.0);
    row.set_atk_player_dmg_correct_rate_physics(rate);
    row.set_atk_player_dmg_correct_rate_magic(rate);
    row.set_atk_player_dmg_correct_rate_fire(rate);
    row.set_atk_player_dmg_correct_rate_thunder(rate);
    row.set_atk_player_dmg_correct_rate_dark(rate);
    row.set_atk_enemy_dmg_correct_rate_physics(1.0);
    row.set_atk_enemy_dmg_correct_rate_magic(1.0);
    row.set_atk_enemy_dmg_correct_rate_fire(1.0);
    row.set_atk_enemy_dmg_correct_rate_thunder(1.0);
    row.set_atk_enemy_dmg_correct_rate_dark(1.0);
    row.set_def_player_dmg_correct_rate_physics(rate);
    row.set_def_player_dmg_correct_rate_magic(rate);
    row.set_def_player_dmg_correct_rate_fire(rate);
    row.set_def_player_dmg_correct_rate_thunder(rate);
    row.set_def_player_dmg_correct_rate_dark(rate);
    row.set_def_enemy_dmg_correct_rate_physics(1.0);
    row.set_def_enemy_dmg_correct_rate_magic(1.0);
    row.set_def_enemy_dmg_correct_rate_fire(1.0);
    row.set_def_enemy_dmg_correct_rate_thunder(1.0);
    row.set_def_enemy_dmg_correct_rate_dark(1.0);
    row.set_def_obj_dmg_correct_rate(1.0);
    FRIENDLY_EFFECT_READY.store(true, Ordering::Release);
    Ok(rate)
}

/// 还原友伤 effect 行；返回是否真的还原了。
pub unsafe fn restore_friendly_damage_effect() -> bool {
    let Some(repo) = repo() else {
        return false;
    };
    restore_friendly_damage_effect_with(repo)
}

/// 同 [`restore_friendly_damage_effect`]，复用调用方的 repo。
pub unsafe fn restore_friendly_damage_effect_with(repo: &mut SoloParamRepository) -> bool {
    FRIENDLY_EFFECT_READY.store(false, Ordering::Release);
    let Ok(mut original) = FRIENDLY_EFFECT_ORIGINAL.lock() else {
        return false;
    };
    let Some(values) = original.take() else {
        return false;
    };
    if let Some(row) = repo.get_mut::<SpEffectParam>(FRIENDLY_FIRE_SPEFFECT) {
        write_friendly_effect(row, &values);
        true
    } else {
        false
    }
}

/// 读回 `NpcThinkParam` 里被权重写过的字段（验证「写进去了没有」）。
///
/// 注意：param 行写进去 ≠ 已经生效 —— 引擎多数字段在 spawn 时缓存，
/// 所以验证方式是「改权重 → `resummon` → 看 `combat:`」。
pub unsafe fn probe_think(repo: &SoloParamRepository, row: u32) -> serde_json::Value {
    if row == 0 {
        return serde_json::Value::Null;
    }
    let Some(t) = repo.get::<NpcThinkParam>(row) else {
        return serde_json::json!({ "row": row, "missing": true });
    };
    serde_json::json!({
        "row": row,
        "logic_id": t.logic_id(),
        "battle_goal_id": t.battle_goal_id(),
        "is_buddy_ai": t.is_buddy_ai(),
        "battle_start_dist": t.battle_start_dist(),
        "eye_dist": t.eye_dist(),
        "search_eye_dist": t.search_eye_dist(),
        "battle_eye_update_dist": t.battle_eye_update_dist(),
        "backhome_dist": t.backhome_dist(),
        "max_backhome_dist": t.max_backhome_dist(),
        "is_guard_act": t.is_guard_act(),
        "team_attack_effectivity": t.team_attack_effectivity(),
        "search_target_lv1_forget_time": t.search_target_lv1_forget_time(),
        "search_target_lv2_forget_time": t.search_target_lv2_forget_time(),
    })
}

fn behavior_slot(row: &NPC_AI_BEHAVIOR_PROBABILITY_PARAM_ST, slot: usize) -> Option<i16> {
    Some(match slot {
        0 => row.param000(),
        1 => row.param001(),
        13 => row.param013(),
        14 => row.param014(),
        20 => row.param020(),
        21 => row.param021(),
        22 => row.param022(),
        23 => row.param023(),
        24 => row.param024(),
        25 => row.param025(),
        26 => row.param026(),
        27 => row.param027(),
        28 => row.param028(),
        97 => row.param097(),
        101 => row.param101(),
        102 => row.param102(),
        103 => row.param103(),
        105 => row.param105(),
        110 => row.param110(),
        111 => row.param111(),
        115 => row.param115(),
        116 => row.param116(),
        118 => row.param118(),
        120 => row.param120(),
        121 => row.param121(),
        126 => row.param126(),
        130 => row.param130(),
        131 => row.param131(),
        _ => return None,
    })
}

/// 读回 `NpcAiBehaviorProbability` 里我们写过的槽。
pub unsafe fn probe_behavior(repo: &SoloParamRepository, row: u32) -> serde_json::Value {
    if row == 0 {
        return serde_json::Value::Null;
    }
    let Some(r) = repo.get::<NpcAiBehaviorProbability>(row) else {
        return serde_json::json!({ "row": row, "missing": true });
    };
    let mut slots = serde_json::Map::new();
    for slot in [
        0usize, 1, 13, 14, 20, 23, 97, 101, 105, 110, 115, 126, 130, 131,
    ] {
        if let Some(v) = behavior_slot(r, slot) {
            slots.insert(slot.to_string(), serde_json::json!(v));
        }
    }
    serde_json::json!({ "row": row, "slots": slots })
}

fn pct(v: f32) -> i16 {
    (v.clamp(0.0, 1.0) * 100.0).round() as i16
}

/// `BuddyParam` 一行的可复制字段（crate 只暴露了这些；够用了）。
#[derive(Clone, Copy, Debug)]
pub struct BuddyRow {
    pub trigger_sp_effect_id: i32,
    pub npc_param_id: i32,
    pub npc_think_param_id: i32,
    pub npc_param_id_ridden: i32,
    pub npc_think_param_id_ridden: i32,
    pub npc_player_init_param_id: i32,
    pub x_offset: f32,
    pub z_offset: f32,
    pub y_angle: f32,
    pub appear_on_around_sekihi: u8,
    pub disable_pc_target_share: u8,
    pub pc_follow_type: u8,
}

/// 读一行 `BuddyParam`。
pub unsafe fn read_buddy(repo: &SoloParamRepository, id: u32) -> Option<BuddyRow> {
    let r = repo.get::<BuddyParam>(id)?;
    Some(BuddyRow {
        trigger_sp_effect_id: r.trigger_sp_effect_id(),
        npc_param_id: r.npc_param_id(),
        npc_think_param_id: r.npc_think_param_id(),
        npc_param_id_ridden: r.npc_param_id_ridden(),
        npc_think_param_id_ridden: r.npc_think_param_id_ridden(),
        npc_player_init_param_id: r.npc_player_init_param_id(),
        x_offset: r.x_offset(),
        z_offset: r.z_offset(),
        y_angle: r.y_angle(),
        appear_on_around_sekihi: r.appear_on_around_sekihi(),
        disable_pc_target_share: r.disable_pc_target_share(),
        pc_follow_type: r.pc_follow_type(),
    })
}

/// 写一行 `BuddyParam`（`keep_trigger` = 保留目标行自己的触发 spEffect）。
pub unsafe fn write_buddy(
    repo: &mut SoloParamRepository,
    id: u32,
    v: &BuddyRow,
    keep_trigger: bool,
) -> bool {
    let own_trigger = if keep_trigger {
        match repo.get::<BuddyParam>(id) {
            Some(r) => r.trigger_sp_effect_id(),
            None => return false,
        }
    } else {
        v.trigger_sp_effect_id
    };
    let Some(r) = repo.get_mut::<BuddyParam>(id) else {
        return false;
    };
    r.set_trigger_sp_effect_id(own_trigger);
    r.set_npc_param_id(v.npc_param_id);
    r.set_npc_think_param_id(v.npc_think_param_id);
    r.set_npc_param_id_ridden(v.npc_param_id_ridden);
    r.set_npc_think_param_id_ridden(v.npc_think_param_id_ridden);
    r.set_npc_player_init_param_id(v.npc_player_init_param_id);
    r.set_x_offset(v.x_offset);
    r.set_z_offset(v.z_offset);
    r.set_y_angle(v.y_angle);
    r.set_appear_on_around_sekihi(v.appear_on_around_sekihi);
    r.set_disable_pc_target_share(v.disable_pc_target_share);
    r.set_pc_follow_type(v.pc_follow_type);
    true
}

/// 把 `from` 行整行复制到 `to` 里的每一行（默认保留各自 trigger spEffect）。
///
/// 用途：我们借「离群野狼」的骨灰（23200000..2）当载体，但真正想复刻的是
/// **拟态泪滴本体行 20700001**（`npc=100000010 think=100000010 init=26050 follow=0`）。
/// 之前只改了 npc/think/init/follow 四个字段，剩下的 x/z offset、`disable_pc_target_share`
/// 等还是狼的，行为自然不像骨灰本体。
pub unsafe fn copy_buddy_row(
    repo: &mut SoloParamRepository,
    from: u32,
    to: &[u32],
    keep_trigger: bool,
) -> usize {
    let Some(src) = read_buddy(repo, from) else {
        log::warn!("copy_buddy_row: source row {from} not found");
        return 0;
    };
    let mut n = 0;
    for &id in to {
        if id == from {
            continue;
        }
        if write_buddy(repo, id, &src, keep_trigger) {
            n += 1;
        }
    }
    log::info!("copy_buddy_row: {from} -> {n} row(s) (keep_trigger={keep_trigger}): {src:?}");
    n
}

/// 载体骨灰行原来的 trigger spEffect（被 `apply_buddy_count` 改过之后还要能还原）。
pub static BASE_BUDDY_TRIGGER: std::sync::atomic::AtomicI32 =
    std::sync::atomic::AtomicI32::new(0);

/// 用 `BuddyParam.trigger_sp_effect_id` 控制实际召唤几个。
///
/// 3 个载体行共享同一个 trigger（232000 = 离群野狼），引擎按 trigger 找出整组；
/// 把第 4 个以后的行 trigger 改成 -1，它们就不会被这次召唤带出来。
/// `count = 0` 时全部改 -1 —— 等于「这次不召唤任何人」。
pub unsafe fn apply_buddy_count(rows: &[u32], count: usize) -> (usize, i32) {
    use std::sync::atomic::Ordering;
    let Some(repo) = repo() else { return (0, 0) };
    let mut base = BASE_BUDDY_TRIGGER.load(Ordering::Relaxed);
    if base == 0 {
        base = rows
            .first()
            .and_then(|id| repo.get::<BuddyParam>(*id))
            .map(|r| r.trigger_sp_effect_id())
            .filter(|v| *v > 0)
            .unwrap_or(207000);
        BASE_BUDDY_TRIGGER.store(base, Ordering::Relaxed);
    }
    let mut changed = 0usize;
    for (i, id) in rows.iter().enumerate() {
        let Some(row) = repo.get_mut::<BuddyParam>(*id) else {
            continue;
        };
        // 第 0 行永远保留 trigger：引擎的 trigger→BuddyParam 映射链以它为键，
        // 全改成 -1 会让键消失，之后再调回 1 人就召不出来了（实测）。
        let want = if i == 0 || i < count { base } else { -1 };
        if row.trigger_sp_effect_id() != want {
            row.set_trigger_sp_effect_id(want);
            changed += 1;
        }
    }
    log::info!(
        "buddy count: {count}/{} active (trigger={base}, changed={changed} row(s))",
        rows.len()
    );
    (changed, base)
}

/// 给克隆体用的 NpcParam 行加保命：免疫摔落伤害 + 提高 HP。
/// （Mimic 的两个形态：133201000 史莱姆 / 100000010 本体。）
pub unsafe fn buff_clone_rows() {
    let Some(repo) = repo() else { return };
    for id in [133201000u32, 100000010u32] {
        if let Some(npc) = repo.get_mut::<NpcParam>(id) {
            npc.set_fall_damage_dump(100);
            npc.set_hp(9999);
            log::info!("buffed NpcParam {id}: fall_damage_dump=100, hp=9999");
        } else {
            log::warn!("NpcParam {id} not found");
        }
    }
}

// ---------------------------------------------------------------- 队友 AI（每号位一行 think）

/// 队友号位数（和 `roster::MAX_SLOTS` 一致；roster 依赖 ui/i18n，这里不反向引用）。
pub const AI_SLOT_COUNT: usize = 3;

/// 每个号位用哪一行 `NpcThinkParam`。0 = 没有独立行（该号位跟随全局 `think_row`）。
///
/// 为什么要独立行：`NpcThinkParam` 是按行共享的，三个克隆体都用 100000010 的话
/// 改一个人的交战半径就是改所有人的。赐福菜单里选择「队友 AI」后，把
/// `teammate_think_rows[i]` 作为第 i 个队友的 think 行（`BuddyParam.npc_think_param_id`），
/// 每行先整行复制基准行、再只改这个队友的 4 个字段。
static AI_THINK_ROWS: Mutex<[u32; AI_SLOT_COUNT]> = Mutex::new([0; AI_SLOT_COUNT]);

/// 设置每号位的 think 行（来自 ini `[ai] teammate_think_rows=` 或 IPC）。
pub fn set_teammate_think_rows(rows: &[u32]) {
    let mut out = [0u32; AI_SLOT_COUNT];
    for (dst, src) in out.iter_mut().zip(rows.iter()) {
        *dst = *src;
    }
    if let Ok(mut g) = AI_THINK_ROWS.lock() {
        *g = out;
    }
    log::info!("ai: teammate think rows -> {out:?}");
}

pub fn teammate_think_rows() -> [u32; AI_SLOT_COUNT] {
    AI_THINK_ROWS
        .lock()
        .map(|g| *g)
        .unwrap_or([0; AI_SLOT_COUNT])
}

/// 把 `from` 行的**全部字段**（含 crate 没暴露的）原样复制到 `to`。
///
/// 用途：让每号位的独立 think 行从「和拟态泪滴完全一样」开始，再只覆盖预设里那几项；
/// 这样不会因为某一行本来属于别的 AI（比如史莱姆形态）而带上不同的逻辑/数值。
///
/// SAFETY: 主线程；两行都必须存在。只复制同一张表的同一种结构体。
pub unsafe fn clone_think_row(repo: &mut SoloParamRepository, from: u32, to: u32) -> bool {
    if from == 0 || to == 0 || from == to {
        return false;
    }
    const SIZE: usize = std::mem::size_of::<NPC_THINK_PARAM_ST>();
    let Some(src) = repo.get::<NpcThinkParam>(from) else {
        return false;
    };
    let bytes = std::slice::from_raw_parts(src as *const NPC_THINK_PARAM_ST as *const u8, SIZE)
        .to_vec();
    let Some(dst) = repo.get_mut::<NpcThinkParam>(to) else {
        return false;
    };
    std::ptr::copy_nonoverlapping(
        bytes.as_ptr(),
        dst as *mut NPC_THINK_PARAM_ST as *mut u8,
        SIZE,
    );
    true
}

/// 把「感知 / 交战 / 防御 / 换目标」这几项写进一行 `NpcThinkParam`。
///
/// 全局权重行和每个队友自己的行共用这一份代码：先 `clone_think_row` 成基准行，
/// 再调用它，就得到「基准 AI + 这个队友的 4 个旋钮」。
///
/// SAFETY: 主线程；`row` 行必须存在。
pub unsafe fn write_think_weights(
    repo: &mut SoloParamRepository,
    row: u32,
    w: &Weights,
    leash: f32,
) -> bool {
    if row == 0 {
        return false;
    }
    with_think(repo, row, |t| {
        // `backhome_dist` 只有在 keep_close 明确指定「绳长」时才改：
        // mimic 本体这一行原值是 9979（= 不受绳长约束），改成 30 多会让骨灰 AI
        // 频繁「回家」；不指定就保持原值，交给骨灰自己的掉队处理（§14.6）。
        t.set_battle_start_dist((3.0 + 9.0 * w.aggression) as u16);
        t.set_eye_dist((6.0 + 14.0 * w.aggression) as u16);
        // 侦测半径：mimic 行原值是 2 m（贴脸才反应）—— 这就是「法系同伴永远不施法」的
        // 根因：它根本不会在射程外进入战斗。抬到 6..20 m 之后才会「发现→接近→施法」。
        t.set_search_eye_dist((6.0 + 14.0 * w.aggression) as u16);
        t.set_battle_eye_update_dist((4.0 + 8.0 * w.aggression) as u16);
        if leash > 0.0 {
            t.set_backhome_dist(leash as u16);
            t.set_max_backhome_dist(leash as u16);
        }
        t.set_is_guard_act((w.guard_rate > 0.5) as u8);
        // 同伴**绝不能打队友**：这个字段是「对同队的攻击效果」，写死 0。
        // （实测把它拉到 100 会让召唤物误伤玩家。）
        t.set_team_attack_effectivity(0);
        // target_switch 高 = 更快忘记目标/换目标
        t.set_search_target_lv1_forget_time(1.0 + 19.0 * w.target_switch);
        t.set_search_target_lv2_forget_time(1.0 + 29.0 * w.target_switch);
    })
}

/// 给第 `slot` 个队友位写 AI 到它的独立 think 行，返回实际使用的行。
///
/// `None` = 这个号位没有独立行（配置缺失 / 行在 regulation 里不存在），
/// 该号位跟随全局 `think_row`（和加这个功能之前完全一样）。
///
/// SAFETY: 主线程；`base_row` 必须存在（全局权重行）。
pub unsafe fn apply_teammate_ai(
    repo: &mut SoloParamRepository,
    slot: usize,
    base_row: u32,
    w: &Weights,
    leash: f32,
) -> Option<u32> {
    if slot >= AI_SLOT_COUNT || base_row == 0 {
        return None;
    }
    let row = teammate_think_rows()[slot];
    if row == 0 || row == base_row {
        return None;
    }
    if !clone_think_row(repo, base_row, row) {
        return None;
    }
    if write_think_weights(repo, row, w, leash) {
        Some(row)
    } else {
        None
    }
}

/// 把「第 i 个载体骨灰行用哪一行 think」写进 `BuddyParam.npc_think_param_id`。
///
/// 引擎在**生成那一刻**按 BuddyParam 行取 think，所以换 AI 后要下次召唤才生效
/// （法术槽是每个克隆体自己写，立即生效）。
///
/// 返回改动的行数。
pub unsafe fn set_buddy_think_rows(
    repo: &mut SoloParamRepository,
    buddy_rows: &[u32],
    think_rows: &[u32; AI_SLOT_COUNT],
) -> usize {
    let mut changed = 0usize;
    for (i, id) in buddy_rows.iter().take(AI_SLOT_COUNT).enumerate() {
        let want = think_rows[i] as i32;
        if want <= 0 {
            continue;
        }
        let Some(row) = repo.get_mut::<BuddyParam>(*id) else {
            continue;
        };
        if row.npc_think_param_id() != want {
            row.set_npc_think_param_id(want);
            changed += 1;
        }
    }
    changed
}

/// 读回每个载体行当前的 `npc_think_param_id`（诊断/status 用）。
pub unsafe fn buddy_think_ids(repo: &SoloParamRepository, buddy_rows: &[u32]) -> Vec<i32> {
    buddy_rows
        .iter()
        .map(|id| {
            repo.get::<BuddyParam>(*id)
                .map(|r| r.npc_think_param_id())
                .unwrap_or(0)
        })
        .collect()
}

/// 权重 → 具体槽位/字段。映射表见 `config/behavior_map.yaml`。
///
/// 所有槽位编号都是社区标注，**必须逐条实测**。
pub unsafe fn apply_weights(w: &Weights) {
    let Some(repo) = repo() else { return };

    let mut slots: Vec<(usize, i16)> = Vec::with_capacity(32);
    // 连段
    slots.push((0, pct(w.combo_rate)));
    slots.push((1, pct(w.combo_rate)));
    slots.push((115, pct(w.combo_rate)));
    // 翻滚/侧移
    for slot in [101, 102, 103, 110, 111, 116, 120, 121] {
        slots.push((slot, pct(w.dodge_rate)));
    }
    // 防御
    for slot in [105, 112, 113, 118] {
        slots.push((slot, pct(w.guard_rate)));
    }
    // 法术
    for slot in [13, 14, 20, 21, 22, 23, 24, 25, 26, 27, 28] {
        slots.push((slot, pct(w.spell_rate)));
    }
    // 回血 / 喝药
    slots.push((23, pct(w.heal_priority)));
    slots.push((97, pct(w.heal_priority)));
    // 接近/拉扯
    slots.push((126, pct(w.spacing)));
    // 主动开战（[Find Attack] 一带，待实测）
    slots.push((130, pct(w.aggression)));
    slots.push((131, pct(w.aggression)));

    let (behavior_row, think_row, npc_row) = rows::get();
    if behavior_row != 0 {
        write_behavior_slots(repo, behavior_row, &slots);
    }

    // 感知/交战（可能需要重召才生效）
    if think_row != 0 {
        write_think_weights(repo, think_row, w, crate::leash());
    }

    // 数值侧：防御角度/物理减伤（NpcParam 没有 estus 概率字段，喝药用行为表控）
    if npc_row != 0 {
        with_npc(repo, npc_row, |n| {
            n.set_guard_angle((60.0 + 120.0 * w.guard_rate) as i16);
            n.set_phys_guard_cut_rate(20.0 + 70.0 * w.guard_rate);
        });
    }
}

// ---------------------------------------------------------------- 体型 / spawn 种子

/// 体型是**建模型时**从 `CharaInitParam -> FACE_PARAM` 烘焙的（§28）：
/// 出生后写 `PlayerGameData.face_data` 只能改脸，改不了身体的骨长/网格。
/// 所以「每个队友自己的体型」必须让它在出生时就读到自己的 FACE_PARAM 行。
///
/// 这个探针只读：列出 `CharaInitParam` / `FACE_PARAM` 的 id 空间、26050 的字段、
/// 以及它指向的那一行体型值，用来判断能不能「复制几行给三个号位」。
pub unsafe fn probe_init(init_id: u32) -> Result<serde_json::Value, String> {
    let repo = repo().ok_or("no SoloParamRepository")?;

    let mut init_ids: Vec<u32> = repo.rows::<CharaInitParam>().map(|(id, _)| id).collect();
    init_ids.sort_unstable();
    let mut face_ids: Vec<u32> = repo.rows::<FaceParam>().map(|(id, _)| id).collect();
    face_ids.sort_unstable();

    // 所有 init 行引用到的 face 行（用来找「没人用」的 spare 行）
    let mut used_face: Vec<u32> = Vec::new();
    for (_id, row) in repo.rows::<CharaInitParam>() {
        let f = row.npc_player_face_gen_id();
        if f > 0 {
            used_face.push(f as u32);
        }
    }
    used_face.sort_unstable();
    used_face.dedup();

    let mut out = serde_json::json!({
        "init_rows": init_ids.len(),
        "init_first": init_ids.iter().take(10).collect::<Vec<_>>(),
        "init_last": init_ids.iter().rev().take(10).collect::<Vec<_>>(),
        "face_rows": face_ids.len(),
        "face_first": face_ids.iter().take(10).collect::<Vec<_>>(),
        "face_last": face_ids.iter().rev().take(10).collect::<Vec<_>>(),
        "face_referenced": used_face.len(),
        "face_unreferenced_sample": face_ids.iter().filter(|id| !used_face.contains(id)).take(10).collect::<Vec<_>>(),
    });

    if let Some(row) = repo.get::<CharaInitParam>(init_id) {
        let face_id = row.npc_player_face_gen_id();
        out["init"] = serde_json::json!({
            "id": init_id,
            "npc_player_sex": row.npc_player_sex(),
            "npc_player_type": row.npc_player_type(),
            "npc_player_draw_type": row.npc_player_draw_type(),
            "face_gen_id": face_id,
            "soul_lv": row.soul_lv(),
            "voice_type": row.voice_type(),
        });
        if face_id > 0 {
            if let Some(face) = repo.get::<FaceParam>(face_id as u32) {
                out["face"] = serde_json::json!({
                    "id": face_id,
                    "gender": face.gender(),
                    "age": face.age(),
                    "face_parts_id": face.face_parts_id(),
                    "body": [
                        face.chr_body_scale_head(),
                        face.chr_body_scale_breast(),
                        face.chr_body_scale_abdomen(),
                        face.chr_body_scale_r_arm(),
                        face.chr_body_scale_r_leg(),
                        face.chr_body_scale_l_arm(),
                        face.chr_body_scale_l_leg(),
                    ],
                });
            } else {
                out["face"] = serde_json::json!({ "id": face_id, "missing": true });
            }
        }
    } else {
        out["init"] = serde_json::json!({ "id": init_id, "missing": true });
    }
    Ok(out)
}

/// 把第 `profile_index` 个档案的体型（5 个滑条 + gender）写进
/// `CharaInitParam(init_id).npc_player_face_gen_id` 指向的 FACE_PARAM 行。
///
/// 验证用：改完 `resummon`，新召唤的克隆体会在建模型时读到这份体型。
/// 注意这是**共享**行 —— 三个克隆体会用同一个体型；正式版要给每号位各复制一行。
pub unsafe fn write_face_body_from_profile(
    init_id: u32,
    profile_index: usize,
) -> Result<serde_json::Value, String> {
    let profiles = crate::clone_profiles();
    if profiles.is_empty() {
        return Err("no clone profiles loaded".into());
    }
    let target = &profiles[profile_index % profiles.len()];
    let face_block = target.face();
    if face_block.len() < crate::profile::FACE_BODY_OFFSET + 5 {
        return Err("profile face block too short".into());
    }
    let body = &face_block[crate::profile::FACE_BODY_OFFSET..crate::profile::FACE_BODY_OFFSET + 5];
    let gender = target.body_type;

    let repo = repo().ok_or("no SoloParamRepository")?;
    let init = repo
        .get::<CharaInitParam>(init_id)
        .ok_or_else(|| format!("CharaInitParam {init_id} not found"))?;
    let face_id = init.npc_player_face_gen_id();
    if face_id <= 0 {
        return Err(format!("CharaInitParam {init_id}.npc_player_face_gen_id = {face_id}"));
    }
    let face = repo
        .get_mut::<FaceParam>(face_id as u32)
        .ok_or_else(|| format!("FaceParam {face_id} not found"))?;
    let before = [
        face.chr_body_scale_head(),
        face.chr_body_scale_breast(),
        face.chr_body_scale_abdomen(),
        face.chr_body_scale_r_arm(),
        face.chr_body_scale_r_leg(),
        face.chr_body_scale_l_arm(),
        face.chr_body_scale_l_leg(),
    ];
    let g_before = face.gender();
    face.set_chr_body_scale_head(body[0]);
    face.set_chr_body_scale_breast(body[1]);
    face.set_chr_body_scale_abdomen(body[2]);
    face.set_chr_body_scale_r_arm(body[3]);
    face.set_chr_body_scale_r_leg(body[4]);
    face.set_chr_body_scale_l_arm(body[3]);
    face.set_chr_body_scale_l_leg(body[4]);
    face.set_gender(gender);
    let after = [
        face.chr_body_scale_head(),
        face.chr_body_scale_breast(),
        face.chr_body_scale_abdomen(),
        face.chr_body_scale_r_arm(),
        face.chr_body_scale_r_leg(),
        face.chr_body_scale_l_arm(),
        face.chr_body_scale_l_leg(),
    ];
    log::info!(
        "face_row_body: init {init_id} -> FaceParam {face_id} '{}' body {before:?} -> {after:?}, gender {g_before} -> {gender}",
        target.name
    );
    Ok(serde_json::json!({
        "profile": target.name,
        "init_id": init_id,
        "face_id": face_id,
        "before": before,
        "after": after,
        "gender_before": g_before,
        "gender_after": gender,
    }))
}

// ---------------------------------------------------------------- 每号位体型（spawn 种子）

/// 拟态泪滴本体用的 init 行；我们的载体骨灰行默认也指向它。
pub const MIMIC_INIT_ROW: u32 = 26050;
const TEAMMATE_SLOTS: usize = 3;

static TEAMMATE_INIT_ROWS: Mutex<[u32; TEAMMATE_SLOTS]> = Mutex::new([0; TEAMMATE_SLOTS]);
static TEAMMATE_FACE_ROWS: Mutex<[u32; TEAMMATE_SLOTS]> = Mutex::new([0; TEAMMATE_SLOTS]);

pub fn teammate_init_rows() -> [u32; TEAMMATE_SLOTS] {
    TEAMMATE_INIT_ROWS.lock().map(|g| *g).unwrap_or([0; TEAMMATE_SLOTS])
}

pub fn teammate_face_rows() -> [u32; TEAMMATE_SLOTS] {
    TEAMMATE_FACE_ROWS.lock().map(|g| *g).unwrap_or([0; TEAMMATE_SLOTS])
}

fn copy_param_row<P: SoloParam + 'static>(
    repo: &mut SoloParamRepository,
    from: u32,
    to: u32,
) -> bool {
    let size = std::mem::size_of::<P::StructType>();
    let Some(src) = repo.get::<P>(from) else {
        return false;
    };
    let bytes = unsafe {
        std::slice::from_raw_parts(src as *const P::StructType as *const u8, size).to_vec()
    };
    let Some(dst) = repo.get_mut::<P>(to) else {
        return false;
    };
    unsafe {
        std::ptr::copy_nonoverlapping(
            bytes.as_ptr(),
            dst as *mut P::StructType as *mut u8,
            size,
        );
    }
    true
}

/// 给 1/2/3 号位各准备一行「出生参数」：把 26050 整行复制到空闲 init 行，
/// 再把该行指向的 FACE_PARAM 行里的体型（5 个滑条 + gender）改成对应档案。
///
/// 为什么要这么做：体型是**建模型时**从 `CharaInitParam -> FACE_PARAM` 烘焙的
/// （§28）；出生后再写 `PlayerGameData.face_data` 只改脸，不改身体。
///
/// 返回每个号位的 (profile, init_row, face_row, body, gender)。
pub unsafe fn setup_teammate_bodies(
    repo: &mut SoloParamRepository,
    profiles: &[crate::profile::Profile],
    buddy_rows: &[u32],
) -> Result<serde_json::Value, String> {
    if profiles.is_empty() {
        return Err("no profiles loaded".into());
    }
    let count = profiles.len();

    // 号位 -> 档案下标（和 auto_apply 的 slot_for_clone 完全一致）
    let mut targets = Vec::with_capacity(TEAMMATE_SLOTS);
    for i in 0..TEAMMATE_SLOTS {
        let slot = crate::roster::slot_for_clone(i, count);
        if slot < 0 {
            targets.push(None);
        } else {
            targets.push(Some((slot as usize) % count));
        }
    }
    if targets.iter().all(Option::is_none) {
        return Err("roster has no active slot".into());
    }

    // 1) 收集谁在用 init / face 行
    let mut init_ids: Vec<u32> = repo.rows::<CharaInitParam>().map(|(id, _)| id).collect();
    init_ids.sort_unstable();
    let mut used_init: Vec<u32> = repo
        .rows::<BuddyParam>()
        .map(|(_, r)| r.npc_player_init_param_id() as u32)
        .filter(|v| *v > 0)
        .collect();
    used_init.push(MIMIC_INIT_ROW);
    used_init.sort_unstable();
    used_init.dedup();

    let mut face_ids: Vec<u32> = repo.rows::<FaceParam>().map(|(id, _)| id).collect();
    face_ids.sort_unstable();
    let mut used_face: Vec<u32> = repo
        .rows::<CharaInitParam>()
        .map(|(_, r)| r.npc_player_face_gen_id() as u32)
        .filter(|v| *v > 0)
        .collect();
    used_face.sort_unstable();
    used_face.dedup();

    // 2) 选行：优先复用上次我们自己建的 3 行（它们已经被载体行引用，不算“别人在用”），
    //    不够再从大到小挑空闲行 —— 避免每次改人数/档案都吃掉新的备用行。
    let prev_init = teammate_init_rows();
    let prev_face = teammate_face_rows();
    let mut spare_init: Vec<u32> = prev_init
        .iter()
        .copied()
        .filter(|id| *id != 0 && init_ids.binary_search(id).is_ok())
        .collect();
    if spare_init.len() < TEAMMATE_SLOTS {
        for id in init_ids.iter().rev().copied() {
            if spare_init.contains(&id) || used_init.contains(&id) {
                continue;
            }
            spare_init.push(id);
            if spare_init.len() == TEAMMATE_SLOTS {
                break;
            }
        }
    }
    let mut spare_face: Vec<u32> = prev_face
        .iter()
        .copied()
        .filter(|id| *id != 0 && face_ids.binary_search(id).is_ok())
        .collect();
    if spare_face.len() < TEAMMATE_SLOTS {
        for id in face_ids.iter().rev().copied() {
            if spare_face.contains(&id) || used_face.contains(&id) {
                continue;
            }
            spare_face.push(id);
            if spare_face.len() == TEAMMATE_SLOTS {
                break;
            }
        }
    }
    if spare_init.len() < TEAMMATE_SLOTS || spare_face.len() < TEAMMATE_SLOTS {
        return Err(format!(
            "not enough spare rows: init {}/{} face {}/{} (used_init={} used_face={})",
            spare_init.len(),
            TEAMMATE_SLOTS,
            spare_face.len(),
            TEAMMATE_SLOTS,
            used_init.len(),
            used_face.len()
        ));
    }

    // 3) 为每个号位复制 init + face 行，并按档案写体型
    let mut out = Vec::with_capacity(TEAMMATE_SLOTS);
    let mut init_rows = [0u32; TEAMMATE_SLOTS];
    let mut face_rows = [0u32; TEAMMATE_SLOTS];
    for i in 0..TEAMMATE_SLOTS {
        let Some(pi) = targets[i] else { continue };
        let target = &profiles[pi];
        let face_block = target.face();
        if face_block.len() < crate::profile::FACE_BODY_OFFSET + 5 {
            return Err(format!("profile '{}' face block too short", target.name));
        }
        let body = &face_block[crate::profile::FACE_BODY_OFFSET..crate::profile::FACE_BODY_OFFSET + 5];

        let init_row = spare_init[i];
        let face_row = spare_face[i];
        if !copy_param_row::<CharaInitParam>(repo, MIMIC_INIT_ROW, init_row) {
            return Err(format!("copy CharaInitParam {MIMIC_INIT_ROW} -> {init_row} failed"));
        }
        if !copy_param_row::<FaceParam>(repo, 1, face_row) {
            return Err(format!("copy FaceParam 1 -> {face_row} failed"));
        }

        // init：性别（体型 A/B）+ 指向我们自己的 face 行
        if let Some(row) = repo.get_mut::<CharaInitParam>(init_row) {
            row.set_npc_player_sex(target.body_type);
            row.set_npc_player_face_gen_id(face_row as i32);
        }
        // face：5 个滑条 + gender（引擎内部的 gender 是 0..255，128 = 标准；
        // 体型 A/B 由 init.npc_player_sex 决定，这里只写 body 滑条）。
        if let Some(row) = repo.get_mut::<FaceParam>(face_row) {
            row.set_chr_body_scale_head(body[0]);
            row.set_chr_body_scale_breast(body[1]);
            row.set_chr_body_scale_abdomen(body[2]);
            row.set_chr_body_scale_r_arm(body[3]);
            row.set_chr_body_scale_r_leg(body[4]);
            row.set_chr_body_scale_l_arm(body[3]);
            row.set_chr_body_scale_l_leg(body[4]);
        }

        init_rows[i] = init_row;
        face_rows[i] = face_row;
        out.push(serde_json::json!({
            "slot": i,
            "profile": target.name,
            "profile_index": pi,
            "init_row": init_row,
            "face_row": face_row,
            "body_type": target.body_type,
            "body": body,
        }));
    }

    // 4) 载体骨灰行按号位指向各自 init 行
    let mut changed = 0usize;
    for (i, row_id) in buddy_rows.iter().take(TEAMMATE_SLOTS).enumerate() {
        if init_rows[i] == 0 {
            continue;
        }
        if let Some(row) = repo.get_mut::<BuddyParam>(*row_id) {
            if row.npc_player_init_param_id() != init_rows[i] as i32 {
                row.set_npc_player_init_param_id(init_rows[i] as i32);
                changed += 1;
            }
        }
    }

    if let Ok(mut g) = TEAMMATE_INIT_ROWS.lock() {
        *g = init_rows;
    }
    if let Ok(mut g) = TEAMMATE_FACE_ROWS.lock() {
        *g = face_rows;
    }
    log::info!(
        "setup_teammate_bodies: init={init_rows:?} face={face_rows:?} buddy_changed={changed} (profiles={count})"
    );
    Ok(serde_json::json!({
        "init_rows": init_rows,
        "face_rows": face_rows,
        "buddy_changed": changed,
        "slots": out,
    }))
}
