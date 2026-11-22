//! 召唤限制（区域 / 召唤石范围 / 冷却）与「灵体外观」（PhantomParam）的运行时处理。
//!
//! 两个独立的问题：
//!
//! 1. **能不能召** —— 骨灰的可用范围由 `BuddyStoneParam.activate_range`（召唤石半径）
//!    和 `SummonBuddyManager` 的几个范围标志决定。玩家离所有召唤石都远 = 「dead zone」，
//!    骨灰用不出来。解决办法：把每行 `activate_range` 抬到很大 + 每帧把管理器的
//!    `is_within_activation_range` 置真（管理器若自己重算，param 那条仍然生效）。
//!
//! 2. **长什么样** —— 灵体的蓝白发光/半透明来自 `PHANTOM_PARAM_ST`（phantom shader）。
//!    运行时把对应行的 edge/light alpha 与 glow 归零就能恢复本来的材质颜色，
//!    不用改 regulation.bin。

use eldenring::cs::{
    BuddyStoneParam, CSLuaEventManImp, CSLuaEventProxy, CSNowLoadingHelper, ChrIns, ChrInsExt,
    NpcParam, PhantomParam, PlayerGameData, SoloParamRepository, SummonBuddyManager, WorldChrMan,
};
use fromsoftware_shared::FromStatic;
use serde_json::{json, Map, Value};

/// 赐福/事件控制位的 Debug 文本 —— 诊断「哪些位在动」用。
pub fn bonfire_flags_debug() -> Option<String> {
    let man = unsafe { CSLuaEventManImp::instance() }.ok()?;
    let proxy = man.lua_event_proxy.as_ptr() as usize;
    if proxy == 0 {
        return None;
    }
    Some(format!("{:?}", unsafe {
        (*(proxy as *const CSLuaEventProxy)).control_flags
    }))
}

/// 进入加载画面（传送/世界重置）的次数：每次进加载画面 +1。
pub fn menu_load_counter() -> Option<i32> {
    Some(unsafe { CSNowLoadingHelper::instance() }.ok()?.menu_load_counter)
}

/// 玩家当前血量（死亡过程中是 0）。
pub fn player_hp(world: &WorldChrMan) -> Option<u32> {
    let p = world.main_player.as_ref()?;
    let raw = p.player_game_data.as_ptr() as usize;
    if raw == 0 {
        return None;
    }
    Some(unsafe { (*(raw as *const PlayerGameData)).current_hp })
}

/// 玩家当前 block id（换图/传送会变）。
pub fn player_block(world: &WorldChrMan) -> Option<u32> {
    Some(world.main_player.as_ref()?.chr_ins.block_id.0 as u32)
}

///
/// 赐福菜单是 ESD + 前端驱动的，DLL 塞不进菜单项；但引擎把「坐下/起身」的
/// 动画状态放在 `CSLuaEventMan.lua_event_proxy.control_flags` 里：
///   bit5 `bonfire_loop_begin_requested`、bit7 `bonfire_sitting_loop_active`、
///   bit8 `bonfire_stand_up_in_progress`。
/// 用它就能把「召唤」挂到休息流程上：坐下 → 世界重置 → 起身 → 自动召唤。
pub fn is_sitting_at_grace() -> Option<bool> {
    let man = unsafe { CSLuaEventManImp::instance() }.ok()?;
    let ptr = man.lua_event_proxy.as_ptr();
    if ptr.is_null() {
        return None;
    }
    Some(unsafe { (*ptr).control_flags.bonfire_sitting_loop_active() })
}


/// `WorldChrMan::summon_buddy_manager` 的字节偏移（编译期算出来，别手写 0x1e538）。
const SUMMON_MGR_OFFSET: usize =
    std::mem::offset_of!(eldenring::cs::WorldChrMan, summon_buddy_manager);

/// 直接按字节读管理器指针。
///
/// 走 `OwnedPtr::as_ptr()` 时编译器知道指针来自 `NonNull`（带 nonnull 属性），
/// 会把 `is_null()` 判定当 UB 删掉 —— 这正是两次 0xc0000005 的根因
/// （反汇编里 `movl ...,0x28(%rax)` 而 `rax=0`，判空根本不存在）。
/// 所以这里绕开类型系统：按偏移读原始 `usize`，值是 0 就是 0。
fn manager_ptr(world: &WorldChrMan) -> usize {
    let base = world as *const WorldChrMan as usize;
    let raw = unsafe { *((base + SUMMON_MGR_OFFSET) as *const usize) };
    // black_box：否则优化器仍可能“证明”这个指针非空（NonNull 的 nonnull 属性），
    // 把 `if raw == 0` 整个删掉 —— 反汇编里就是这样，判空不存在，直接崩。
    std::hint::black_box(raw)
}

/// 安全取召唤管理器。
///
/// 读档 / 过场 / 死亡复活 / 退回标题时 `WorldChrMan` 还在，但
/// `summon_buddy_manager` 会被释放成空指针。
pub fn manager(world: &WorldChrMan) -> Option<&SummonBuddyManager> {
    let raw = manager_ptr(world);
    if raw == 0 {
        None
    } else {
        Some(unsafe { &*(raw as *const SummonBuddyManager) })
    }
}

/// 同上，可变版本。
pub fn manager_mut(world: &mut WorldChrMan) -> Option<&mut SummonBuddyManager> {
    let raw = manager_ptr(world);
    if raw == 0 {
        None
    } else {
        Some(unsafe { &mut *(raw as *mut SummonBuddyManager) })
    }
}

/// 召唤组 / trigger→BuddyParam 映射的快照（诊断「人数为什么没生效」用）。
pub fn summon_groups_snapshot(world: &WorldChrMan) -> Value {
    let Some(mgr) = manager(world) else {
        return json!({ "error": "summon_buddy_manager is null" });
    };
    let mut groups = Vec::new();
    for pair in mgr.groups.iter() {
        for g in pair.second.iter() {
            // 原始字节：确认 SummonBuddyGroup 的字段偏移和 1.17.2 一致
            let raw = unsafe {
                std::slice::from_raw_parts(g as *const _ as *const u8, 0x30)
            };
            groups.push(json!({
                "event": pair.first,
                "buddy_param_id": g.buddy_param_id,
                "buddy_stone_param_id": g.buddy_stone_param_id,
                "warp_requested": g.warp_requested,
                "disappear_requested": g.disappear_requested,
                "disappear_delay_sec": g.disappear_delay_sec,
                "has_spawn_point": g.has_spawn_point,
                "follow_type": g.follow_type,
                "chr": g.chr_ins.as_ptr() as usize,
                "raw": raw.iter().map(|b| format!("{b:02X}")).collect::<String>(),
            }));
        }
    }
    let mut trigger_map = Vec::new();
    for (trigger, buddy) in mgr.trigger_speffect_to_buddy_map.iter() {
        trigger_map.push(json!({ "trigger": trigger, "buddy_param_id": buddy }));
    }
    json!({ "groups": groups, "trigger_map": trigger_map })
}

/// 当前召唤组的 BuddyParam id 列表（trim 诊断用）。
pub fn group_buddy_ids(world: &WorldChrMan) -> Vec<i32> {
    let Some(mgr) = manager(world) else {
        return Vec::new();
    };
    let mut ids = Vec::new();
    for pair in mgr.groups.iter() {
        for g in pair.second.iter() {
            ids.push(g.buddy_param_id);
        }
    }
    ids
}

/// 把「trigger spEffect → 一组 BuddyParam」的映射链对齐到当前人数。
///
/// 引擎在**世界加载时**用 BuddyParam.trigger_sp_effect_id 建这张
/// `ChainingMap`，运行时改 trigger 不会更新它。所以人数变了以后：
/// * 变少：把链截断到 `count` 个；
/// * 变多：把被踢掉的桶项重新链回 trigger 的链上。
///
/// 桶项（`ChainingMapBucketEntry`）在 map 的 `buckets` 数组里一直存在，
/// 只是没被链进 trigger；这里按 BuddyParam id 找回来重连，无需分配/释放。
/// 返回是否成功（trigger 键不存在时返回 false）。
pub unsafe fn sync_trigger_chain(
    world: &mut WorldChrMan,
    trigger: i32,
    rows: &[u32],
    count: usize,
) -> bool {
    use std::ptr::NonNull;

    let Some(mgr) = manager_mut(world) else {
        return false;
    };
    let map = &mut mgr.trigger_speffect_to_buddy_map;
    let bucket_ptr = map.buckets().as_ptr() as *mut eldenring::ChainingMapBucketEntry<i32>;
    let bucket_len = map.buckets().len();
    if bucket_ptr.is_null() || bucket_len == 0 {
        return false;
    }

    // 1) 找到该 trigger 的链头
    let mut head: *mut eldenring::ChainingMapBucketEntry<i32> = std::ptr::null_mut();
    for (key, entry) in map.iter_chains_mut() {
        if *key == trigger {
            head = entry as *mut _;
            break;
        }
    }
    if head.is_null() || count == 0 {
        return false;
    }

    // 2) 收集当前人数内每一行对应的桶项
    let wanted: Vec<i32> = rows.iter().take(count).map(|r| *r as i32).collect();
    let mut entries: Vec<*mut eldenring::ChainingMapBucketEntry<i32>> = Vec::new();
    for i in 0..bucket_len {
        let e = bucket_ptr.add(i);
        if wanted.contains(&(*e).data) {
            entries.push(e);
        }
    }
    if entries.len() < count {
        log::warn!(
            "buddy chain: only found {}/{} bucket entries for rows {rows:?}",
            entries.len(),
            count
        );
        return false;
    }
    entries.sort_by_key(|e| {
        wanted
            .iter()
            .position(|r| *r == (**e).data)
            .unwrap_or(usize::MAX)
    });

    // 3) 重连：head 保留，按 rows 顺序接上其余项
    if head != entries[0] {
        (*head).data = (*entries[0]).data;
    }
    let mut cur = head;
    (*cur).next = None;
    for e in entries.iter().skip(1).take(count - 1) {
        if *e == head || *e == cur {
            continue;
        }
        (*cur).next = NonNull::new(*e);
        (**e).next = None;
        cur = *e;
    }
    (*cur).next = None;
    true
}

/// 把多出来的召唤组标记为消失，最终只保留 `count` 个。
///
/// 为什么需要这个：引擎的 `trigger_speffect_to_buddy_map` 是**世界加载时**
/// 从 BuddyParam 建的映射（trigger spEffect → 一组 BuddyParam id）。运行时改
/// `BuddyParam.trigger_sp_effect_id` 不会更新它，而 `disappear_requested` 的
/// 全局解散又经常被引擎忽略（实测 8 秒都没消失）。所以人数变少/重召后，
/// 按 `SummonBuddyGroup.buddy_param_id` 逐个把多余的组置 `disappear_requested`：
///
/// * 优先保留 `rows[..count]` 里的组，最多 `count` 个；
/// * 其余的（包括老队伍 + 新队伍叠加出来的重复组）全部标记消失。
///
/// 返回被标记的组数（已经标记过的不重复计数）。
pub fn trim_extra_buddy_groups(
    world: &mut WorldChrMan,
    count: usize,
    rows: &[u32],
) -> usize {
    let wanted: Vec<i32> = rows.iter().take(count).map(|r| *r as i32).collect();
    let Some(mgr) = manager_mut(world) else {
        return 0;
    };
    let mut kept = 0usize;
    let mut marked = 0usize;
    for pair in mgr.groups.iter_mut() {
        for group in pair.second.iter_mut() {
            // 已经在消失（flag + delay=0）的组不算「保留名额」
            let despawning = group.disappear_requested && group.disappear_delay_sec <= 0.0;
            if despawning {
                continue;
            }
            let is_wanted = wanted.contains(&group.buddy_param_id);
            if is_wanted && kept < count {
                kept += 1;
                continue;
            }
            if !group.disappear_requested || group.disappear_delay_sec != 0.0 {
                group.disappear_requested = true;
                group.disappear_delay_sec = 0.0;
                marked += 1;
            }
        }
    }
    marked
}


/// 灵体外观「正常化」的一组值：删掉描边/自发光/半透，diffuse 保持中性。
///
/// 说明：`PHANTOM_PARAM_ST` 的 alpha/blend_rate 语义是「幻影叠加层」，
/// 灵体之所以看起来是蓝白半透明，是因为这行给了带颜色的 edge/light。
/// 归零 edge/light + glow，同时把 diffuse 乘数保持 1.0，角色就回到本体材质。
pub const NEUTRAL: &[(&str, f32)] = &[
    ("edge_color_a", 0.0),
    ("front_color_a", 0.0),
    ("diff_mul_color_a", 1.0),
    ("spec_mul_color_a", 1.0),
    ("light_color_a", 0.0),
    ("alpha", 1.0),
    ("blend_rate", 0.0),
    ("edge_power", 0.0),
    ("glow_scale", 0.0),
];

/// 召唤管理器状态快照（诊断用：看卡在哪一步）。
pub fn summon_state(world: &WorldChrMan) -> Value {
    let Some(mgr) = manager(world) else {
        return json!({ "error": "summon_buddy_manager is null (still loading?)" });
    };
    let mut chrs = Vec::new();
    for chr in world.summon_buddy_chr_set.characters() {
        chrs.push(json!({
            "npc_param_id": chr.npc_param_id,
            "team_type": chr.team_type,
            "phantom_param_override": chr.phantom_param_override,
            "base_transparency": chr.base_transparency,
            "tint_alpha_multiplier": chr.tint_alpha_multiplier,
            "opacity_keyframes_multiplier": chr.opacity_keyframes_multiplier,
        }));
    }
    let warp_dist = {
        let p = mgr.warp_manager.as_ptr();
        if p.is_null() {
            Value::Null
        } else {
            json!(unsafe { (*p).trigger_dist_to_player })
        }
    };
    json!({
        "request_summon_speffect_id": mgr.request_summon_speffect_id,
        "active_summon_speffect_id": mgr.active_summon_speffect_id,
        "requested_summon_goods_id": mgr.requested_summon_goods_id,
        "active_summon_goods_id": mgr.active_summon_goods_id,
        "disappear_requested": mgr.disappear_requested,
        "player_has_alive_summon": mgr.player_has_alive_summon,
        "is_within_activation_range": mgr.is_within_activation_range,
        "prev_is_within_activation_range": mgr.prev_is_within_activation_range,
        "is_within_warn_range": mgr.is_within_warn_range,
        "prev_is_within_warn_range": mgr.prev_is_within_warn_range,
        "item_use_cooldown_timer": mgr.item_use_cooldown_timer,
        "buddy_disappear_delay_sec": mgr.buddy_disappear_delay_sec,
        "buddy_stone_entity_id": mgr.buddy_stone_entity_id,
        "active_summmon_buddy_stone_entity_id": mgr.active_summmon_buddy_stone_entity_id,
        "spawn_origin": [mgr.spawn_origin.0, mgr.spawn_origin.1, mgr.spawn_origin.2],
        "spawn_rotation": mgr.spawn_rotation,
        "last_buddy_slot": mgr.last_buddy_slot,
        "warp_trigger_dist_to_player": warp_dist,
        "groups": mgr.groups.len(),
        "summon_chr_count": chrs.len(),
        "summon_chrs": chrs,
    })
}

/// 每帧把这些门禁位强行置真：范围判定、冷却、消失请求。
///
/// 只动「判定输入」，不动实体本身；管理器下一帧自己重算也不会出问题。
pub fn bypass_summon_gates(world: &mut WorldChrMan) -> bool {
    let Some(mgr) = manager_mut(world) else {
        return false;
    };
    mgr.is_within_activation_range = true;
    mgr.prev_is_within_activation_range = true;
    mgr.is_within_warn_range = true;
    mgr.prev_is_within_warn_range = true;
    // 连着用骨灰时的冷却（原版防止快速招/撤刷怪）
    mgr.item_use_cooldown_timer = 0.0;
    mgr.disappear_requested = false;
    true
}

/// 允许「已经有召唤物时再召一次」：管理器用它阻止第二次使用骨灰。
pub fn clear_alive_summon_flag(world: &mut WorldChrMan) -> bool {
    let Some(mgr) = manager_mut(world) else {
        return false;
    };
    mgr.player_has_alive_summon = false;
    true
}

/// 把每行 `BuddyStoneParam.activate_range` 抬到 `range`。
///
/// 返回 `(改了几行, 改之前的最小值, 改之前的最大值)`。
pub unsafe fn widen_buddy_stone_range(
    repo: &mut SoloParamRepository,
    range: u16,
) -> (usize, u16, u16) {
    let mut n = 0;
    let mut lo = u16::MAX;
    let mut hi = 0u16;
    for (_id, row) in repo.rows_mut::<BuddyStoneParam>() {
        let old = row.activate_range();
        lo = lo.min(old);
        hi = hi.max(old);
        if old != range {
            row.set_activate_range(range);
            n += 1;
        }
    }
    if lo == u16::MAX {
        lo = 0;
    }
    (n, lo, hi)
}

/// 召唤石（BuddyStoneParam）现状：行数 + 范围分布。
pub fn stone_state(repo: &SoloParamRepository) -> Value {
    let mut rows = Vec::new();
    for (id, row) in repo.rows::<BuddyStoneParam>() {
        rows.push(json!({
            "id": id,
            "buddy_id": row.buddy_id(),
            "activate_range": row.activate_range(),
            "overwrite_return_range": row.overwrite_return_range(),
            "doping_sp_effect_id": row.doping_sp_effect_id(),
        }));
    }
    let mut ranges: Vec<u16> = rows
        .iter()
        .filter_map(|r| r["activate_range"].as_u64().map(|v| v as u16))
        .collect();
    ranges.sort_unstable();
    json!({
        "count": rows.len(),
        "activate_range_min": ranges.first().copied(),
        "activate_range_max": ranges.last().copied(),
        "rows": rows,
    })
}

/// 把 `PHANTOM_PARAM_ST` 某行按 `fields` 覆写（只认白名单字段）。
pub unsafe fn patch_phantom(
    repo: &mut SoloParamRepository,
    id: u32,
    fields: &Map<String, Value>,
) -> Result<Vec<(String, f32)>, String> {
    let Some(row) = repo.get_mut::<PhantomParam>(id) else {
        return Err(format!("PHANTOM_PARAM_ST {id} not found"));
    };
    let mut applied = Vec::new();
    for (key, value) in fields {
        let Some(f) = value.as_f64().map(|v| v as f32) else {
            continue;
        };
        match key.as_str() {
            "edge_color_a" => row.set_edge_color_a(f),
            "front_color_a" => row.set_front_color_a(f),
            "diff_mul_color_a" => row.set_diff_mul_color_a(f),
            "spec_mul_color_a" => row.set_spec_mul_color_a(f),
            "light_color_a" => row.set_light_color_a(f),
            "alpha" => row.set_alpha(f),
            "blend_rate" => row.set_blend_rate(f),
            "edge_power" => row.set_edge_power(f),
            "glow_scale" => row.set_glow_scale(f),
            "blend_type" => row.set_blend_type(f as u8),
            "is_edge_subtract" => row.set_is_edge_subtract(f as u8),
            "is_front_subtract" => row.set_is_front_subtract(f as u8),
            "is_no2_pass" => row.set_is_no2_pass(f as u8),
            "edge_color_r" => row.set_edge_color_r(f as u8),
            "edge_color_g" => row.set_edge_color_g(f as u8),
            "edge_color_b" => row.set_edge_color_b(f as u8),
            "front_color_r" => row.set_front_color_r(f as u8),
            "front_color_g" => row.set_front_color_g(f as u8),
            "front_color_b" => row.set_front_color_b(f as u8),
            "light_color_r" => row.set_light_color_r(f as u8),
            "light_color_g" => row.set_light_color_g(f as u8),
            "light_color_b" => row.set_light_color_b(f as u8),
            _ => continue,
        }
        applied.push((key.clone(), f));
    }
    if applied.is_empty() {
        return Err("no known field in args".into());
    }
    Ok(applied)
}

/// 把某行 `PHANTOM_PARAM_ST` 写成「无灵体特效」（见 [`NEUTRAL`]）。
pub unsafe fn neutralize_phantom(repo: &mut SoloParamRepository, id: u32) -> Result<(), String> {
    let fields: Map<String, Value> = NEUTRAL
        .iter()
        .map(|(k, v)| ((*k).to_string(), json!(v)))
        .collect();
    patch_phantom(repo, id, &fields).map(|_| ())
}

/// 给所有克隆体设 `phantom_param_override`（-1 = 不覆盖，交还引擎）。
pub fn set_clone_phantom_override(world: &mut WorldChrMan, id: i32) -> usize {
    let mut n = 0;
    for chr in world.summon_buddy_chr_set.characters() {
        chr.phantom_param_override = id;
        n += 1;
    }
    n
}

/// 克隆体用到的 NpcParam 行（拟态泪滴本体 / 史莱姆形态）。
pub const CLONE_NPCS: &[u32] = &[100000010, 133201000];

/// 是不是「我们的」克隆体：同伴队伍 + 拟态泪滴 NpcParam。
///
/// 不能只看 `team_type == 47`：玩家同时用原版骨灰时，它们也在
/// `summon_buddy_chr_set` 里，但**不该**被摘掉 296000 / 钉锁定位 / 改伤害修正。
pub fn is_clone(chr: &ChrIns) -> bool {
    chr.team_type == 47 && CLONE_NPCS.contains(&(chr.npc_param_id as u32))
}

/// 原版「骨灰伤害修正」spEffect（挂在 NpcParam 的常驻槽里，所有灵体都吃）：
///
/// * `296000`：对敌人/对玩家伤害 ×0.25、受到伤害 ×0.5、削韧伤害 ×0.05
///   —— 这就是「队友伤害只有玩家四分之一」的来源；
/// * `20297000`：受到削韧 ×0.5（骨灰专用）。
///
/// 我们的克隆体是 `PlayerIns`，不应该吃灵体削弱。做法是**只针对拟态泪滴**
/// （NpcParam 100000010 / 133201000）把这两个 spEffect 的常驻槽清掉，
/// 并从已经生成的克隆体身上摘掉 —— 不修改 SpEffectParam 行本身，
/// 因此不会连带强化玩家召唤的其它骨灰。
pub const SUMMON_CORRECTION_SPEFFECTS: &[i32] = &[296000, 20297000];

/// 「骨灰外观」spEffect：295000 = 普通骨灰（白雾虚影），295200 = 傀儡骨灰。
///
/// 来源：社区做法是把 `NpcParam` 的 `SpEffect ID` 槽里这两个 id 改成 -1，
/// 骨灰就按本体材质显示。我们运行时直接把 spEffect 从 chr 身上摘掉（对新召唤
/// 则是把 NpcParam 行里的槽改成 -1），效果一致且不动 regulation.bin。
pub const GLOW_SPEFFECTS: &[i32] = &[295000, 295200];

/// 从每个克隆体身上摘掉 `ids` 里的 spEffect。返回 `(处理了几个 chr, 实际摘掉的 id)`。
pub fn strip_speffects(world: &mut WorldChrMan, ids: &[i32]) -> (usize, Vec<i32>) {
    let mut removed: Vec<i32> = Vec::new();
    let mut n = 0;
    for chr in world.summon_buddy_chr_set.characters() {
        if !is_clone(chr) {
            continue;
        }
        n += 1;
        let present: Vec<i32> = chr
            .special_effect
            .entries()
            .map(|e| e.param_id)
            .filter(|id| ids.contains(id))
            .collect();
        for id in present {
            chr.remove_speffect(id);
            if !removed.contains(&id) {
                removed.push(id);
            }
        }
    }
    (n, removed)
}

/// 兼容旧名：摘除「骨灰外观」spEffect。
pub fn strip_glow(world: &mut WorldChrMan, ids: &[i32]) -> (usize, Vec<i32>) {
    strip_speffects(world, ids)
}

/// 禁止/允许玩家锁定克隆体（`ChrCtrlModifierActionFlags::disable_lock_on`）。
///
/// 友伤打开时，队友会变成「能被打中」的友军；显式把锁定位也钉住，
/// 避免玩家在混战里把准星锁到队友身上。`blocked = false` 用于关闭友伤时还原。
pub fn set_clone_lock_on_blocked(world: &mut WorldChrMan, blocked: bool) -> usize {
    let mut n = 0;
    for chr in world.summon_buddy_chr_set.characters() {
        if !is_clone(chr) {
            continue;
        }
        let ctrl = chr.chr_ctrl.as_mut();
        ctrl.modifier
            .as_mut()
            .data
            .action_flags
            .set_disable_lock_on(blocked);
        if blocked {
            chr.is_locked_on = false;
        }
        n += 1;
    }
    n
}

/// 给**我们的克隆体**挂/摘友伤倍率 spEffect（`20011466`）。
///
/// 只挂克隆体、不挂玩家：克隆体的 `atkPlayer=rate` 管「克隆体→玩家」，
/// 克隆体的 `defPlayer=rate` 管「玩家→克隆体」；敌人打玩家/克隆体时走
/// `atkEnemy/defEnemy=1`，不变。返回实际改动的克隆体数量。
pub fn set_friendly_damage_effect(world: &mut WorldChrMan, on: bool) -> usize {
    let id = crate::params::FRIENDLY_FIRE_SPEFFECT as i32;
    // 行没 patch 成功时原字段是 def*=0（无敌），绝不能挂。
    if on && !crate::params::friendly_effect_ready() {
        return 0;
    }
    fn toggle(chr: &mut ChrIns, id: i32, on: bool) -> bool {
        let present = chr.special_effect.entries().any(|e| e.param_id == id);
        if on {
            if present {
                false
            } else {
                chr.apply_speffect(id, true);
                true
            }
        } else if present {
            chr.remove_speffect(id);
            true
        } else {
            false
        }
    }

    let mut n = 0;
    // 玩家本体永远不挂这个 effect；顺手清掉旧版 DLL 可能留在玩家身上的那份。
    if let Some(player) = world.main_player.as_mut() {
        let present = player
            .chr_ins
            .special_effect
            .entries()
            .any(|e| e.param_id == id);
        if present {
            player.chr_ins.remove_speffect(id);
        }
    }
    for chr in world.summon_buddy_chr_set.characters() {
        if !is_clone(chr) {
            continue;
        }
        if toggle(chr, id, on) {
            n += 1;
        }
    }
    n
}

/// `NPC_PARAM_ST` 的 32 个常驻 spEffect 槽（0..31）读/写。
fn sp_effect_slot(row: &eldenring::param::NPC_PARAM_ST, index: usize) -> Option<i32> {
    Some(match index {
        0 => row.sp_effect_id0(),
        1 => row.sp_effect_id1(),
        2 => row.sp_effect_id2(),
        3 => row.sp_effect_id3(),
        4 => row.sp_effect_id4(),
        5 => row.sp_effect_id5(),
        6 => row.sp_effect_id6(),
        7 => row.sp_effect_id7(),
        8 => row.sp_effect_id8(),
        9 => row.sp_effect_id9(),
        10 => row.sp_effect_id10(),
        11 => row.sp_effect_id11(),
        12 => row.sp_effect_id12(),
        13 => row.sp_effect_id13(),
        14 => row.sp_effect_id14(),
        15 => row.sp_effect_id15(),
        16 => row.sp_effect_id16(),
        17 => row.sp_effect_id17(),
        18 => row.sp_effect_id18(),
        19 => row.sp_effect_id19(),
        20 => row.sp_effect_id20(),
        21 => row.sp_effect_id21(),
        22 => row.sp_effect_id22(),
        23 => row.sp_effect_id23(),
        24 => row.sp_effect_id24(),
        25 => row.sp_effect_id25(),
        26 => row.sp_effect_id26(),
        27 => row.sp_effect_id27(),
        28 => row.sp_effect_id28(),
        29 => row.sp_effect_id29(),
        30 => row.sp_effect_id30(),
        31 => row.sp_effect_id31(),
        _ => return None,
    })
}

fn set_sp_effect_slot(row: &mut eldenring::param::NPC_PARAM_ST, index: usize, value: i32) -> bool {
    match index {
        0 => row.set_sp_effect_id0(value),
        1 => row.set_sp_effect_id1(value),
        2 => row.set_sp_effect_id2(value),
        3 => row.set_sp_effect_id3(value),
        4 => row.set_sp_effect_id4(value),
        5 => row.set_sp_effect_id5(value),
        6 => row.set_sp_effect_id6(value),
        7 => row.set_sp_effect_id7(value),
        8 => row.set_sp_effect_id8(value),
        9 => row.set_sp_effect_id9(value),
        10 => row.set_sp_effect_id10(value),
        11 => row.set_sp_effect_id11(value),
        12 => row.set_sp_effect_id12(value),
        13 => row.set_sp_effect_id13(value),
        14 => row.set_sp_effect_id14(value),
        15 => row.set_sp_effect_id15(value),
        16 => row.set_sp_effect_id16(value),
        17 => row.set_sp_effect_id17(value),
        18 => row.set_sp_effect_id18(value),
        19 => row.set_sp_effect_id19(value),
        20 => row.set_sp_effect_id20(value),
        21 => row.set_sp_effect_id21(value),
        22 => row.set_sp_effect_id22(value),
        23 => row.set_sp_effect_id23(value),
        24 => row.set_sp_effect_id24(value),
        25 => row.set_sp_effect_id25(value),
        26 => row.set_sp_effect_id26(value),
        27 => row.set_sp_effect_id27(value),
        28 => row.set_sp_effect_id28(value),
        29 => row.set_sp_effect_id29(value),
        30 => row.set_sp_effect_id30(value),
        31 => row.set_sp_effect_id31(value),
        _ => return false,
    }
    true
}

/// 把克隆体 NPC 行里指向 `ids` 的常驻 spEffect 槽改成 -1。
///
/// 只影响**之后**的召唤（param 在 spawn 时读）；已经存在的克隆体用 [`strip_speffects`]。
pub unsafe fn strip_npc_speffect_slots(
    repo: &mut SoloParamRepository,
    npc_ids: &[u32],
    ids: &[i32],
) -> Vec<(u32, Vec<(usize, i32)>)> {
    let mut out = Vec::new();
    for &npc_id in npc_ids {
        let Some(row) = repo.get_mut::<NpcParam>(npc_id) else {
            continue;
        };
        let mut changed = Vec::new();
        for index in 0..32 {
            let Some(value) = sp_effect_slot(row, index) else {
                break;
            };
            if ids.contains(&value) {
                set_sp_effect_slot(row, index, -1);
                changed.push((index, value));
            }
        }
        out.push((npc_id, changed));
    }
    out
}

/// 读一个 NpcParam 行里所有非空的常驻 spEffect id（诊断用）。
pub unsafe fn resident_speffects(repo: &SoloParamRepository, npc_id: u32) -> Vec<i32> {
    let Some(row) = repo.get::<NpcParam>(npc_id) else {
        return Vec::new();
    };
    (0..32)
        .filter_map(|index| sp_effect_slot(row, index))
        .filter(|id| *id > 0)
        .collect()
}

/// 把克隆体 NPC 行里指向「骨灰外观」的常驻 spEffect 槽改成 -1。
///
/// 只影响**之后**的召唤（param 在 spawn 时读）；已经存在的克隆体用 [`strip_glow`]。
pub unsafe fn strip_npc_glow(
    repo: &mut SoloParamRepository,
    npc_ids: &[u32],
    glow_ids: &[i32],
) -> Vec<(u32, Vec<(usize, i32)>)> {
    strip_npc_speffect_slots(repo, npc_ids, glow_ids)
}

/// 把「克隆体 NPC 行引用的 phantom shader 行」改成中性（备用路线；骨灰外观
/// 实测不是走 PhantomParam，而是 spEffect 295000，见 [`GLOW_SPEFFECTS`]）。
#[allow(dead_code)]
pub unsafe fn neutralize_clone_phantoms(
    repo: &mut SoloParamRepository,
) -> Result<(i32, Vec<u32>), String> {
    let mut shaders: Vec<i32> = Vec::new();
    for &npc_id in CLONE_NPCS {
        if let Some(npc) = repo.get::<NpcParam>(npc_id) {
            let id = npc.phantom_shader_id();
            if id > 0 && !shaders.contains(&id) {
                shaders.push(id);
            }
        }
    }
    for &id in &shaders {
        neutralize_phantom(repo, id as u32)
            .map_err(|e| format!("phantom row {id}: {e}"))?;
    }
    Ok((
        shaders.first().copied().unwrap_or(-1),
        CLONE_NPCS.to_vec(),
    ))
}

/// 诊断：PHANTOM_PARAM_ST 全表 + 关键 NpcParam 的 `phantom_shader_id`
/// + 克隆体/玩家当前挂着的 spEffect。
pub unsafe fn dump_phantom(
    repo: &mut SoloParamRepository,
    world: &mut WorldChrMan,
    npc_ids: &[u32],
) -> Result<String, String> {
    let mut rows = Vec::new();
    for (id, row) in repo.rows::<PhantomParam>() {
        rows.push(json!({
            "id": id,
            "alpha": row.alpha(),
            "blend_rate": row.blend_rate(),
            "blend_type": row.blend_type(),
            "edge_color_a": row.edge_color_a(),
            "front_color_a": row.front_color_a(),
            "diff_mul_color_a": row.diff_mul_color_a(),
            "spec_mul_color_a": row.spec_mul_color_a(),
            "light_color_a": row.light_color_a(),
            "edge_rgb": [row.edge_color_r(), row.edge_color_g(), row.edge_color_b()],
            "front_rgb": [row.front_color_r(), row.front_color_g(), row.front_color_b()],
            "light_rgb": [row.light_color_r(), row.light_color_g(), row.light_color_b()],
            "edge_power": row.edge_power(),
            "glow_scale": row.glow_scale(),
            "is_edge_subtract": row.is_edge_subtract(),
            "is_front_subtract": row.is_front_subtract(),
            "is_no2_pass": row.is_no2_pass(),
        }));
    }

    let mut npcs = Vec::new();
    for &id in npc_ids {
        if let Some(npc) = repo.get::<NpcParam>(id) {
            npcs.push(json!({
                "id": id,
                "phantom_shader_id": npc.phantom_shader_id(),
                "hp": npc.hp(),
                "team_type": npc.team_type(),
            }));
        } else {
            npcs.push(json!({ "id": id, "missing": true }));
        }
    }

    let speffects = |chr: &eldenring::cs::ChrIns| -> Vec<Value> {
        chr.special_effect
            .entries()
            .map(|e| {
                json!({
                    "id": e.param_id,
                    "duration": e.duration,
                    "removal_timer": e.removal_timer,
                })
            })
            .collect()
    };

    let mut clones = Vec::new();
    for chr in world.summon_buddy_chr_set.characters() {
        clones.push(json!({
            "npc_param_id": chr.npc_param_id,
            "team_type": chr.team_type,
            "phantom_param_override": chr.phantom_param_override,
            "base_transparency": chr.base_transparency,
            "base_transparency_modifier": chr.base_transparency_modifier,
            "tint_alpha_multiplier": chr.tint_alpha_multiplier,
            "opacity_keyframes_multiplier": chr.opacity_keyframes_multiplier,
            "camouflage_transparency": chr.camouflage_transparency,
            "mimicry_asset": chr.mimicry_asset,
            "speffects": speffects(chr),
        }));
    }
    let player = world.main_player.as_ref().map(|p| {
        json!({
            "npc_param_id": p.chr_ins.npc_param_id,
            "phantom_param_override": p.chr_ins.phantom_param_override,
            "speffects": speffects(&p.chr_ins),
        })
    });

    let value = json!({
        "phantom_rows": rows,
        "npcs": npcs,
        "clones": clones,
        "player": player,
        "summon": summon_state(world),
        "stones": stone_state(repo),
    });
    let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
    std::fs::write("er_echo_spirit.json", &text).map_err(|e| format!("write: {e}"))?;
    Ok(format!("er_echo_spirit.json: {} bytes", text.len()))
}
