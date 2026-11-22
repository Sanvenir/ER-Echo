//! 同伴 AI：法术记忆槽（施法能力的开关）。
//!
//! 背景（2026-11-15 实测，见 docs/implementation-log.md §16）：
//! 克隆体是 `npc_param_id = 100000010`（拟态泪滴本体）的 `PlayerIns`，它的 AI
//! （`NpcThinkParam 100000010`）本身就会「学玩家」施法 —— 但**法术列表在它自己的
//! `EquipGameData.equip_magic_data` 里**，而我们把克隆体造出来时只注入了
//! 装备 22 槽 / 属性 / 脸，14 个记忆槽全是 `-1`：
//!
//! ```text
//! [magic] clone 'May' fp=95/95 slots=[-1 x14]   ← 没有法术可放，只能砍人
//! ```
//!
//! 所以「占星师不施法」不是 AI 权重的问题，是它**没带法术**。这里负责把
//! 记忆槽写进去（以及给一个「法术要 FP」的兜底）。

use eldenring::cs::{EquipMagicData, PlayerGameData};
use serde::{Deserialize, Deserializer, Serialize};

/// 记忆槽数量（`EquipMagicData.entries: [EquipMagicItem; 14]`）。
pub const MAGIC_SLOTS: usize = 14;

// ---------------------------------------------------------------- 队友 AI

/// 赐福菜单「队友 AI」里可以点的风格（每个队友独立保存到自己的 profile）。
///
/// 一个预设只覆盖 4 个**真正能落到运行期**的旋钮（见 `params::write_think_weights`）：
///
/// | 旋钮 | 落点 | 是否按队友分开 |
/// |---|---|---|
/// | `aggression` | 该队友 think 行的 `eye_dist / search_eye_dist / battle_start_dist / battle_eye_update_dist` | ✅ 每号位一行 |
/// | `guard_rate` | 该队友 think 行的 `is_guard_act`（`NpcParam` 的防御角度/减伤是共享行，仍跟全局） | ✅ |
/// | `target_switch` | 该队友 think 行的 `search_target_lv1/lv2_forget_time` | ✅ |
/// | `spell_rate` | **该克隆体自己的记忆槽开几发**（`kit::apply`，见 §17.2） | ✅ |
///
/// `dodge_rate / combo_rate / heal_priority / item_rate / spacing` 没有按实体区分的落点
/// （behavior 表是共享行且槽位语义未证实），所以不放进预设，避免菜单里给出无效选项。
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "snake_case")]
pub enum AiPreset {
    /// 均衡（= 出厂权重 0.5，和没设置时一样）
    #[default]
    Balanced,
    /// 近战：只砍不放法术
    Melee,
    /// 法术：记忆槽全开、拉开距离
    Caster,
    /// 守护：贴身举盾、少追人
    Guardian,
    /// 激进：交战半径最大、频繁换目标
    Aggressive,
}

/// 一个预设展开后的 4 个权重（0..1）。
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct AiWeights {
    pub aggression: f32,
    pub spell_rate: f32,
    pub guard_rate: f32,
    pub target_switch: f32,
}

impl AiPreset {
    /// 菜单里循环的顺序。
    pub const CYCLE: [Self; 5] = [
        Self::Balanced,
        Self::Melee,
        Self::Caster,
        Self::Guardian,
        Self::Aggressive,
    ];

    pub fn next(self) -> Self {
        let idx = Self::CYCLE.iter().position(|p| *p == self).unwrap_or(0);
        Self::CYCLE[(idx + 1) % Self::CYCLE.len()]
    }

    /// i18n 键（文案在 `i18n.rs`；也允许 `er_echo_i18n.ini` 覆盖）。
    pub fn key(self) -> &'static str {
        match self {
            Self::Balanced => "ai_balanced",
            Self::Melee => "ai_melee",
            Self::Caster => "ai_caster",
            Self::Guardian => "ai_guardian",
            Self::Aggressive => "ai_aggressive",
        }
    }

    /// 写进日志 / JSON 的稳定名字（和 profile 里 `"preset": "caster"` 一致）。
    pub fn code(self) -> &'static str {
        match self {
            Self::Balanced => "balanced",
            Self::Melee => "melee",
            Self::Caster => "caster",
            Self::Guardian => "guardian",
            Self::Aggressive => "aggressive",
        }
    }

    /// 从 IPC / ini 里的字符串解析（大小写不敏感，容忍几个别名）。
    pub fn parse(s: &str) -> Option<Self> {
        match s.trim().to_ascii_lowercase().as_str() {
            "balanced" | "balance" | "normal" | "b" => Some(Self::Balanced),
            "melee" | "fighter" | "m" => Some(Self::Melee),
            "caster" | "mage" | "spell" | "spellcaster" | "c" => Some(Self::Caster),
            "guardian" | "guard" | "tank" | "g" => Some(Self::Guardian),
            "aggressive" | "aggro" | "rush" | "a" => Some(Self::Aggressive),
            _ => None,
        }
    }

    pub fn weights(self) -> AiWeights {
        match self {
            Self::Balanced => AiWeights {
                aggression: 0.5,
                spell_rate: 0.5,
                guard_rate: 0.5,
                target_switch: 0.5,
            },
            Self::Melee => AiWeights {
                aggression: 0.75,
                spell_rate: 0.0,
                guard_rate: 0.25,
                target_switch: 0.5,
            },
            Self::Caster => AiWeights {
                aggression: 0.5,
                spell_rate: 1.0,
                guard_rate: 0.2,
                target_switch: 0.6,
            },
            Self::Guardian => AiWeights {
                aggression: 0.25,
                spell_rate: 0.3,
                guard_rate: 1.0,
                target_switch: 0.25,
            },
            Self::Aggressive => AiWeights {
                aggression: 1.0,
                spell_rate: 0.5,
                guard_rate: 0.15,
                target_switch: 0.9,
            },
        }
    }
}

/// profile JSON 里的 `ai` 段（`"ai": { "preset": "caster", ... }`）。
///
/// 数字字段和 `preset` 都写进去：菜单点的是预设，手改数字也认（这时菜单会显示「自定义」）。
/// 字段缺省 = 0.5（均衡），所以旧 profile 不需要补字段。
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct AiProfile {
    /// 预设名；不认识的字符串（手改打错）回退 `balanced`，不让整份 profile 解析失败。
    #[serde(default, deserialize_with = "deserialize_preset")]
    pub preset: AiPreset,
    #[serde(default = "half")]
    pub aggression: f32,
    #[serde(default = "half")]
    pub spell_rate: f32,
    #[serde(default = "half")]
    pub guard_rate: f32,
    #[serde(default = "half")]
    pub target_switch: f32,
}

fn half() -> f32 {
    0.5
}

fn deserialize_preset<'de, D>(deserializer: D) -> Result<AiPreset, D::Error>
where
    D: Deserializer<'de>,
{
    let raw = String::deserialize(deserializer)?;
    Ok(AiPreset::parse(&raw).unwrap_or(AiPreset::Balanced))
}

impl Default for AiProfile {
    fn default() -> Self {
        Self::from_preset(AiPreset::Balanced)
    }
}

impl AiProfile {
    pub fn from_preset(preset: AiPreset) -> Self {
        let w = preset.weights();
        Self {
            preset,
            aggression: w.aggression,
            spell_rate: w.spell_rate,
            guard_rate: w.guard_rate,
            target_switch: w.target_switch,
        }
    }

    /// 数值钳到 0..1（手改 profile 可能写出 2.0 / -1）。
    pub fn weights(&self) -> AiWeights {
        AiWeights {
            aggression: self.aggression.clamp(0.0, 1.0),
            spell_rate: self.spell_rate.clamp(0.0, 1.0),
            guard_rate: self.guard_rate.clamp(0.0, 1.0),
            target_switch: self.target_switch.clamp(0.0, 1.0),
        }
    }

    /// 菜单里显示的 i18n 键：数字被手改过就显示「自定义」。
    pub fn label_key(&self) -> &'static str {
        if self.weights() == self.preset.weights() {
            self.preset.key()
        } else {
            "ai_custom"
        }
    }

    /// 菜单点击：切到下一个预设（数字跟着重置）。
    pub fn cycle(self) -> Self {
        Self::from_preset(self.preset.next())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn preset_cycle_walks_all_and_wraps() {
        let mut p = AiPreset::Balanced;
        let mut seen = Vec::new();
        for _ in 0..AiPreset::CYCLE.len() {
            seen.push(p);
            p = p.next();
        }
        assert_eq!(seen, AiPreset::CYCLE.to_vec());
        assert_eq!(p, AiPreset::Balanced);
    }

    #[test]
    fn presets_are_clamped_and_distinct() {
        for p in AiPreset::CYCLE {
            let w = p.weights();
            for v in [w.aggression, w.spell_rate, w.guard_rate, w.target_switch] {
                assert!((0.0..=1.0).contains(&v), "{p:?} -> {v}");
            }
        }
        assert_eq!(AiPreset::Melee.weights().spell_rate, 0.0);
        assert_eq!(AiPreset::Caster.weights().spell_rate, 1.0);
        assert!(AiPreset::Guardian.weights().guard_rate > 0.9);
    }

    #[test]
    fn profile_defaults_to_balanced_half() {
        let ai: AiProfile = serde_json::from_str("{}").unwrap();
        assert_eq!(ai, AiProfile::from_preset(AiPreset::Balanced));
        assert_eq!(ai.weights().aggression, 0.5);
    }

    #[test]
    fn profile_parses_preset_and_numbers() {
        let ai: AiProfile =
            serde_json::from_str(r#"{"preset":"caster","spell_rate":0.5}"#).unwrap();
        assert_eq!(ai.preset, AiPreset::Caster);
        assert_eq!(ai.weights().spell_rate, 0.5);
        // 预设仍是 caster，但数字被改过 -> 显示「自定义」
        assert_eq!(ai.label_key(), "ai_custom");
    }

    #[test]
    fn presets_round_trip_through_json() {
        for p in AiPreset::CYCLE {
            let ai = AiProfile::from_preset(p);
            let text = serde_json::to_string(&ai).unwrap();
            let back: AiProfile = serde_json::from_str(&text).unwrap();
            assert_eq!(back, ai);
            assert_eq!(back.label_key(), p.key());
        }
    }

    #[test]
    fn cycle_from_custom_starts_from_its_preset() {
        let ai: AiProfile =
            serde_json::from_str(r#"{"preset":"melee","aggression":0.9}"#).unwrap();
        assert_eq!(ai.label_key(), "ai_custom");
        let next = ai.cycle();
        assert_eq!(next, AiProfile::from_preset(AiPreset::Caster));
    }

    #[test]
    fn parse_accepts_codes_and_aliases() {
        for p in AiPreset::CYCLE {
            assert_eq!(AiPreset::parse(p.code()), Some(p));
            assert_eq!(AiPreset::parse(&p.code().to_uppercase()), Some(p));
        }
        assert_eq!(AiPreset::parse("mage"), Some(AiPreset::Caster));
        assert_eq!(AiPreset::parse("tank"), Some(AiPreset::Guardian));
        assert_eq!(AiPreset::parse("nope"), None);
    }

    #[test]
    fn unknown_preset_falls_back_instead_of_breaking_the_profile() {
        let ai: AiProfile =
            serde_json::from_str(r#"{"preset":"wizard","spell_rate":0.9}"#).unwrap();
        assert_eq!(ai.preset, AiPreset::Balanced);
        assert_eq!(ai.weights().spell_rate, 0.9);
        assert_eq!(ai.label_key(), "ai_custom");
    }
}

/// 记忆槽一项：法术 `Magic` param id + 蓄能（`-1` = 空槽）。
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MagicSlot {
    pub id: i32,
    pub charges: i32,
}

impl MagicSlot {
    pub const EMPTY: Self = Self {
        id: -1,
        charges: -1,
    };

    pub fn is_empty(self) -> bool {
        self.id <= 0
    }
}

/// 一次读取的快照（诊断用）。
#[derive(Debug, Clone)]
pub struct MagicState {
    /// `equip_magic_data` 原始指针（0 说明这个 PlayerIns 还没有这套数据）
    pub ptr: usize,
    pub selected: i32,
    pub unlocked: u8,
    pub effective_unlocked: u32,
    pub slots: [MagicSlot; MAGIC_SLOTS],
}

impl MagicState {
    pub fn equipped(&self) -> impl Iterator<Item = MagicSlot> + '_ {
        self.slots.iter().copied().filter(|s| !s.is_empty())
    }
}

/// `equip_magic_data` 是 `OwnedPtr`（内部 `NonNull`）——对 `NonNull` 做 null 判断
/// 会被编译器当成 UB 直接删掉（§15.5 两次闪退的根因），所以只能按原始 `usize` 读。
///
/// SAFETY: `pgd` 必须指向存活的 `PlayerGameData`。
pub unsafe fn magic_ptr(pgd: &PlayerGameData) -> usize {
    let field = std::ptr::addr_of!(pgd.equipment.equip_magic_data);
    std::ptr::read(std::hint::black_box(field) as *const usize)
}

/// 读一个 PlayerIns 的记忆槽。
///
/// SAFETY: `pgd` 必须存活；主线程调用。
pub unsafe fn snapshot(pgd: &PlayerGameData) -> MagicState {
    let mut state = MagicState {
        ptr: magic_ptr(pgd),
        selected: 0,
        unlocked: pgd.unlocked_magic_slots,
        effective_unlocked: pgd.effective_unlocked_magic_slots,
        slots: [MagicSlot::EMPTY; MAGIC_SLOTS],
    };
    if state.ptr == 0 {
        return state;
    }
    let data = &*(state.ptr as *const EquipMagicData);
    state.selected = data.selected_slot;
    for (dst, src) in state.slots.iter_mut().zip(data.entries.iter()) {
        *dst = MagicSlot {
            id: src.param_id,
            charges: src.charges,
        };
    }
    state
}

/// 写记忆槽，返回实际写入的槽数（0 = 没有 `equip_magic_data` 或全是空槽）。
///
/// 只写 `entries` / `selected_slot` / 槽位解锁数，**不碰** `equip_game_data` 回指指针
/// （那是引擎用来找背包的，写错会崩）。
///
/// SAFETY: `pgd` 必须存活；`slots` 里的 id 必须存在（否则相当于给了个非法法术）。
pub unsafe fn write(pgd: &mut PlayerGameData, slots: &[MagicSlot]) -> usize {
    let ptr = magic_ptr(pgd);
    if ptr == 0 {
        return 0;
    }
    let data = &mut *(ptr as *mut EquipMagicData);
    let mut written = 0;
    for (i, entry) in data.entries.iter_mut().enumerate() {
        let slot = slots.get(i).copied().unwrap_or(MagicSlot::EMPTY);
        if slot.is_empty() {
            entry.param_id = -1;
            entry.charges = -1;
            continue;
        }
        entry.param_id = slot.id;
        // 存档/玩家侧已装备的记忆槽是 `charges = -1`（无限次）；写成 0/1 会让引擎
        // 施放一次后把槽当成「耗尽」，AI 就再也不放这个法术了。
        entry.charges = if slot.charges == 0 { -1 } else { slot.charges };
        written += 1;
    }
    if written > 0 {
        data.selected_slot = 0;
        // 记忆槽数量：引擎/UI 看这两个，写小了会出现「有法术但槽位没开」。
        let need = written.min(u8::MAX as usize) as u8;
        pgd.unlocked_magic_slots = pgd.unlocked_magic_slots.max(need);
        pgd.effective_unlocked_magic_slots = pgd.effective_unlocked_magic_slots.max(written as u32);
    }
    written
}

/// 把当前 FP 顶到上限。
///
/// 克隆体的 FP 上限来自档案 `pools.fp`，但「当前值」是造出来那一刻的，之后只减不增；
/// 放几个法术就干了。同伴当「无限蓝」处理，AI 才有持续施法的机会。
pub fn top_up_fp(pgd: &mut PlayerGameData, ratio: f32) {
    if pgd.current_max_fp == 0 {
        return;
    }
    let target = (pgd.current_max_fp as f32 * ratio.clamp(0.0, 1.0)) as u32;
    if pgd.current_fp < target {
        pgd.current_fp = target;
    }
}
