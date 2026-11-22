//! 战斗验证台（M4/M5）：把**已经在场的一只克隆体**临时改成「敌对木桩」。
//!
//! 为什么这么做：要验证「权重有没有真的改变行为」「法系克隆体会不会施法」，
//! 必须有敌人。而生成新敌人需要一个 `(npc, think, chara_init)` 三元组，得和地图
//! 实体一致 —— 猜错要么生成空实体、要么崩。克隆体本来就是 `PlayerIns`，
//! `ChrIns.team_type` 又是运行时字段，改个队伍号引擎立刻按敌对处理；乱改之前把
//! 原值记下来，`dummy {"on":false}` 一键还原。全程不碰 param。
//!
//! 实测结论（2026-11-15 22:2x）：
//!
//! * **血量上限改不动**：引擎每帧从属性重算 `current_max_hp`（写 30000 下一帧就回 680），
//!   所以木桩就用它自己的血量（Sv 680 / May 396）。指标改成「掉血 / 多久打死（TTK）」，
//!   而不是「打掉了我灌的假血」。
//! * 克隆体**只认贴脸目标**：拟态 think 行原值 `eye_dist=2 / battle_start_dist=2`，
//!   敌人在 10 m 外时它们根本不理。把 `search_eye_dist` 抬到 20 m 左右之后才会
//!   「发现 → 接近 → 开打 → 放法术」（见 implementation-log §17）。

use eldenring::cs::{ChrIns, PlayerIns, WorldChrMan};
use fromsoftware_shared::{FromStatic, Superclass};
use serde_json::{json, Value};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;

/// 同伴队伍号（`ChrIns.team_type`）。
pub const CLONE_TEAM: u8 = 47;
/// 木桩默认敌对队伍：6 = 普通敌人（NpcParam 里 4475 行都是 6）。
pub const DEFAULT_TEAM: u8 = 6;

#[derive(Clone, Copy)]
struct Dummy {
    who: usize,
    team: u8,
    saved_team: u8,
    saved_hp: (u32, u32),
    since: u64,
    death_logged: bool,
}

static DUMMY: Mutex<Option<Dummy>> = Mutex::new(None);
static TEAM_FIXES: AtomicU64 = AtomicU64::new(0);

fn find<'a>(world: &'a mut WorldChrMan, team: u8, who: usize) -> Option<&'a mut ChrIns> {
    let mut idx = 0usize;
    for chr in world.summon_buddy_chr_set.characters() {
        if chr.team_type != team {
            continue;
        }
        if idx == who {
            return Some(chr);
        }
        idx += 1;
    }
    None
}

pub fn is_active() -> bool {
    DUMMY.lock().map(|g| g.is_some()).unwrap_or(false)
}

/// 打开木桩：第 `who` 只 team 47 克隆体 → `team`（血量保持原样，引擎会重算上限）。
pub fn on(who: usize, team: u8) -> Result<String, String> {
    if matches!(team, 0 | 1 | CLONE_TEAM) {
        return Err(format!("team {team} is not a hostile team (use 6 etc.)"));
    }
    if is_active() {
        let cur = DUMMY.lock().ok().and_then(|g| *g);
        return Err(match cur {
            Some(d) => format!("dummy already on (clone #{} team {})", d.who, d.team),
            None => "dummy already on".into(),
        });
    }
    let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
    let target = find(world, CLONE_TEAM, who)
        .ok_or_else(|| format!("clone #{who} not found (need team-47 summons)"))?;
    let saved_team = target.team_type;
    let saved_hp;
    {
        let p = target
            .as_subclass_mut::<PlayerIns>()
            .ok_or("target is not a PlayerIns (mimic clone required)")?;
        let pgd = unsafe { p.player_game_data.as_mut() };
        saved_hp = (pgd.current_hp, pgd.current_max_hp);
    }
    target.team_type = team;
    *DUMMY.lock().map_err(|_| "dummy lock")? = Some(Dummy {
        who,
        team,
        saved_team,
        saved_hp,
        since: crate::frame(),
        death_logged: false,
    });
    log::info!(
        "dummy: clone #{who} team {saved_team}->{team}, hp {}x{} (test target; 血量上限由引擎重算，改不了)",
        saved_hp.0,
        saved_hp.1
    );
    Ok(format!(
        "dummy on: clone #{who} team {saved_team}->{team} hp {}x{}",
        saved_hp.0, saved_hp.1
    ))
}

/// 还原木桩（队伍号 + 血量）。
pub fn off() -> Result<String, String> {
    let Some(d) = DUMMY.lock().map_err(|_| "dummy lock")?.take() else {
        return Err("dummy not active".into());
    };
    let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
    let mut n = 0;
    for chr in world.summon_buddy_chr_set.characters() {
        if chr.team_type != d.team {
            continue;
        }
        chr.team_type = d.saved_team;
        if let Some(p) = chr.as_subclass_mut::<PlayerIns>() {
            let pgd = unsafe { p.player_game_data.as_mut() };
            pgd.current_max_hp = d.saved_hp.1;
            pgd.current_hp = d.saved_hp.0.min(d.saved_hp.1);
            n += 1;
        }
    }
    log::info!(
        "dummy off: {n} chr restored to team {}, hp {}x{}",
        d.saved_team,
        d.saved_hp.0,
        d.saved_hp.1
    );
    Ok(format!("dummy off: {n} chr restored (team {})", d.saved_team))
}

/// 每 15 帧钉一次队伍号（引擎刷新时可能按 NpcParam 重算 team），并记录第一次死亡。
pub fn tick() {
    let Ok(mut guard) = DUMMY.lock() else { return };
    let Some(d) = guard.as_mut() else { return };
    let Ok(world) = (unsafe { WorldChrMan::instance_mut() }) else {
        return;
    };
    for chr in world.summon_buddy_chr_set.characters() {
        if chr.team_type != d.team {
            continue;
        }
        if TEAM_FIXES.fetch_add(1, Ordering::Relaxed) == 0 {
            log::info!("dummy: pinning team {} (engine may re-derive it)", d.team);
        }
        chr.team_type = d.team;
        if !d.death_logged {
            if let Some(p) = chr.as_subclass_mut::<PlayerIns>() {
                let pgd = unsafe { p.player_game_data.as_ref() };
                if pgd.current_hp == 0 {
                    d.death_logged = true;
                    let secs = (crate::frame().saturating_sub(d.since) as f32) / 60.0;
                    log::info!("dummy: killed after {secs:.1}s — `dummy {{\"on\":false}}` to restore");
                }
            }
        }
        break;
    }
}

/// 木桩快照：血量 / 掉血 / 存活秒数（TTK 用）。
pub fn snapshot(world: &mut WorldChrMan) -> Value {
    let d = match DUMMY.lock() {
        Ok(g) => *g,
        Err(_) => None,
    };
    let Some(d) = d else {
        return json!({ "active": false });
    };
    let mut hp: Option<u32> = None;
    let mut max: Option<u32> = None;
    for chr in world.summon_buddy_chr_set.characters() {
        if chr.team_type != d.team {
            continue;
        }
        if let Some(p) = chr.as_subclass_mut::<PlayerIns>() {
            let pgd = unsafe { p.player_game_data.as_ref() };
            hp = Some(pgd.current_hp);
            max = Some(pgd.current_max_hp);
        }
        break;
    }
    let secs = (crate::frame().saturating_sub(d.since) as f32) / 60.0;
    json!({
        "active": true,
        "who": d.who,
        "team": d.team,
        "hp": hp,
        "max": max,
        "dmg": hp.map(|h| d.saved_hp.0.saturating_sub(h)),
        "hp_start": d.saved_hp.0,
        "elapsed_s": (secs * 10.0).round() / 10.0,
        "dead": hp == Some(0),
    })
}
