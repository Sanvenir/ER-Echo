//! 运行时数据导出：不需要 Smithbox，也能看到真实的 param 行。
//!
//! 命令（IPC）：
//!   dump_buddies  → er_echo_buddies.json   所有 BuddyParam 行（找 Mimic Tear / 骨灰）
//!   dump_ride     → er_echo_ride.json      所有 RideParam 行（找 c0000 ↔ 坐骑）
//!   dump_profile  → er_echo_profile.json   当前玩家等级/属性/装备/脸数据
//!
//! 这些文件是「实现 fan-out / 骑乘」的输入：知道行 id 后，DLL 才能在运行时改行。

use eldenring::cs::{BuddyParam, Magic, NpcParam, NpcThinkParam, PlayerIns, RideParam, SoloParamRepository};
use fromsoftware_shared::FromStatic;
use serde_json::json;

fn write_json(name: &str, value: &serde_json::Value) -> Result<String, String> {
    let text = serde_json::to_string_pretty(value).map_err(|e| e.to_string())?;
    std::fs::write(name, &text).map_err(|e| format!("write {name}: {e}"))?;
    Ok(format!("{name}: {} bytes", text.len()))
}

/// 把 `ChrAsmEquipEntries` 按 22 槽顺序展开成 param id（空槽 = -1），
/// 用来和 `ChrAsm.equipment_param_ids` 对照。
fn equipment_entry_param_ids(entries: &eldenring::cs::ChrAsmEquipEntries) -> Vec<i64> {
    let id = |v: &eldenring::cs::OptionalItemId| v.param_id().map(|x| x as i64).unwrap_or(-1);
    vec![
        id(&entries.weapon_primary_left.as_optional()),
        id(&entries.weapon_primary_right.as_optional()),
        id(&entries.weapon_secondary_left.as_optional()),
        id(&entries.weapon_secondary_right.as_optional()),
        id(&entries.weapon_tertiary_left.as_optional()),
        id(&entries.weapon_tertiary_right.as_optional()),
        id(&entries.arrow_primary),
        id(&entries.bolt_primary),
        id(&entries.arrow_secondary),
        id(&entries.bolt_secondary),
        id(&entries.arrow_tertiary),
        id(&entries.bolt_tertiary),
        id(&entries.protector_head.as_optional()),
        id(&entries.protector_chest.as_optional()),
        id(&entries.protector_hands.as_optional()),
        id(&entries.protector_legs.as_optional()),
        id(&entries.unused40),
        id(&entries.accessories[0]),
        id(&entries.accessories[1]),
        id(&entries.accessories[2]),
        id(&entries.accessories[3]),
        id(&entries.covenant),
    ]
}

/// 所有 BuddyParam 行（骨灰召唤定义）。
pub unsafe fn dump_buddies(repo: &mut SoloParamRepository) -> Result<String, String> {
    let mut rows = Vec::new();
    for (id, row) in repo.rows::<BuddyParam>() {
        rows.push(json!({
            "id": id,
            "trigger_sp_effect_id": row.trigger_sp_effect_id(),
            "npc_param_id": row.npc_param_id(),
            "npc_think_param_id": row.npc_think_param_id(),
            "npc_param_id_ridden": row.npc_param_id_ridden(),
            "npc_think_param_id_ridden": row.npc_think_param_id_ridden(),
            "npc_player_init_param_id": row.npc_player_init_param_id(),
            "pc_follow_type": row.pc_follow_type(),
            "x_offset": row.x_offset(),
            "z_offset": row.z_offset(),
            "y_angle": row.y_angle(),
            "appear_on_around_sekihi": row.appear_on_around_sekihi(),
        }));
    }
    let value = json!({ "count": rows.len(), "rows": rows });
    write_json("er_echo_buddies.json", &value)
}

/// 所有 RideParam 行（骑手 ↔ 坐骑）。
pub unsafe fn dump_ride(repo: &mut SoloParamRepository) -> Result<String, String> {
    let mut rows = Vec::new();
    for (id, row) in repo.rows::<RideParam>() {
        rows.push(json!({
            "id": id,
            "atk_chr_id": row.atk_chr_id(),
            "def_chr_id": row.def_chr_id(),
            "atk_chr_anim_id": row.atk_chr_anim_id(),
            "def_chr_anim_id": row.def_chr_anim_id(),
            "dist": row.dist(),
        }));
    }
    let value = json!({ "count": rows.len(), "rows": rows });
    write_json("er_echo_ride.json", &value)
}

/// 所有 NpcParam 行的关键字段（数值/队伍/幻影着色器）。
pub unsafe fn dump_npc(repo: &mut SoloParamRepository) -> Result<String, String> {
    let mut rows = Vec::new();
    for (id, row) in repo.rows::<NpcParam>() {
        rows.push(json!({
            "id": id,
            "name_id": row.name_id(),
            "hp": row.hp(),
            "mp": row.mp(),
            "stamina": row.stamina(),
            "team_type": row.team_type(),
            "behavior_variation_id": row.behavior_variation_id(),
            "phantom_shader_id": row.phantom_shader_id(),
            "role_name_id": row.role_name_id(),
            "npc_player_weight_type": row.npc_player_weight_type(),
        }));
    }
    let value = json!({ "count": rows.len(), "rows": rows });
    write_json("er_echo_npc.json", &value)
}

/// 所有 NpcThinkParam 行的关键字段（AI 身份/感知/跟随）。
pub unsafe fn dump_think(repo: &mut SoloParamRepository) -> Result<String, String> {
    let mut rows = Vec::new();
    for (id, row) in repo.rows::<NpcThinkParam>() {
        rows.push(json!({
            "id": id,
            "logic_id": row.logic_id(),
            "battle_goal_id": row.battle_goal_id(),
            "is_buddy_ai": row.is_buddy_ai(),
            "team_attack_effectivity": row.team_attack_effectivity(),
            "battle_start_dist": row.battle_start_dist(),
            "eye_dist": row.eye_dist(),
            "backhome_dist": row.backhome_dist(),
            "navi_ladder": row.enable_navi_flg_ladder(),
        }));
    }
    let value = json!({ "count": rows.len(), "rows": rows });
    write_json("er_echo_think.json", &value)
}

/// 场上子弹（法术弹 / 战技弹）按施放者归类。
///
/// 验证「克隆体到底有没有施法」的硬证据：每个法术都会生成 bullet，
/// `CSBulletIns.targeting_owner.owner_chr_handle` 就是施放者。
#[derive(Debug, Default, Clone)]
pub struct BulletScan {
    pub total: usize,
    pub clone: usize,
    pub others: usize,
    pub samples: Vec<String>,
}

/// SAFETY: 主线程调用；`world` 必须存活。
pub unsafe fn bullet_scan(world: &mut eldenring::cs::WorldChrMan) -> BulletScan {
    let mut out = BulletScan::default();
    let Ok(mgr) = eldenring::cs::CSBulletManager::instance_mut() else {
        return out;
    };
    for bullet in mgr.bullets() {
        out.total += 1;
        let handle = bullet.targeting_owner.owner_chr_handle;
        let owner = world.chr_ins_by_handle(&handle);
        let is_clone = owner.as_ref().is_some_and(|c| c.team_type == 47);
        if is_clone {
            out.clone += 1;
        } else {
            out.others += 1;
        }
        if out.samples.len() < 4 {
            out.samples.push(match owner {
                Some(chr) => format!("npc={} team={}", chr.npc_param_id, chr.team_type),
                None => "owner=?".to_string(),
            });
        }
    }
    out
}

/// 所有 `Magic` 行（法术 id 表 + 耗蓝/需求）。
///
/// 用途：① 离线导出存档里的记忆槽时要校验「这个 id 真的是法术」；② 换法术时看耗蓝。
pub unsafe fn dump_magic(repo: &mut SoloParamRepository) -> Result<String, String> {
    let mut rows = Vec::new();
    for (id, row) in repo.rows::<Magic>() {
        rows.push(json!({
            "id": id,
            "mp": row.mp(),
            "stamina": row.stamina(),
            "behavior_id": row.behavior_id(),
            "slot_length": row.slot_length(),
            "requirement_intellect": row.requirement_intellect(),
            "requirement_faith": row.requirement_faith(),
            "ai_notify_type": row.ai_notify_type(),
        }));
    }
    rows.sort_by_key(|r| r["id"].as_i64().unwrap_or(0));
    let value = json!({ "count": rows.len(), "rows": rows });
    write_json("er_echo_magic.json", &value)
}

/// 一个 PlayerIns 的记忆法术槽（`EquipGameData.equip_magic_data`）。
fn magic_row(p: &PlayerIns) -> serde_json::Value {
    let pgd = unsafe { p.player_game_data.as_ref() };
    let state = unsafe { crate::ai::snapshot(pgd) };
    let name: String = String::from_utf16_lossy(&pgd.character_name)
        .trim_end_matches('\0')
        .to_string();
    json!({
        "name": name,
        "level": pgd.level,
        "npc_param_id": p.chr_ins.npc_param_id,
        "intelligence": pgd.intelligence,
        "fp": [pgd.current_fp, pgd.current_max_fp],
        "magic_ptr": format!("0x{:x}", state.ptr),
        "selected_slot": state.selected,
        "unlocked_magic_slots": state.unlocked,
        "effective_unlocked_magic_slots": state.effective_unlocked,
        "magic_used": state.equipped().count(),
        "slots": state
            .slots
            .iter()
            .map(|s| json!({ "id": s.id, "charges": s.charges }))
            .collect::<Vec<_>>(),
    })
}

/// 玩家 + 所有克隆体的记忆法术槽 → `er_echo_magic_probe.json`。
///
/// 诊断「为什么不施法」：法术列表空 = 没法术可放（AI 权重再高也没用）。
pub unsafe fn dump_magic_probe(world: &mut eldenring::cs::WorldChrMan) -> Result<String, String> {
    let mut rows = Vec::new();
    if let Some(player) = world.main_player.as_mut() {
        let mut row = magic_row(player);
        row["role"] = json!("player");
        rows.push(row);
    }
    for chr in world.summon_buddy_chr_set.characters() {
        let Ok(p) = <&PlayerIns>::try_from(&*chr) else {
            continue;
        };
        let mut row = magic_row(p);
        row["role"] = json!("clone");
        rows.push(row);
    }
    let value = json!({ "count": rows.len(), "rows": rows });
    write_json("er_echo_magic_probe.json", &value)
}

/// 所有可用装备行的 id（挑「明显不同的外观」时用）：武器 / 防具 / 护符。
pub unsafe fn dump_equip(repo: &mut SoloParamRepository) -> Result<String, String> {
    let mut weapons: Vec<u32> = repo.rows::<eldenring::cs::EquipParamWeapon>().map(|(id, _)| id).collect();
    let mut protectors: Vec<u32> = repo
        .rows::<eldenring::cs::EquipParamProtector>()
        .map(|(id, _)| id)
        .collect();
    let mut accessories: Vec<u32> = repo
        .rows::<eldenring::cs::EquipParamAccessory>()
        .map(|(id, _)| id)
        .collect();
    weapons.sort_unstable();
    protectors.sort_unstable();
    accessories.sort_unstable();
    let value = json!({
        "weapon_count": weapons.len(),
        "protector_count": protectors.len(),
        "accessory_count": accessories.len(),
        "weapons": weapons,
        "protectors": protectors,
        "accessories": accessories,
    });
    write_json("er_echo_equip.json", &value)
}

/// 克隆体探测：召唤物里有没有 `PlayerIns`（带 PlayerGameData/face_data）的实例。
pub unsafe fn dump_clone_info(world: &mut eldenring::cs::WorldChrMan) -> Result<String, String> {
    // 距离用物理矩阵的世界坐标算（`chr_inses_by_distance` 里的指针对不上，见 lib.rs::world_pos）。
    let ppos = world
        .main_player
        .as_ref()
        .and_then(|p| crate::world_pos(&p.chr_ins));
    let mut rows = Vec::new();
    for chr in world.summon_buddy_chr_set.characters() {
        let distance = match (ppos, crate::world_pos(chr)) {
            (Some(a), Some(b)) => Some(
                (((a.0 - b.0).powi(2) + (a.1 - b.1).powi(2) + (a.2 - b.2).powi(2)).sqrt() * 10.0)
                    .round()
                    / 10.0,
            ),
            _ => None,
        };
        let as_player = <&eldenring::cs::PlayerIns>::try_from(&*chr).ok();
        let mut info = json!({
            "npc_param_id": chr.npc_param_id,
            "npc_id": chr.npc_id,
            "chr_type": format!("{:?}", chr.chr_type),
            "team_type": chr.team_type,
            "is_player_ins": as_player.is_some(),
            "distance": distance,
            "world_pos": crate::world_pos(chr).map(|(x, y, z)| json!([x, y, z])),
        });
        if let Some(p) = as_player {
            let pgd = p.player_game_data.as_ref();
            let face = &pgd.face_data.face_data_buffer;
            let name: String = String::from_utf16_lossy(&pgd.character_name)
                .trim_end_matches('\0')
                .to_string();
            info["name"] = json!(name);
            info["level"] = json!(pgd.level);
            info["vigor"] = json!(pgd.vigor);
            info["effective_vigor"] = json!(pgd.effective_vigor);
            info["hp"] = json!([pgd.current_hp, pgd.current_max_hp]);
            info["is_main_player"] = json!(pgd.is_main_player);
            info["face_magic"] = json!(String::from_utf8_lossy(&face.magic).to_string());
            info["face_size"] = json!(face.buffer_size);
            info["face_prefix"] = json!(face.buffer[..24].iter().map(|b| format!("{b:02x}")).collect::<String>());
            // 体型诊断：存档 body_type == 运行时 gender；缓冲里的 5 个 u8 滑条；
            // 引擎解析后的 7 个 f32（FaceData.unk130 与 PlayerIns+0x650 两份）。
            let scales = |base: *const f32| -> Vec<f32> {
                (0..crate::profile::BODY_SCALE_COUNT)
                    .map(|i| unsafe { *base.add(i) })
                    .collect()
            };
            let fd = &pgd.face_data as *const eldenring::cs::FaceData as *const f32;
            let ins = p as *const PlayerIns as *const f32;
            info["gender"] = json!(pgd.gender);
            info["body_bytes"] = json!(&face.buffer[0xA0..0xA5]);
            info["body_scales_face"] = json!(scales(unsafe {
                fd.add(crate::profile::FACE_BODY_SCALES_OFFSET / 4)
            }));
            info["body_scales_ins"] = json!(scales(unsafe {
                ins.add(crate::kit::PLAYER_INS_BODY_SCALES / 4)
            }));
            info["equip"] = json!(p.chr_asm.as_ref().equipment_param_ids);
            info["equip_head"] = json!(p.chr_asm.as_ref().equipment_param_ids[12]);
            info["equip_body"] = json!(p.chr_asm.as_ref().equipment_param_ids[13]);
            info["equip_right"] = json!(p.chr_asm.as_ref().equipment_param_ids[1]);
            // 三份「装备真相」的对照：引擎到底认哪一份？
            info["pgd_chr_asm"] = json!(pgd.equipment.chr_asm.equipment_param_ids);
            info["entries"] = json!(equipment_entry_param_ids(&pgd.equipment.equipment_entries));
            info["gaitem_handles"] = json!(p
                .chr_asm
                .as_ref()
                .gaitem_handles
                .iter()
                .map(|h| format!("{h:?}"))
                .collect::<Vec<_>>());
            info["equip_idx_list"] = json!(pgd.equipment.equipment_item_idx_list);
        }
        rows.push(info);
    }
    let value = json!({ "count": rows.len(), "rows": rows });
    write_json("er_echo_clone_info.json", &value)
}

/// 当前存活的所有角色里，离玩家最近的若干实体（用于定位「看得见的克隆体」）。
pub unsafe fn dump_chrs(world: &mut eldenring::cs::WorldChrMan) -> Result<String, String> {
    let Some(ref player) = world.main_player else {
        return Err("no player".into());
    };
    let ppos = crate::world_pos(&player.chr_ins);
    let mut rows = Vec::new();
    for set in world.chr_sets.iter_mut() {
        let Some(set) = set.as_mut() else { continue };
        for chr in set.characters() {
            let pos = chr.chunk_position;
            let d = match (ppos, crate::world_pos(chr)) {
                (Some(a), Some(b)) => {
                    ((a.0 - b.0).powi(2) + (a.1 - b.1).powi(2) + (a.2 - b.2).powi(2)).sqrt()
                }
                _ => f32::INFINITY,
            };
            if d > 120.0 && chr.team_type != 47 {
                continue;
            }
            rows.push(json!({
                "npc_param_id": chr.npc_param_id,
                "npc_id": chr.npc_id,
                "team_type": chr.team_type,
                "dist": if d.is_finite() { json!((d * 10.0).round() / 10.0) } else { json!(null) },
                "pos": [pos.0, pos.1, pos.2],
                "world_pos": crate::world_pos(chr).map(|(x, y, z)| json!([x, y, z])),
                "block": format!("{:?}", chr.block_id),
            }));
        }
    }
    rows.sort_by(|a, b| {
        let da = a["dist"].as_f64().unwrap_or(0.0);
        let db = b["dist"].as_f64().unwrap_or(0.0);
        da.partial_cmp(&db).unwrap_or(std::cmp::Ordering::Equal)
    });
    rows.truncate(80);
    let value = json!({
        "player_pos": ppos.map(|(x, y, z)| json!([x, y, z])),
        "count": rows.len(),
        "rows": rows,
    });
    write_json("er_echo_chrs.json", &value)
}

/// 当前活跃的召唤物（summon_buddy_chr_set）+ 召唤管理器状态。
pub unsafe fn dump_summons(world: &mut eldenring::cs::WorldChrMan) -> Result<String, String> {
    let Some(mgr) = crate::spirit::manager(world) else {
        return Err("summon_buddy_manager is null (loading/dead?)".into());
    };
    let mut chrs = Vec::new();
    for chr in world.summon_buddy_chr_set.characters() {
        chrs.push(json!({
            "npc_param_id": chr.npc_param_id,
            "npc_id": chr.npc_id,
            "team_type": chr.team_type,
            "block_id": format!("{:?}", chr.block_id),
            "pos": [chr.chunk_position.0, chr.chunk_position.1, chr.chunk_position.2],
        }));
    }
    let value = json!({
        "request_summon_speffect_id": mgr.request_summon_speffect_id,
        "active_summon_speffect_id": mgr.active_summon_speffect_id,
        "disappear_requested": mgr.disappear_requested,
        "count": chrs.len(),
        "chrs": chrs,
    });
    write_json("er_echo_summons.json", &value)
}
pub unsafe fn dump_profile(player: &PlayerIns) -> Result<String, String> {
    let pgd = player.player_game_data.as_ref();
    let face = &pgd.face_data.face_data_buffer;
    // 存档里的 FaceData 是 0x12F 自描述块：marker(4) + "FACE"(4) + version(4) + size(4)
    // + 276 字节缓冲 + 11 字节尾（FACE param overrides）。运行时不保存 marker/尾，
    // 这里补回来，导出的 profile 才能和「从存档导出的」格式完全一致。
    let mut block = Vec::with_capacity(0x12F);
    block.extend_from_slice(&[0xff; 4]);
    block.extend_from_slice(&face.magic);
    block.extend_from_slice(&face.version.to_le_bytes());
    block.extend_from_slice(&face.buffer_size.to_le_bytes());
    block.extend_from_slice(&face.buffer);
    block.resize(0x12F, 0);
    let name: String = String::from_utf16_lossy(&pgd.character_name)
        .trim_end_matches('\0')
        .to_string();
    let value = json!({
        "name": name,
        "level": pgd.level,
        "stats": {
            "vigor": pgd.vigor,
            "mind": pgd.mind,
            "endurance": pgd.endurance,
            "strength": pgd.strength,
            "dexterity": pgd.dexterity,
            "intelligence": pgd.intelligence,
            "faith": pgd.faith,
            "arcane": pgd.arcane,
        },
        "hp": { "current": pgd.current_hp, "max": pgd.current_max_hp, "base_max": pgd.base_max_hp },
        "fp": { "current": pgd.current_fp, "max": pgd.current_max_fp, "base_max": pgd.base_max_fp },
        "stamina": { "current": pgd.current_stamina, "max": pgd.current_max_stamina, "base_max": pgd.base_max_stamina },
        "runes": pgd.rune_count,
        "rune_memory": pgd.rune_memory,
        "scadutree_blessing": pgd.scadutree_blessing,
        // —— 下面这些是「存档里也有、但以前的导出器没解析」的字段，用来做离线↔运行时对照
        "identity": {
            "player_id": pgd.player_id,
            "character_id": pgd.character_id,
            "gender": pgd.gender,
            "archetype": pgd.archetype,
            "voice_type": pgd.voice_type,
            "starting_gift": pgd.starting_gift,
            "unlocked_magic_slots": pgd.unlocked_magic_slots,
            "unlocked_talisman_slots": pgd.unlocked_talisman_slots,
            "spirit_ashes_level": pgd.matchmaking_spirit_ashes_level,
            "weapon_level": pgd.matching_weapon_level,
            "flasks": [pgd.max_hp_flask, pgd.max_fp_flask],
        },
        "resistances": [pgd.poison_resist, pgd.rot_resist, pgd.bleed_resist, pgd.death_resist,
                        pgd.frost_resist, pgd.sleep_resist, pgd.madness_resist],
        "resistance_gauges": pgd.resistance_gauges,
        "poise": pgd.poise,
        "discovery": pgd.discovery,
        "max_equip_load": pgd.max_equip_load,
        "block_position": [player.block_position.x, player.block_position.y, player.block_position.z],
        "block_id": format!("{:?}", player.chr_ins.block_id),
        "chunk_position": [player.chr_ins.chunk_position.0, player.chr_ins.chunk_position.1, player.chr_ins.chunk_position.2],
        "equipment_param_ids": player.chr_asm.as_ref().equipment_param_ids,
        "equipment_gaitem_handles": player.chr_asm.as_ref().gaitem_handles
            .iter().map(|h| format!("{h:?}")).collect::<Vec<_>>(),
        "equipment_entries": equipment_entry_param_ids(&pgd.equipment.equipment_entries),
        "equipment_item_idx_list": pgd.equipment.equipment_item_idx_list,
        "face": {
            "magic": String::from_utf8_lossy(&face.magic).to_string(),
            "version": face.version,
            "buffer_size": face.buffer_size,
            "payload_hex": face.buffer.iter().map(|b| format!("{b:02x}")).collect::<String>(),
            "hex": block.iter().map(|b| format!("{b:02x}")).collect::<String>(),
        },
    });
    write_json("er_echo_profile.json", &value)
}
