//! 克隆体注入：把目标档案直接写进「已召唤的 PlayerIns」（不改玩家）。
//!
//! 依据（2026-11-15 实测，见 docs/implementation-log.md §11/§12）：
//! 泪滴本体 `npc_param_id = 100000010` 是一个 `PlayerIns`，自带 `PlayerGameData`
//! （`face_data` + `chr_asm`），所以外观/装备可以「召唤后注入」，
//! 不必先改玩家外形再让引擎复制。
//!
//! 注入点（三处都写，实测哪个生效见 §12.5）：
//!   1. `PlayerIns.chr_asm.equipment_param_ids[22]`      —— 渲染用的 ChrAsm（玩家换装走这里，已验证）
//!   2. `PlayerGameData.equipment.chr_asm`               —— PGD 内部那份 ChrAsm（可能才是引擎真源）
//!   3. `PlayerGameData.equipment.equipment_entries`     —— 带 category 的 ItemId（引擎刷新时可能以它为准）
//!   4. `PlayerGameData.face_data.face_data_buffer`      —— 捏脸数据（276B，已实测可写）
//!
//! 注意：引擎在「史莱姆 → 人形」变身/重招时可能重新复制玩家数据，
//! 所以调用方要**持续**注入（每 N 帧），而不是只写一次。

use eldenring::cs::{ItemCategory, ItemId, OptionalItemId, PlayerGameData, PlayerIns};

use crate::profile::{self, Profile, FACE_PAYLOAD_LEN, SLOT_COUNT};

#[derive(Debug, Default, Clone, Copy)]
pub struct Applied {
    pub equip: u32,
    pub face: u32,
    /// 体型（gender + FaceData 的 7 个 f32 缩放）写了几份
    pub body: u32,
    pub stats: u32,
    /// 写进去的记忆法术槽数（0 = 档案没带法术 / 克隆体还没这套数据）
    pub magic: u32,
    /// 档案里非空的法术数
    pub magic_total: u32,
    /// 按 `spell_rate` 实际开了几发
    pub magic_used: u32,
    /// 写完后立刻回读的 22 个槽（判断有没有被引擎覆盖）
    pub readback: [i32; SLOT_COUNT],
}

/// `PlayerIns` 内部与 FaceData 同步的 7 个体型 f32（0x650 起）。
///
/// 实测：引擎会把 `PlayerGameData.face_data.unk130` 同步到这里（地图上一只克隆体
/// 的 0x650 与它 PGD 的 0x890 完全一致）；只改一边时另一边会被引擎刷回。
pub const PLAYER_INS_BODY_SCALES: usize = 0x650;
const _: () = assert!(std::mem::size_of::<PlayerIns>() >= PLAYER_INS_BODY_SCALES + 28);
const BODY_SCALE_BYTES: usize = 7 * 4;

/// 写入体型：`gender`（体型 A/B）+ 引擎解析缓存里的 7 个 f32 缩放。
///
/// 为什么要两份：脸缓冲（276B）只是序列化数据，引擎渲染体型读的是解析后的
/// `FaceData.unk130`；`PlayerIns + 0x650` 又是一份会被引擎回写的副本。
/// 三处（缓冲、FaceData float、PlayerIns float）都写才不会被刷回。
///
/// SAFETY: 主线程；`p` 必须是存活 PlayerIns。
pub unsafe fn apply_body(p: &mut PlayerIns, target: &Profile) -> bool {
    let face = target.face();
    let Some(scales) = profile::body_scales_from_face(&face) else {
        return false;
    };
    let pgd = p.player_game_data.as_mut();
    // 存档 `body_type`（+0xB6）就是运行时的 `gender`（体型 A/B）。
    pgd.gender = target.body_type;
    let fd = &mut pgd.face_data as *mut eldenring::cs::FaceData as *mut u8;
    std::ptr::copy_nonoverlapping(
        scales.as_ptr() as *const u8,
        fd.add(profile::FACE_BODY_SCALES_OFFSET),
        BODY_SCALE_BYTES,
    );
    let ins = p as *mut PlayerIns as *mut u8;
    std::ptr::copy_nonoverlapping(
        scales.as_ptr() as *const u8,
        ins.add(PLAYER_INS_BODY_SCALES),
        BODY_SCALE_BYTES,
    );
    true
}

/// 把档案写进一个克隆体。返回实际写入的字段。
///
/// `spell_rate` = LLM 的「法术倾向」（0~1）。这是目前**唯一能真正控制施法**的落点：
/// 拟态 think 行里没有「施法概率」这种字段（§17.2 实测），所以用「记忆槽里开几发」
/// 来表达倾向 —— 0 = 关法术（纯近战），0.5 = 只开第一发，1 = 全开。
///
/// SAFETY: 主线程调用；`p` 必须是当前存活的 PlayerIns（召唤物集合里的那个人形）。
pub unsafe fn apply(
    p: &mut PlayerIns,
    target: &Profile,
    write_stats: bool,
    spell_rate: f32,
) -> Applied {
    let mut out = Applied::default();

    if target.equipment_param_ids.len() == SLOT_COUNT {
        let ids = target.equipment_param_ids.clone();
        // 1) PlayerIns 自己的 ChrAsm（玩家换装走的就是这条，已验证会重绘）
        {
            let asm = p.chr_asm.as_mut();
            write_asm(asm, &ids);
        }
        // 2) PGD 内部的 ChrAsm + 3) 带 category 的 ItemId 表
        {
            let pgd = p.player_game_data.as_mut();
            write_asm(&mut pgd.equipment.chr_asm, &ids);
            write_equipment_entries(&mut pgd.equipment.equipment_entries, &ids);
        }
        out.equip = 1;
        out.readback = p.chr_asm.as_ref().equipment_param_ids;
    }

    let face = target.face();
    if face.len() >= profile::FACE_PAYLOAD_OFFSET + FACE_PAYLOAD_LEN {
        let pgd = p.player_game_data.as_mut();
        let mut backup = [0u8; FACE_PAYLOAD_LEN];
        if profile::apply_face_from_profile(pgd, &face, &mut backup) {
            out.face = 1;
            if write_stats {
                apply_stats(pgd, target);
                out.stats = 1;
            }
        }
    }
    // 体型：gender（A/B）+ 解析缓存里的 7 个 f32 缩放。
    // 只写缓冲不够 —— 见 apply_body 的注释 / §28。
    if unsafe { apply_body(p, target) } {
        out.body = 1;
    }

    // 记忆法术：AI 会施法，但法术列表是「每个 PlayerIns 自己一份」，不写就永远空手。
    //
    // 这里同时实现 `spell_rate` 权重：按比例决定「开几发法术」。
    //   spell_rate < 0.1 → 清空记忆槽（纯近战）
    //   0.1~1          → 开 ceil(rate * 非空法术数) 发（至少 1 发）
    // 这样 LLM 说「别放法术」和「全开」都有可见效果（`status` 里的 magic 少/多）。
    if !target.magic.is_empty() {
        let ids: Vec<i32> = target.magic.iter().copied().filter(|id| *id > 0).collect();
        let total = ids.len();
        let rate = spell_rate.clamp(0.0, 1.0);
        let take = if rate < 0.1 || total == 0 {
            0
        } else {
            ((rate * total as f32).ceil() as usize).clamp(1, total)
        };
        let slots: Vec<crate::ai::MagicSlot> = ids
            .iter()
            .take(take)
            .map(|&id| crate::ai::MagicSlot { id, charges: -1 })
            .collect();
        let pgd = p.player_game_data.as_mut();
        let n = unsafe { crate::ai::write(pgd, &slots) };
        out.magic = if take == 0 { 0 } else { n as u32 };
        out.magic_total = total as u32;
        out.magic_used = take as u32;
    }

    out
}

fn write_asm(asm: &mut eldenring::cs::ChrAsm, ids: &[i32]) {
    for (slot, id) in asm.equipment_param_ids.iter_mut().zip(ids.iter().copied()) {
        *slot = id;
    }
}

/// 22 槽的 category 规则：0–11 武器/箭矢（Weapon 表），12–15 防具（Protector），
/// 16 是 hair/unused，17–21 护符（Accessory）。`<= 0` 视为空槽。
pub(crate) fn slot_category(slot: usize) -> Option<ItemCategory> {
    match slot {
        0..=11 => Some(ItemCategory::Weapon),
        12..=15 => Some(ItemCategory::Protector),
        17..=21 => Some(ItemCategory::Accessory),
        _ => None,
    }
}

fn write_equipment_entries(entries: &mut eldenring::cs::ChrAsmEquipEntries, ids: &[i32]) {
    for (slot, &id) in ids.iter().enumerate() {
        let Some(category) = slot_category(slot) else {
            continue;
        };
        let value = if id > 0 {
            match ItemId::new(category, id as u32) {
                Ok(item) => OptionalItemId::from(item),
                Err(_) => OptionalItemId::NONE,
            }
        } else {
            OptionalItemId::NONE
        };
        // 注意：武器/防具/护符字段是 `ItemId`，箭矢/尾巴是 `OptionalItemId`；
        // 统一写到底层 `OptionalItemId`（ItemId::as_optional_mut）。
        let dst: &mut OptionalItemId = match slot {
            0 => entries.weapon_primary_left.as_optional_mut(),
            1 => entries.weapon_primary_right.as_optional_mut(),
            2 => entries.weapon_secondary_left.as_optional_mut(),
            3 => entries.weapon_secondary_right.as_optional_mut(),
            4 => entries.weapon_tertiary_left.as_optional_mut(),
            5 => entries.weapon_tertiary_right.as_optional_mut(),
            6 => &mut entries.arrow_primary,
            7 => &mut entries.bolt_primary,
            8 => &mut entries.arrow_secondary,
            9 => &mut entries.bolt_secondary,
            10 => &mut entries.arrow_tertiary,
            11 => &mut entries.bolt_tertiary,
            12 => entries.protector_head.as_optional_mut(),
            13 => entries.protector_chest.as_optional_mut(),
            14 => entries.protector_hands.as_optional_mut(),
            15 => entries.protector_legs.as_optional_mut(),
            17 => &mut entries.accessories[0],
            18 => &mut entries.accessories[1],
            19 => &mut entries.accessories[2],
            20 => &mut entries.accessories[3],
            21 => &mut entries.covenant,
            _ => continue,
        };
        *dst = value;
    }
}

/// 写等级/属性/三围上限。
///
/// `level` + 8 维属性是引擎算派生值（HP/FP/耐力上限、负重、攻击力）的输入，
/// 但引擎**不会**因为属性被改写就自动重算 —— 所以如果档案里带了离线导出的
/// `pools`（存档里引擎算好的最终值），这里直接抄过去，克隆体的血量才和本体一致。
pub unsafe fn apply_stats(pgd: &mut PlayerGameData, target: &Profile) {
    let s = &target.stats;
    pgd.level = target.level;
    pgd.vigor = s.vigor;
    pgd.mind = s.mind;
    pgd.endurance = s.endurance;
    pgd.strength = s.strength;
    pgd.dexterity = s.dexterity;
    pgd.intelligence = s.intelligence;
    pgd.faith = s.faith;
    pgd.arcane = s.arcane;
    // effective_* 是「加成后」的值；不写的话 UI/伤害计算仍按旧值。
    pgd.effective_vigor = s.vigor;
    pgd.effective_mind = s.mind;
    pgd.effective_endurance = s.endurance;
    pgd.effective_vitality = s.vigor;
    pgd.effective_strength = s.strength;
    pgd.effective_dexterity = s.dexterity;
    pgd.effective_intelligence = s.intelligence;
    pgd.effective_faith = s.faith;
    pgd.effective_arcane = s.arcane;

    if let Some(pools) = target.pools {
        // base_max_* 是「基础值」，current_max_* 是含护符/增益的最终值；两者都写。
        // 注意：auto_apply 每 15 帧会重跑一次注入，所以「当前值」不能直接写成满血，
        // 否则克隆体永远不掉血。这里只把超出新上限的当前值压回来（幂等），不主动回血。
        pgd.current_max_hp = pools.hp;
        pgd.base_max_hp = pools.hp;
        pgd.current_hp = pgd.current_hp.min(pools.hp);
        pgd.current_max_fp = pools.fp;
        pgd.base_max_fp = pools.fp;
        pgd.current_fp = pgd.current_fp.min(pools.fp);
        pgd.current_max_stamina = pools.stamina;
        pgd.base_max_stamina = pools.stamina;
        pgd.current_stamina = pgd.current_stamina.min(pools.stamina);
    }
}
