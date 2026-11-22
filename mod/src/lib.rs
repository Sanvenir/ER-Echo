//! ER Echo — 游戏内 DLL 骨架（Rust / eldenring-rs 0.14 / 1.17.2）
//!
//! 这不是可编译的成品，而是「接线图」：每个 TODO 都对应 docs/design.md 的一个实验。
//! 已按官方示例的真实 API 写好入口（CSTaskImp::wait_for_instance + run_recurring）。
//!
//! 加载方式（二选一）：
//!   ModEngine2: config_eldenring.toml -> [modengine] external_dlls = ["er_echo.dll"]
//!   me3       : profile.toml -> [[natives]] path = "er_echo.dll"
//!
//! 配置：`er_echo.ini`（放在 DLL 同目录）
//!   [ipc] addr=127.0.0.1:7811 token=change-me
//!   [profile] path=./profiles/target.json
//!   [keys] summon=0x77 reload=0x78 apply=0x79
//!   [tuning] max_delta=0.15 hysteresis=0.03

mod ai;
mod balance;
mod bench;
mod dump;
mod ezstate;
mod i18n;
mod ipc;
mod kit;
mod params;
mod profile;
mod roster;
mod spirit;
mod ui;

use std::io::Write;
use std::os::windows::ffi::OsStringExt;
use std::sync::atomic::{AtomicBool, AtomicI32, AtomicU32, AtomicU64, Ordering};
use std::time::Duration;

use eldenring::cs::{
    CSTaskGroupIndex, CSTaskImp, ChrDebugSpawnRequest, ChrInsExt, CSEventFlagMan, CSLuaEventManImp,
    CSMenuManImp, EquipParamProtector, ItemCategory, ItemId, OptionalItemId, PlayerIns,
    WorldChrMan,
};
use eldenring::fd4::FD4TaskData;
use eldenring::position::HavokPosition;
use eldenring::util::input;
use fromsoftware_shared::{F32Vector4, FromStatic, SharedTaskImpExt, Superclass};

use params::Weights;

/// 极简文件日志（避免为骨架引入 env_logger）。
struct FileLogger;

static LOG_FILE: std::sync::OnceLock<std::sync::Mutex<std::fs::File>> = std::sync::OnceLock::new();
/// 日志时间戳的起点（相对进程启动的秒数 —— 比墙上时间更好对帧号）。
static LOG_START: std::sync::OnceLock<std::time::Instant> = std::sync::OnceLock::new();

impl log::Log for FileLogger {
    fn enabled(&self, _: &log::Metadata) -> bool {
        true
    }
    fn log(&self, record: &log::Record) {
        if let Some(file) = LOG_FILE.get() {
            if let Ok(mut file) = file.lock() {
                let t = LOG_START
                    .get()
                    .map(|s| s.elapsed().as_secs_f32())
                    .unwrap_or(0.0);
                let _ = writeln!(file, "[{:?} +{t:.1}s] {}", record.level(), record.args());
            }
        }
    }
    fn flush(&self) {}
}

fn init_logger() {
    if LOG_FILE.get().is_some() {
        return;
    }
    rotate_log();
    let _ = LOG_START.set(std::time::Instant::now());
    if let Ok(file) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open("er_echo.log")
    {
        let _ = LOG_FILE.set(std::sync::Mutex::new(file));
        let _ = log::set_logger(&FileLogger);
        log::set_max_level(log::LevelFilter::Info);
    }
}

/// 日志轮转：超过 8 MB 就 `er_echo.log` → `.1` → `.2`（只留两份）。
///
/// 之前是一路 append，玩了几天就已经 130 KB；长时间挂着录 state/子弹会到几十 MB，
/// 用文本编辑器打开都卡。轮转在**打开日志之前**做，所以不会丢当前这局。
fn rotate_log() {
    const MAX_BYTES: u64 = 8 * 1024 * 1024;
    let path = std::path::Path::new("er_echo.log");
    let Ok(meta) = std::fs::metadata(path) else { return };
    if meta.len() <= MAX_BYTES {
        return;
    }
    let _ = std::fs::remove_file("er_echo.log.2");
    let _ = std::fs::rename("er_echo.log.1", "er_echo.log.2");
    let _ = std::fs::rename(path, "er_echo.log.1");
}

/// 上一局的心跳/最后动作 —— 闪退后至少知道「死在哪个操作上」。
fn report_previous_session() {
    if let Ok(text) = std::fs::read_to_string("er_echo_heartbeat.txt") {
        let text = text.trim();
        if !text.is_empty() {
            log::warn!("previous session heartbeat: {text}");
        }
    }
}

/// 心跳：每 60 帧写一次（帧号 + 最后一个可能崩的操作）。
///
/// 这不是「崩溃恢复」的全部 —— DLL 里抓不到访问违例（0xc0000005 直接带走进程），
/// 但下次启动能看到上一局停在哪一步；再配合 `[debug] safe_mode` 关掉高风险特性，
/// 就够定位「换行改崩了」这类问题了。
fn write_heartbeat(frame: u64) {
    let op = LAST_OP.lock().map(|g| g.clone()).unwrap_or_default();
    let _ = std::fs::write("er_echo_heartbeat.txt", format!("frame={frame} op={op}\n"));
}

/// 记录「最后一个可能崩的操作」（写心跳时带上）。
fn set_op(op: &str) {
    if let Ok(mut g) = LAST_OP.lock() {
        *g = op.to_string();
    }
}

fn last_op() -> String {
    LAST_OP.lock().map(|g| g.clone()).unwrap_or_default()
}

/// 请求解散所有召唤物（把消失标记置位 + 停掉 keep-alive）。
fn dismiss_now() {
    CLONE_ACTIVE.store(false, Ordering::Release);
    if let Ok(world) = unsafe { WorldChrMan::instance_mut() } {
        if let Some(mgr) = spirit::manager_mut(world) {
            mgr.disappear_requested = true;
            mgr.buddy_disappear_delay_sec = 0.0;
        }
    }
}

/// 解散 → 隔 `summon_after` 帧重召。
fn start_resummon(dismiss_for: u64, summon_after: u64) {
    let now = frame();
    DISMISS_AT.store(now + dismiss_for, Ordering::Release);
    RESUMMON_AT.store(now + summon_after, Ordering::Release);
    RESUMMON_DEADLINE.store(now + summon_after + 300, Ordering::Release);
}

static PROFILE: std::sync::Mutex<Option<profile::Profile>> = std::sync::Mutex::new(None);
static FRAME: AtomicU64 = AtomicU64::new(0);
/// 卡顿诊断：相邻两帧的时间差（毫秒），每 ~5 秒取一次最大值。
static LAST_TICK_MS: AtomicU64 = AtomicU64::new(0);
static MAX_FRAME_GAP_MS: AtomicU64 = AtomicU64::new(0);
static APPLIED_SEQ: AtomicU64 = AtomicU64::new(u64::MAX);
static CURRENT: std::sync::Mutex<Weights> = std::sync::Mutex::new(Weights {
    aggression: 0.5,
    dodge_rate: 0.5,
    guard_rate: 0.5,
    combo_rate: 0.5,
    heal_priority: 0.5,
    spell_rate: 0.5,
    item_rate: 0.5,
    spacing: 0.5,
    target_switch: 0.5,
});
static DEBUG_APPLY: AtomicBool = AtomicBool::new(false);
static SUMMON_REQ: AtomicBool = AtomicBool::new(false);
/// 热键召唤的冷却（帧）。
static LAST_SUMMON_FRAME: AtomicU64 = AtomicU64::new(0);
static RELOAD_REQ: AtomicBool = AtomicBool::new(false);
static AUTO_PARAMS_DONE: AtomicBool = AtomicBool::new(false);
static AUTO_PROFILE_DONE: AtomicBool = AtomicBool::new(false);
static PENDING_RESTORE: AtomicU64 = AtomicU64::new(0);
static BACKUP_IDS: std::sync::Mutex<[i32; 22]> = std::sync::Mutex::new([0; 22]);
static SUMMON_SP: AtomicI32 = AtomicI32::new(207000); // Mimic Tear 的 trigger spEffect（实测值）
static CLONE_ACTIVE: AtomicBool = AtomicBool::new(false);
static PREP_ACTIVE: AtomicBool = AtomicBool::new(false);
static PREP_DEADLINE: AtomicU64 = AtomicU64::new(0);
static FACE_DIRTY: AtomicBool = AtomicBool::new(false);
/// 召唤后注入：按顺序给第 i 个克隆体套第 `i % len` 个档案（多存档同场）。
static CLONE_PROFILES: std::sync::Mutex<Vec<profile::Profile>> = std::sync::Mutex::new(Vec::new());
/// 每份档案的来源路径（与 `CLONE_PROFILES` 同下标）。自动升级时把改动写回磁盘。
static CLONE_PROFILE_PATHS: std::sync::Mutex<Vec<Option<String>>> =
    std::sync::Mutex::new(Vec::new());
/// 档案**从磁盘加载时**的原样快照；F12 没选中项时按它把队友恢复成原本的装备/法术。
/// 只在装档案时写入（`install_profiles`），之后的运行时改动（F12 给装备 / LLM 工具）都不碰它。
static ORIGINAL_PROFILES: std::sync::Mutex<Vec<profile::Profile>> =
    std::sync::Mutex::new(Vec::new());
static AUTO_APPLY: AtomicBool = AtomicBool::new(true);
static APPLY_STATS: AtomicBool = AtomicBool::new(false);
/// 玩家升级时队友跟着升级（并把新等级/属性写回 profile 文件）。
static AUTO_LEVEL: AtomicBool = AtomicBool::new(true);
/// 玩家上一帧的等级/属性/上限快照（只用于算「这次升级涨了什么」）。
static PLAYER_LEVEL_BASE: std::sync::Mutex<Option<PlayerLevelSnapshot>> =
    std::sync::Mutex::new(None);
/// 赐福菜单「友伤」开关：玩家/同伴的攻击能不能命中对方。
static FRIENDLY_FIRE: AtomicBool = AtomicBool::new(false);
/// 同伴使用和玩家一致的伤害修正（摘掉灵体 296000 的 ×0.25/×0.5/×0.05 削弱）。
static DAMAGE_FIX: AtomicBool = AtomicBool::new(true);
static LAST_DAMAGE_LOG: AtomicU32 = AtomicU32::new(0);
static LAST_FRIENDLY_EFFECT_LOG: AtomicU32 = AtomicU32::new(0);
/// 同伴「无限蓝」：每帧把克隆体的 FP 顶回上限（否则放几个法术就没蓝、再也不施法）。
static INFINITE_FP: AtomicBool = AtomicBool::new(true);
/// 施法观测：克隆体子弹的日志次数上限 / 见过的最大值。
static BULLET_LOGS: AtomicU32 = AtomicU32::new(0);
static BULLET_MAX: AtomicU32 = AtomicU32::new(0);
/// F6 按下的状态快照请求。
static STATUS_REQ: AtomicBool = AtomicBool::new(false);
/// 每 30 秒自动打一份状态（`[debug] auto_status`）。
static AUTO_STATUS: AtomicBool = AtomicBool::new(false);
/// 掉队保底（`[tuning] lost_resummon`）：全体都掉到 `lost_distance` 之外多久之后解散重召。
static LOST_RESUMMON: AtomicBool = AtomicBool::new(false);
static LOST_DIST_BITS: AtomicU32 = AtomicU32::new(0);
static LOST_SECONDS: AtomicU32 = AtomicU32::new(0);
static LAST_CLONE_COUNT: AtomicU32 = AtomicU32::new(0);
static LAST_FOLLOW_REPORT: AtomicU64 = AtomicU64::new(0);
static PENDING_SPAWN: std::sync::Mutex<Option<(i32, i32, i32, f32)>> = std::sync::Mutex::new(None);
/// 载体骨灰行（`[clone] buddy_rows`）；人数控制要改这些行的 trigger。
static BUDDY_ROWS: std::sync::Mutex<Vec<u32>> = std::sync::Mutex::new(Vec::new());
/// F12：把置物包当前选中项给队友；没选中则把队友恢复成档案原样。
static GIVE_REQ: AtomicBool = AtomicBool::new(false);
/// LLM 工具调用的回滚点（`set_equipment` / `set_stats` 之前的档案快照）。
static EQUIP_BACKUP: std::sync::Mutex<Option<Vec<Vec<i32>>>> = std::sync::Mutex::new(None);
static STATS_BACKUP: std::sync::Mutex<Option<Vec<profile::Profile>>> = std::sync::Mutex::new(None);
static BACKUP_FACE: std::sync::Mutex<[u8; profile::FACE_PAYLOAD_LEN]> =
    std::sync::Mutex::new([0u8; profile::FACE_PAYLOAD_LEN]);

const CONFIG: &str = "er_echo.ini";

/// DllMain 拿到的模块句柄，用来定位「DLL 自己所在的目录」。
static DLL_HMODULE: AtomicU64 = AtomicU64::new(0);

#[link(name = "kernel32")]
unsafe extern "system" {
    fn GetModuleFileNameW(module: *mut std::ffi::c_void, filename: *mut u16, size: u32) -> u32;
}

/// DLL 所在目录。取不到（例如单元测试、裸加载）返回 None。
pub(crate) fn dll_dir() -> Option<std::path::PathBuf> {
    let h = DLL_HMODULE.load(Ordering::Acquire) as *mut std::ffi::c_void;
    if h.is_null() {
        return None;
    }
    let mut buf = vec![0u16; 2048];
    let n = unsafe { GetModuleFileNameW(h, buf.as_mut_ptr(), buf.len() as u32) } as usize;
    if n == 0 || n >= buf.len() {
        return None;
    }
    let s = std::ffi::OsString::from_wide(&buf[..n]);
    std::path::Path::new(&s)
        .parent()
        .map(|p| p.to_path_buf())
}

/// 数据文件查找：**优先 DLL 同目录**，其次当前工作目录（老布局）。
///
/// 这样插件可以整包放在 `Game\er-echo\` 里：`er-echo\er_echo.dll` +
/// `er-echo\er_echo.ini`，游戏根目录不用留配置文件。
pub(crate) fn data_file(name: &str) -> std::path::PathBuf {
    if let Some(dir) = dll_dir() {
        let p = dir.join(name);
        if p.exists() {
            return p;
        }
    }
    std::path::PathBuf::from(name)
}

/// 启动时读到的配置，等 param 仓库就绪后再应用（见 `apply_config_once`）。
static CONFIG_DATA: std::sync::OnceLock<Config> = std::sync::OnceLock::new();
static CONFIG_DONE: AtomicBool = AtomicBool::new(false);

/// 召唤限制绕过：每帧把 SummonBuddyManager 的范围/冷却门禁位置真。
static ANYWHERE: AtomicBool = AtomicBool::new(false);
/// 允许「已有召唤物时再用骨灰」（清掉 player_has_alive_summon）。
static MULTI_SUMMON: AtomicBool = AtomicBool::new(false);
/// 在赐福休息完自动召唤（等价于「篝火菜单里点召唤」）。
static ON_EVENTS: AtomicBool = AtomicBool::new(false);
/// 上一步是否坐在赐福上（用于取上升/下降沿）。
static SITTING: AtomicBool = AtomicBool::new(false);
/// 计划在哪个帧执行「事件触发召唤」（0 = 没有计划）。
static SUMMON_AT: AtomicU64 = AtomicU64::new(0);
/// 触发来源（日志用）：1=坐火 2=传送/加载 3=复活。
static SUMMON_SRC: AtomicU32 = AtomicU32::new(0);
/// 召唤后做一次验证的帧（0 = 没有）；验证时若场上仍无克隆体就再召一次。
static SUMMON_VERIFY_AT: AtomicU64 = AtomicU64::new(0);
/// 验证重试剩余次数（事件后最多补 2 次，不是常驻轮询）。
static SUMMON_RETRIES: AtomicU32 = AtomicU32::new(0);
/// 上一次读到的玩家血量 / block / 加载计数 / 是否坐着（用于取边沿）。
static PLAYER_HP: AtomicU32 = AtomicU32::new(u32::MAX);
static PLAYER_BLOCK: AtomicU32 = AtomicU32::new(u32::MAX);
static LOAD_COUNTER: AtomicU32 = AtomicU32::new(u32::MAX);
/// 最近一次「进入加载画面」的帧（用于在过场/世界重置期间不碰召唤管理器）。
static LOAD_AT: AtomicU64 = AtomicU64::new(0);
/// 上一次看到的事件控制位文本（诊断用，变化才打日志）。
static LAST_FLAGS: std::sync::Mutex<String> = std::sync::Mutex::new(String::new());
/// 坐火期间用于发现「世界刷新把克隆体清空」的计数。
static RESET_CLONE_COUNT: AtomicU32 = AtomicU32::new(0);
/// 启动时把每行 `BuddyStoneParam.activate_range` 抬到这个值（0 = 不改）。
static STONE_RANGE: AtomicU32 = AtomicU32::new(0);
/// 灵体外观归零（把克隆体用的 phantom shader 行改成中性）。
static GLOW_OFF: AtomicBool = AtomicBool::new(false);
/// 中性化用哪一行 `PHANTOM_PARAM_ST`（-1 = 不动）。
static PHANTOM_ROW: AtomicI32 = AtomicI32::new(-1);
/// 要去掉的「骨灰外观」spEffect（默认 295000/295200，见 spirit::GLOW_SPEFFECTS）。
static GLOW_IDS: std::sync::Mutex<Vec<i32>> = std::sync::Mutex::new(Vec::new());
/// glow_off 日志节流（引擎若每帧重挂 spEffect，别刷屏）。
static LAST_GLOW_LOG: AtomicU64 = AtomicU64::new(0);
/// 「安全模式」：关掉高风险特性（事件召唤 / 灵体摘除 / 木桩 / 调试生成），
/// 闪退排查时用（`[debug] safe_mode=true` 或 `safe_mode on`）。
static SAFE_MODE: AtomicBool = AtomicBool::new(false);
/// 最后一个可能崩的操作（写进心跳文件，下次启动可见）。
static LAST_OP: std::sync::Mutex<String> = std::sync::Mutex::new(String::new());
/// 排队重召（解散之后隔 120 帧再召，避免和消失流程撞车）。
static RESUMMON_AT: AtomicU64 = AtomicU64::new(0);
/// 正在「解散」：这期间必须停掉 `summon_anywhere` 的门禁绕过 ——
/// 它每帧把 `disappear_requested` 置回 false，否则请求消失永远不生效
/// （实测：`resummon` 日志说「request sent」，场上克隆体一个没少）。
static DISMISS_AT: AtomicU64 = AtomicU64::new(0);
/// 重召的**绝对**截止帧：等不到 manager 清干净就在这里强制补一队。
/// （不能拿 `RESUMMON_AT` 自己当截止 —— 每次「再等 30 帧」都会把窗口一起推后，永远等不到。）
static RESUMMON_DEADLINE: AtomicU64 = AtomicU64::new(0);
/// 掉队保底：全体克隆体都远到一定程度之后，从哪一帧开始算。
static LOST_SINCE: AtomicU64 = AtomicU64::new(0);
static LAST_RESUMMON: AtomicU64 = AtomicU64::new(0);
/// 当前帧（给 bench/命令用）。
pub(crate) fn frame() -> u64 {
    FRAME.load(Ordering::Relaxed)
}

/// 取当前要摘的 spEffect 列表（空 = 用默认值）。
fn glow_ids() -> Vec<i32> {
    match GLOW_IDS.lock() {
        Ok(v) if !v.is_empty() => v.clone(),
        _ => spirit::GLOW_SPEFFECTS.to_vec(),
    }
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn DllMain(hmodule: u64, reason: u32) -> bool {
    if reason != 1 {
        return true;
    }
    DLL_HMODULE.store(hmodule, Ordering::Release);
    // 不要在 loader lock 里做初始化：起线程，等游戏任务系统就绪。
    std::thread::spawn(move || {
        init_logger();
        report_previous_session();
        log::info!("er_echo thread spawned; waiting for CSTaskImp (target exe 2.7.2.0)");
        let cfg = Config::load(&data_file(CONFIG));
        set_follow_dist(cfg.follow_distance);
        AUTO_RECALL.store(cfg.auto_recall, Ordering::Release);
        ipc::start(cfg.ipc_addr.clone(), cfg.ipc_token.clone());
        let _ = CONFIG_DATA.set(cfg);

        let cs_task = match std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            CSTaskImp::wait_for_instance(Duration::MAX)
        })) {
            Ok(Ok(task)) => task,
            Ok(Err(_)) => {
                log::error!("CSTaskImp not found — 游戏版本不匹配？DLL 保持空闲");
                return;
            }
            Err(_) => {
                log::error!("wait_for_instance panicked（exe 名/版本不匹配）— DLL 保持空闲");
                return;
            }
        };
        log::info!("er_echo attached (target exe 2.7.2.0)");
        // EzState 注入钩子尽早装（标题界面时 talk machine 还没跑起来）。
        // 即使 nested_menu=false 也装钩子：detour 里只做一次原子读就放行，
        // 这样运行期可以用 IPC 随时开/关，而不用重编译。
        ezstate::set_enabled(CONFIG_DATA.get().map(|c| c.nested_menu).unwrap_or(true));
        unsafe {
            ezstate::install();
        }
        log::info!("ezstate: {}", ezstate::status());
        cs_task.run_recurring(tick, CSTaskGroupIndex::FrameBegin);
    });
    true
}

/// 把当前名单的「人数」落到载体骨灰行上（第 4 个以后不再召唤）。
fn apply_roster_count() {
    let profiles = clone_profiles();
    let count = roster::active_count(profiles.len());
    let rows = BUDDY_ROWS.lock().map(|g| g.clone()).unwrap_or_default();
    if rows.is_empty() {
        return;
    }
    let (_, base) = unsafe { params::apply_buddy_count(&rows, count) };
    // 引擎的 trigger→BuddyParam 映射链是世界加载时建的，改 BuddyParam 不会更新它；
    // 这里把链对齐到当前人数（截断/重连），人数切换后不用重开游戏也能生效。
    if base > 0 {
        if let Ok(world) = unsafe { WorldChrMan::instance_mut() } {
            if spirit::manager(world).is_some() {
                let ok = unsafe { spirit::sync_trigger_chain(world, base, &rows, count) };
                if !ok && count > 0 {
                    log::warn!("buddy chain: sync failed (trigger={base}, count={count})");
                }
            }
        }
    }
}

/// 把「置物包/装备菜单当前选中项」给当前出场的队友。
///
/// 落点：
/// * 武器 → 右手当前槽（1），**不**碰待切换的 3/5；
/// * 防具 → 按 `protector_category` 直接替换 12..15；
/// * 护符 → 第 1 个护符槽（17）；
/// * 法术 → 插到记忆列表**最前面**（`kit::apply` 按 `spell_rate` 只取前 N 发，
///   追加到末尾在低施法率下不生效）。
///
/// 如果菜单没有选中项（`selected_*` 为 NONE），不再复制玩家装备，而是把出场队友的
/// **装备和法术恢复成档案原样**（`ORIGINAL_PROFILES`，加载档案时留的快照）。
fn give_selected() -> Result<String, String> {
    let (goods, magic_item) = match unsafe { CSMenuManImp::instance_mut() } {
        Ok(menu) => (
            menu.player_menu_ctrl.selected_goods_item,
            menu.player_menu_ctrl.selected_magic_item,
        ),
        Err(_) => (OptionalItemId::NONE, OptionalItemId::NONE),
    };

    let mut slot_id: Option<(usize, i32)> = None;
    if let Some(item) = goods.as_valid() {
        match item.category() {
            ItemCategory::Weapon => slot_id = Some((1, item.param_id() as i32)),
            ItemCategory::Protector => {
                if let Some(cat) = unsafe { params::repo() }
                    .and_then(|r| r.get::<EquipParamProtector>(item.param_id()))
                    .map(|r| r.protector_category())
                {
                    slot_id = Some((12 + cat.min(3) as usize, item.param_id() as i32));
                }
            }
            ItemCategory::Accessory => slot_id = Some((17, item.param_id() as i32)),
            _ => {}
        }
    }
    let spell = magic_item.as_valid().map(|i| i.param_id() as i32);

    // 关键：改的是**档案**而不是克隆体。auto_apply 每 15 帧按档案重写装备，
    // 直接写克隆体的话最多 15 帧就被覆盖回去了。
    let mut profiles = clone_profiles();
    if profiles.is_empty() {
        return Err("no clone profiles loaded".into());
    }
    let count = roster::active_count(profiles.len());

    // 没选中 → 恢复档案原样。只回滚 F12 能改的东西（装备槽 + 法术），
    // 等级/属性/外观不在这里处理（那是 set_stats / 重载档案的事）。
    if slot_id.is_none() && spell.is_none() {
        let original = ORIGINAL_PROFILES
            .lock()
            .map(|g| g.clone())
            .unwrap_or_default();
        if original.is_empty() {
            return Err("no original profiles loaded (reload profile first)".into());
        }
        let mut n = 0usize;
        let mut fields = 0usize;
        for i in 0..count {
            let idx = roster::slot_for_clone(i, profiles.len());
            if idx < 0 {
                continue;
            }
            let Some(orig) = original.get(idx as usize) else {
                continue;
            };
            let target = &mut profiles[idx as usize];
            if target.equipment_param_ids != orig.equipment_param_ids {
                target
                    .equipment_param_ids
                    .clone_from(&orig.equipment_param_ids);
                fields += 1;
            }
            if target.magic != orig.magic {
                target.magic.clone_from(&orig.magic);
                fields += 1;
            }
            n += 1;
        }
        if n == 0 {
            return Err("no active companion (summon first)".into());
        }
        *CLONE_PROFILES.lock().map_err(|_| "profile lock")? = profiles;
        apply_to_clones(false)?;
        log::info!("give: restore original gear for {n} companion(s), {fields} field(s) reverted");
        return Ok(format!("give: restore original -> {n} companion(s)"));
    }

    let mut n = 0usize;
    let mut changed = 0usize;
    for i in 0..count {
        let idx = roster::slot_for_clone(i, profiles.len());
        if idx < 0 {
            continue;
        }
        let target = &mut profiles[idx as usize];
        if let Some((slot, id)) = slot_id {
            target.equipment_param_ids[slot] = id;
            changed += 1;
        }
        if let Some(spell) = spell {
            if !target.magic.contains(&spell) && target.magic.len() < crate::ai::MAGIC_SLOTS {
                // 放最前面：kit::apply 按 spell_rate 只取前 ceil(rate*n) 发，
                // 追加到末尾的话低 spell_rate 下新法术不会生效。
                target.magic.insert(0, spell);
                changed += 1;
            }
        }
        n += 1;
    }
    if n == 0 {
        return Err("no active companion (summon first)".into());
    }
    *CLONE_PROFILES.lock().map_err(|_| "profile lock")? = profiles;
    apply_to_clones(false)?;

    let what = match slot_id {
        Some((slot, id)) => format!("slot {slot} <- item {id}"),
        None => format!("spell {spell:?}"),
    };
    log::info!("give: {what} to {n} companion(s), {changed} profile edit(s), spell={spell:?}");
    Ok(format!("give: {what} -> {n} companion(s)"))
}

// ---------------------------------------------------------------- 队友 AI

/// 第 `slot` 号位当前用的档案下标（只看 `roster.slots`，不看人数）。
fn slot_profile_index(profiles: &[profile::Profile], slot: usize) -> Option<usize> {
    if profiles.is_empty() || slot >= roster::MAX_SLOTS {
        return None;
    }
    let idx = roster::get().slots[slot];
    if idx < 0 || idx as usize >= profiles.len() {
        None
    } else {
        Some(idx as usize)
    }
}

/// 状态/日志里的 AI 名字：`inherit`（跟随全局）/ `custom`（数字手改）/ 预设 code。
fn ai_code(ai: Option<ai::AiProfile>) -> &'static str {
    match ai {
        None => "inherit",
        Some(a) if a.label_key() == "ai_custom" => "custom",
        Some(a) => a.preset.code(),
    }
}

/// 把每个号位的 AI 落到「它自己的 think 行」+ 载体骨灰行。
///
/// * 档案设置了 `ai` 时，这个号位用**自己的一行** `NpcThinkParam`（ini
///   `[ai] teammate_think_rows`，默认 100000020/30/40）：先整行复制全局 think 行
///   （拟态泪滴 100000010，含全局权重），再只改这个队友的
///   `aggression / guard_rate / target_switch`；
/// * 档案没有 `ai`（旧 profile / 手改删掉）= 跟随全局：直接用 `think_row`，
///   不去碰那几行 —— 谁都没点过菜单时行为和加这个功能之前完全一样；
/// * 最后把 `BuddyParam.npc_think_param_id` 指到对应行 —— 引擎在**生成那一刻**读它，
///   所以换 AI 后要下次召唤才生效（法术槽是每个克隆体自己写，立即生效）。
///
/// 调用时机：配置初始化、菜单改人数/号位/AI、全局权重变化、profile 重载，
/// 以及 tick 里每 20 秒兜底一次。
fn sync_teammate_ai() {
    let Some(repo) = (unsafe { params::repo() }) else {
        return;
    };
    sync_teammate_ai_with(repo);
}

/// 同 [`sync_teammate_ai`]，复用调用方已拿到的 repo（`apply_config_once` 里）。
fn sync_teammate_ai_with(repo: &mut eldenring::cs::SoloParamRepository) {
    let profiles = clone_profiles();
    if profiles.is_empty() {
        return;
    }
    let (_behavior_row, think_row, _npc_row) = params::rows::get();
    // 出生体型不依赖 think 行：先做（think 行没配也要能按档案长身体）。
    sync_teammate_bodies_with(repo);
    if think_row == 0 {
        return;
    }
    let global = *CURRENT.lock().unwrap_or_else(|e| e.into_inner());
    let leash = leash();
    let buddy_rows = BUDDY_ROWS.lock().map(|g| g.clone()).unwrap_or_default();

    let mut assigned = [think_row; params::AI_SLOT_COUNT];
    let mut presets: Vec<&'static str> = Vec::with_capacity(params::AI_SLOT_COUNT);
    for i in 0..params::AI_SLOT_COUNT {
        // 没设置 ai 的档案 = 跟随全局：不占用独立 think 行，也不碰那几行，
        // 这样「谁都没在菜单里点过」时和加这个功能之前 100% 一样。
        let Some(ai) = slot_profile_index(&profiles, i).and_then(|idx| profiles[idx].ai) else {
            presets.push("inherit");
            continue;
        };
        let a = ai.weights();
        let mut w = global;
        w.aggression = a.aggression;
        w.guard_rate = a.guard_rate;
        w.target_switch = a.target_switch;
        // 只用于 kit::apply 的每克隆体法术槽；写 think 行时用不到。
        w.spell_rate = a.spell_rate;
        presets.push(ai.preset.code());
        if let Some(row) = unsafe { params::apply_teammate_ai(repo, i, think_row, &w, leash) } {
            assigned[i] = row;
        }
    }
    let changed = unsafe { params::set_buddy_think_rows(repo, &buddy_rows, &assigned) };

    // 只在「映射真的变了」时打日志（这个函数会被定时兜底调用）。
    static LAST: std::sync::Mutex<Option<([u32; 3], [u32; 3])>> =
        std::sync::Mutex::new(None);
    let snapshot = (params::teammate_think_rows(), assigned);
    let mut last = LAST.lock().unwrap_or_else(|e| e.into_inner());
    if last.as_ref() != Some(&snapshot) || changed > 0 {
        log::info!(
            "ai: think row per slot {:?} (global={think_row}, buddy_rows={} changed={changed}, presets={presets:?})",
            assigned,
            buddy_rows.len()
        );
        *last = Some(snapshot);
    }
}

/// 把每个号位的「出生体型」落到 `CharaInitParam -> FACE_PARAM` 行上（§28）。
///
/// 体型是建模型时烘焙的，出生后改不了；所以这里给 1/2/3 号位各复制一行
/// init + face 行、写入该号位档案的 5 个滑条和 body_type，并把载体骨灰行的
/// `npc_player_init_param_id` 指过去。下次召唤生效。
///
/// 只在「号位→档案/体型/载体行」真的变化时才重做（sync_teammate_ai 每 20 秒兜底调用）。
fn sync_teammate_bodies_with(repo: &mut eldenring::cs::SoloParamRepository) {
    let profiles = clone_profiles();
    if profiles.is_empty() {
        return;
    }
    let buddy_rows = BUDDY_ROWS.lock().map(|g| g.clone()).unwrap_or_default();

    // FNV-1a 签名：号位档案下标 + body_type + 5 个体型字节 + 载体行 id
    let mut sig: u64 = 0xcbf2_9ce4_8422_2325;
    let mut mix = |v: u64| {
        sig ^= v;
        sig = sig.wrapping_mul(0x0000_0100_0000_01b3);
    };
    for i in 0..params::AI_SLOT_COUNT {
        let slot = roster::slot_for_clone(i, profiles.len());
        mix(i as u64);
        mix(buddy_rows.get(i).copied().unwrap_or(0) as u64);
        if slot < 0 {
            mix(0xFFFF_FFFF);
            continue;
        }
        let p = &profiles[(slot as usize) % profiles.len()];
        mix(slot as u64);
        mix(p.body_type as u64);
        let face = p.face();
        if face.len() >= profile::FACE_BODY_OFFSET + 5 {
            for b in &face[profile::FACE_BODY_OFFSET..profile::FACE_BODY_OFFSET + 5] {
                mix(*b as u64);
            }
        }
    }
    static LAST_BODY_SIG: std::sync::Mutex<Option<u64>> = std::sync::Mutex::new(None);
    if let Ok(last) = LAST_BODY_SIG.lock() {
        if last.as_ref() == Some(&sig) {
            return;
        }
    }
    match unsafe { params::setup_teammate_bodies(repo, &profiles, &buddy_rows) } {
        Ok(value) => {
            log::info!("bodies: {value}");
            if let Ok(mut last) = LAST_BODY_SIG.lock() {
                *last = Some(sig);
            }
        }
        Err(err) => log::warn!("bodies: setup failed: {err}"),
    }
}

/// 赐福菜单三级菜单「队友 AI」：把第 `slot` 个号位档案的预设切到下一个，并写回 profile 文件。
///
/// 写回的是 `CLONE_PROFILE_PATHS[idx]`（ini `profiles=` / `load_profile` /
/// `set_clone_profiles` 带进来的源路径）；没有路径时只在内存里改并告警。
fn cycle_teammate_ai(slot: usize) -> Result<String, String> {
    let mut profiles = clone_profiles();
    if profiles.is_empty() {
        return Err("no clone profiles loaded".into());
    }
    let idx = slot_profile_index(&profiles, slot).ok_or_else(|| {
        format!(
            "slot {} has no companion (pick a profile on the slot row first)",
            slot + 1
        )
    })?;
    let next = match profiles[idx].ai {
        Some(ai) => ai.cycle(),
        None => ai::AiProfile::from_preset(ai::AiPreset::Balanced),
    };
    profiles[idx].ai = Some(next);
    // 原始快照同步 ai：F12 只恢复装备/法术，但两份档案保持一致，排查时不会自相矛盾。
    if let Ok(mut originals) = ORIGINAL_PROFILES.lock() {
        if let Some(p) = originals.get_mut(idx) {
            p.ai = Some(next);
        }
    }
    let paths = profile_paths();
    let path = paths.get(idx).cloned().flatten();
    let written = match &path {
        Some(path) => match save_profile(path, &profiles[idx]) {
            Ok(()) => true,
            Err(err) => {
                log::warn!("ai: write '{path}' failed: {err}");
                false
            }
        },
        None => {
            log::warn!("ai: profile {idx} has no source path; AI kept in memory only");
            false
        }
    };
    let name = profiles[idx].name.clone();
    *CLONE_PROFILES.lock().map_err(|_| "profile lock")? = profiles;
    sync_teammate_ai();
    // 法术槽立即生效；交战半径/举盾/换目标要下次召唤（引擎按 BuddyParam 行取 think）。
    if let Err(err) = apply_to_clones(false) {
        log::info!("ai: live apply skipped: {err}");
    }
    ui::refresh_texts();
    let w = next.weights();
    log::info!(
        "ai: slot {} profile[{idx}] '{}' -> {:?} (aggr={:.2} spell={:.2} guard={:.2} target={:.2}), write_back={written}",
        slot + 1,
        name,
        next.preset,
        w.aggression,
        w.spell_rate,
        w.guard_rate,
        w.target_switch
    );
    Ok(format!(
        "ai: slot {} '{}' -> {}",
        slot + 1,
        name,
        next.preset.code()
    ))
}

/// 显式设置某个号位档案的 AI（IPC `set_teammate_ai`，也用于手改数字）。
fn set_teammate_ai(slot: usize, preset: Option<ai::AiPreset>, args: &serde_json::Value) -> Result<String, String> {
    let mut profiles = clone_profiles();
    if profiles.is_empty() {
        return Err("no clone profiles loaded".into());
    }
    let idx = slot_profile_index(&profiles, slot)
        .ok_or_else(|| format!("slot {} has no companion", slot + 1))?;
    let inherit = args
        .get("inherit")
        .and_then(|v| v.as_bool())
        .unwrap_or(false);
    let new_ai = if inherit {
        None
    } else {
        let mut ai = profiles[idx].ai.unwrap_or_default();
        if let Some(p) = preset {
            ai = ai::AiProfile::from_preset(p);
        }
        for (key, dst) in [
            ("aggression", &mut ai.aggression),
            ("spell_rate", &mut ai.spell_rate),
            ("guard_rate", &mut ai.guard_rate),
            ("target_switch", &mut ai.target_switch),
        ] {
            if let Some(v) = args.get(key).and_then(|v| v.as_f64()) {
                *dst = (v as f32).clamp(0.0, 1.0);
            }
        }
        Some(ai)
    };
    profiles[idx].ai = new_ai;
    if let Ok(mut originals) = ORIGINAL_PROFILES.lock() {
        if let Some(p) = originals.get_mut(idx) {
            p.ai = new_ai;
        }
    }
    let paths = profile_paths();
    let path = paths.get(idx).cloned().flatten();
    let written = match &path {
        Some(path) => match save_profile(path, &profiles[idx]) {
            Ok(()) => true,
            Err(err) => {
                log::warn!("ai: write '{path}' failed: {err}");
                false
            }
        },
        None => false,
    };
    let name = profiles[idx].name.clone();
    let label = new_ai.map(|a| a.label_key()).unwrap_or("inherit");
    let detail = new_ai
        .map(|a| {
            let w = a.weights();
            format!(
                "aggr={:.2} spell={:.2} guard={:.2} target={:.2}",
                w.aggression, w.spell_rate, w.guard_rate, w.target_switch
            )
        })
        .unwrap_or_default();
    *CLONE_PROFILES.lock().map_err(|_| "profile lock")? = profiles;
    sync_teammate_ai();
    let _ = apply_to_clones(false);
    ui::refresh_texts();
    log::info!(
        "ai: set slot {} profile[{idx}] '{}' -> {label} ({detail}), write_back={written}",
        slot + 1,
        name
    );
    Ok(format!("ai: slot {} '{}' -> {label}", slot + 1, name))
}

/// 原生赐福菜单写的标志 → 队伍配置。
fn poll_roster_flags() {
    if !CONFIG_DONE.load(Ordering::Acquire) {
        return;
    }
    let Some(flag) = (unsafe { roster::take_flag() }) else {
        return;
    };
    // 友伤开关不依赖档案：没有加载 profile 也能改。
    if flag == roster::FLAG_FRIENDLY_FIRE {
        let on = roster::toggle_friendly_fire();
        FRIENDLY_FIRE.store(on, Ordering::Release);
        let rate = params::friendly_rate();
        match unsafe { params::set_friendly_fire(on) } {
            Ok((changed, total, already)) => log::info!(
                "menu: friendly_fire -> {on} ({changed} AtkParam_Pc row(s) changed, total={total}, already={already}, damage={:.0}%)",
                rate * 100.0
            ),
            Err(err) => log::warn!("menu: friendly_fire -> {on} failed: {err}"),
        }
        if on {
            match unsafe { params::patch_friendly_damage_effect(rate) } {
                Ok(rate) => log::info!("menu: friendly fire damage -> {:.0}%", rate * 100.0),
                Err(err) => log::warn!("menu: friendly fire damage effect failed: {err}"),
            }
        }
        if let Ok(world) = unsafe { WorldChrMan::instance_mut() } {
            let changed = spirit::set_friendly_damage_effect(world, on);
            if changed > 0 {
                log::info!(
                    "menu: friendly_fire={on} -> damage effect {} on {changed} clone(s)",
                    if on { "applied" } else { "removed" }
                );
            }
            let n = spirit::set_clone_lock_on_blocked(world, on);
            if n > 0 {
                log::info!("menu: friendly_fire={on} -> lock-on blocked on {n} clone(s)");
            }
        }
        if !on {
            unsafe { params::restore_friendly_damage_effect() };
        }
        ui::refresh_texts();
        return;
    }
    let profiles = clone_profiles();
    if profiles.is_empty() {
        return;
    }
    // 三级菜单「队友 AI」：每个号位一个标志，点一次切到下一个预设并写回 profile。
    if let Some(slot) = roster::FLAG_AI_SLOT.iter().position(|f| *f == flag) {
        match cycle_teammate_ai(slot) {
            Ok(msg) => log::info!("menu: {msg}"),
            Err(err) => log::warn!("menu: ai slot {}: {err}", slot + 1),
        }
        return;
    }
    match flag {
        roster::FLAG_COUNT_0 => {
            roster::set_count(0, profiles.len());
            apply_roster_count();
            log::info!("menu: companion count -> 0 (no summon until changed)");
        }
        roster::FLAG_COUNT_1 => {
            roster::set_count(1, profiles.len());
            apply_roster_count();
            log::info!("menu: companion count -> 1");
        }
        roster::FLAG_COUNT_2 => {
            roster::set_count(2, profiles.len());
            apply_roster_count();
            log::info!("menu: companion count -> 2");
        }
        roster::FLAG_COUNT_3 => {
            roster::set_count(3, profiles.len());
            apply_roster_count();
            log::info!("menu: companion count -> 3");
        }
        roster::FLAG_SLOT_0 => {
            roster::cycle_slot(0, profiles.len());
        }
        roster::FLAG_SLOT_1 => {
            roster::cycle_slot(1, profiles.len());
        }
        roster::FLAG_SLOT_2 => {
            roster::cycle_slot(2, profiles.len());
        }
        roster::FLAG_APPLY => {
            log::info!("menu: apply roster -> dismiss + re-summon");
            apply_roster_count();
            start_resummon(30, 90);
        }
        roster::FLAG_COUNT_CYCLE => {
            let next = (roster::get().count + 1) % 4;
            roster::set_count(next, profiles.len());
            apply_roster_count();
            log::info!("menu: companion count -> {next} (cycle)");
        }
        _ => {}
    }
    // 名单/人数变了 → 每个号位的 AI 也要跟着换到新档案/新行。
    sync_teammate_ai();
    ui::refresh_texts();
}

fn tick(_task: &FD4TaskData) {
    let frame = FRAME.fetch_add(1, Ordering::Relaxed) + 1;

    // ---- 卡顿诊断：记录相邻帧最大间隔；ezstate 钩子的调用次数/耗时 ----
    if let Some(start) = LOG_START.get() {
        let now_ms = start.elapsed().as_millis() as u64;
        let last = LAST_TICK_MS.swap(now_ms, Ordering::Relaxed);
        if last != 0 {
            MAX_FRAME_GAP_MS.fetch_max(now_ms.saturating_sub(last), Ordering::Relaxed);
        }
    }
    if frame % 300 == 0 {
        let gap = MAX_FRAME_GAP_MS.swap(0, Ordering::Relaxed);
        let (calls, micros) = ezstate::perf_take();
        // 坐火/传送时游戏自己的世界重置会有 100~300ms 的卡顿，不算我们的问题；
        // 只有 EzState 钩子本身累计 >20ms 或单帧 >400ms 才值得报警。
        if micros > 20_000 || gap > 400 {
            log::warn!("perf: max frame gap {gap}ms, ezstate {calls} calls/{micros}us (last ~5s)");
        } else if frame % 3600 == 0 {
            log::info!("perf: max frame gap {gap}ms, ezstate {calls} calls/{micros}us (last ~5s)");
        }
    }

    // ---- 热键（调试）----
    if input::is_key_pressed(0x77) {
        SUMMON_REQ.store(true, Ordering::Release);
    }
    if input::is_key_pressed(0x78) {
        RELOAD_REQ.store(true, Ordering::Release);
    }
    if input::is_key_pressed(0x79) {
        DEBUG_APPLY.store(!DEBUG_APPLY.load(Ordering::Acquire), Ordering::Release);
        log::info!("debug apply = {}", DEBUG_APPLY.load(Ordering::Acquire));
    }
    // F6 = 打印一份当前状态（克隆体/木桩/权重/开关）
    if input::is_key_pressed(0x75) {
        STATUS_REQ.store(true, Ordering::Release);
    }
    // F11 = 开关「持续注入」（查「注入是不是让 AI 变傻」时用）
    if input::is_key_pressed(0x7a) {
        let now = !AUTO_APPLY.load(Ordering::Acquire);
        AUTO_APPLY.store(now, Ordering::Release);
        log::info!("hotkey F11: auto_apply = {now}");
    }
    // F12 = 把置物包/装备菜单当前选中项给队友（不选中则恢复档案原样）
    if input::is_key_pressed(0x7b) {
        GIVE_REQ.store(true, Ordering::Release);
    }
    // F7 = 收回克隆体（等价于 dismiss）
    if input::is_key_pressed(0x76) {
        CLONE_ACTIVE.store(false, Ordering::Release);
        if let Ok(world) = unsafe { WorldChrMan::instance_mut() } {
            if let Some(mgr) = spirit::manager_mut(world) {
                mgr.disappear_requested = true;
                mgr.buddy_disappear_delay_sec = 0.0;
            }
        }
        log::info!("hotkey F7: dismiss requested (auto summon off until next F8/rest)");
    }

    // ---- 请求 ----
    if RELOAD_REQ.swap(false, Ordering::AcqRel) {
        reload_profile();
    }
    if SUMMON_REQ.swap(false, Ordering::AcqRel) {
        // 热键有 250ms 去抖，按住会连发；这里再加 1 秒冷却，避免一口气召出十几组。
        let now = FRAME.load(Ordering::Relaxed);
        if now.saturating_sub(LAST_SUMMON_FRAME.load(Ordering::Acquire)) >= 60 {
            LAST_SUMMON_FRAME.store(now, Ordering::Release);
            if let Err(err) = summon() {
                log::error!("summon failed: {err}");
            }
        }
    }

    // ---- 等玩家用骨灰：检测到克隆体出现后还原玩家 ----
    if PREP_ACTIVE.load(Ordering::Acquire) {
        let (req, clone_present) = {
            let Ok(world) = (unsafe { WorldChrMan::instance_mut() }) else { return };
            let present = world
                .summon_buddy_chr_set
                .characters()
                .any(|c| c.team_type == 47 && matches!(c.npc_param_id, 133201000 | 100000010));
            let req = spirit::manager(world).map_or(-1, |m| m.request_summon_speffect_id);
            (req, present)
        };
        let frame_now = FRAME.load(Ordering::Relaxed);
        if req != -1 || clone_present {
            PREP_ACTIVE.store(false, Ordering::Release);
            PENDING_RESTORE.store(frame_now + 90, Ordering::Release);
            log::info!(
                "prep_clone: summon detected (req={req}, clone_present={clone_present}); restore in 90 frames"
            );
        } else if frame_now > PREP_DEADLINE.load(Ordering::Acquire) {
            PREP_ACTIVE.store(false, Ordering::Release);
            restore_player();
            log::info!("prep_clone: timeout, player restored");
        }
    }

    // ---- 延迟生成：等玩家坐标有效（读档/传送时 chunk_position 是 0）----
    try_pending_spawn();

    // ---- 手动状态快照（F6）----
    if STATUS_REQ.swap(false, Ordering::AcqRel) {
        log::info!("{}", status_line().unwrap_or_else(|e| format!("status failed: {e}")));
    }

    // ---- 配置驱动的自动准备（只跑一次，等 param 仓库/玩家就绪）----
    apply_config_once();
    // ---- 原生赐福菜单（队伍人数 / 名单）----
    poll_roster_flags();
    // ---- 人数上限：踢掉引擎多召出来的组 ----
    // 引擎的 trigger→BuddyParam 映射是启动时建的，改 BuddyParam.trigger 不会少召
    // （实测人数=1 仍召 3 个），所以按 SummonBuddyGroup.buddy_param_id 后处理。
    if !world_busy() && !SAFE_MODE.load(Ordering::Acquire) {
        let profiles = clone_profiles();
        let want = roster::active_count(profiles.len());
        if !profiles.is_empty() {
            let rows = BUDDY_ROWS.lock().map(|g| g.clone()).unwrap_or_default();
            if !rows.is_empty() && want < rows.len() {
                if let Ok(world) = unsafe { WorldChrMan::instance_mut() } {
                    let group_count = spirit::group_buddy_ids(world).len();
                    if group_count > want {
                        let alive = world.summon_buddy_chr_set.characters().count();
                        let n = spirit::trim_extra_buddy_groups(world, want, &rows);
                        if n > 0 {
                            log::info!(
                                "roster: trim {n} extra summon group(s) -> {want} (chr set {alive})"
                            );
                        } else if frame % 300 == 0 {
                            log::info!(
                                "roster: {group_count} group(s) > want {want}, nothing marked yet; groups={:?}",
                                spirit::group_buddy_ids(world)
                            );
                        }
                    }
                }
            }
        }
    }
    // ---- F12：把选中项给队友 / 没选中则恢复档案原样 ----
    if GIVE_REQ.swap(false, Ordering::AcqRel) {
        if let Err(err) = give_selected() {
            log::warn!("give failed: {err}");
        }
    }

    // ---- 事件触发召唤：坐火 / 传送 / 复活（不做常驻维持）----
    // 只在进游戏之后读（标题/读盘时 CSLuaEventMan 的 proxy 还没建好）。
    let in_game = unsafe { WorldChrMan::instance_mut() }
        .map(|w| w.main_player.is_some())
        .unwrap_or(false);
    if ON_EVENTS.load(Ordering::Acquire) && !SAFE_MODE.load(Ordering::Acquire) {
        detect_summon_events(in_game);
        run_scheduled_summon();
        run_summon_verify();
    }

    // ---- 解散后重召（掉队保底 / `resummon` 命令）----
    let resummon_at = RESUMMON_AT.load(Ordering::Acquire);
    if resummon_at != 0 && frame >= resummon_at && !world_busy() {
        // 等「上一队」彻底清掉再请求：manager 的 active id 还是 232000 时再写
        // request，引擎会直接丢掉（实测：request -1->-1、chrs 不涨）。
        let settled = unsafe { WorldChrMan::instance_mut() }
            .map(|w| {
                spirit::manager(w)
                    .map(|m| {
                        m.active_summon_speffect_id <= 0
                            && m.request_summon_speffect_id <= 0
                            && !m.player_has_alive_summon
                    })
                    .unwrap_or(false)
            })
            .unwrap_or(false);
        if !settled && frame < RESUMMON_DEADLINE.load(Ordering::Acquire) {
            RESUMMON_AT.store(frame + 30, Ordering::Release);
            if frame % 120 < 30 {
                log::info!("resummon: waiting for previous squad to clear");
            }
        } else {
            RESUMMON_AT.store(0, Ordering::Release);
            if !settled {
                // 引擎在某些状态下会忽略 `disappear_requested`（实测：8 秒都没消失）。
                // 因为开了 `multi_summon`（会清 player_has_alive_summon），直接补一队也能成功。
                log::warn!(
                    "resummon: previous squad still alive ({} clone) — dismiss ignored, summoning an extra squad",
                    clone_count()
                );
            }
            set_op("resummon");
            match summon_force() {
                Ok(()) => log::info!("resummon: request sent (settled={settled})"),
                Err(err) => log::warn!("resummon failed: {err}"),
            }
        }
    }

    // ---- 解散中：把消失请求钉住 ----
    // 这期间**必须**停掉 `summon_anywhere` 的门禁绕过：它每帧把 disappear_requested
    // 置回 false，不然「解散」永远不生效（实测：日志说 request sent，克隆体一个没少）。
    let dismissing = DISMISS_AT.load(Ordering::Acquire) != 0;
    if dismissing && !world_busy() {
        if clone_count() == 0 {
            DISMISS_AT.store(0, Ordering::Release);
            log::info!("dismiss: all summons gone; resummon queued");
        } else if frame >= DISMISS_AT.load(Ordering::Acquire) + 300 {
            DISMISS_AT.store(0, Ordering::Release);
            log::warn!("dismiss: timeout ({} left) — stopping dismiss", clone_count());
        } else {
            dismiss_now();
        }
    }

    // ---- 召唤门禁绕过：区域判定 / 召唤石范围 / 骨灰冷却 ----
    // 必须在管理器 update 之前写（FrameBegin 就够），否则这一帧仍按原值判。
    // 死亡/加载/世界重置期间不碰管理器（会被释放 → 闪退）。
    if ANYWHERE.load(Ordering::Acquire) && !world_busy() && !dismissing {
        if let Ok(world) = unsafe { WorldChrMan::instance_mut() } {
            if world.main_player.is_some() {
                spirit::bypass_summon_gates(world);
                // 「已经有一个召唤物」时不允许再用骨灰 —— 清掉就能反复召
                if MULTI_SUMMON.load(Ordering::Acquire) {
                    spirit::clear_alive_summon_flag(world);
                }
            }
        }
    }

    // ---- 维持召唤物（原版在没有召唤石时会请求消失）----
    if CLONE_ACTIVE.load(Ordering::Acquire) && !world_busy() {
        keep_summons();
        keep_clone_fp();
    }

    // ---- 召唤后注入：把档案写进克隆体（不改玩家）----
    if frame % 15 == 0 {
        auto_apply_clones();
        // 木桩（bench）：钉住队伍号/血量上限。必须在 auto_apply 之后 ——
        // 后者会按档案重写 HP 上限（apply_stats）。
        if !world_busy() {
            bench::tick();
            // 战友模式：按当前出战友人数补正场上敌人的生命上限
            // （直接写 CSChrDataModule，不碰 NpcParam；详见 balance.rs）。
            if let Ok(world) = unsafe { WorldChrMan::instance_mut() } {
                balance::tick(world);
            }
        }
        // 伤害修正 = 玩家褪色者：摘掉灵体削弱 spEffect（296000 / 20297000）。
        // NpcParam 常驻槽在 config 里已清掉；这里兜底处理「已在场」和「变身/重招」的克隆体。
        if DAMAGE_FIX.load(Ordering::Acquire) && !world_busy() {
            if let Ok(world) = unsafe { WorldChrMan::instance_mut() } {
                let (n, removed) =
                    spirit::strip_speffects(world, spirit::SUMMON_CORRECTION_SPEFFECTS);
                if !removed.is_empty() && LAST_DAMAGE_LOG.fetch_add(1, Ordering::Relaxed) < 5 {
                    log::info!(
                        "damage_fix: removed summon correction spEffect {removed:?} from {n} clone(s)"
                    );
                }
            }
        }
        // 友伤：维持 20%（或配置倍率）的玩家类目标伤害修正，并钉住「队友不可锁定」。
        let friendly = FRIENDLY_FIRE.load(Ordering::Acquire);
        if friendly {
            match unsafe { params::patch_friendly_damage_effect(params::friendly_rate()) } {
                Ok(_) => {}
                Err(err) => {
                    if LAST_FRIENDLY_EFFECT_LOG.fetch_add(1, Ordering::Relaxed) < 3 {
                        log::warn!("friendly_fire: damage effect patch failed: {err}");
                    }
                }
            }
        }
        if let Ok(world) = unsafe { WorldChrMan::instance_mut() } {
            spirit::set_friendly_damage_effect(world, friendly);
            spirit::set_clone_lock_on_blocked(world, friendly);
        }
        if !friendly {
            unsafe { params::restore_friendly_damage_effect() };
        }
        // 灵体外观：摘掉「骨灰外观」spEffect（295000 普通 / 295200 傀儡）。
        // 引擎只在 spawn 时按 NpcParam 的常驻槽挂一次，但重生/变身会重新挂，所以循环摘。
        if GLOW_OFF.load(Ordering::Acquire) && !SAFE_MODE.load(Ordering::Acquire) {
            let ids = glow_ids();
            if let Ok(world) = unsafe { WorldChrMan::instance_mut() } {
                let (n, removed) = spirit::strip_glow(world, &ids);
                if !removed.is_empty() && LAST_GLOW_LOG.fetch_add(1, Ordering::Relaxed) < 5 {
                    log::info!("glow_off: removed spEffect {removed:?} from {n} chr(s)");
                }
            }
        }
        // 备用路线：把克隆体的 phantom shader 指到「中性」那一行
        let row = PHANTOM_ROW.load(Ordering::Acquire);
        if GLOW_OFF.load(Ordering::Acquire) && row >= 0 {
            if let Ok(world) = unsafe { WorldChrMan::instance_mut() } {
                spirit::set_clone_phantom_override(world, row);
            }
        }
        // 施法观测：克隆体放法术会生成自己的 bullet（owner handle = 克隆体）。
        // 这是「占星师到底有没有施法」的唯一硬证据（日志里 rate-limit 前 10 次）。
        if !world_busy() {
            if let Ok(world) = unsafe { WorldChrMan::instance_mut() } {
                let scan = unsafe { dump::bullet_scan(world) };
                if scan.clone > 0 {
                    BULLET_MAX.fetch_max(scan.clone as u32, Ordering::Relaxed);
                    if BULLET_LOGS.fetch_add(1, Ordering::Relaxed) < 10 {
                        log::info!(
                            "bullet: clone={} other={} samples={:?}",
                            scan.clone,
                            scan.others,
                            scan.samples
                        );
                    }
                }
            }
        }
    }

    // ---- 延迟还原（载体克隆：先改玩家 → 召唤泪滴 → 还原玩家）----
    let restore_at = PENDING_RESTORE.load(Ordering::Acquire);
    if restore_at != 0 && frame >= restore_at {
        PENDING_RESTORE.store(0, Ordering::Release);
        restore_player();
    }

    // ---- 命令队列 ----
    for cmd in ipc::take_commands() {
        let name = cmd.name.clone();
        match run_command(&cmd) {
            Ok(()) => ipc::send_ack(&name, true, "ok"),
            Err(err) => {
                log::warn!("command {name} failed: {err}");
                ipc::send_ack(&name, false, &err);
            }
        }
    }

    // ---- LLM 权重 → param ----
    if let Some(target) = take_target_weights() {
        let prev = *CURRENT.lock().unwrap();
        let next = Weights::blend(&prev, &target, 0.15, 0.03);
        // 只有 set_rows 指定的行非 0 时才会真正写 param，默认 0 = 不动任何东西。
        unsafe { params::apply_weights(&next) };
        *CURRENT.lock().unwrap() = next;
        // 每号位的独立 think 行从新的全局行复制，再覆盖各自的 AI 预设。
        sync_teammate_ai();
    }

    // 兜底：档案重载 / 参数被别的 mod 改动之后，每 20 秒重新对齐一次每号位 AI 行。
    if frame % 600 == 0 {
        sync_teammate_ai();
    }

    // ---- 跟随保底 / 玩家升级跟随 / 状态上报 ----
    if frame % 30 == 0 {
        follow_guard();
        watch_summon();
        if let Some((level_delta, stat_deltas, pool_deltas)) = observe_level_up() {
            follow_player_level_up(level_delta, stat_deltas, pool_deltas);
        }
    }
    if frame % 60 == 0 {
        report_state();
        auto_dump(frame);
        write_heartbeat(frame);
    }
    // 每 30 秒打一份紧凑状态（长时间挂机时日志里能看到「还在正常跑」）。
    if AUTO_STATUS.load(Ordering::Acquire) && frame % 1800 == 0 {
        log::info!("{}", status_line().unwrap_or_else(|e| format!("status failed: {e}")));
    }
}

/// 召唤管理器状态变化时报一行。
///
/// 目的：玩家「按骨灰」这个动作到底有没有被引擎接受（引擎会写
/// `request_summon_speffect_id`），以及门禁位在那一瞬间是什么值。
fn watch_summon() {
    #[derive(Clone, Copy, PartialEq, Eq)]
    struct Snap {
        request: i32,
        active: i32,
        alive: bool,
        in_range: bool,
        chrs: usize,
    }
    static LAST: std::sync::Mutex<Option<Snap>> = std::sync::Mutex::new(None);

    let Ok(world) = (unsafe { WorldChrMan::instance_mut() }) else { return };
    let Some(mgr) = spirit::manager(world) else { return };
    let snap = Snap {
        request: mgr.request_summon_speffect_id,
        active: mgr.active_summon_speffect_id as i32,
        alive: mgr.player_has_alive_summon,
        in_range: mgr.is_within_activation_range,
        chrs: world.summon_buddy_chr_set.characters().count(),
    };
    let Ok(mut last) = LAST.lock() else { return };
    if last.as_ref() == Some(&snap) {
        return;
    }
    let prev = last.replace(snap);
    log::info!(
        "summon state: request {}->{} active {}->{} alive {:?}->{:?} in_range {:?}->{:?} chrs {:?}->{}",
        prev.map(|p| p.request).unwrap_or(-999),
        snap.request,
        prev.map(|p| p.active).unwrap_or(-999),
        snap.active,
        prev.map(|p| p.alive),
        snap.alive,
        prev.map(|p| p.in_range),
        snap.in_range,
        prev.map(|p| p.chrs),
        snap.chrs
    );
}

/// 常驻维持已按用户要求去掉：只在**坐火 / 传送 / 复活**三个事件之后召唤。
///
/// 三个事件各自都有可靠的引擎状态：
///   - 坐火：`CSLuaEventMan.lua_event_proxy.control_flags.bonfire_sitting_loop_active`
///     （bit7，坐下为真、起身为假）；
///   - 传送/世界重置：`CSNowLoadingHelper.menu_load_counter`（每次进加载画面 +1），
///     外加 player `block_id` 变化兜底；
///   - 复活：`PlayerGameData.current_hp` 从 0 变回 >0。
///
/// 触发后不立刻召：先排一个延迟帧，执行时如果还在坐着/加载中就往后推 ——
/// 因为世界重置会把召唤物清掉（实测「起身就召」会被重置清空）。
const SRC_REST: u32 = 1;
const SRC_TRAVEL: u32 = 2;
const SRC_RESPAWN: u32 = 3;
const SRC_LOAD: u32 = 4;

fn src_name(src: u32) -> &'static str {
    match src {
        SRC_REST => "rest",
        SRC_TRAVEL => "travel",
        SRC_RESPAWN => "respawn",
        SRC_LOAD => "load",
        _ => "manual",
    }
}

fn schedule_summon(src: u32, delay: u64) {
    let at = FRAME.load(Ordering::Relaxed) + delay;
    let cur = SUMMON_AT.load(Ordering::Acquire);
    if cur != 0 && cur <= at {
        return; // 已经有更早的计划
    }
    SUMMON_AT.store(at, Ordering::Release);
    SUMMON_SRC.store(src, Ordering::Release);
    log::info!("event: {} -> summon scheduled in {delay} frames", src_name(src));
}

fn detect_summon_events(in_game: bool) {
    static SEEN_PLAYER: AtomicBool = AtomicBool::new(false);
    if !in_game {
        // 回标题 / 换档：下次进游戏重新算一次「刚进来」
        SEEN_PLAYER.store(false, Ordering::Release);
        return;
    }
    // 进游戏（读档完成、玩家实体出现）→ 自动刷一队
    if !SEEN_PLAYER.swap(true, Ordering::AcqRel) {
        log::info!("event: entered game -> summon scheduled in 360 frames");
        schedule_summon(SRC_LOAD, 360);
        // 新档/新世界：把边沿检测的基准重置掉，避免拿上一局的旧值误判
        SITTING.store(false, Ordering::Release);
        PLAYER_HP.store(u32::MAX, Ordering::Release);
        PLAYER_BLOCK.store(u32::MAX, Ordering::Release);
        RESET_CLONE_COUNT.store(0, Ordering::Release);
    }
    // 坐火：**坐下那一刻**就排（世界刷新/敌人重生是坐下时做的，不是起身时；
    // 用户实测确认）。起身只记一条日志，不再作为触发点。
    if let Some(sitting) = spirit::is_sitting_at_grace() {
        let prev = SITTING.swap(sitting, Ordering::AcqRel);
        if sitting && !prev {
            log::info!("event: sat at grace -> summon scheduled in 150 frames");
            schedule_summon(SRC_REST, 150);
        } else if !sitting && prev {
            log::info!("event: stood up from grace");
        }
    }
    // 诊断：任何事件控制位变化都记一条（坐火到底是哪一位在动）
    if let Some(flags) = spirit::bonfire_flags_debug() {
        let changed = LAST_FLAGS.lock().map(|mut last| {
            if *last == flags {
                false
            } else {
                *last = flags.clone();
                true
            }
        });
        if changed.unwrap_or(false) {
            log::info!("event flags changed: {flags}");
        }
    }
    // 世界刷新的旁证：坐着的时候克隆体被清空（重置发生了）→ 90 帧后补
    if spirit::is_sitting_at_grace().unwrap_or(false) {
        let count = clone_count() as u32;
        let prev = RESET_CLONE_COUNT.swap(count, Ordering::AcqRel);
        if prev > 0 && count == 0 {
            log::info!("event: world reset while sitting (clones cleared) -> summon in 90 frames");
            schedule_summon(SRC_REST, 90);
        }
    }
    let Ok(world) = (unsafe { WorldChrMan::instance_mut() }) else { return };
    // 复活
    if let Some(hp) = spirit::player_hp(world) {
        let prev = PLAYER_HP.swap(hp, Ordering::AcqRel);
        if prev != u32::MAX && prev == 0 && hp > 0 {
            schedule_summon(SRC_RESPAWN, 120);
        }
    }
    // 传送（加载画面）
    if let Some(counter) = spirit::menu_load_counter() {
        let prev = LOAD_COUNTER.swap(counter as u32, Ordering::AcqRel);
        if prev != u32::MAX && prev != counter as u32 {
            LOAD_AT.store(FRAME.load(Ordering::Relaxed), Ordering::Release);
            schedule_summon(SRC_TRAVEL, 240);
        }
    }
    // 传送（换 block 兜底）
    if let Some(block) = spirit::player_block(world) {
        let prev = PLAYER_BLOCK.swap(block, Ordering::AcqRel);
        if prev != u32::MAX && prev != block {
            schedule_summon(SRC_TRAVEL, 240);
        }
    }
}

/// 执行排队的召唤；返回是否真的执行了。
fn run_scheduled_summon() -> bool {
    let at = SUMMON_AT.load(Ordering::Acquire);
    if at == 0 || FRAME.load(Ordering::Relaxed) < at {
        return false;
    }
    // 只在「人死了」或「刚进加载画面」时推后；**坐着不推**（世界刷新是坐下时做的，
    // 起身才召会被重置清掉 —— 之前就是这么错的）。
    let now = FRAME.load(Ordering::Relaxed);
    let dead = unsafe { WorldChrMan::instance_mut() }
        .map(|w| spirit::player_hp(w) == Some(0))
        .unwrap_or(true);
    if dead || now.saturating_sub(LOAD_AT.load(Ordering::Acquire)) < 30 {
        SUMMON_AT.store(now + 60, Ordering::Release);
        log::info!("event summon: postponed (dead/loading)");
        return false;
    }
    SUMMON_AT.store(0, Ordering::Release);
    let src = SUMMON_SRC.load(Ordering::Acquire);
    // 场上还有克隆体就不补：坐火/传送/复活会先把它们清掉，所以这些情况 count 必为 0；
    // 走路跨 block 也触发同一个事件，但不该再叠一队。
    let alive = clone_count();
    if alive > 0 {
        log::info!("event summon: src={} skipped ({} clone alive)", src_name(src), alive);
        return true;
    }
    match summon_force() {
        Ok(()) => {
            log::info!("event summon: src={} ok", src_name(src));
            SUMMON_VERIFY_AT.store(now + 240, Ordering::Release);
            SUMMON_RETRIES.store(2, Ordering::Release);
        }
        Err(err) => log::warn!("event summon: src={} failed: {err}", src_name(src)),
    }
    true
}

/// 世界是否正处在「不该碰召唤管理器」的阶段：没进游戏 / 玩家已死 / 刚进过加载画面。
///
/// 死亡、传送、世界重置期间 `WorldChrMan.summon_buddy_manager` 会被释放，写入就是
/// 0xc0000005（两次闪退都是这个）。这里从源头避开：这些帧干脆不碰。
fn world_busy() -> bool {
    let Ok(world) = (unsafe { WorldChrMan::instance_mut() }) else { return true };
    if world.main_player.is_none() {
        return true;
    }
    if spirit::player_hp(world) == Some(0) {
        return true;
    }
    let now = FRAME.load(Ordering::Relaxed);
    now.saturating_sub(LOAD_AT.load(Ordering::Acquire)) < 300
}

fn clone_count() -> usize {    let Ok(world) = (unsafe { WorldChrMan::instance_mut() }) else { return 0 };
    world
        .summon_buddy_chr_set
        .characters()
        .filter(|c| c.as_subclass::<PlayerIns>().is_some())
        .count()
}

/// 事件召唤后的验证：若干帧后场上还是没有克隆体，就重召（最多 `SUMMON_RETRIES` 次）。
fn run_summon_verify() {
    let at = SUMMON_VERIFY_AT.load(Ordering::Acquire);
    if at == 0 || FRAME.load(Ordering::Relaxed) < at {
        return;
    }
    SUMMON_VERIFY_AT.store(0, Ordering::Release);
    if clone_count() > 0 {
        return;
    }
    let left = SUMMON_RETRIES.load(Ordering::Acquire);
    if left == 0 {
        log::warn!("event summon: verify -> still 0 clone, giving up");
        return;
    }
    SUMMON_RETRIES.store(left - 1, Ordering::Release);
    log::info!("event summon: verify -> 0 clone, retry ({left} left)");
    if let Err(err) = summon_force() {
        log::warn!("event summon: retry failed: {err}");
    } else {
        SUMMON_VERIFY_AT.store(FRAME.load(Ordering::Relaxed) + 240, Ordering::Release);
    }
}

/// 首次进游戏后自动落盘一次 param/玩家数据，省得手动敲命令。
fn auto_dump(frame: u64) {
    if frame < 120 {
        return;
    }
    if !AUTO_PARAMS_DONE.load(Ordering::Acquire) {
        if let Some(repo) = unsafe { params::repo() } {
            match unsafe { dump::dump_buddies(repo) } {
                Ok(msg) => log::info!("auto {msg}"),
                Err(err) => log::warn!("auto dump_buddies: {err}"),
            }
            match unsafe { dump::dump_ride(repo) } {
                Ok(msg) => log::info!("auto {msg}"),
                Err(err) => log::warn!("auto dump_ride: {err}"),
            }
            match unsafe { dump::dump_npc(repo) } {
                Ok(msg) => log::info!("auto {msg}"),
                Err(err) => log::warn!("auto dump_npc: {err}"),
            }
            match unsafe { dump::dump_think(repo) } {
                Ok(msg) => log::info!("auto {msg}"),
                Err(err) => log::warn!("auto dump_think: {err}"),
            }
            AUTO_PARAMS_DONE.store(true, Ordering::Release);
        }
    }
    if !AUTO_PROFILE_DONE.load(Ordering::Acquire) {
        if let Ok(world) = unsafe { WorldChrMan::instance_mut() } {
            if let Some(ref player) = world.main_player {
                match unsafe { dump::dump_profile(player) } {
                    Ok(msg) => {
                        log::info!("auto {msg}");
                        AUTO_PROFILE_DONE.store(true, Ordering::Release);
                    }
                    Err(err) => log::warn!("auto dump_profile: {err}"),
                }
            }
        }
    }
}

fn take_target_weights() -> Option<Weights> {
    let seq = ipc::mailbox().seq.load(Ordering::Acquire);
    if seq == APPLIED_SEQ.load(Ordering::Acquire) {
        return None;
    }
    let target = ipc::mailbox().target.lock().ok().and_then(|w| *w);
    if target.is_some() {
        APPLIED_SEQ.store(seq, Ordering::Release);
    }
    target
}

// ---------------------------------------------------------------- profile

fn reload_profile() {
    let path = std::env::var("ER_ECHO_PROFILE").unwrap_or_else(|_| "profiles/target.json".into());
    match profile::Profile::load(&path) {
        Ok(p) => {
            log::info!("profile loaded: {} lv{} ({} bytes face)", p.name, p.level, p.face().len());
            *PROFILE.lock().unwrap() = Some(p.clone());
            if let Err(err) = install_profiles(vec![p], vec![Some(path.clone())]) {
                log::error!("profile install failed: {err}");
            } else {
                sync_teammate_ai();
            }
        }
        Err(err) => log::error!("profile load failed: {err}"),
    }
}

// ---------------------------------------------------------------- clone

/// 召唤克隆体（路线 A：Mimic Tear 载体）。
///
/// 步骤：备份玩家装备 → 换成本地 profile（没有就用玩家当前装备）→ 触发 Mimic Tear 的
/// summon spEffect（实测 207000）→ 90 帧后还原玩家。
fn try_pending_spawn() {
    let pending = match PENDING_SPAWN.lock() {
        Ok(mut slot) => slot.take(),
        Err(_) => None,
    };
    let Some((npc, think, chara, dy)) = pending else { return };

    let Ok(world) = (unsafe { WorldChrMan::instance_mut() }) else {
        // 放回去，下一帧再试
        if let Ok(mut slot) = PENDING_SPAWN.lock() { *slot = Some((npc, think, chara, dy)); }
        return;
    };
    let pos = {
        let Some(ref player) = world.main_player else {
            if let Ok(mut slot) = PENDING_SPAWN.lock() {
                *slot = Some((npc, think, chara, dy));
            }
            return;
        };
        world_pos(&player.chr_ins)
    };
    let Some((px, py, pz)) = pos else {
        // 物理坐标还没就绪（读档/传送期间）
        if let Ok(mut slot) = PENDING_SPAWN.lock() {
            *slot = Some((npc, think, chara, dy));
        }
        return;
    };

    // 注意：`ChrDebugSpawnRequest` 的位置是**世界坐标**（physics matrix 那一套）。
    // 之前误用了 `chunk_position`（block 内局部坐标，玩家在 40,-88,-80），
    // 结果是「说生成了，但场上什么都没有」—— 生成的实体在几百米外的地图另一头。
    let x = px + dy.max(1.0);
    let y = py + 0.5;
    let z = pz;
    world.spawn_debug_character(&ChrDebugSpawnRequest {
        chr_id: 0,
        chara_init_param_id: chara,
        npc_param_id: npc,
        npc_think_param_id: think,
        event_entity_id: -1,
        talk_id: -1,
        pos_x: x,
        pos_y: y,
        pos_z: z,
    });
    log::info!(
        "spawn_debug at ({x:.1},{y:.1},{z:.1}) npc={npc} think={think} chara={chara} dist={:.1}",
        dy
    );
}

/// 预换外观：把 profile 套到玩家身上，等玩家用骨灰（引擎授权召唤）时由 Mimic 复制。
fn prep_clone() -> Result<(), String> {
    let profile = PROFILE
        .lock()
        .ok()
        .and_then(|p| p.clone())
        .ok_or("no profile loaded (use load_profile)")?;
    let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
    let Some(ref mut player) = world.main_player else { return Err("no player".into()) };

    let backup = player.chr_asm.as_ref().equipment_param_ids;
    *BACKUP_IDS.lock().map_err(|_| "backup lock")? = backup;
    let mut ids = [0i32; 22];
    if profile.equipment_param_ids.len() == 22 {
        ids.copy_from_slice(&profile.equipment_param_ids);
    } else {
        ids = backup;
    }
    unsafe { profile::apply_equipment(player.chr_asm.as_ptr(), &ids) };

    let face = profile.face();
    let mut backup_face = [0u8; profile::FACE_PAYLOAD_LEN];
    let pgd = unsafe { player.player_game_data.as_mut() };
    if unsafe { profile::apply_face_from_profile(pgd, &face, &mut backup_face) } {
        if let Ok(mut slot) = BACKUP_FACE.lock() {
            *slot = backup_face;
        }
        FACE_DIRTY.store(true, Ordering::Release);
    }

    PREP_ACTIVE.store(true, Ordering::Release);
    PREP_DEADLINE.store(FRAME.load(Ordering::Relaxed) + 180 * 60, Ordering::Release);
    log::info!("prep_clone: profile '{}' applied; waiting for ash use (180s deadline)", profile.name);
    Ok(())
}

fn cancel_prep() {
    PREP_ACTIVE.store(false, Ordering::Release);
    restore_player();
    log::info!("prep_clone cancelled");
}

fn summon() -> Result<(), String> {
    // 热键召唤：直接走「强制召唤」这条路（不依赖骨灰物品 / 区域 / 召唤石 / 冷却）。
    summon_force()
}

/// 纯净召唤：不 keep-alive、不强制 alpha，用于观察引擎原生「史莱姆→变身」流程。
fn summon_plain() -> Result<(), String> {
    summon_with(false)
}

/// 强制召唤：不等玩家用骨灰，也不受区域/召唤石范围/冷却/「已有召唤物」限制。
///
/// 和 `summon` 的区别只有两点：请求前后把门禁位全部置真、并把
/// `player_has_alive_summon` 清掉（否则管理器认为「已经有一个」而丢弃请求）。
fn summon_force() -> Result<(), String> {
    set_op("summon_force");
    let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "WorldChrMan unavailable")?;
    if world.main_player.is_none() {
        return Err("main_player not loaded (still in menu?)".into());
    }
    if spirit::player_hp(world) == Some(0) {
        return Err("player is dead".into());
    }
    let profiles = clone_profiles();
    if profiles.is_empty() {
        return Err("no clone profiles loaded".into());
    }
    if roster::active_count(profiles.len()) == 0 {
        return Err("roster count is 0 (set it at a site of grace)".into());
    }
    // 人数 → 载体行 trigger；必须在引擎处理 request 之前写。
    apply_roster_count();
    spirit::bypass_summon_gates(world);
    spirit::clear_alive_summon_flag(world);

    let sp = SUMMON_SP.load(Ordering::Relaxed);
    let pos = world.main_player.as_ref().and_then(|p| world_pos(&p.chr_ins));
    unsafe { params::buff_clone_rows() };
    {
        let mgr = spirit::manager_mut(world).ok_or("summon_buddy_manager is null")?;
        mgr.request_summon_speffect_id = sp;
        mgr.buddy_disappear_delay_sec = 86_400.0;
        if let Some((x, y, z)) = pos {
            mgr.spawn_origin = HavokPosition::from_xyz(x, y, z);
        }
    }
    CLONE_ACTIVE.store(true, Ordering::Release);
    ANYWHERE.store(true, Ordering::Release);
    log::info!("summon_force: gates bypassed (activation/warn range, cooldown, alive flag); request spEffect {sp}");
    Ok(())
}

fn summon_with(keep: bool) -> Result<(), String> {
    let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "WorldChrMan unavailable")?;

    let backup: [i32; 22];
    let target: [i32; 22];
    {
        let Some(ref mut player) = world.main_player else {
            return Err("main_player not loaded (still in menu?)".into());
        };
        let profile = PROFILE.lock().ok().and_then(|p| p.clone());
        backup = player.chr_asm.as_ref().equipment_param_ids;
        target = match &profile {
            Some(p) if p.equipment_param_ids.len() == 22 => {
                log::info!("summon: using profile '{}' lv{}", p.name, p.level);
                let mut ids = [0i32; 22];
                ids.copy_from_slice(&p.equipment_param_ids);
                ids
            }
            _ => {
                log::info!("summon: no profile loaded, using player's own equipment");
                backup
            }
        };
        unsafe { profile::apply_equipment(player.chr_asm.as_ptr(), &target) };

        // 外观：只在 profile 带 face 时写运行时缓冲；召唤瞬间由 mimic 复制
        if let Some(p) = &profile {
            let face = p.face();
            let mut backup_face = [0u8; profile::FACE_PAYLOAD_LEN];
            let pgd = unsafe { player.player_game_data.as_mut() };
            if unsafe { profile::apply_face_from_profile(pgd, &face, &mut backup_face) } {
                if let Ok(mut slot) = BACKUP_FACE.lock() {
                    *slot = backup_face;
                }
                FACE_DIRTY.store(true, Ordering::Release);
                log::info!("summon: face payload applied ({} bytes)", profile::FACE_PAYLOAD_LEN);
            }
        }
    }
    *BACKUP_IDS.lock().map_err(|_| "backup lock")? = backup;

    // 走引擎原生召唤请求（TAE 使用物品时写的就是这个字段），比直接挂 spEffect 更可靠
    let sp = SUMMON_SP.load(Ordering::Relaxed);
    unsafe { params::buff_clone_rows() };
    {
        let mgr = spirit::manager_mut(world).ok_or("summon_buddy_manager is null")?;
        mgr.request_summon_speffect_id = sp;
        if keep {
            mgr.buddy_disappear_delay_sec = 86_400.0;
        }
    }
    if keep {
        CLONE_ACTIVE.store(true, Ordering::Release);
    }

    let at = FRAME.load(Ordering::Relaxed) + 60;
    PENDING_RESTORE.store(at, Ordering::Release);
    log::info!("summon(keep={keep}): request spEffect {sp}; restore player at frame {at}");
    Ok(())
}

/// 同伴「无限蓝」：克隆体施法要 FP，放几个就干了 —— 干了之后 AI 会退化成纯砍人，
/// 看起来就是「不会放法术」。这里每帧顶回上限（`infinite_fp=false` 可关）。
fn keep_clone_fp() {
    if !INFINITE_FP.load(Ordering::Acquire) {
        return;
    }
    let Ok(world) = (unsafe { WorldChrMan::instance_mut() }) else {
        return;
    };
    for chr in world.summon_buddy_chr_set.characters() {
        let Some(p) = chr.as_subclass_mut::<PlayerIns>() else {
            continue;
        };
        let pgd = unsafe { p.player_game_data.as_mut() };
        ai::top_up_fp(pgd, 1.0);
    }
}

/// 每帧阻止召唤管理器把 buddy 标记为「该消失」，并强制不透明（否则会在 fade-in 阶段一直隐形）。
fn keep_summons() {
    let Ok(world) = (unsafe { WorldChrMan::instance_mut() }) else { return };
    if let Some(mgr) = spirit::manager_mut(world) {
        mgr.disappear_requested = false;
        mgr.buddy_disappear_delay_sec = 86_400.0;
    }
    for chr in world.summon_buddy_chr_set.characters() {
        if chr.team_type == 47 {
            chr.tint_alpha_multiplier = 1.0;
            chr.tint_alpha_multiplier_modifier = 0.0;
            chr.opacity_keyframes_multiplier = 1.0;
        }
    }
}

/// 把玩家装备还原成召唤前的样子。
fn restore_player() {
    let Ok(world) = (unsafe { WorldChrMan::instance_mut() }) else { return };
    let Some(ref mut player) = world.main_player else { return };
    let backup = match BACKUP_IDS.lock() {
        Ok(b) => *b,
        Err(_) => return,
    };
    unsafe { profile::apply_equipment(player.chr_asm.as_ptr(), &backup) };

    if FACE_DIRTY.load(Ordering::Acquire) {
        if let Ok(backup_face) = BACKUP_FACE.lock() {
            let pgd = unsafe { player.player_game_data.as_mut() };
            unsafe { profile::restore_face(pgd, &backup_face) };
            FACE_DIRTY.store(false, Ordering::Release);
            log::info!("summon: face buffer restored");
        }
    }
    log::info!("summon: player equipment restored");
}

// ---------------------------------------------------------------- inject

/// 取当前生效的档案列表（空 = 没加载档案，注入不做任何事）。
pub(crate) fn clone_profiles() -> Vec<profile::Profile> {
    CLONE_PROFILES
        .lock()
        .map(|g| g.clone())
        .unwrap_or_default()
}

/// 与 `clone_profiles()` 同下标的来源路径（`None` = 这份档案没有可写回的文件）。
fn profile_paths() -> Vec<Option<String>> {
    CLONE_PROFILE_PATHS
        .lock()
        .map(|g| g.clone())
        .unwrap_or_default()
}

/// 赐福菜单「友伤」当前状态（`ui.rs` 用它选文案）。
pub(crate) fn friendly_fire_enabled() -> bool {
    FRIENDLY_FIRE.load(Ordering::Acquire)
}

/// 友伤倍率（0.2 = 20%），菜单文案/状态用。
pub(crate) fn friendly_fire_rate() -> f32 {
    params::friendly_rate()
}

/// 装入一组「从磁盘加载」的档案：同时记为当前档案和原始快照。
///
/// `paths` 与 `profiles` 同下标，用于自动升级时把新等级/属性写回原文件。
/// 快照是 F12 的「恢复原样」落点：置物包没选中项时，把出场队友的装备/法术
/// 改回档案里的原值（不是复制玩家当前装备）。
fn install_profiles(
    profiles: Vec<profile::Profile>,
    paths: Vec<Option<String>>,
) -> Result<(), String> {
    let snapshot = profiles.clone();
    let n = profiles.len();
    let mut paths = paths;
    paths.resize(n, None);
    *CLONE_PROFILES.lock().map_err(|_| "profiles lock")? = profiles;
    *ORIGINAL_PROFILES.lock().map_err(|_| "profiles lock")? = snapshot;
    *CLONE_PROFILE_PATHS.lock().map_err(|_| "profiles lock")? = paths;
    Ok(())
}

/// 玩家升级快照：等级、8 维基础属性、HP/FP/耐力**基础**上限。
#[derive(Clone, Copy, Debug)]
struct PlayerLevelSnapshot {
    level: u32,
    stats: [u32; 8],
    hp: u32,
    fp: u32,
    stamina: u32,
}

fn player_level_snapshot(player: &PlayerIns) -> PlayerLevelSnapshot {
    let pgd = unsafe { player.player_game_data.as_ref() };
    PlayerLevelSnapshot {
        level: pgd.level,
        stats: [
            pgd.vigor,
            pgd.mind,
            pgd.endurance,
            pgd.strength,
            pgd.dexterity,
            pgd.intelligence,
            pgd.faith,
            pgd.arcane,
        ],
        hp: pgd.base_max_hp,
        fp: pgd.base_max_fp,
        stamina: pgd.base_max_stamina,
    }
}

/// 观察玩家升级：涨了几级 / 哪几点属性 / 三围上限涨了多少。
///
/// 只在玩家**等级上升**时返回增量；读档/切号（等级下降）时静默重设基线。
fn observe_level_up() -> Option<(u32, [i64; 8], [u32; 3])> {
    if !AUTO_LEVEL.load(Ordering::Acquire) {
        return None;
    }
    let Ok(world) = (unsafe { WorldChrMan::instance_mut() }) else {
        return None;
    };
    let Some(player) = world.main_player.as_mut() else {
        if let Ok(mut base) = PLAYER_LEVEL_BASE.lock() {
            *base = None;
        }
        return None;
    };
    let now = player_level_snapshot(player);
    if now.level == 0 {
        return None;
    }
    let Ok(mut base) = PLAYER_LEVEL_BASE.lock() else {
        return None;
    };
    let Some(prev) = *base else {
        *base = Some(now);
        log::info!(
            "levelup: baseline lv{} (vig={} hp={} fp={} st={})",
            now.level,
            now.stats[0],
            now.hp,
            now.fp,
            now.stamina
        );
        return None;
    };
    if now.level <= prev.level {
        *base = Some(now);
        if now.level < prev.level {
            log::info!("levelup: level dropped {} -> {} (save load?), baseline reset", prev.level, now.level);
        }
        return None;
    }
    let mut stat_deltas = [0i64; 8];
    for (i, d) in stat_deltas.iter_mut().enumerate() {
        *d = now.stats[i] as i64 - prev.stats[i] as i64;
    }
    let pool_deltas = [
        now.hp.saturating_sub(prev.hp),
        now.fp.saturating_sub(prev.fp),
        now.stamina.saturating_sub(prev.stamina),
    ];
    *base = Some(now);
    Some((now.level - prev.level, stat_deltas, pool_deltas))
}

/// 玩家升级后：所有已加载档案跟升，并把新档案写回原 JSON。
fn follow_player_level_up(level_delta: u32, stat_deltas: [i64; 8], pool_deltas: [u32; 3]) {
    let mut profiles = clone_profiles();
    if profiles.is_empty() {
        return;
    }
    let mut changed = 0usize;
    for p in &mut profiles {
        if p.apply_level_up(level_delta, &stat_deltas, pool_deltas) {
            changed += 1;
        }
    }
    if changed == 0 {
        return;
    }
    // 原始快照也要跟升：这样 F12「恢复档案原样」不会把等级/属性退回旧值
    // （F12 只恢复装备/法术，但保持两份档案一致，排查时不会自相矛盾）。
    if let Ok(mut originals) = ORIGINAL_PROFILES.lock() {
        for p in originals.iter_mut() {
            p.apply_level_up(level_delta, &stat_deltas, pool_deltas);
        }
    }
    // 旧路线（prep_clone：先把档案套到玩家身上再召唤泪滴）用的单份 PROFILE 也跟升。
    if let Ok(mut single) = PROFILE.lock() {
        if let Some(p) = single.as_mut() {
            p.apply_level_up(level_delta, &stat_deltas, pool_deltas);
        }
    }
    if let Ok(mut g) = CLONE_PROFILES.lock() {
        *g = profiles.clone();
    }

    let paths = profile_paths();
    let mut written = Vec::new();
    for (i, p) in profiles.iter().enumerate() {
        let Some(Some(path)) = paths.get(i) else {
            continue;
        };
        match save_profile(path, p) {
            Ok(()) => written.push(format!("{} Lv{}", p.name, p.level)),
            Err(err) => log::warn!("levelup: write '{path}' failed: {err}"),
        }
    }
    log::info!(
        "levelup: player +{level_delta} -> companions {changed}/{} profile(s) follow (stat deltas {:?}, pool deltas {:?}); wrote [{}]",
        profiles.len(),
        stat_deltas,
        pool_deltas,
        written.join(", ")
    );

    apply_stats_to_clones();
    ui::refresh_texts();
}

/// 把当前档案的等级/属性/三围上限写进场上克隆体（不碰装备/外观/法术）。
fn apply_stats_to_clones() {
    let profiles = clone_profiles();
    if profiles.is_empty() {
        return;
    }
    let Ok(world) = (unsafe { WorldChrMan::instance_mut() }) else {
        return;
    };
    let mut n = 0usize;
    for chr in world.summon_buddy_chr_set.characters() {
        if !spirit::is_clone(chr) {
            continue;
        }
        let Some(p) = chr.as_subclass_mut::<PlayerIns>() else {
            continue;
        };
        let slot = roster::slot_for_clone(n, profiles.len());
        n += 1;
        if slot < 0 {
            continue;
        }
        let target = &profiles[(slot as usize) % profiles.len()];
        let pgd = unsafe { p.player_game_data.as_mut() };
        unsafe { kit::apply_stats(pgd, target) };
    }
    log::info!("levelup: stats applied to {n} clone(s)");
}

/// 原子写 profile JSON（先写 `.tmp` 再替换，避免半截文件）。
fn save_profile(path: &str, p: &profile::Profile) -> Result<(), String> {
    let text = serde_json::to_string_pretty(p).map_err(|e| e.to_string())?;
    let dst = std::path::Path::new(path);
    if let Some(dir) = dst.parent() {
        if !dir.as_os_str().is_empty() {
            let _ = std::fs::create_dir_all(dir);
        }
    }
    let tmp = dst.with_extension("json.tmp");
    std::fs::write(&tmp, text).map_err(|e| format!("write {}: {e}", tmp.display()))?;
    if dst.exists() {
        // Windows 的 rename 不覆盖已存在文件；先删再 rename，窗口期很短。
        std::fs::remove_file(dst).map_err(|e| format!("remove {}: {e}", dst.display()))?;
    }
    std::fs::rename(&tmp, dst).map_err(|e| format!("rename {}: {e}", dst.display()))?;
    Ok(())
}

/// 主循环里的「持续注入」：引擎变身/重招都可能覆盖克隆体数据，所以每 15 帧重写一次。
fn auto_apply_clones() {
    if !AUTO_APPLY.load(Ordering::Acquire) {
        return;
    }
    let profiles = clone_profiles();
    if profiles.is_empty() {
        return;
    }
    let stats = APPLY_STATS.load(Ordering::Acquire);
    let global_spell_rate = CURRENT.lock().map(|w| w.spell_rate).unwrap_or(0.5);
    let Ok(world) = (unsafe { WorldChrMan::instance_mut() }) else {
        return;
    };
    let mut n: u32 = 0;
    let mut equip = 0;
    let mut face = 0;
    let mut magic = 0;
    let mut magic_used = 0;
    let mut magic_total = 0;
    for chr in world.summon_buddy_chr_set.characters() {
        // 只处理同伴队：`summon_buddy_chr_set` 里还可能混着别的东西
        // （测试木桩会把一只克隆体临时改成敌对队，不能给它套档案 —— 会把 HP 上限写回去）。
        if chr.team_type != 47 {
            continue;
        }
        // 只有 PlayerIns 才有 PlayerGameData；史莱姆形态（133201000）会被跳过，
        // 人形化之后自动命中。
        let Some(p) = chr.as_subclass_mut::<PlayerIns>() else {
            continue;
        };
        // 名单：第 i 个克隆体用第 i 个位置指定的档案；位置为空就跳过注入。
        let slot = roster::slot_for_clone(n as usize, profiles.len());
        n += 1;
        if slot < 0 {
            continue;
        }
        let target = &profiles[(slot as usize) % profiles.len()];
        // 这个队友自己的「法术倾向」优先（赐福菜单「队友 AI」）；没设置就跟全局。
        let spell_rate = target
            .ai
            .map(|a| a.weights().spell_rate)
            .unwrap_or(global_spell_rate);
        let applied = unsafe { kit::apply(p, target, stats, spell_rate) };
        equip += applied.equip;
        face += applied.face;
        magic += applied.magic;
        if applied.magic_total > 0 {
            magic_used += applied.magic_used;
            magic_total += applied.magic_total;
        }
    }
    let prev = LAST_CLONE_COUNT.swap(n, Ordering::AcqRel);
    if n != prev {
        log::info!(
            "auto_apply: {n} clone(s) -> equip={equip} face={face} magic={magic} spells={magic_used}/{magic_total} spell_rate={global_spell_rate:.2} (profiles={})",
            profiles.len()
        );
        if magic == 0 && profiles.iter().any(|p| p.magic.is_empty()) {
            log::info!("auto_apply: 档案没有记忆法术 → 克隆体只会近战（见 profile 的 magic 字段）");
        }
    }
}

/// 手动注入一次（`apply_to_clone` 命令）。
fn apply_to_clones(stats: bool) -> Result<String, String> {
    let profiles = clone_profiles();
    if profiles.is_empty() {
        return Err("no clone profiles loaded (use load_profile / set_clone_profiles)".into());
    }
    let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
    let mut n = 0usize;
    let mut equip = 0;
    let mut face = 0;
    let mut body = 0;
    let mut stats_written = 0;
    for chr in world.summon_buddy_chr_set.characters() {
        let Some(p) = chr.as_subclass_mut::<PlayerIns>() else {
            continue;
        };
        let slot = roster::slot_for_clone(n, profiles.len());
        if slot < 0 {
            n += 1;
            continue;
        }
        let target = &profiles[(slot as usize) % profiles.len()];
        let global_spell_rate = CURRENT.lock().map(|w| w.spell_rate).unwrap_or(0.5);
        let spell_rate = target
            .ai
            .map(|a| a.weights().spell_rate)
            .unwrap_or(global_spell_rate);
        let applied = unsafe { kit::apply(p, target, stats, spell_rate) };
        log::info!(
            "apply_to_clone[{n}]: npc={} target='{}' lv{} equip={} face={} body={} stats={} readback={:?}",
            p.chr_ins.npc_param_id,
            target.name,
            target.level,
            applied.equip,
            applied.face,
            applied.body,
            applied.stats,
            &applied.readback[..4]
        );
        n += 1;
        equip += applied.equip;
        face += applied.face;
        body += applied.body;
        stats_written += applied.stats;
    }
    if n == 0 {
        return Err("no PlayerIns clone in summon_buddy_chr_set (summon first)".into());
    }
    Ok(format!(
        "applied to {n} clone(s): equip={equip} face={face} body={body} stats={stats_written}"
    ))
}

// ---------------------------------------------------------------- magic

/// 把玩家的记忆法术整份抄给所有克隆体。
///
/// 用途：① 验证「AI 会施法，只是没法术」这个前提；② 档案里没有法术时的兜底。
fn copy_player_magic() -> Result<String, String> {
    let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
    let source = {
        let player = world.main_player.as_mut().ok_or("no player")?;
        unsafe { ai::snapshot(player.player_game_data.as_ref()) }
    };
    write_magic_to_clones(&source.slots, "player")
}

/// 显式指定法术 id 列表写给所有克隆体：`{"ids": [50000000, 50010000]}`。
fn set_clone_magic(args: &serde_json::Value) -> Result<String, String> {
    let ids: Vec<i32> = args
        .get("ids")
        .and_then(|v| v.as_array())
        .ok_or("magic_set needs {\"ids\": [...]}")?
        .iter()
        .map(|v| v.as_i64().unwrap_or(-1) as i32)
        .collect();
    let slots: Vec<ai::MagicSlot> = ids
        .into_iter()
        .take(ai::MAGIC_SLOTS)
        .map(|id| ai::MagicSlot { id, charges: -1 })
        .collect();
    write_magic_to_clones(&slots, "args")
}

fn write_magic_to_clones(slots: &[ai::MagicSlot], source: &str) -> Result<String, String> {
    let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
    let mut n = 0usize;
    let mut written_total = 0usize;
    for chr in world.summon_buddy_chr_set.characters() {
        let Some(p) = chr.as_subclass_mut::<PlayerIns>() else {
            continue;
        };
        let pgd = unsafe { p.player_game_data.as_mut() };
        let name: String = String::from_utf16_lossy(&pgd.character_name)
            .trim_end_matches('\0')
            .to_string();
        let written = unsafe { ai::write(pgd, slots) };
        ai::top_up_fp(pgd, 1.0);
        let list: Vec<i32> = slots.iter().filter(|s| !s.is_empty()).map(|s| s.id).collect();
        log::info!(
            "magic[{n}]: '{name}' lv{} from={source} wrote={written} fp={}/{} slots={list:?}",
            pgd.level,
            pgd.current_fp,
            pgd.current_max_fp
        );
        n += 1;
        written_total += written;
    }
    if n == 0 {
        return Err("no PlayerIns clone in summon_buddy_chr_set (summon first)".into());
    }
    Ok(format!(
        "magic: {written_total} slot(s) -> {n} clone(s) (from {source})"
    ))
}

// ---------------------------------------------------------------- follow
/// 角色的世界坐标：`ChrCtrl.physics_model_matrix` 的第 4 行就是平移分量。
///
/// 为什么不用别的：
/// * `chunk_position` 是「全局 map chunk 坐标」，玩家和召唤物的表示不一样（实测相减得 114 m，
///   而两只就在旁边），不能直接算距离；
/// * `WorldChrMan.chr_inses_by_distance` 里的 `chr_ins` 指针和 `summon_buddy_chr_set`
///   里的对不上（实测 resolved=0/3），`distance` 值也不可信；
/// * `block_position` 只有 `PlayerIns` 有（普通 NPC 没有）。
///
/// 物理矩阵对所有 chr 都存在，是唯一一套通用坐标。
pub(crate) fn world_pos(chr: &eldenring::cs::ChrIns) -> Option<(f32, f32, f32)> {
    let ctrl = chr.chr_ctrl.as_ref();
    let t = ctrl.physics_model_matrix.3;
    if t.0 == 0.0 && t.1 == 0.0 && t.2 == 0.0 {
        return None;
    }
    Some((t.0, t.1, t.2))
}

fn dist3(a: (f32, f32, f32), b: (f32, f32, f32)) -> f32 {
    ((a.0 - b.0).powi(2) + (a.1 - b.1).powi(2) + (a.2 - b.2).powi(2)).sqrt()
}

/// 跟随观察：原生骨灰跟随（`pc_follow_type`）自带「掉队传送」，这里只测真实距离并记日志。
fn follow_guard() {
    let Ok(world) = (unsafe { WorldChrMan::instance_mut() }) else {
        return;
    };
    let Some(ref player) = world.main_player else {
        return;
    };
    let Some(ppos) = world_pos(&player.chr_ins) else {
        return;
    };
    let threshold = follow_dist();

    let mut rows: Vec<(i32, f32)> = Vec::new();
    for chr in world.summon_buddy_chr_set.characters() {
        if chr.team_type != 47 {
            continue;
        }
        // -1 = 拿不到坐标（还在加载/未落地）
        let d = world_pos(chr).map(|p| dist3(ppos, p)).unwrap_or(-1.0);
        rows.push((chr.npc_param_id, d));
    }
    if rows.is_empty() {
        return;
    }
    let resolved = rows.iter().filter(|(_, d)| *d >= 0.0).count();
    let far = rows.iter().filter(|(_, d)| *d > threshold).count();
    // 每 ~10 秒打一次「真实距离」，避免只在掉队时才可见（也用来确认坐标能不能拿到）。
    let now = FRAME.load(Ordering::Relaxed);
    let last = LAST_FOLLOW_REPORT.load(Ordering::Acquire);
    let should_log = far > 0 || now.saturating_sub(last) >= 600;
    if !should_log || now.saturating_sub(last) < 60 {
        return;
    }
    LAST_FOLLOW_REPORT.store(now, Ordering::Release);
    let detail = rows
        .iter()
        .map(|(npc, d)| format!("{npc}:{d:.1}"))
        .collect::<Vec<_>>()
        .join(" ");
    log::info!(
        "follow: far(>{threshold:.0})={far} resolved={resolved}/{} dists=[{detail}] (physics world pos)",
        rows.len()
    );

    // 保底：掉队告警。**不做传送** —— 两条传送路线都实测会把实体弄死（§14.6）。
    if far > 0 && AUTO_RECALL.load(Ordering::Acquire) {
        let last = LAST_RECALL_FRAME.load(Ordering::Acquire);
        if now.saturating_sub(last) >= 600 {
            LAST_RECALL_FRAME.store(now, Ordering::Release);
            log::warn!(
                "follow: {far} clone(s) left behind (> {threshold:.0} m); \
                 teleport unsupported, use `keep_close` to shorten the leash"
            );
        }
    }

    // 掉队保底（`[tuning] lost_resummon`）：**全体**都远到 `lost_distance` 之外
    // 并持续 `lost_seconds` 秒 → 解散重召。传送两条路都会把克隆体弄死（§14.6），
    // 而召唤请求层可以直接写（§15.3），所以「重召」是唯一可靠的拉回手段。
    if LOST_RESUMMON.load(Ordering::Acquire) && !rows.is_empty() && resolved == rows.len() {
        let all_far = rows.iter().all(|(_, d)| *d > lost_distance());
        if all_far {
            let since = LOST_SINCE.load(Ordering::Acquire);
            if since == 0 {
                LOST_SINCE.store(now, Ordering::Release);
                log::warn!(
                    "follow: all {} clone(s) lost (> {:.0} m); watching for {}s (lost_resummon)",
                    rows.len(),
                    lost_distance(),
                    lost_seconds()
                );
            } else if now.saturating_sub(since) >= 60 * lost_seconds() {
                LOST_SINCE.store(0, Ordering::Release);
                let last = LAST_RESUMMON.load(Ordering::Acquire);
                if now.saturating_sub(last) >= 1800 {
                    LAST_RESUMMON.store(now, Ordering::Release);
                    if let Some(mgr) = spirit::manager_mut(world) {
                        mgr.disappear_requested = true;
                        mgr.buddy_disappear_delay_sec = 0.0;
                    }
                    CLONE_ACTIVE.store(false, Ordering::Release);
                    start_resummon(180, 300);
                    log::warn!("follow: lost_resummon — dismissed, resummon in 300 frames");
                }
            }
        } else {
            LOST_SINCE.store(0, Ordering::Release);
        }
    }
}

/// 把克隆体拉到玩家身边 —— **已禁用**（保留说明，避免以后又踩一遍）。
///
/// 实测（2026-11-15 20:1x，两轮实机）：
/// 1. 写 `PlayerIns.block_position`：克隆体这个字段一直是 `(0,0,0)`（NPC 型 PlayerIns 不用它），
///    写完之后它们从空中掉下去，`world_pos.y` 掉到 -400、血量归零；
/// 2. 写 `ChrCtrl.physics_model_matrix` 的第 4 行 + `position_sync_requested = 1`：同样坠落到
///    y ≈ -400 并死亡（那个矩阵是每帧从 `CSChrPhysicsModule::position` 重算的派生值，
///    直接改它不会建立碰撞/地面信息）。
///
/// 真正可行的入口应该是 `CSChrPhysicsModule::position`（crate 未暴露）或引擎的 warp 函数，
/// 需要额外逆向；`request_summon`（spEffect 207000）单独调用也召不出东西，
/// 所以「解散+重召」也不能由 DLL 自己完成。详见 implementation-log §14.6。
fn recall_clones() -> Result<String, String> {
    Err("recall disabled: writing chr position makes clones fall out of the world \
         (implementation-log §14.6); use `keep_close` instead"
        .into())
}


fn follow_dist() -> f32 {
    match FOLLOW_DIST_BITS.load(Ordering::Acquire) {
        0 => 35.0,
        bits => f32::from_bits(bits),
    }
}

/// 跟随保底距离（超过这个值只记录，除非开了 `auto_recall`）。
static FOLLOW_DIST_BITS: AtomicU32 = AtomicU32::new(0);
/// auto_recall：掉队时只告警（传送不可用，见 §14.6）。
static AUTO_RECALL: AtomicBool = AtomicBool::new(false);
static LAST_RECALL_FRAME: AtomicU64 = AtomicU64::new(0);
/// 「绳长」：把克隆体的 `backhome_dist` 压到这个值以内，让它们更早回头（0 = 不干预）。
static LEASH_DIST_BITS: AtomicU32 = AtomicU32::new(0);

/// 设置绳长（米）。0 = 交回权重控制。
fn set_leash(d: f32) {
    LEASH_DIST_BITS.store(if d <= 0.0 { 0 } else { d.to_bits() }, Ordering::Release);
}

pub(crate) fn leash() -> f32 {
    match LEASH_DIST_BITS.load(Ordering::Acquire) {
        0 => 0.0,
        bits => f32::from_bits(bits),
    }
}

fn set_follow_dist(d: f32) {
    FOLLOW_DIST_BITS.store(d.to_bits(), Ordering::Release);
}

fn lost_distance() -> f32 {
    match LOST_DIST_BITS.load(Ordering::Acquire) {
        0 => 150.0,
        bits => f32::from_bits(bits),
    }
}

fn lost_seconds() -> u64 {
    let s = LOST_SECONDS.load(Ordering::Acquire);
    if s == 0 {
        15
    } else {
        s as u64
    }
}

// ---------------------------------------------------------------- state

/// 上一帧状态的「边沿检测」快照：事件（玩家低血/死亡/复活、敌人消失、克隆体数量变化）
/// 只在跳变的那一次上报，LLM 不会被同一件事刷屏。
struct StatePrev {
    hp_bits: u32,
    enemy_present: bool,
    clones: u32,
}

static STATE_PREV: std::sync::Mutex<StatePrev> = std::sync::Mutex::new(StatePrev {
    hp_bits: 0,
    enemy_present: false,
    clones: 0,
});

const LOW_HP: f32 = 0.35;

fn ratio(cur: u32, max: u32) -> f32 {
    if max == 0 {
        return 1.0;
    }
    (cur as f32 / max as f32).clamp(0.0, 1.0)
}

/// 给 sidecar/LLM 的战斗状态：玩家三围 + 克隆体 + 最近的敌人 + 事件。
///
/// 距离一律用引擎自己的 `chr_inses_by_distance`（`ChunkPosition` 那套坐标算不准，见 §12.6）。
fn report_state() {
    if !ipc::is_connected() {
        return;
    }
    let Ok(world) = (unsafe { WorldChrMan::instance_mut() }) else {
        return;
    };
    let Some(ref player) = world.main_player else {
        return;
    };
    let pgd = unsafe { player.player_game_data.as_ref() };
    let hp = ratio(pgd.current_hp, pgd.current_max_hp);
    let player_team = player.chr_ins.team_type;
    let ppos = world_pos(&player.chr_ins);

    // 克隆体（team 47 = 同伴）：等级/血量/距离/名字，LLM 需要知道「谁在打、还剩多少血」
    let profiles = clone_profiles();
    let mut clones = Vec::new();
    let mut idx = 0usize;
    for chr in world.summon_buddy_chr_set.characters() {
        if chr.team_type != 47 {
            continue;
        }
        let dist = match (ppos, world_pos(chr)) {
            (Some(a), Some(b)) => dist3(a, b),
            _ => -1.0,
        };
        let target = profiles.get(idx % profiles.len().max(1));
        let mut entry = serde_json::json!({
            "npc": chr.npc_param_id,
            "name": target.map(|p| p.name.clone()).unwrap_or_default(),
            "ai": ai_code(target.and_then(|p| p.ai)),
            "dist": dist,
        });
        if let Ok(p) = <&PlayerIns>::try_from(&*chr) {
            let cpgd = unsafe { p.player_game_data.as_ref() };
            entry["level"] = serde_json::json!(cpgd.level);
            entry["hp"] = serde_json::json!(ratio(cpgd.current_hp, cpgd.current_max_hp));
        }
        clones.push(entry);
        idx += 1;
    }

    // 最近的敌对单位：遍历所有 chr，统一用物理矩阵坐标
    let mut enemy = serde_json::Value::Null;
    let mut best = f32::MAX;
    if let Some(pp) = ppos {
        for set in world.chr_sets.iter_mut() {
            let Some(set) = set.as_mut() else { continue };
            for chr in set.characters() {
                let team = chr.team_type;
                // 0 = 中立（Torrent/引导），1 = 玩家自己 —— 都不是「敌人」。
                if team == 0 || team == 1 || team == player_team || team == 47 {
                    continue;
                }
                if chr.npc_param_id <= 0 {
                    continue;
                }
                let Some(pos) = world_pos(chr) else { continue };
                let d = dist3(pp, pos);
                if d > 0.05 && d < best {
                    best = d;
                    enemy = serde_json::json!({
                        "npc": chr.npc_param_id,
                        "team": team,
                        "dist": d,
                    });
                }
            }
        }
    }

    // 事件（只在跳变时发）
    let mut events: Vec<&str> = Vec::new();
    {
        let mut prev = match STATE_PREV.lock() {
            Ok(g) => g,
            Err(_) => return,
        };
        let prev_hp = f32::from_bits(prev.hp_bits);
        if hp <= 0.01 && prev_hp > 0.01 {
            events.push("player_dead");
        } else if hp > 0.5 && prev_hp <= 0.01 {
            events.push("revive");
        } else if hp < LOW_HP && prev_hp >= LOW_HP {
            events.push("player_low_hp");
        }
        if !enemy.is_null() && !prev.enemy_present {
            events.push("enemy_engaged");
        }
        if enemy.is_null() && prev.enemy_present {
            events.push("enemy_dead");
        }
        if (clones.len() as u32) > prev.clones {
            events.push("clone_summoned");
        } else if (clones.len() as u32) < prev.clones && prev.clones > 0 {
            events.push("clone_gone");
        }
        prev.hp_bits = hp.to_bits();
        prev.enemy_present = !enemy.is_null();
        prev.clones = clones.len() as u32;
    }

    let w = *CURRENT.lock().unwrap();
    let strategy = ipc::mailbox()
        .strategy
        .lock()
        .ok()
        .and_then(|s| s.clone())
        .unwrap_or_default();
    let state = serde_json::json!({
        "v": 1,
        "type": "state",
        "seq": ipc::mailbox().seq.load(Ordering::Acquire),
        "frame": FRAME.load(Ordering::Relaxed),
        "player": {
            "hp": hp,
            "fp": ratio(pgd.current_fp, pgd.current_max_fp),
            "stam": ratio(pgd.current_stamina, pgd.current_max_stamina),
            "level": pgd.level,
            "runes": pgd.rune_count,
            "blessing": pgd.scadutree_blessing,
        },
        "clones": clones,
        "enemy": enemy,
        "weights": {
            "aggression": w.aggression, "dodge_rate": w.dodge_rate,
            "guard_rate": w.guard_rate, "combo_rate": w.combo_rate,
            "heal_priority": w.heal_priority, "spell_rate": w.spell_rate,
            "item_rate": w.item_rate, "spacing": w.spacing,
            "target_switch": w.target_switch,
        },
        "strategy": strategy,
        "events": events,
    });
    ipc::send_state(&state.to_string());
}

// ---------------------------------------------------------------- 状态 / 探针

/// 克隆体（team 47）逐只快照：名字/等级/血量/FP/距离/法术槽。
fn clone_rows(world: &mut WorldChrMan, ppos: Option<(f32, f32, f32)>) -> Vec<serde_json::Value> {
    let profiles = clone_profiles();
    let mut out = Vec::new();
    let mut idx = 0usize;
    for chr in world.summon_buddy_chr_set.characters() {
        if chr.team_type != 47 {
            continue;
        }
        let dist = match (ppos, world_pos(chr)) {
            (Some(a), Some(b)) => dist3(a, b),
            _ => -1.0,
        };
        let name = profiles
            .get(idx % profiles.len().max(1))
            .map(|p| p.name.clone())
            .unwrap_or_default();
        let mut row = serde_json::json!({
            "npc": chr.npc_param_id,
            "name": name,
            "dist": dist,
        });
        if let Some(p) = chr.as_subclass_mut::<PlayerIns>() {
            let pgd = unsafe { p.player_game_data.as_ref() };
            row["level"] = serde_json::json!(pgd.level);
            row["hp"] = serde_json::json!([pgd.current_hp, pgd.current_max_hp]);
            row["fp"] = serde_json::json!([pgd.current_fp, pgd.current_max_fp]);
            let magic = unsafe { ai::snapshot(pgd) };
            row["magic"] = serde_json::json!(magic.equipped().map(|s| s.id).collect::<Vec<i32>>());
        }
        out.push(row);
        idx += 1;
    }
    out
}

/// 把「现在这一局」压成一个 JSON（status / 日志 / 排障都用它）。
fn status_json() -> Result<serde_json::Value, String> {
    let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
    let (ppos, player_hp, player_team) = {
        let player = world.main_player.as_ref().ok_or("no player loaded")?;
        (
            world_pos(&player.chr_ins),
            spirit::player_hp(world).unwrap_or(0),
            player.chr_ins.team_type,
        )
    };
    let clones = clone_rows(world, ppos);
    let dummy = bench::snapshot(world);
    let bullets = unsafe { dump::bullet_scan(world) };

    let mut enemies = 0usize;
    let mut nearest = f32::MAX;
    let mut nearest_npc = 0i32;
    if let Some(pp) = ppos {
        for set in world.chr_sets.iter_mut() {
            let Some(set) = set.as_mut() else { continue };
            for chr in set.characters() {
                let team = chr.team_type;
                // 0 = 中立（Torrent/引导之类），1 = 玩家自己：都不是敌人。
                if team == 0 || team == 1 || team == player_team || team == 47 {
                    continue;
                }
                if chr.npc_param_id <= 0 {
                    continue;
                }
                if let Some(pos) = world_pos(chr) {
                    let d = dist3(pp, pos);
                    if d > 0.05 && d < 200.0 {
                        enemies += 1;
                        if d < nearest {
                            nearest = d;
                            nearest_npc = chr.npc_param_id;
                        }
                    }
                }
            }
        }
    }

    let w = *CURRENT.lock().unwrap();
    let (behavior_row, think_row, npc_row) = params::rows::get();
    let roster_state = roster::get();
    let profiles = clone_profiles();
    let profile_names: Vec<String> = profiles
        .iter()
        .map(|p| format!("{} Lv{}", p.name, p.level))
        .collect();
    let ai_slots: Vec<&'static str> = (0..roster::MAX_SLOTS)
        .map(|i| {
            let idx = roster_state.slots[i];
            if idx < 0 || idx as usize >= profiles.len() {
                "-"
            } else {
                ai_code(profiles[idx as usize].ai)
            }
        })
        .collect();
    let ai_think_rows = params::teammate_think_rows();
    let buddy_rows = BUDDY_ROWS.lock().map(|g| g.clone()).unwrap_or_default();
    let buddy_think = unsafe { params::repo() }
        .map(|repo| unsafe { params::buddy_think_ids(repo, &buddy_rows) })
        .unwrap_or_default();
    Ok(serde_json::json!({
        "frame": FRAME.load(Ordering::Relaxed),
        "player": { "hp": player_hp },
        "clones": clones,
        "dummy": dummy,
        "bullets": { "clone": bullets.clone, "others": bullets.others, "samples": bullets.samples },
        "enemies": { "count": enemies, "nearest": if nearest == f32::MAX { -1.0 } else { nearest }, "nearest_npc": nearest_npc },
        "enemy_hp": {
            "enabled": balance::enabled(),
            "rates": balance::rates(),
            "comrades": balance::last_count(),
            "multiplier": if balance::enabled() {
                balance::multiplier_for(balance::last_count())
            } else {
                1.0
            },
        },
        "weights": {
            "aggression": w.aggression, "dodge_rate": w.dodge_rate,
            "guard_rate": w.guard_rate, "combo_rate": w.combo_rate,
            "heal_priority": w.heal_priority, "spell_rate": w.spell_rate,
            "item_rate": w.item_rate, "spacing": w.spacing,
            "target_switch": w.target_switch,
        },
        "rows": { "behavior": behavior_row, "think": think_row, "npc": npc_row },
        "roster": {
            "count": roster_state.count,
            "slots": roster_state.slots,
            "profiles": profile_names,
            "ai": ai_slots,
            "ai_think_rows": ai_think_rows,
            "buddy_think": buddy_think,
        },
        "ui": { "msg_hook": ui::hook_status(), "ezstate": ezstate::status(), "language": i18n::current(), "language_source": i18n::source() },
        "flags": {
            "anywhere": ANYWHERE.load(Ordering::Acquire),
            "events": ON_EVENTS.load(Ordering::Acquire),
            "auto_apply": AUTO_APPLY.load(Ordering::Acquire),
            "apply_stats": APPLY_STATS.load(Ordering::Acquire),
            "glow_off": GLOW_OFF.load(Ordering::Acquire),
            "infinite_fp": INFINITE_FP.load(Ordering::Acquire),
            "player_damage": DAMAGE_FIX.load(Ordering::Acquire),
            "auto_level": AUTO_LEVEL.load(Ordering::Acquire),
            "friendly_fire": friendly_fire_enabled(),
            "friendly_fire_rate": params::friendly_rate(),
            "enemy_hp_scaling": balance::enabled(),
            "enemy_hp_rates": balance::rates(),
            "safe_mode": SAFE_MODE.load(Ordering::Acquire),
            "last_op": last_op(),
        },
    }))
}

/// 一行紧凑状态（F6 / 每 30 秒 / `status` 命令）。
fn status_line() -> Result<String, String> {
    let v = status_json()?;
    let _ = std::fs::write("er_echo_status.json", serde_json::to_string_pretty(&v).unwrap_or_default());
    let empty = Vec::new();
    let clones = v["clones"].as_array().unwrap_or(&empty);
    let dists: Vec<String> = clones
        .iter()
        .map(|c| format!("{:.1}", c["dist"].as_f64().unwrap_or(-1.0)))
        .collect();
    let hps: Vec<String> = clones
        .iter()
        .map(|c| match c["hp"].as_array() {
            Some(h) if h.len() == 2 => format!("{}/{}", h[0], h[1]),
            _ => "?".to_string(),
        })
        .collect();
    let magic: Vec<String> = clones
        .iter()
        .map(|c| {
            let ids: Vec<String> = c["magic"]
                .as_array()
                .map(|a| a.iter().map(|v| v.to_string()).collect())
                .unwrap_or_default();
            format!("[{}]", ids.join(","))
        })
        .collect();
    let w = &v["weights"];
    let f = &v["flags"];
    let dummy = if v["dummy"]["active"].as_bool().unwrap_or(false) {
        format!(
            "hp={} dmg={}",
            v["dummy"]["hp"],
            v["dummy"]["dmg"]
        )
    } else {
        "off".to_string()
    };
    let roster = &v["roster"];
    let roster_slots = serde_json::to_string(&roster["slots"]).unwrap_or_default();
    let roster_ai = serde_json::to_string(&roster["ai"]).unwrap_or_default();
    let enemy_hp_rate = if balance::enabled() {
        balance::multiplier_for(balance::last_count())
    } else {
        1.0
    };
    Ok(format!(
        "status: frame={} clones={} dists=[{}] hp=[{}] magic={} dummy={dummy} \
         roster(count={} slots={roster_slots} ai={roster_ai}) \
         enemies={} nearest={:.1}m bullets(clone={} other={}) \
         weights(aggr={:.2} dodge={:.2} guard={:.2} spell={:.2}) \
         flags(anywhere={} events={} apply={} stats={} glow={} fp={} dmg={} lvl={} ff={} ehp={:.2} safe={}) rows(b={} t={} n={})",
        v["frame"],
        clones.len(),
        dists.join(" "),
        hps.join(" "),
        magic.join(" "),
        roster["count"],
        v["enemies"]["count"],
        v["enemies"]["nearest"].as_f64().unwrap_or(-1.0),
        v["bullets"]["clone"],
        v["bullets"]["others"],
        w["aggression"].as_f64().unwrap_or(0.0),
        w["dodge_rate"].as_f64().unwrap_or(0.0),
        w["guard_rate"].as_f64().unwrap_or(0.0),
        w["spell_rate"].as_f64().unwrap_or(0.0),
        f["anywhere"],
        f["events"],
        f["auto_apply"],
        f["apply_stats"],
        f["glow_off"],
        f["infinite_fp"],
        f["player_damage"],
        f["auto_level"],
        f["friendly_fire"],
        enemy_hp_rate,
        f["safe_mode"],
        v["rows"]["behavior"],
        v["rows"]["think"],
        v["rows"]["npc"],
    ))
}

/// 战斗探针：一次采样，用来量「这一段时间里克隆体打掉了木桩多少血 / 放了几发法术」。
fn combat_probe() -> Result<String, String> {
    let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
    let ppos = world
        .main_player
        .as_ref()
        .and_then(|p| world_pos(&p.chr_ins));
    let clones = clone_rows(world, ppos);
    let dummy = bench::snapshot(world);
    let scan = unsafe { dump::bullet_scan(world) };
    let w = *CURRENT.lock().unwrap();
    let value = serde_json::json!({
        "frame": FRAME.load(Ordering::Relaxed),
        "dummy": dummy,
        "clones": clones,
        "bullets": { "clone": scan.clone, "others": scan.others, "total": scan.total, "samples": scan.samples },
        "weights": {
            "aggression": w.aggression, "spell_rate": w.spell_rate,
            "dodge_rate": w.dodge_rate, "guard_rate": w.guard_rate,
        },
    });
    let text = serde_json::to_string_pretty(&value).unwrap_or_default();
    let _ = std::fs::write("er_echo_combat.json", &text);
    let line = format!(
        "combat: dummy={} dmg={} clones_hp=[{}] bullets(clone={} other={}) weights(aggr={:.2} spell={:.2})",
        dummy["hp"],
        dummy["dmg"],
        value["clones"]
            .as_array()
            .map(|a| a
                .iter()
                .map(|c| match c["hp"].as_array() {
                    Some(h) if h.len() == 2 => format!("{}/{}", h[0], h[1]),
                    _ => "?".to_string(),
                })
                .collect::<Vec<_>>()
                .join(" "))
            .unwrap_or_default(),
        scan.clone,
        scan.others,
        w.aggression,
        w.spell_rate,
    );
    log::info!("{line}");
    Ok(line)
}

// ---------------------------------------------------------------- commands

fn run_command(cmd: &ipc::Command) -> Result<(), String> {
    match cmd.name.as_str() {
        "set_equipment" => set_clone_equipment(&cmd.args),
        "set_stats" => set_clone_stats(&cmd.args),
        "rollback_equipment" => rollback_equipment(),
        "set_weights" => {
            if let Ok(w) = serde_json::from_value::<ipc::WeightsIn>(cmd.args.clone()) {
                let base = *CURRENT.lock().unwrap();
                let merged = w.merged(&base);
                if let Ok(mut target) = ipc::mailbox().target.lock() {
                    *target = Some(merged);
                }
                log::info!(
                    "set_weights: aggr={:.2} spell={:.2} dodge={:.2} (未给的字段沿用当前值)",
                    merged.aggression,
                    merged.spell_rate,
                    merged.dodge_rate
                );
            }
            Ok(())
        }
        "set_rows" => {
            let behavior = cmd.args.get("behavior").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
            let think = cmd.args.get("think").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
            let npc = cmd.args.get("npc").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
            params::rows::set(behavior, think, npc);
            log::info!("rows set: behavior={behavior} think={think} npc={npc}");
            Ok(())
        }
        "dump_buddies" | "dump_ride" | "dump_npc" | "dump_think" | "dump_equip" | "dump_magic" => {
            let repo = unsafe { params::repo() }.ok_or("no SoloParamRepository")?;
            let result = match cmd.name.as_str() {
                "dump_buddies" => unsafe { dump::dump_buddies(repo) },
                "dump_ride" => unsafe { dump::dump_ride(repo) },
                "dump_npc" => unsafe { dump::dump_npc(repo) },
                "dump_equip" => unsafe { dump::dump_equip(repo) },
                "dump_magic" => unsafe { dump::dump_magic(repo) },
                _ => unsafe { dump::dump_think(repo) },
            };
            log::info!("{}", result?);
            Ok(())
        }
        "summon" => summon(),
        "summon_plain" => summon_plain(),
        "summon_force" => summon_force(),
        "prep_clone" => prep_clone(),
        "cancel_prep" => {
            cancel_prep();
            Ok(())
        }
        "request_summon" => {
            let sp = cmd.args.get("id").and_then(|v| v.as_i64()).unwrap_or(207000) as i32;
            let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
            // 生成点：引擎用 spawn_origin 定位；不走骨灰物品时它是上一次使用的残留值，
            // 会把克隆体放到几百米外（然后靠原生 warp 拉回来）。这里直接写给玩家脚下。
            let pos = world.main_player.as_ref().and_then(|p| world_pos(&p.chr_ins));
            let mgr = spirit::manager_mut(world).ok_or("summon_buddy_manager is null")?;
            mgr.request_summon_speffect_id = sp;
            if let Some((x, y, z)) = pos {
                mgr.spawn_origin = HavokPosition::from_xyz(x, y, z);
            }
            log::info!("request_summon_speffect_id = {sp} spawn_origin={pos:?}");
            Ok(())
        }
        "keep_summons" => {
            let on = cmd.args.get("on").and_then(|v| v.as_bool()).unwrap_or(true);
            CLONE_ACTIVE.store(on, Ordering::Release);
            if !on {
                let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
                if let Some(mgr) = spirit::manager_mut(world) {
                    mgr.disappear_requested = true;
                }
            }
            log::info!("keep_summons = {on}");
            Ok(())
        }
        // ---- 召唤限制绕过 / 灵体外观 ----
        "probe_spirit" | "phantom_dump" => {
            let repo = unsafe { params::repo() }.ok_or("no SoloParamRepository")?;
            let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
            let msg = unsafe { spirit::dump_phantom(repo, world, spirit::CLONE_NPCS) }?;
            log::info!("{msg}");
            Ok(())
        }
        // ---- 法术（同伴 AI 施法） ----
        "magic_probe" => {
            let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
            let msg = unsafe { dump::dump_magic_probe(world) }?;
            log::info!("{msg}");
            Ok(())
        }
        "magic_copy" => {
            log::info!("{}", copy_player_magic()?);
            Ok(())
        }
        "magic_set" => {
            log::info!("{}", set_clone_magic(&cmd.args)?);
            Ok(())
        }
        // 临时给**玩家自己**写记忆槽（只改内存，不写存档）。
        // 用途：验证「拟态 AI 到底读谁的法术列表」—— 如果玩家的槽里有法术它才会放，
        // 那说明 mimic 的 think 读的是玩家 PGD，而不是克隆体自己的（§16.9）。
        "magic_player" => {
            let ids: Vec<i32> = cmd
                .args
                .get("ids")
                .and_then(|v| v.as_array())
                .map(|a| a.iter().filter_map(|x| x.as_i64()).map(|x| x as i32).collect())
                .unwrap_or_default();
            let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
            let Some(ref mut player) = world.main_player else {
                return Err("no player".into());
            };
            let pgd = unsafe { player.player_game_data.as_mut() };
            let mut slots = [ai::MagicSlot::EMPTY; ai::MAGIC_SLOTS];
            for (i, id) in ids.iter().take(ai::MAGIC_SLOTS).enumerate() {
                slots[i] = ai::MagicSlot { id: *id, charges: -1 };
            }
            let n = unsafe { ai::write(pgd, &slots) };
            log::info!("magic_player: wrote {n} slot(s) to player (runtime only): {ids:?}");
            Ok(())
        }
        "infinite_fp" => {
            let on = cmd.args.get("on").and_then(|v| v.as_bool()).unwrap_or(true);
            INFINITE_FP.store(on, Ordering::Release);
            log::info!("infinite_fp = {on}");
            Ok(())
        }
        "bullet_probe" => {
            let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
            let scan = unsafe { dump::bullet_scan(world) };
            log::info!(
                "bullet_probe: total={} clone={} other={} samples={:?} max_seen={}",
                scan.total,
                scan.clone,
                scan.others,
                scan.samples,
                BULLET_MAX.load(Ordering::Relaxed)
            );
            Ok(())
        }
        // ---- M4/M5：战斗验证台 / 状态 ----
        "dummy" => {
            let on = cmd.args.get("on").and_then(|v| v.as_bool()).unwrap_or(true);
            if on {
                if SAFE_MODE.load(Ordering::Acquire) {
                    return Err("safe_mode on: dummy disabled".into());
                }
                let who = cmd.args.get("who").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
                let team = cmd
                    .args
                    .get("team")
                    .and_then(|v| v.as_u64())
                    .unwrap_or(bench::DEFAULT_TEAM as u64) as u8;
                set_op("dummy on");
                log::info!("{}", bench::on(who, team)?);
            } else {
                set_op("dummy off");
                log::info!("{}", bench::off()?);
            }
            Ok(())
        }
        "combat_probe" => {
            log::info!("{}", combat_probe()?);
            Ok(())
        }
        "status" => {
            log::info!("{}", status_line()?);
            Ok(())
        }
        "friendly_fire" => {
            let on = cmd.args.get("on").and_then(|v| v.as_bool()).unwrap_or(true);
            if let Some(rate) = cmd.args.get("rate").and_then(|v| v.as_f64()) {
                log::info!("friendly_fire: rate -> {:.0}%", params::set_friendly_rate(rate as f32) * 100.0);
            }
            let rate = params::friendly_rate();
            roster::set_friendly_fire(on);
            FRIENDLY_FIRE.store(on, Ordering::Release);
            let (changed, total, already) = unsafe { params::set_friendly_fire(on)? };
            if on {
                unsafe { params::patch_friendly_damage_effect(rate)? };
            }
            if let Ok(world) = unsafe { WorldChrMan::instance_mut() } {
                spirit::set_friendly_damage_effect(world, on);
                spirit::set_clone_lock_on_blocked(world, on);
            }
            if !on {
                unsafe { params::restore_friendly_damage_effect() };
            }
            ui::refresh_texts();
            log::info!(
                "friendly_fire: {on} ({changed} AtkParam_Pc row(s) changed, total={total}, already={already}, damage={:.0}%)",
                rate * 100.0
            );
            Ok(())
        }
        "friendly_fire_status" => {
            let v = unsafe { params::friendly_fire_stats() };
            log::info!(
                "friendly_fire_status: enabled={} {}",
                friendly_fire_enabled(),
                serde_json::to_string(&v).unwrap_or_default()
            );
            Ok(())
        }
        // ---- 战友模式：敌人生命值补正 ----
        "enemy_hp_scale" => {
            if let Some(on) = cmd.args.get("on").and_then(|v| v.as_bool()) {
                balance::set_enabled(on);
            }
            // rates=[1.5,1.8,2.0] 或 rate_1/rate_2/rate_3 两种写法都收。
            let mut rates: Vec<f32> = cmd
                .args
                .get("rates")
                .and_then(|v| v.as_array())
                .map(|a| a.iter().filter_map(|v| v.as_f64()).map(|v| v as f32).collect())
                .unwrap_or_default();
            if rates.is_empty() {
                for key in ["rate_1", "rate_2", "rate_3"] {
                    if let Some(v) = cmd.args.get(key).and_then(|v| v.as_f64()) {
                        rates.push(v as f32);
                    }
                }
            }
            if !rates.is_empty() {
                balance::set_rates(&rates);
            }
            // 立即对场上敌人生效（不用等下一个 15 帧 tick）。
            if !world_busy() {
                if let Ok(world) = unsafe { WorldChrMan::instance_mut() } {
                    balance::tick(world);
                }
            }
            log::info!(
                "enemy_hp_scale: enabled={} rates={:?}",
                balance::enabled(),
                balance::rates()
            );
            Ok(())
        }
        "enemy_hp_status" => {
            let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
            let value = balance::status(world);
            let line = serde_json::to_string(&value).map_err(|e| e.to_string())?;
            let pretty = serde_json::to_string_pretty(&value).unwrap_or_else(|_| line.clone());
            let _ = std::fs::write("er_echo_enemy_hp.json", &pretty);
            log::info!("enemy_hp_status: {line}");
            Ok(())
        }
        "level_status" => {
            let base = PLAYER_LEVEL_BASE.lock().ok().and_then(|b| *b);
            let profiles = clone_profiles();
            let paths = profile_paths();
            let rows: Vec<serde_json::Value> = profiles
                .iter()
                .enumerate()
                .map(|(i, p)| {
                    serde_json::json!({
                        "index": i,
                        "name": p.name,
                        "level": p.level,
                        "vigor": p.stats.vigor,
                        "path": paths.get(i).cloned().flatten(),
                    })
                })
                .collect();
            log::info!(
                "level_status: auto_level={} baseline={:?} profiles={}",
                AUTO_LEVEL.load(Ordering::Acquire),
                base.map(|b| serde_json::json!({
                    "level": b.level, "stats": b.stats, "hp": b.hp, "fp": b.fp, "stamina": b.stamina
                })),
                serde_json::to_string(&rows).unwrap_or_default()
            );
            Ok(())
        }
        "teammate_ai_status" => {
            let profiles = clone_profiles();
            let paths = profile_paths();
            let roster_state = roster::get();
            let slots: Vec<serde_json::Value> = (0..roster::MAX_SLOTS)
                .map(|i| {
                    let idx = roster_state.slots[i];
                    let (name, ai) = if idx >= 0 && (idx as usize) < profiles.len() {
                        let p = &profiles[idx as usize];
                        (
                            p.name.clone(),
                            p.ai.map(|a| {
                                serde_json::json!({
                                    "preset": a.preset.code(),
                                    "label": a.label_key(),
                                    "aggression": a.aggression,
                                    "spell_rate": a.spell_rate,
                                    "guard_rate": a.guard_rate,
                                    "target_switch": a.target_switch,
                                })
                            }),
                        )
                    } else {
                        ("-".to_string(), None)
                    };
                    serde_json::json!({ "slot": i + 1, "profile": idx, "name": name, "ai": ai })
                })
                .collect();
            let buddy_rows = BUDDY_ROWS.lock().map(|g| g.clone()).unwrap_or_default();
            let buddy_think = unsafe { params::repo() }
                .map(|repo| unsafe { params::buddy_think_ids(repo, &buddy_rows) })
                .unwrap_or_default();
            let value = serde_json::json!({
                "slots": slots,
                "think_rows": params::teammate_think_rows(),
                "global_think_row": params::rows::get().1,
                "buddy_rows": buddy_rows,
                "buddy_think": buddy_think,
                "profiles": profiles.iter().enumerate().map(|(i, p)| serde_json::json!({
                    "index": i,
                    "name": p.name,
                    "level": p.level,
                    "ai": p.ai.map(|a| a.label_key()),
                    "path": paths.get(i).cloned().flatten(),
                })).collect::<Vec<_>>(),
            });
            log::info!(
                "teammate_ai_status: {}",
                serde_json::to_string(&value).unwrap_or_default()
            );
            let _ = std::fs::write(
                "er_echo_teammate_ai.json",
                serde_json::to_string_pretty(&value).unwrap_or_default(),
            );
            Ok(())
        }
        "set_teammate_ai" => {
            let slot = cmd.args.get("slot").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
            let preset = cmd
                .args
                .get("preset")
                .and_then(|v| v.as_str())
                .and_then(ai::AiPreset::parse);
            let msg = set_teammate_ai(slot, preset, &cmd.args)?;
            log::info!("{msg}");
            Ok(())
        }
        "teammate_think_rows" => {
            let rows: Vec<u32> = cmd
                .args
                .get("rows")
                .and_then(|v| v.as_array())
                .map(|a| {
                    a.iter()
                        .filter_map(|x| x.as_u64().map(|v| v as u32))
                        .collect()
                })
                .unwrap_or_default();
            params::set_teammate_think_rows(&rows);
            sync_teammate_ai();
            log::info!(
                "teammate_think_rows: {:?} (下一个号位换行在下次召唤生效)",
                params::teammate_think_rows()
            );
            Ok(())
        }
        "damage_probe" => {
            let repo = unsafe { params::repo() }.ok_or("no SoloParamRepository")?;
            let npc_rows: Vec<serde_json::Value> = spirit::CLONE_NPCS
                .iter()
                .map(|&id| {
                    serde_json::json!({
                        "npc": id,
                        "resident": unsafe { spirit::resident_speffects(repo, id) },
                    })
                })
                .collect();
            let mut clones = Vec::new();
            let mut player_friendly_effect = false;
            if let Ok(world) = unsafe { WorldChrMan::instance_mut() } {
                for chr in world.summon_buddy_chr_set.characters() {
                    if !spirit::is_clone(chr) {
                        continue;
                    }
                    let ids: Vec<i32> = chr
                        .special_effect
                        .entries()
                        .map(|e| e.param_id)
                        .collect();
                    let has_correction = ids
                        .iter()
                        .any(|id| spirit::SUMMON_CORRECTION_SPEFFECTS.contains(id));
                    let lock = chr
                        .chr_ctrl
                        .as_ref()
                        .modifier
                        .as_ref()
                        .data
                        .action_flags
                        .disable_lock_on();
                    clones.push(serde_json::json!({
                        "npc": chr.npc_param_id,
                        "chr_type": format!("{:?}", chr.chr_type),
                        "team_type": chr.team_type,
                        "has_correction": has_correction,
                        "disable_lock_on": lock,
                        "speffects": ids,
                    }));
                }
                player_friendly_effect = world
                    .main_player
                    .as_ref()
                    .map(|p| {
                        p.chr_ins
                            .special_effect
                            .entries()
                            .any(|e| e.param_id == params::FRIENDLY_FIRE_SPEFFECT as i32)
                    })
                    .unwrap_or(false);
            }
            log::info!(
                "damage_probe: {}",
                serde_json::to_string(&serde_json::json!({
                    "player_damage": DAMAGE_FIX.load(Ordering::Acquire),
                    "correction_ids": spirit::SUMMON_CORRECTION_SPEFFECTS,
                    "friendly_fire": {
                        "enabled": friendly_fire_enabled(),
                        "rate": params::friendly_rate(),
                        "effect_id": params::FRIENDLY_FIRE_SPEFFECT,
                        "player_has_effect": player_friendly_effect,
                    },
                    "npc_rows": npc_rows,
                    "clones": clones,
                }))
                .unwrap_or_default()
            );
            Ok(())
        }
        "weights_probe" => {
            let w = *CURRENT.lock().unwrap();
            let (behavior_row, think_row, npc_row) = params::rows::get();
            let repo = unsafe { params::repo() }.ok_or("no SoloParamRepository")?;
            let think = unsafe { params::probe_think(repo, think_row) };
            let behavior = unsafe { params::probe_behavior(repo, behavior_row) };
            let value = serde_json::json!({
                "weights": {
                    "aggression": w.aggression, "dodge_rate": w.dodge_rate,
                    "guard_rate": w.guard_rate, "combo_rate": w.combo_rate,
                    "heal_priority": w.heal_priority, "spell_rate": w.spell_rate,
                    "item_rate": w.item_rate, "spacing": w.spacing,
                    "target_switch": w.target_switch,
                },
                "rows": { "behavior": behavior_row, "think": think_row, "npc": npc_row },
                "think": think,
                "behavior": behavior,
            });
            let text = serde_json::to_string_pretty(&value).unwrap_or_default();
            let _ = std::fs::write("er_echo_weights.json", &text);
            log::info!(
                "weights_probe: rows(b={} t={} n={}) think={} behavior={}",
                behavior_row,
                think_row,
                npc_row,
                serde_json::to_string(&value["think"]).unwrap_or_default(),
                serde_json::to_string(&value["behavior"]).unwrap_or_default(),
            );
            Ok(())
        }
        "resummon" => {
            start_resummon(180, 300);
            dismiss_now();
            log::info!("resummon: dismiss requested; summon in 300 frames");
            Ok(())
        }
        "safe_mode" => {
            let on = cmd.args.get("on").and_then(|v| v.as_bool()).unwrap_or(true);
            SAFE_MODE.store(on, Ordering::Release);
            log::warn!("safe_mode = {on} (event summon / glow strip / dummy / spawn disabled)");
            Ok(())
        }
        "summon_state" => {
            let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
            let value = spirit::summon_state(world);
            let text = serde_json::to_string_pretty(&value).map_err(|e| e.to_string())?;
            std::fs::write("er_echo_summon_state.json", &text)
                .map_err(|e| format!("write er_echo_summon_state.json: {e}"))?;
            log::info!(
                "summon_state: req={:?} active={:?} range={}/{} warn={}/{} has_alive={} cooldown={:.2} chrs={}",
                value["request_summon_speffect_id"],
                value["active_summon_speffect_id"],
                value["is_within_activation_range"],
                value["prev_is_within_activation_range"],
                value["is_within_warn_range"],
                value["prev_is_within_warn_range"],
                value["player_has_alive_summon"],
                value["item_use_cooldown_timer"].as_f64().unwrap_or(0.0),
                value["summon_chr_count"],
            );
            Ok(())
        }
        "anywhere" => {
            let on = cmd.args.get("on").and_then(|v| v.as_bool()).unwrap_or(true);
            ANYWHERE.store(on, Ordering::Release);
            if on {
                let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
                spirit::bypass_summon_gates(world);
            }
            log::info!("summon_anywhere = {on}");
            Ok(())
        }
        "multi_summon" => {
            let on = cmd.args.get("on").and_then(|v| v.as_bool()).unwrap_or(true);
            MULTI_SUMMON.store(on, Ordering::Release);
            log::info!("multi_summon = {on}");
            Ok(())
        }
        "summon_events" => {
            let on = cmd.args.get("on").and_then(|v| v.as_bool()).unwrap_or(true);
            ON_EVENTS.store(on, Ordering::Release);
            log::info!("summon_events = {on}");
            Ok(())
        }
        "rest_probe" | "event_probe" => {
            let sitting = spirit::is_sitting_at_grace();
            let counter = spirit::menu_load_counter();
            let (hp, block) = {
                let Ok(world) = (unsafe { WorldChrMan::instance_mut() }) else {
                    return Err("no WorldChrMan".into());
                };
                (spirit::player_hp(world), spirit::player_block(world))
            };
            log::info!(
                "event_probe: sitting={sitting:?} hp={hp:?} block={block:?} load_counter={counter:?} \
                 summon_events={} scheduled_at={} clones={}",
                ON_EVENTS.load(Ordering::Acquire),
                SUMMON_AT.load(Ordering::Acquire),
                clone_count()
            );
            match sitting {
                Some(_) => Ok(()),
                None => Err("CSLuaEventMan.lua_event_proxy is null".into()),
            }
        }
        "stone_range" => {
            let range = cmd
                .args
                .get("range")
                .and_then(|v| v.as_u64())
                .unwrap_or(9999) as u16;
            let repo = unsafe { params::repo() }.ok_or("no SoloParamRepository")?;
            let (n, lo, hi) = unsafe { spirit::widen_buddy_stone_range(repo, range) };
            STONE_RANGE.store(range as u32, Ordering::Release);
            log::info!("stone_range: {lo}..{hi} -> {range} ({n} row(s))");
            Ok(())
        }
        "glow_off" | "glow_strip" => {
            let on = cmd.args.get("on").and_then(|v| v.as_bool()).unwrap_or(true);
            if on {
                let ids: Vec<i32> = cmd
                    .args
                    .get("ids")
                    .and_then(|v| v.as_array())
                    .map(|a| a.iter().filter_map(|x| x.as_i64().map(|v| v as i32)).collect())
                    .filter(|v: &Vec<i32>| !v.is_empty())
                    .unwrap_or_else(|| spirit::GLOW_SPEFFECTS.to_vec());
                if let Ok(mut cur) = GLOW_IDS.lock() {
                    *cur = ids.clone();
                }
                // 1) 之后召唤的：改 NpcParam 常驻槽
                let repo = unsafe { params::repo() }.ok_or("no SoloParamRepository")?;
                let stripped = unsafe { spirit::strip_npc_glow(repo, spirit::CLONE_NPCS, &ids) };
                for (npc, changed) in &stripped {
                    log::info!("glow_off: NpcParam {npc} slots {changed:?} -> -1");
                }
                // 2) 已经在场的：直接摘 spEffect
                let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
                let (n, removed) = spirit::strip_glow(world, &ids);
                GLOW_OFF.store(true, Ordering::Release);
                log::info!("glow_off=on: ids={ids:?}, removed {removed:?} from {n} chr(s)");
            } else {
                GLOW_OFF.store(false, Ordering::Release);
                PHANTOM_ROW.store(-1, Ordering::Release);
                if let Ok(world) = unsafe { WorldChrMan::instance_mut() } {
                    spirit::set_clone_phantom_override(world, -1);
                }
                log::info!("glow_off=off (existing clones keep their current look; resummon to restore)");
            }
            Ok(())
        }
        "phantom_set" | "phantom_neutral" => {
            let repo = unsafe { params::repo() }.ok_or("no SoloParamRepository")?;
            let id = cmd.args.get("id").and_then(|v| v.as_u64()).ok_or("need id")? as u32;
            let msg = if cmd.name == "phantom_neutral" {
                unsafe { spirit::neutralize_phantom(repo, id) }.map_err(|e| e.to_string())?;
                format!("PHANTOM_PARAM_ST {id} -> neutral ({})", spirit::NEUTRAL.len())
            } else {
                let mut fields = cmd.args.clone();
                if let Some(obj) = fields.as_object_mut() {
                    obj.remove("id");
                }
                let applied = unsafe { spirit::patch_phantom(repo, id, fields.as_object().ok_or("args must be object")?) }?;
                format!("PHANTOM_PARAM_ST {id} <- {applied:?}")
            };
            log::info!("{msg}");
            Ok(())
        }
        "phantom_override" => {
            let id = cmd.args.get("id").and_then(|v| v.as_i64()).unwrap_or(-1) as i32;
            let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
            let n = spirit::set_clone_phantom_override(world, id);
            PHANTOM_ROW.store(id, Ordering::Release);
            GLOW_OFF.store(id >= 0, Ordering::Release);
            log::info!("phantom_param_override = {id} on {n} chr(s)");
            Ok(())
        }
        "give_selected" => {
            let msg = give_selected()?;
            log::info!("{msg}");
            Ok(())
        }
        "msg_test" => {
            let id = cmd.args.get("id").and_then(|v| v.as_u64()).unwrap_or(69100000) as u32;
            let text = unsafe { ui::test_lookup(id) }?;
            log::info!("msg_test: id={id} -> {text:?}");
            Ok(())
        }
        "menu_status" => {
            let s = ezstate::status();
            log::info!("menu_status: {s}");
            Ok(())
        }
        "menu_dump" => {
            ezstate::request_dump();
            log::info!("menu_dump: 下一次 EnterState 会打印赐福 state group（再坐一次火）");
            Ok(())
        }
        "menu_reset" => {
            ezstate::reset_patch();
            log::info!("menu_reset: 下次进入赐福初始 state 时重新打补丁");
            Ok(())
        }
        "menu_enable" => {
            let on = cmd.args.get("on").and_then(|v| v.as_bool()).unwrap_or(true);
            ezstate::set_enabled(on);
            log::info!("menu_enable: nested_menu={on}");
            Ok(())
        }
        "set_language" => {
            let spec = cmd
                .args
                .get("lang")
                .and_then(|v| v.as_str())
                .unwrap_or("auto");
            let code = i18n::configure(spec);
            ui::refresh_texts();
            log::info!(
                "set_language: {spec:?} -> {code} (source={}, menu texts rebuilt)",
                i18n::source()
            );
            Ok(())
        }
        "summon_groups" => {
            let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
            let v = spirit::summon_groups_snapshot(world);
            log::info!(
                "summon_groups: {}",
                serde_json::to_string(&v).unwrap_or_else(|_| "{}".into())
            );
            Ok(())
        }
        "sit_grace" => {
            let man = unsafe { CSLuaEventManImp::instance_mut() }
                .map_err(|_| "no CSLuaEventManImp")?;
            let p = man.lua_event_proxy.as_ptr();
            if p.is_null() {
                return Err("lua_event_proxy is null".into());
            }
            unsafe {
                (*p)
                    .control_flags
                    .set_bonfire_loop_begin_requested(true);
            }
            log::info!("sit_grace: bonfire_loop_begin_requested = true");
            Ok(())
        }
        "flag_test" => {
            let id = cmd.args.get("id").and_then(|v| v.as_u64()).unwrap_or(6720) as u32;
            let man = unsafe { CSEventFlagMan::instance_mut() }.map_err(|_| "no CSEventFlagMan")?;
            let keep = cmd.args.get("keep").and_then(|v| v.as_bool()).unwrap_or(false);
            let before = man.virtual_memory_flag.get_flag(id);
            man.virtual_memory_flag.set_flag(id, true);
            let after = man.virtual_memory_flag.get_flag(id);
            if !keep {
                man.virtual_memory_flag.set_flag(id, false);
            }
            let holders = man.virtual_memory_flag.event_flag_holder_count;
            let holder_size = man.virtual_memory_flag.event_flag_holder_size;
            let divisor = man.virtual_memory_flag.event_flag_divisor;
            let blocks = man.virtual_memory_flag.flag_blocks;
            log::info!(
                "flag_test: id={id} group={} before={before} after_set={after} \
                 holders={holders} holder_size={holder_size} divisor={divisor} blocks={blocks:?}",
                id / 1000,
            );
            Ok(())
        }
        "load_profile" => {
            let path = cmd
                .args
                .get("path")
                .and_then(|v| v.as_str())
                .unwrap_or("profiles/target.json");
            let p = profile::Profile::load(path)?;
            log::info!("profile loaded: {} lv{}", p.name, p.level);
            *PROFILE.lock().map_err(|_| "profile lock")? = Some(p.clone());
            install_profiles(vec![p], vec![Some(path.to_string())])?;
            sync_teammate_ai();
            Ok(())
        }
        "set_clone_profiles" => {
            let paths: Vec<String> = cmd
                .args
                .get("paths")
                .and_then(|v| v.as_array())
                .map(|a| {
                    a.iter()
                        .filter_map(|x| x.as_str().map(str::to_string))
                        .collect()
                })
                .unwrap_or_default();
            let mut loaded = Vec::with_capacity(paths.len());
            for path in &paths {
                let p = profile::Profile::load(path)
                    .map_err(|e| format!("{path}: {e}"))?;
                log::info!("clone profile[{}/{}]: '{}' lv{}", loaded.len(), paths.len(), p.name, p.level);
                loaded.push(p);
            }
            let n = loaded.len();
            install_profiles(loaded, paths.into_iter().map(Some).collect())?;
            sync_teammate_ai();
            log::info!("clone profiles set: {n} (clone i -> profile i % {n})");
            Ok(())
        }
        "apply_to_clone" => {
            let stats = cmd.args.get("stats").and_then(|v| v.as_bool()).unwrap_or(false);
            let msg = apply_to_clones(stats)?;
            log::info!("{msg}");
            Ok(())
        }
        // 体型是建模型时烘焙的：先写档案（gender + 7 个 f32），再让引擎重建模型。
        // ⚠ 实测直接调 ChrIns 的 vtable `initialize_model_resources` 会闪退（§28.4），
        // 所以这里只做诊断/写 FaceParam，不碰模型重建。
        "init_probe" => {
            let msg = unsafe { params::probe_init(26050) }?;
            log::info!("{msg}");
            Ok(())
        }
        // 给 1/2/3 号位各准备一行 spawn 用的 init/FaceParam（体型在这里烘焙）。
        // 改完要 `resummon` 才会用新行出生。
        "setup_bodies" => {
            let profiles = clone_profiles();
            let rows = BUDDY_ROWS.lock().map(|g| g.clone()).unwrap_or_default();
            let repo = unsafe { params::repo() }.ok_or("no SoloParamRepository")?;
            let value = unsafe { params::setup_teammate_bodies(repo, &profiles, &rows) }?;
            log::info!("setup_bodies: {value}");
            Ok(())
        }
        // 把某个 profile 的体型写进 `CharaInitParam.npc_player_face_gen_id` 指向的
        // FACE_PARAM 行，然后 `resummon` 让新克隆体在出生时就用这个体型。
        // 这是验证「体型在 spawn 时从 FaceParam 烘焙」用的；正式版要做成每号位一行。
        "face_row_body" => {
            let profile = cmd.args.get("profile").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
            let msg = unsafe { params::write_face_body_from_profile(26050, profile) }?;
            log::info!("{msg}");
            Ok(())
        }
        "equip_probe" => {
            // 诊断：写装备后**同一帧立刻回读**三份「装备真相」，看引擎认哪一份。
            let profiles = clone_profiles();
            let Some(target) = profiles.first().cloned() else {
                return Err("no clone profiles loaded".into());
            };
            let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
            let mut n = 0;
            for chr in world.summon_buddy_chr_set.characters() {
                let Some(p) = chr.as_subclass_mut::<PlayerIns>() else {
                    continue;
                };
                let applied = unsafe { kit::apply(p, &target, false, 1.0) };
                let pgd = unsafe { p.player_game_data.as_ref() };
                log::info!(
                    "equip_probe[{n}]: chr_asm={:?} pgd_chr_asm={:?} entries_head={} gaitem0={} idx0={}",
                    &applied.readback[..6],
                    &pgd.equipment.chr_asm.equipment_param_ids[..6],
                    pgd.equipment.equipment_entries.protector_head.param_id(),
                    p.chr_asm.as_ref().gaitem_handles[0],
                    pgd.equipment.equipment_item_idx_list[0],
                );
                n += 1;
            }
            if n == 0 {
                return Err("no PlayerIns clone".into());
            }
            Ok(())
        }
        "auto_apply" => {
            let on = cmd.args.get("on").and_then(|v| v.as_bool()).unwrap_or(true);
            AUTO_APPLY.store(on, Ordering::Release);
            log::info!("auto_apply = {on}");
            if on {
                let msg = apply_to_clones(APPLY_STATS.load(Ordering::Acquire)).unwrap_or_else(|e| e);
                log::info!("auto_apply immediate: {msg}");
            }
            Ok(())
        }
        "apply_stats" => {
            let on = cmd.args.get("on").and_then(|v| v.as_bool()).unwrap_or(true);
            APPLY_STATS.store(on, Ordering::Release);
            log::info!("apply_stats = {on}");
            Ok(())
        }
        "set_follow" => {
            if let Some(v) = cmd.args.get("dist").and_then(|v| v.as_f64()) {
                let d = v as f32;
                set_follow_dist(d);
                log::info!("follow distance set to {d}");
            }
            if let Some(auto) = cmd.args.get("auto_recall").and_then(|v| v.as_bool()) {
                AUTO_RECALL.store(auto, Ordering::Release);
                log::info!("auto_recall = {auto}");
            }
            Ok(())
        }
        "copy_buddy_row" => {
            let repo = unsafe { params::repo() }.ok_or("no SoloParamRepository")?;
            let from = cmd.args.get("from").and_then(|v| v.as_u64()).unwrap_or(20700001) as u32;
            let keep = cmd
                .args
                .get("keep_trigger")
                .and_then(|v| v.as_bool())
                .unwrap_or(true);
            let to: Vec<u32> = cmd
                .args
                .get("to")
                .and_then(|v| v.as_array())
                .map(|a| a.iter().filter_map(|x| x.as_u64()).map(|x| x as u32).collect())
                .filter(|v: &Vec<u32>| !v.is_empty())
                .unwrap_or_else(|| {
                    CONFIG_DATA
                        .get()
                        .map(|c| c.buddy_rows.clone())
                        .unwrap_or_default()
                });
            if to.is_empty() {
                return Err("copy_buddy_row: no target rows (pass `to` or set config buddy_rows)".into());
            }
            let n = unsafe { params::copy_buddy_row(repo, from, &to, keep) };
            if n == 0 {
                return Err(format!("copy_buddy_row: nothing copied (from={from} to={to:?})"));
            }
            Ok(())
        }
        "recall" => {
            let msg = recall_clones()?;
            log::info!("recall: {msg}");
            Ok(())
        }
        "keep_close" => {
            let d = cmd.args.get("dist").and_then(|v| v.as_f64()).unwrap_or(20.0) as f32;
            set_leash(d);
            // 立刻按新绳长重写一次 think 行（对已存在的实体通常要等下次召唤才生效）
            unsafe { params::apply_weights(&*CURRENT.lock().unwrap()) };
            log::info!("keep_close: leash = {d} m (backhome_dist clamped); 下次召唤生效");
            Ok(())
        }
        "set_player_equipment" => {
            let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
            let Some(ref mut player) = world.main_player else { return Err("no player".into()) };
            let mut ids = player.chr_asm.as_ref().equipment_param_ids;
            for (key, slot) in [
                ("weapon_left", 0usize),
                ("weapon_right", 1),
                ("head", 12),
                ("body", 13),
                ("hands", 14),
                ("legs", 15),
            ] {
                if let Some(v) = cmd.args.get(key).and_then(|v| v.as_i64()) {
                    ids[slot] = v as i32;
                }
            }
            unsafe { profile::apply_equipment(player.chr_asm.as_ptr(), &ids) };
            log::info!("player equipment set: {:?}", ids);
            Ok(())
        }
        "dismiss" => {
            CLONE_ACTIVE.store(false, Ordering::Release);
            let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
            let mgr = spirit::manager_mut(world).ok_or("summon_buddy_manager is null")?;
            mgr.disappear_requested = true;
            mgr.buddy_disappear_delay_sec = 0.0;
            log::info!("dismiss requested");
            Ok(())
        }
        "fix_clone" => {
            let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
            let (pb, pbo, pp) = {
                let Some(ref player) = world.main_player else { return Err("no player".into()) };
                let c = &player.chr_ins;
                (c.block_id, c.block_origin, c.chunk_position)
            };
            let mut n = 0;
            for chr in world.summon_buddy_chr_set.characters() {
                chr.block_id = pb;
                chr.block_id_override = pb;
                chr.block_origin = pbo;
                chr.chunk_position = F32Vector4(pp.0 + 1.2, pp.1 + 0.5, pp.2, 0.0);
                chr.tint_alpha_multiplier = 1.0;
                chr.tint_alpha_multiplier_modifier = 0.0;
                chr.opacity_keyframes_multiplier = 1.0;
                n += 1;
            }
            log::info!("fix_clone: moved {n} summon buddy(s) into player block {:?}", pb);
            Ok(())
        }
        "set_buddy_row" => {
            let id = cmd.args.get("id").and_then(|v| v.as_u64()).unwrap_or(20700000) as u32;
            let repo = unsafe { params::repo() }.ok_or("no SoloParamRepository")?;
            let Some(row) = repo.get_mut::<eldenring::cs::BuddyParam>(id) else {
                return Err(format!("BuddyParam {id} not found"));
            };
            if let Some(v) = cmd.args.get("npc").and_then(|v| v.as_i64()) {
                row.set_npc_param_id(v as i32);
            }
            if let Some(v) = cmd.args.get("think").and_then(|v| v.as_i64()) {
                row.set_npc_think_param_id(v as i32);
            }
            if let Some(v) = cmd.args.get("init").and_then(|v| v.as_i64()) {
                row.set_npc_player_init_param_id(v as i32);
            }
            if let Some(v) = cmd.args.get("follow").and_then(|v| v.as_i64()) {
                row.set_pc_follow_type(v as u8);
            }
            log::info!(
                "buddy row {id}: npc={} think={} init={} follow={}",
                row.npc_param_id(),
                row.npc_think_param_id(),
                row.npc_player_init_param_id(),
                row.pc_follow_type()
            );
            Ok(())
        }
        "dump_summons" => {
            let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
            log::info!("{}", unsafe { dump::dump_summons(world) }?);
            Ok(())
        }
        "clone_info" => {
            let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
            log::info!("{}", unsafe { dump::dump_clone_info(world) }?);
            Ok(())
        }
        "spawn_debug" => {
            if SAFE_MODE.load(Ordering::Acquire) {
                return Err("safe_mode on: spawn_debug disabled".into());
            }
            let npc = cmd.args.get("npc").and_then(|v| v.as_i64()).unwrap_or(100000010) as i32;
            let think = cmd.args.get("think").and_then(|v| v.as_i64()).unwrap_or(100000010) as i32;
            let chara = cmd.args.get("chara").and_then(|v| v.as_i64()).unwrap_or(26050) as i32;
            let dist = cmd
                .args
                .get("dist")
                .or_else(|| cmd.args.get("dy"))
                .and_then(|v| v.as_f64())
                .unwrap_or(1.5) as f32;
            *PENDING_SPAWN.lock().map_err(|_| "spawn lock")? = Some((npc, think, chara, dist));
            set_op("spawn_debug");
            log::info!("spawn_debug queued npc={npc} think={think} chara={chara} dist={dist}");
            Ok(())
        }
        "dump_chrs" => {
            let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
            log::info!("{}", unsafe { dump::dump_chrs(world) }?);
            Ok(())
        }
        "set_speffect" => {
            let id = cmd.args.get("id").and_then(|v| v.as_i64()).unwrap_or(207000) as i32;
            SUMMON_SP.store(id, Ordering::Relaxed);
            if cmd.args.get("apply").and_then(|v| v.as_bool()).unwrap_or(false) {
                let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
                let Some(ref mut player) = world.main_player else { return Err("no player".into()) };
                player.chr_ins.apply_speffect(id, true);
                log::info!("applied spEffect {id} to player");
            }
            log::info!("summon spEffect set to {id}");
            Ok(())
        }
        "dump_profile" => {            let world = unsafe { WorldChrMan::instance_mut() }.map_err(|_| "no WorldChrMan")?;
            let Some(ref player) = world.main_player else { return Err("no player".into()) };
            log::info!("{}", unsafe { dump::dump_profile(player) }?);
            Ok(())
        }
        other => Err(format!("unknown command {other}")),
    }
}

// ---------------------------------------------------------------- LLM tools

/// 槽位名 → 22 槽索引（与 `ChrAsm.equipment_param_ids` 顺序、存档 PGD+0x58 表一致）。
fn slot_from_name(name: &str) -> Option<usize> {
    let slot = match name {
        "weapon_left" | "left1" => 0,
        "weapon_right" | "right1" => 1,
        "weapon_left2" | "left2" => 2,
        "weapon_right2" | "right2" => 3,
        "weapon_left3" | "left3" => 4,
        "weapon_right3" | "right3" => 5,
        "arrow1" => 6,
        "bolt1" => 7,
        "arrow2" => 8,
        "bolt2" => 9,
        "arrow3" => 10,
        "bolt3" => 11,
        "head" => 12,
        "body" | "chest" => 13,
        "hands" => 14,
        "legs" => 15,
        "talisman1" => 17,
        "talisman2" => 18,
        "talisman3" => 19,
        "talisman4" => 20,
        "covenant" => 21,
        _ => return name.parse::<usize>().ok().filter(|s| *s < 22),
    };
    Some(slot)
}

/// 单步变化限制在 ±`frac`，避免 LLM 一次把角色改成怪物（design §10.4「clamp 到目标 ±20%」）。
fn clamp_step(current: u32, want: u32, frac: f32) -> u32 {
    let cur = current.max(1) as f32;
    let lo = (cur * (1.0 - frac)).floor() as u32;
    let hi = (cur * (1.0 + frac)).ceil() as u32;
    want.clamp(lo.max(1), hi)
}

/// LLM 工具：换装。**作用对象是克隆体**（不是玩家），带槽位白名单 + 参数存在性检查 + 回滚点。
fn set_clone_equipment(args: &serde_json::Value) -> Result<(), String> {
    let repo = unsafe { params::repo() }.ok_or("no SoloParamRepository (wait until in-game)")?;
    let who = args.get("who").and_then(|v| v.as_u64()).map(|v| v as usize);

    let mut edits: Vec<(usize, i32)> = Vec::new();
    if let Some(loadout) = args.get("loadout").and_then(|v| v.as_object()) {
        for (key, value) in loadout {
            let slot = slot_from_name(key).ok_or_else(|| format!("unknown slot '{key}'"))?;
            let id = value
                .as_i64()
                .ok_or_else(|| format!("slot '{key}': id must be an integer"))? as i32;
            edits.push((slot, id));
        }
    }
    if let Some(slot_arg) = args.get("slot") {
        let slot = match slot_arg {
            serde_json::Value::String(s) => {
                slot_from_name(s).ok_or_else(|| format!("unknown slot '{s}'"))?
            }
            serde_json::Value::Number(n) => n.as_u64().map(|v| v as usize).ok_or("bad slot")?,
            _ => return Err("slot must be a string or a number".into()),
        };
        let id = args
            .get("item_id")
            .and_then(|v| v.as_i64())
            .ok_or("item_id required when using slot")? as i32;
        edits.push((slot, id));
    }
    if edits.is_empty() {
        return Err("nothing to change: pass `slot`+`item_id` or `loadout`".into());
    }

    // 强化：只对武器槽生效，而且**必须真的存在** —— 直接拿 id+N 去参数表查，
    // 查不到就拒绝，不猜「+N 的编码规则」（design §11.3）。
    let upgrade = args.get("upgrade").and_then(|v| v.as_i64()).unwrap_or(0) as i32;
    for (slot, id) in &mut edits {
        let category =
            kit::slot_category(*slot).ok_or_else(|| format!("slot {slot} is not an equipment slot"))?;
        if *id <= 0 {
            *id = -1;
            continue;
        }
        let mut wanted = *id;
        if upgrade != 0 {
            if category != ItemCategory::Weapon {
                return Err("upgrade only applies to weapon slots".into());
            }
            wanted += upgrade;
        }
        let item = ItemId::new(category, wanted as u32).map_err(|_| format!("bad item id {wanted}"))?;
        if repo.get_equip_param(item).is_none() {
            return Err(format!("item {wanted} not present in {category:?} param table"));
        }
        *id = wanted;
    }

    let mut profiles = clone_profiles();
    if profiles.is_empty() {
        return Err("no clone profiles loaded (load_profile / set_clone_profiles first)".into());
    }
    if let Ok(mut backup) = EQUIP_BACKUP.lock() {
        *backup = Some(profiles.iter().map(|p| p.equipment_param_ids.clone()).collect());
    }
    let mut changed = 0usize;
    for (i, p) in profiles.iter_mut().enumerate() {
        if who.map(|w| w != i).unwrap_or(false) {
            continue;
        }
        for (slot, id) in &edits {
            if *slot < p.equipment_param_ids.len() {
                p.equipment_param_ids[*slot] = *id;
            }
        }
        changed += 1;
    }
    if changed == 0 {
        return Err(format!("who={who:?} matched no profile"));
    }
    *CLONE_PROFILES.lock().map_err(|_| "profile lock")? = profiles;
    log::info!("set_equipment: {changed} profile(s) <- {edits:?} (upgrade={upgrade})");
    apply_to_clones(false)?;
    Ok(())
}

/// LLM 工具：加点/升级。作用对象是克隆体；单项变化 clamp 到 ±20%。
fn set_clone_stats(args: &serde_json::Value) -> Result<(), String> {
    let who = args.get("who").and_then(|v| v.as_u64()).map(|v| v as usize);
    let mut profiles = clone_profiles();
    if profiles.is_empty() {
        return Err("no clone profiles loaded".into());
    }
    if let Ok(mut backup) = STATS_BACKUP.lock() {
        *backup = Some(profiles.clone());
    }
    let mut changed = 0usize;
    for (i, p) in profiles.iter_mut().enumerate() {
        if who.map(|w| w != i).unwrap_or(false) {
            continue;
        }
        changed += 1;
        let old_level = p.level.max(1);
        let mut touched = false;
        for key in [
            "vigor",
            "mind",
            "endurance",
            "strength",
            "dexterity",
            "intelligence",
            "faith",
            "arcane",
        ] {
            let Some(want) = args.get(key).and_then(|v| v.as_u64()) else {
                continue;
            };
            let cur = match key {
                "vigor" => p.stats.vigor,
                "mind" => p.stats.mind,
                "endurance" => p.stats.endurance,
                "strength" => p.stats.strength,
                "dexterity" => p.stats.dexterity,
                "intelligence" => p.stats.intelligence,
                "faith" => p.stats.faith,
                _ => p.stats.arcane,
            };
            let next = clamp_step(cur, want as u32, 0.2).clamp(1, 99);
            match key {
                "vigor" => p.stats.vigor = next,
                "mind" => p.stats.mind = next,
                "endurance" => p.stats.endurance = next,
                "strength" => p.stats.strength = next,
                "dexterity" => p.stats.dexterity = next,
                "intelligence" => p.stats.intelligence = next,
                "faith" => p.stats.faith = next,
                _ => p.stats.arcane = next,
            }
            touched = true;
        }
        if let Some(want) = args.get("level").and_then(|v| v.as_u64()) {
            let next = clamp_step(old_level, want as u32, 0.2).clamp(1, 713);
            if next != old_level {
                // 存档里的三围上限是按旧等级算出来的；等级一变就按比例缩放（近似），
                // 否则「升了级但血量不动」会很怪。
                if let Some(pools) = p.pools.as_mut() {
                    let k = next as f32 / old_level as f32;
                    pools.hp = ((pools.hp as f32 * k).round() as u32).clamp(1, 30_000);
                    pools.fp = ((pools.fp as f32 * k).round() as u32).clamp(1, 3_000);
                    pools.stamina = ((pools.stamina as f32 * k).round() as u32).clamp(1, 3_000);
                }
                p.level = next;
            }
            touched = true;
        }
        if touched {
            log::info!(
                "set_stats: profile {i} '{}' -> lv{} (vigor {})",
                p.name,
                p.level,
                p.stats.vigor
            );
        }
    }
    if changed == 0 {
        return Err(format!("who={who:?} matched no profile"));
    }
    *CLONE_PROFILES.lock().map_err(|_| "profile lock")? = profiles;
    apply_to_clones(true)?;
    Ok(())
}

/// 回滚上一次 `set_equipment`（LLM 工具必须能撤销，design §10.4）。
fn rollback_equipment() -> Result<(), String> {
    let backup = EQUIP_BACKUP
        .lock()
        .map_err(|_| "backup lock")?
        .clone()
        .ok_or("no equipment backup to roll back to")?;
    let mut profiles = clone_profiles();
    if profiles.is_empty() {
        return Err("no clone profiles loaded".into());
    }
    for (p, ids) in profiles.iter_mut().zip(backup.iter()) {
        p.equipment_param_ids.clone_from(ids);
    }
    *CLONE_PROFILES.lock().map_err(|_| "profile lock")? = profiles;
    log::info!("rollback_equipment: restored {} profile(s)", backup.len());
    apply_to_clones(false)?;
    Ok(())
}

// ---------------------------------------------------------------- config

/// 配置驱动的「一次准备」：读档后自动加载档案 + 覆盖骨灰行。
/// 这样玩家只需要「用骨灰」，不用每次手动敲 IPC 命令。
fn apply_config_once() {
    if CONFIG_DONE.load(Ordering::Acquire) {
        return;
    }
    let Some(cfg) = CONFIG_DATA.get() else {
        return;
    };
    // 等仓库/玩家都起来，避免在主菜单里摸空指针
    if FRAME.load(Ordering::Relaxed) < 120 {
        return;
    }
    let Some(repo) = (unsafe { params::repo() }) else {
        return;
    };
    if unsafe { WorldChrMan::instance_mut() }.is_err() {
        return;
    }

    if !cfg.profiles.is_empty() {
        let mut loaded = Vec::new();
        let mut loaded_paths = Vec::new();
        for path in &cfg.profiles {
            match profile::Profile::load(path) {
                Ok(p) => {
                    log::info!(
                        "config profile[{}/{}]: '{}' lv{}",
                        loaded.len(),
                        cfg.profiles.len(),
                        p.name,
                        p.level
                    );
                    loaded.push(p);
                    loaded_paths.push(Some(path.clone()));
                }
                Err(err) => log::error!("config profile '{path}': {err}"),
            }
        }
        if !loaded.is_empty() {
            if let Err(err) = install_profiles(loaded, loaded_paths) {
                log::error!("config profiles: {err}");
            }
        }
    }
    // 队伍名单：默认按 ini 里的档案顺序出场；之后由篝火菜单改。
    let profile_count = clone_profiles().len();
    roster::init(profile_count, cfg.friendly_fire);
    unsafe { roster::clear_flags() };

    // 友伤开关：roster 文件里持久化的状态优先（菜单点过就记住）。
    let friendly = roster::get().friendly_fire;
    FRIENDLY_FIRE.store(friendly, Ordering::Release);
    let friendly_rate = params::set_friendly_rate(cfg.friendly_fire_rate);
    match unsafe { params::set_friendly_fire_with(repo, friendly) } {
        Ok((changed, total, already)) if friendly => log::info!(
            "config: friendly_fire=on — AtkParam_Pc friendlyTarget {changed} row(s) enabled \
             (total={total}, already={already}); damage rate={:.0}%; companions cannot be lock-on targets",
            friendly_rate * 100.0
        ),
        Ok((restored, total, _)) => log::info!(
            "config: friendly_fire=off — {restored} patched row(s) restored (total={total})"
        ),
        Err(err) => log::warn!("config: friendly_fire failed: {err}"),
    }
    if friendly {
        match unsafe { params::patch_friendly_damage_effect_with(repo, friendly_rate) } {
            Ok(rate) => log::info!("config: friendly fire damage effect = {:.0}%", rate * 100.0),
            Err(err) => log::warn!("config: friendly fire damage effect failed: {err}"),
        }
    } else {
        unsafe { params::restore_friendly_damage_effect_with(repo) };
    }

    // 同伴伤害修正 = 玩家褪色者：摘掉拟态泪滴行上的灵体削弱 spEffect。
    DAMAGE_FIX.store(cfg.player_damage, Ordering::Release);
    if cfg.player_damage {
        let stripped = unsafe {
            spirit::strip_npc_speffect_slots(
                repo,
                spirit::CLONE_NPCS,
                spirit::SUMMON_CORRECTION_SPEFFECTS,
            )
        };
        for (npc, changed) in &stripped {
            if changed.is_empty() {
                log::warn!(
                    "config: NpcParam {npc} has no {:?} in resident spEffect slots",
                    spirit::SUMMON_CORRECTION_SPEFFECTS
                );
            } else {
                log::info!(
                    "config: NpcParam {npc} resident spEffect slots {changed:?} -> -1 (player-like damage)"
                );
            }
        }
    }
    AUTO_LEVEL.store(cfg.auto_level, Ordering::Release);

    // 战友模式：按出战友人数补正敌人生命上限（默认 1.5 / 1.8 / 2.0）。
    // 实际写入在 tick 里每 15 帧一次；这里只把配置落到 balance 模块。
    balance::set_enabled(cfg.enemy_hp_scaling);
    let enemy_hp_rates = balance::set_rates(&cfg.enemy_hp_rates);
    log::info!(
        "config: enemy_hp_scaling={} rates={:?} (comrades 1/2/3 -> enemy max HP multiplier; 0 comrades = 1.0)",
        cfg.enemy_hp_scaling,
        enemy_hp_rates
    );

    ui::refresh_texts();
    unsafe { ui::install_msg_hook() };
    AUTO_APPLY.store(cfg.auto_apply, Ordering::Release);
    APPLY_STATS.store(cfg.apply_stats, Ordering::Release);
    INFINITE_FP.store(cfg.infinite_fp, Ordering::Release);

    // 权重落点：默认 think=100000010（拟态泪滴本体行），所以 set_weights 开箱即用；
    // behavior/npc 默认 0（不写），因为那两张表的槽位语义还没逐条实测（§16.1）。
    params::rows::set(cfg.behavior_row, cfg.think_row, cfg.npc_row);
    // 每号位自己的 think 行（先设好，下面的初次 apply_weights / sync 才会用到）。
    params::set_teammate_think_rows(&cfg.teammate_think_rows);
    log::info!(
        "config: weight rows behavior={} think={} npc={} (0 = 不写); teammate AI rows={:?}",
        cfg.behavior_row,
        cfg.think_row,
        cfg.npc_row,
        cfg.teammate_think_rows
    );

    // 开箱即用：立刻把默认权重写一次 think 行。
    // 拟态泪滴 think 行的出厂值是「贴脸才反应」（eye_dist = battle_start_dist = 2 m），
    // 法系同伴因此在射程外永远不进入战斗、也就永远不放法术（§17.1 实测）。
    // 抬到 6..20 m 之后「发现 → 接近 → 开打 → 施法」整条链路才通。
    if cfg.think_row != 0 {
        let w = *CURRENT.lock().unwrap();
        unsafe { params::apply_weights(&w) };
        log::info!(
            "config: default weights -> think {} (aggr={:.2}: eye={}m battle_start={}m)",
            cfg.think_row,
            w.aggression,
            (6.0 + 14.0 * w.aggression) as u16,
            (3.0 + 9.0 * w.aggression) as u16
        );
    }

    SAFE_MODE.store(cfg.safe_mode, Ordering::Release);
    if cfg.safe_mode {
        log::warn!(
            "config: safe_mode=on — 事件召唤 / 灵体摘除 / 木桩 / 调试生成 已禁用（排查闪退用）"
        );
    }
    LOST_RESUMMON.store(cfg.lost_resummon, Ordering::Release);
    LOST_DIST_BITS.store(cfg.lost_distance.to_bits(), Ordering::Release);
    LOST_SECONDS.store(cfg.lost_seconds, Ordering::Release);
    AUTO_STATUS.store(cfg.auto_status, Ordering::Release);
    log::info!(
        "config: lost_resummon={} lost_distance={:.0}m lost_seconds={}s auto_status={}",
        cfg.lost_resummon,
        cfg.lost_distance,
        cfg.lost_seconds,
        cfg.auto_status
    );

    for &row_id in &cfg.buddy_rows {
        let Some(row) = repo.get_mut::<eldenring::cs::BuddyParam>(row_id) else {
            log::warn!("config: BuddyParam {row_id} not found");
            continue;
        };
        if let Some(v) = cfg.buddy_npc {
            row.set_npc_param_id(v);
        }
        if let Some(v) = cfg.buddy_think {
            row.set_npc_think_param_id(v);
        }
        if let Some(v) = cfg.buddy_init {
            row.set_npc_player_init_param_id(v);
        }
        if let Some(v) = cfg.buddy_follow {
            row.set_pc_follow_type(v);
        }
        log::info!(
            "config: BuddyParam {row_id} -> npc={} think={} init={} follow={}",
            row.npc_param_id(),
            row.npc_think_param_id(),
            row.npc_player_init_param_id(),
            row.pc_follow_type()
        );
    }

    // 整行复制：把「拟态泪滴本体」的 BuddyParam 行为照搬过来（保留各自 trigger spEffect）。
    // 这比逐字段改更省事，也更接近「完全走骨灰逻辑」—— 跟随/掉队处理本来就是骨灰行在管。
    if let Some(from) = cfg.buddy_copy_from {
        if !cfg.buddy_rows.is_empty() {
            let n = unsafe { params::copy_buddy_row(repo, from, &cfg.buddy_rows, true) };
            log::info!("config: buddy_copy_from={from} applied to {n} row(s)");
        }
    }

    // 召唤请求用的 trigger spEffect：优先用配置，否则取第一行载体骨灰自己的 tipgger。
    // 直接写这个字段就能绕过「骨灰物品 / 区域 / 召唤石 / 冷却」整套判定。
    let trigger = cfg.summon_trigger.unwrap_or_else(|| {
        cfg.buddy_rows
            .first()
            .and_then(|id| repo.get::<eldenring::cs::BuddyParam>(*id))
            .map(|r| r.trigger_sp_effect_id())
            .unwrap_or(207000)
    });
    SUMMON_SP.store(trigger, Ordering::Release);
    log::info!("config: summon trigger spEffect = {trigger} (hotkey F8 / summon_force 用这个)");
    if let Ok(mut rows) = BUDDY_ROWS.lock() {
        *rows = cfg.buddy_rows.clone();
    }
    apply_roster_count();
    // 每个号位的 AI：把 think 行复制成基准行 + 覆盖该号位档案的预设，
    // 并把 BuddyParam.npc_think_param_id 指到对应行（必须在第一次召唤之前）。
    sync_teammate_ai_with(repo);

    // 召唤石半径：骨灰能不能用，玩家离召唤石多远是硬条件（dead zone 就是这么来的）。
    if cfg.stone_range > 0 {
        let (n, lo, hi) = unsafe { spirit::widen_buddy_stone_range(repo, cfg.stone_range) };
        log::info!(
            "config: BuddyStoneParam.activate_range {lo}..{hi} -> {} ({n} row(s))",
            cfg.stone_range
        );
    }
    ANYWHERE.store(cfg.summon_anywhere, Ordering::Release);
    MULTI_SUMMON.store(cfg.multi_summon, Ordering::Release);
    ON_EVENTS.store(cfg.summon_events, Ordering::Release);
    STONE_RANGE.store(cfg.stone_range as u32, Ordering::Release);
    if cfg.summon_anywhere {
        log::info!("config: summon_anywhere=on (activation range / cooldown bypassed every frame)");
    }

    // 灵体外观：摘掉 NpcParam 常驻槽里的「骨灰外观」spEffect（295000/295200）。
    // 之后召唤出来的克隆体就没有白雾虚影；已存在的克隆体由 tick 里的 strip_glow 处理。
    if cfg.no_spirit_glow {
        if let Ok(mut ids) = GLOW_IDS.lock() {
            *ids = cfg.glow_speffects.clone();
        }
        let stripped = unsafe { spirit::strip_npc_glow(repo, spirit::CLONE_NPCS, &cfg.glow_speffects) };
        for (npc, changed) in &stripped {
            if changed.is_empty() {
                log::warn!("config: NpcParam {npc} has no {:?} in its resident spEffect slots", cfg.glow_speffects);
            } else {
                log::info!("config: NpcParam {npc} resident spEffect slots {changed:?} -> -1 (no ash glow)");
            }
        }
        GLOW_OFF.store(true, Ordering::Release);
    }

    log::info!(
        "config applied: profiles={} auto_apply={} apply_stats={} player_damage={} auto_level={} friendly_fire={} enemy_hp_scaling={} buddy_rows={}",
        cfg.profiles.len(),
        cfg.auto_apply,
        cfg.apply_stats,
        cfg.player_damage,
        cfg.auto_level,
        roster::get().friendly_fire,
        cfg.enemy_hp_scaling,
        cfg.buddy_rows.len()
    );
    CONFIG_DONE.store(true, Ordering::Release);
}

struct Config {
    ipc_addr: String,
    ipc_token: String,
    follow_distance: f32,
    /// 每次进游戏自动加载的档案（clones: i -> i % n）
    profiles: Vec<String>,
    auto_apply: bool,
    apply_stats: bool,
    /// 同伴使用和玩家一致的伤害修正（摘掉灵体 spEffect 296000 / 20297000，默认开）
    player_damage: bool,
    /// 玩家升级时队友跟着升级，并把新等级/属性写回 profile（默认开）
    auto_level: bool,
    /// 掉队超过 `follow_distance` 就自动把克隆体拉回玩家身边（默认关）
    auto_recall: bool,
    /// 要改写成「人形泪滴」的骨灰 BuddyParam 行
    buddy_rows: Vec<u32>,
    buddy_npc: Option<i32>,
    buddy_think: Option<i32>,
    buddy_init: Option<i32>,
    buddy_follow: Option<u8>,
    /// 把这一行 BuddyParam 的行为整行复制到 `buddy_rows`（默认拟态泪滴本体 20700001）
    buddy_copy_from: Option<u32>,
    /// 跳过骨灰的区域/召唤石范围限制
    summon_anywhere: bool,
    /// 启动时把每行 BuddyStoneParam.activate_range 抬到这个值（0 = 不改）
    stone_range: u16,
    /// 去掉灵体的蓝白发光/半透（摘掉「骨灰外观」spEffect）
    no_spirit_glow: bool,
    /// 「骨灰外观」spEffect id（默认 295000 普通 / 295200 傀儡）
    glow_speffects: Vec<i32>,
    /// 允许已有召唤物时再用骨灰（默认开）
    multi_summon: bool,
    /// 召唤请求用的 trigger spEffect（默认取第一行载体骨灰自己的）
    summon_trigger: Option<i32>,
    /// 坐火 / 传送 / 复活之后自动召唤
    summon_events: bool,
    /// 同伴无限蓝（每帧把克隆体 FP 顶回上限，默认开）
    infinite_fp: bool,
    /// 权重落到 `NpcAiBehaviorProbability` 的哪一行（0 = 不写）
    behavior_row: u32,
    /// 权重落到 `NpcThinkParam` 的哪一行（默认拟态泪滴本体 100000010，开箱即用）
    think_row: u32,
    /// 权重落到 `NpcParam` 的哪一行（0 = 不写）
    npc_row: u32,
    /// 每号位队友 AI 用的 `NpcThinkParam` 行（顺序 = 1/2/3 号位；0 / 行不存在 = 该号位跟随 `think_row`）。
    /// 默认取拟态泪滴家族里行为相同的几行（运行时会把基准行整行复制过去，所以只借 id 不借语义）。
    teammate_think_rows: Vec<u32>,
    /// 安全模式：关掉事件召唤 / 灵体摘除 / 木桩 / 调试生成（闪退排查用）
    safe_mode: bool,
    /// 掉队保底：全体克隆体都掉到 `lost_distance` 之外 `lost_seconds` 秒 → 解散重召
    lost_resummon: bool,
    lost_distance: f32,
    lost_seconds: u32,
    /// 每 30 秒自动往日志里打一份状态
    auto_status: bool,
    /// 赐福「战友」二级菜单：运行时往 live EzState 注入（false = 不做注入，
    /// 配合离线 ESD 根列表 fallback，见 tools/switch_menu_mode.ps1）
    nested_menu: bool,
    /// 友伤初始默认值（只在第一次生成 `er_echo_roster.json` 时生效；
    /// 之后以菜单里点的状态为准）
    friendly_fire: bool,
    /// 友伤倍率（0.2 = 造成 20% 伤害；默认 0.2）
    friendly_fire_rate: f32,
    /// 战友模式：按当前出战友人数补正敌人生命上限（默认开）
    enemy_hp_scaling: bool,
    /// 1/2/3 名战友对应的敌人生命上限倍率（默认 1.5 / 1.8 / 2.0）
    enemy_hp_rates: Vec<f32>,
    /// 菜单文案语言：auto（跟 Windows 显示语言）/ zh-CN / zh-TW / en / ja /
    /// 自定义代码（配合 er_echo_i18n.ini）
    language: String,
}

fn parse_bool(v: &str) -> bool {
    matches!(v.trim().to_ascii_lowercase().as_str(), "1" | "true" | "yes" | "on")
}

impl Config {
    fn load(path: &std::path::Path) -> Self {
        let mut cfg = Config {
            ipc_addr: "127.0.0.1:7811".into(),
            ipc_token: "change-me".into(),
            follow_distance: 35.0,
            profiles: Vec::new(),
            auto_apply: true,
            apply_stats: false,
            player_damage: true,
            auto_level: true,
            auto_recall: false,
            buddy_rows: Vec::new(),
            buddy_npc: None,
            buddy_think: None,
            buddy_init: None,
            buddy_follow: None,
            buddy_copy_from: Some(20700001),
            summon_anywhere: false,
            stone_range: 0,
            no_spirit_glow: false,
            glow_speffects: spirit::GLOW_SPEFFECTS.to_vec(),
            multi_summon: true,
            summon_trigger: None,
            summon_events: false,
            infinite_fp: true,
            behavior_row: 0,
            think_row: 100000010,
            npc_row: 0,
            teammate_think_rows: vec![100000020, 100000030, 100000040],
            safe_mode: false,
            lost_resummon: false,
            lost_distance: 150.0,
            lost_seconds: 15,
            auto_status: true,
            nested_menu: true,
            friendly_fire: false,
            friendly_fire_rate: 0.2,
            enemy_hp_scaling: true,
            enemy_hp_rates: balance::DEFAULT_RATES.to_vec(),
            // 兜底 `game`（跟随游戏文本语言；拿不到就退 Windows 显示语言），和安装器
            // `INI_TEMPLATE` 一致，见 docs/i18n.md。配置**没读到**时也是这个值 ——
            // 日志会打印 config 路径、loaded / not read 和语言来源。
            language: "game".into(),
        };
        // TODO: 用 ini 解析（或直接读环境变量），MVP 先支持 env：
        if let Ok(v) = std::env::var("ER_ECHO_ADDR") {
            cfg.ipc_addr = v;
        }
        if let Ok(v) = std::env::var("ER_ECHO_TOKEN") {
            cfg.ipc_token = v;
        }
        let read = std::fs::read_to_string(path);
        let read_ok = read.is_ok();
        if let Ok(text) = read {
            for line in text.lines() {
                let line = line.trim();
                if line.is_empty() || line.starts_with([';', '#', '[']) {
                    continue;
                }
                let Some((key, value)) = line.split_once('=') else {
                    continue;
                };
                let value = value.trim();
                match key.trim() {
                    "addr" => cfg.ipc_addr = value.to_string(),
                    "token" => cfg.ipc_token = value.to_string(),
                    "follow_distance" => {
                        if let Ok(d) = value.parse::<f32>() {
                            cfg.follow_distance = d;
                        }
                    }
                    "profiles" => {
                        cfg.profiles = value
                            .split(',')
                            .map(str::trim)
                            .filter(|s| !s.is_empty())
                            .map(str::to_string)
                            .collect();
                    }
                    "auto_apply" => cfg.auto_apply = parse_bool(value),
                    "apply_stats" => cfg.apply_stats = parse_bool(value),
                    "player_damage" => cfg.player_damage = parse_bool(value),
                    "auto_level" => cfg.auto_level = parse_bool(value),
                    "friendly_fire" => cfg.friendly_fire = parse_bool(value),
                    "friendly_fire_rate" => {
                        if let Ok(v) = value.parse::<f32>() {
                            cfg.friendly_fire_rate = v.clamp(0.01, 1.0);
                        }
                    }
                    "enemy_hp_scaling" => cfg.enemy_hp_scaling = parse_bool(value),
                    "enemy_hp_rates" => {
                        let rates: Vec<f32> = value
                            .split(',')
                            .filter_map(|s| s.trim().parse::<f32>().ok())
                            .collect();
                        if !rates.is_empty() {
                            cfg.enemy_hp_rates = rates;
                        }
                    }
                    "auto_recall" => cfg.auto_recall = parse_bool(value),
                    "buddy_rows" => {
                        cfg.buddy_rows = value
                            .split(',')
                            .filter_map(|s| s.trim().parse::<u32>().ok())
                            .collect();
                    }
                    "buddy_npc" => cfg.buddy_npc = value.parse().ok(),
                    "buddy_think" => cfg.buddy_think = value.parse().ok(),
                    "buddy_init" => cfg.buddy_init = value.parse().ok(),
                    "buddy_follow" => cfg.buddy_follow = value.parse().ok(),
                    "buddy_copy_from" => {
                        cfg.buddy_copy_from = value.parse::<u32>().ok().filter(|v| *v != 0);
                    }
                    "summon_anywhere" => cfg.summon_anywhere = parse_bool(value),
                    "stone_range" => {
                        if let Ok(v) = value.parse::<u16>() {
                            cfg.stone_range = v;
                        }
                    }
                    "no_spirit_glow" => cfg.no_spirit_glow = parse_bool(value),
                    "multi_summon" => cfg.multi_summon = parse_bool(value),
                    "summon_trigger" => cfg.summon_trigger = value.parse().ok(),
                    "summon_events" => cfg.summon_events = parse_bool(value),
                    "infinite_fp" => cfg.infinite_fp = parse_bool(value),
                    "behavior_row" => cfg.behavior_row = value.parse().unwrap_or(cfg.behavior_row),
                    "think_row" => cfg.think_row = value.parse().unwrap_or(cfg.think_row),
                    "npc_row" => cfg.npc_row = value.parse().unwrap_or(cfg.npc_row),
                    "teammate_think_rows" => {
                        cfg.teammate_think_rows = value
                            .split(',')
                            .filter_map(|s| s.trim().parse::<u32>().ok())
                            .collect();
                    }
                    "safe_mode" => cfg.safe_mode = parse_bool(value),
                    "lost_resummon" => cfg.lost_resummon = parse_bool(value),
                    "lost_distance" => {
                        if let Ok(d) = value.parse::<f32>() {
                            cfg.lost_distance = d;
                        }
                    }
                    "lost_seconds" => {
                        if let Ok(v) = value.parse::<u32>() {
                            cfg.lost_seconds = v;
                        }
                    }
                    "auto_status" => cfg.auto_status = parse_bool(value),
                    "nested_menu" => cfg.nested_menu = parse_bool(value),
                    "language" => cfg.language = value.to_string(),
                    "glow_speffects" => {
                        let ids: Vec<i32> = value
                            .split(',')
                            .filter_map(|s| s.trim().parse::<i32>().ok())
                            .collect();
                        if !ids.is_empty() {
                            cfg.glow_speffects = ids;
                        }
                    }
                    _ => {}
                }
            }
        }
        let resolved = i18n::configure(&cfg.language);
        log::info!(
            "i18n: language={resolved} (source={}, config {}: {}, language={:?}, override file {}, builtin: {})",
            i18n::source(),
            path.display(),
            if read_ok { "loaded" } else { "not read — defaults" },
            if cfg.language.is_empty() {
                "(unset → auto)"
            } else {
                cfg.language.as_str()
            },
            if i18n::override_path().exists() {
                "loaded"
            } else {
                "absent"
            },
            i18n::BUILTIN_LANGS.join(",")
        );
        cfg
    }
}
