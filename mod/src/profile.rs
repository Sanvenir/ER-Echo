//! 角色档案（离线导出 → 运行时应用）
//!
//! 存档侧字段与偏移见 `docs/design.md` §7；这里只负责「内存中的 profile」。
//! 注意：`ChrAsm.equipment_param_ids` 是 22 个 i32 槽，顺序与存档 PGD+0x58 表一致。

use serde::{Deserialize, Serialize};

pub const SLOT_COUNT: usize = 22;
pub const FACE_SIZE: usize = 0x12F;
pub const MAX_LEVEL: u32 = 713;
pub const MAX_STAT: u32 = 99;
pub const MIN_STAT: u32 = 1;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Profile {
    pub v: u32,
    #[serde(default)]
    pub source: Source,
    pub name: String,
    pub level: u32,
    pub stats: Stats,
    pub equipment_param_ids: Vec<i32>,
    #[serde(default)]
    pub face_hex: String,
    #[serde(default)]
    pub body_type: u8,
    #[serde(default)]
    pub summon_spirit_level: u8,
    #[serde(default)]
    pub scadutree_blessing: u8,
    /// 存档里引擎算好的 HP/FP/耐力上限（离线导出时直接抄，不用按属性表重算）
    #[serde(default)]
    pub pools: Option<Pools>,
    #[serde(default)]
    pub resistances: Option<Vec<u32>>,
    /// 记忆法术 14 槽（`Magic` param id，`-1`/缺省 = 空槽）。
    ///
    /// 这条是「占星师不施法」的解法：克隆体的 AI 会施法，但法术列表在它自己的
    /// `EquipGameData.equip_magic_data` 里，不注入就是空手砍人（见 log §16）。
    #[serde(default)]
    pub magic: Vec<i32>,
    /// 已解锁的记忆槽数量（缺省 = 按非空槽数自动给）
    #[serde(default)]
    pub unlocked_magic_slots: u8,
    /// 这个队友自己的 AI 风格（赐福菜单「队友 AI」写入；缺省 = 跟随全局权重）。
    ///
    /// 写在**档案**里而不是 roster 里：换一套 profiles、换一个号，AI 风格跟着角色走；
    /// 同一个档案被两个号位选中时两者共享这份 AI。
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub ai: Option<crate::ai::AiProfile>,
    /// 装备表的原始 i32（未掩码），仅留档，注入只用 equipment_param_ids
    #[serde(default)]
    pub equipment_raw: Option<Vec<i32>>,
}

/// 三围池上限。存档 PGD 里存的就是最终的「当前/上限」，比按属性重算靠谱。
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Pools {
    pub hp: u32,
    pub fp: u32,
    pub stamina: u32,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Source {
    #[serde(default)]
    pub slot: u8,
    #[serde(default)]
    pub steam_id: String,
    #[serde(default)]
    pub exported_by: String,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Stats {
    pub vigor: u32,
    pub mind: u32,
    pub endurance: u32,
    pub strength: u32,
    pub dexterity: u32,
    pub intelligence: u32,
    pub faith: u32,
    pub arcane: u32,
}

impl Profile {
    pub fn load(path: &str) -> Result<Self, String> {
        let text = std::fs::read_to_string(path).map_err(|e| format!("read {path}: {e}"))?;
        let profile: Profile = serde_json::from_str(&text).map_err(|e| format!("parse: {e}"))?;
        profile.validate()?;
        Ok(profile)
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.v != 1 {
            return Err(format!("unsupported profile version {}", self.v));
        }
        if self.equipment_param_ids.len() != SLOT_COUNT {
            return Err(format!(
                "equipment_param_ids must have {SLOT_COUNT} entries, got {}",
                self.equipment_param_ids.len()
            ));
        }
        if self.face().len() != FACE_SIZE {
            return Err(format!(
                "face data must be 0x{FACE_SIZE:X} bytes, got {}",
                self.face().len()
            ));
        }
        if self.magic.len() > crate::ai::MAGIC_SLOTS {
            return Err(format!(
                "magic must have at most {} entries, got {}",
                crate::ai::MAGIC_SLOTS,
                self.magic.len()
            ));
        }
        Ok(())
    }

    pub fn face(&self) -> Vec<u8> {
        // 容忍两种写法：纯 hex，或 "0x..." 前缀
        let hex = self.face_hex.trim().trim_start_matches("0x");
        (0..hex.len() / 2)
            .filter_map(|i| u8::from_str_radix(&hex[i * 2..i * 2 + 2], 16).ok())
            .collect()
    }

    /// 玩家升级时把「同样的升级」追给这份档案。
    ///
    /// `stat_deltas` 是玩家 8 维属性的增量（顺序 Vig/Mind/End/Str/Dex/Int/Fai/Arc），
    /// `pool_deltas` 是 HP/FP/耐力上限的绝对增量（玩家升级时引擎算出来的差值）。
    /// 返回是否有字段真的变了。
    pub fn apply_level_up(
        &mut self,
        level_delta: u32,
        stat_deltas: &[i64; 8],
        pool_deltas: [u32; 3],
    ) -> bool {
        if level_delta == 0 && stat_deltas.iter().all(|d| *d == 0) {
            return false;
        }
        let before = (
            self.level,
            self.stats.vigor,
            self.stats.mind,
            self.stats.endurance,
            self.stats.strength,
            self.stats.dexterity,
            self.stats.intelligence,
            self.stats.faith,
            self.stats.arcane,
            self.pools.map(|p| (p.hp, p.fp, p.stamina)),
        );

        self.level = self.level.saturating_add(level_delta).min(MAX_LEVEL);
        let s = &mut self.stats;
        s.vigor = bump_stat(s.vigor, stat_deltas[0]);
        s.mind = bump_stat(s.mind, stat_deltas[1]);
        s.endurance = bump_stat(s.endurance, stat_deltas[2]);
        s.strength = bump_stat(s.strength, stat_deltas[3]);
        s.dexterity = bump_stat(s.dexterity, stat_deltas[4]);
        s.intelligence = bump_stat(s.intelligence, stat_deltas[5]);
        s.faith = bump_stat(s.faith, stat_deltas[6]);
        s.arcane = bump_stat(s.arcane, stat_deltas[7]);
        if let Some(pools) = &mut self.pools {
            pools.hp = pools.hp.saturating_add(pool_deltas[0]);
            pools.fp = pools.fp.saturating_add(pool_deltas[1]);
            pools.stamina = pools.stamina.saturating_add(pool_deltas[2]);
        }

        before
            != (
                self.level,
                self.stats.vigor,
                self.stats.mind,
                self.stats.endurance,
                self.stats.strength,
                self.stats.dexterity,
                self.stats.intelligence,
                self.stats.faith,
                self.stats.arcane,
                self.pools.map(|p| (p.hp, p.fp, p.stamina)),
            )
    }
}

fn bump_stat(current: u32, delta: i64) -> u32 {
    (current as i64 + delta).clamp(MIN_STAT as i64, MAX_STAT as i64) as u32
}

/// 把 profile 的装备 id 写进 ChrAsm 的 22 个槽。
///
/// SAFETY: 调用方必须保证 `chr_asm` 指向一个已初始化、当前存活的 ChrAsm，
/// 并且 `equipment_param_ids` 里的 id 全部存在（否则可能 T-pose / 崩溃）。
pub unsafe fn apply_equipment(chr_asm: *mut eldenring::cs::ChrAsm, ids: &[i32]) {
    let asm = &mut *chr_asm;
    for (slot, id) in asm.equipment_param_ids.iter_mut().zip(ids.iter().copied()) {
        *slot = id;
    }
}

// TODO(Phase 2)：外观注入。
// 两条路：
//   A) 写 `PlayerIns.player_game_data.face_data.face_data_buffer`，然后触发模型重建
//      （重建函数未公开，需要 RE；或借 Mimic Tear 召唤瞬间的复制路径）；
//   B) 离线把 0x12F 块写进当前活跃槽的 face_data，再进游戏召唤（见 design.md §6 路线 A）。
#[allow(dead_code)]
pub unsafe fn apply_face(_player_game_data: *mut eldenring::cs::PlayerGameData, _face: &[u8]) {
    todo!("Phase 2: face injection — see docs/design.md §6 / §7.3")
}

/// 运行时 FaceDataBuffer.buffer 是 276 字节，对应存档 FaceData 块的 `[0x10..0x124]`
/// （即去掉 marker/magic/size 头与尾部的 FaceParam override 字段）。
pub const FACE_PAYLOAD_OFFSET: usize = 0x10;
pub const FACE_PAYLOAD_LEN: usize = 0x114; // 276

/// 0x12F 块里的 5 个体型滑条（相对块起点，u8，128 = 标准）。
///
/// 布局按 ER-Save-Lib 的 `FaceData`：0x6C 起 64B FaceGen 参数，0xB0 起
/// head/chest/abdomen/arms/legs，0xB5..0xB7 再跟 2B 保留 + 肤色。
pub const FACE_BODY_OFFSET: usize = 0xB0;
/// 运行时 `PlayerGameData.face_data` 里引擎解析好的 7 个体型 f32
/// （`FaceData` 的 `unk130`）：头/胸/腹/右臂/右腿/左臂/左腿。
///
/// 实测映射：`f = (byte - 127.5) / 127.5`（byte 128 → 0.0，0 → -1，255 → +1），
/// 左右臂/腿各复制一份。见 docs/implementation-log.md §28。
pub const FACE_BODY_SCALES_OFFSET: usize = 0x130;
pub const BODY_SCALE_COUNT: usize = 7;

/// 从 profile 的 0x12F 脸块推出 7 个体型缩放 f32（引擎模型实际读的那份）。
///
/// 只写 276B 缓冲不够：克隆体出生时 `FaceData.unk130` 是标准值（128 → 1/255），
/// 引擎渲染体型读的是这 7 个 float，不是缓冲里的 u8。所以每次注入都要把两者一起写。
pub fn body_scales_from_face(face: &[u8]) -> Option<[f32; BODY_SCALE_COUNT]> {
    if face.len() < FACE_BODY_OFFSET + 5 {
        return None;
    }
    let b = &face[FACE_BODY_OFFSET..];
    let scale = |v: u8| (v as f32 - 127.5) / 127.5;
    Some([
        scale(b[0]), // head
        scale(b[1]), // chest
        scale(b[2]), // abdomen
        scale(b[3]), // right arm（引擎用同一份 arm）
        scale(b[4]), // right leg
        scale(b[3]), // left arm
        scale(b[4]), // left leg
    ])
}

/// 把 profile 的 FaceData 写进玩家运行时缓冲，并备份旧值。
///
/// SAFETY: 只能在主线程调用；`pgd` 必须指向存活的 PlayerGameData。
pub unsafe fn apply_face_from_profile(
    pgd: &mut eldenring::cs::PlayerGameData,
    face: &[u8],
    backup: &mut [u8; FACE_PAYLOAD_LEN],
) -> bool {
    if face.len() < FACE_PAYLOAD_OFFSET + FACE_PAYLOAD_LEN {
        return false;
    }
    let buf = &mut pgd.face_data.face_data_buffer.buffer;
    backup.copy_from_slice(buf);
    let src = &face[FACE_PAYLOAD_OFFSET..FACE_PAYLOAD_OFFSET + FACE_PAYLOAD_LEN];
    buf.copy_from_slice(src);
    true
}

/// 还原玩家脸部缓冲。
pub unsafe fn restore_face(pgd: &mut eldenring::cs::PlayerGameData, backup: &[u8; FACE_PAYLOAD_LEN]) {
    let buf = &mut pgd.face_data.face_data_buffer.buffer;
    buf.copy_from_slice(backup);
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> Profile {
        Profile {
            v: 1,
            source: Source::default(),
            name: "test".into(),
            level: 10,
            stats: Stats {
                vigor: 12,
                mind: 10,
                endurance: 11,
                strength: 12,
                dexterity: 12,
                intelligence: 9,
                faith: 9,
                arcane: 7,
            },
            equipment_param_ids: vec![0; SLOT_COUNT],
            face_hex: String::new(),
            body_type: 0,
            summon_spirit_level: 0,
            scadutree_blessing: 0,
            pools: Some(Pools {
                hp: 500,
                fp: 95,
                stamina: 100,
            }),
            resistances: None,
            magic: Vec::new(),
            unlocked_magic_slots: 0,
            ai: None,
            equipment_raw: None,
        }
    }

    #[test]
    fn level_up_copies_player_growth() {
        let mut p = sample();
        let deltas = [1, 0, 0, 0, 0, 0, 0, 0];
        assert!(p.apply_level_up(1, &deltas, [30, 0, 2]));
        assert_eq!(p.level, 11);
        assert_eq!(p.stats.vigor, 13);
        assert_eq!(p.stats.mind, 10);
        assert_eq!(p.pools.unwrap().hp, 530);
        assert_eq!(p.pools.unwrap().stamina, 102);
    }

    #[test]
    fn level_up_is_capped() {
        let mut p = sample();
        p.level = MAX_LEVEL;
        p.stats.vigor = MAX_STAT;
        let deltas = [1, 0, 0, 0, 0, 0, 0, 0];
        assert!(p.apply_level_up(5, &deltas, [10, 0, 0]));
        assert_eq!(p.level, MAX_LEVEL);
        assert_eq!(p.stats.vigor, MAX_STAT);
    }

    #[test]
    fn level_up_without_pools_keeps_none() {
        let mut p = sample();
        p.pools = None;
        let deltas = [0, 1, 0, 0, 0, 0, 0, 0];
        assert!(p.apply_level_up(1, &deltas, [30, 0, 0]));
        assert_eq!(p.stats.mind, 11);
        assert!(p.pools.is_none());
    }

    #[test]
    fn level_up_noop_returns_false() {
        let mut p = sample();
        assert!(!p.apply_level_up(0, &[0; 8], [0, 0, 0]));
        assert_eq!(p.level, 10);
    }

    #[test]
    fn old_profile_without_ai_still_parses_and_omits_it() {
        let mut p = sample();
        let text = serde_json::to_string(&p).unwrap();
        assert!(
            !text.contains("\"ai\""),
            "unset ai must not be written: {text}"
        );
        let back: Profile = serde_json::from_str(&text).unwrap();
        assert!(back.ai.is_none());

        p.ai = Some(crate::ai::AiProfile::from_preset(
            crate::ai::AiPreset::Caster,
        ));
        let text = serde_json::to_string(&p).unwrap();
        let back: Profile = serde_json::from_str(&text).unwrap();
        assert_eq!(
            back.ai.map(|a| a.preset),
            Some(crate::ai::AiPreset::Caster)
        );
    }
}
