//! 运行时 EzState 注入：给赐福 talk machine 加一个「战友」二级菜单。
//!
//! ## 为什么不能离线改 ESD
//!
//! 用 ESDLANG 重新编译 `t000001000` 做「列表 → 列表」时，菜单事件会被塞进
//! `Unused` 状态，实测要么空菜单要么立刻返回一级（见 docs/handoff-submenu.md §3）。
//! 参考 mod（elden-ring-transmog / erdGameTools）都是**不改 ESD 文件**，而是在
//! `EzState::EnterState` 里往 live state group 追加 `AddTalkListData` 事件和
//! 指向自定义 state 的 transition。这里把那条路移植到 Rust。
//!
//! ## 结构布局（来自 elden-x `ezstate.hpp`，1.17.2 实测可用）
//!
//! ```text
//! machine       : vtable, unk[0x20], state_group*, ...
//! state_group   : id, span<state> states, state* initial_state
//! state         : id, span<transition*> transitions,
//!                 span<event> entry_events, exit_events, while_events
//! transition    : state* target, span<event> pass_events,
//!                 span<transition*> sub_transitions, span<u8> evaluator
//! event         : {bank,id}, span<span<u8>> args
//! ```
//!
//! `span<T>` 就是 `{ T* ptr; size_t len; }`，所以 Rust 里用 `#[repr(C)]` 的
//! `SpanMut<T> { ptr, len }` 一一对应。
//!
//! ## 注入内容
//!
//! 1. 从 initial_state 做 BFS，找到根列表里**第一个加菜单项**的 state（x31/state 2），
//!    把 `AddTalkListData(60, 69100000, -1)` 插到它 entry_events 开头 → 菜单第一项
//!    「战友（n/m）」（赐福时间行是引擎自己加的，排在它前面）；
//! 2. 在根列表的结果分支 state 的 transitions 里插
//!    `GetTalkListEntryResult() == 60 → 二级菜单 state`；
//! 3. 二级菜单 state：`CloseShopMessage / ClearTalkListData / 8×AddTalkListData /
//!    ShowShopMessage(Regular)`，菜单关闭后进 branch state；
//! 4. branch state：按 `GetTalkListEntryResult()` 分到 7 个 callback state
//!    （`SetEventFlag 6728/6724/6725/6726/6727/6729`，DLL 每帧轮询）、
//!    「队友 AI」→ 三级菜单 state、或「返回」→ 根菜单循环入口 state
//!    （BFS 父链上最近的 `ClearTalkListData` state；跳 initial_state 不会重开菜单）；
//! 5. 三级「队友 AI」state：`CloseShopMessage / ClearTalkListData / 3×AddTalkListData /
//!    ShowShopMessage(Regular)`；branch 按结果去 3 个 `SetEventFlag 6730..6732`
//!    （每个号位一个）或「返回」→ 二级菜单 state（会重新跑它的 entry events，
//!    所以文字刷新后回到的仍是「战友」菜单）；
//! 6. callback state 置完标志后等 0.25 秒（`GetCurrentStateElapsedTime()`）再回
//!    二级/三级菜单——DLL 要先改 roster/AI、重建文字，否则菜单会用旧文本建列表；
//!    文字由 `ui.rs` 的消息钩子动态返回。
//!
//! 注入失败时**什么都不改**：游戏退回原版赐福菜单。ini `[ui] nested_menu=false`
//! 可以整体关掉注入，改用离线 ESD 根列表版本（见 tools/switch_menu_mode.ps1）。

use std::ffi::c_void;
use std::ptr;
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

use crate::roster;

// ---------------------------------------------------------------------------
// 常量
// ---------------------------------------------------------------------------

/// 赐福「整理木箱」的文本 ID：原版赐福根菜单里一定有这一项，用它认 state group。
const SORT_CHEST_MSG: i32 = 15000395;

/// 根菜单里「战友」项的 slot / 文本 ID。
const ROOT_SLOT: i32 = 60;
const ROOT_MSG: i32 = 69100000;

/// 二级菜单文本 ID（ui.rs `refresh_texts` 提供）。
const MSG_COUNT: i32 = 69100001;
const MSG_SLOT0: i32 = 69100002;
const MSG_SLOT1: i32 = 69100003;
const MSG_SLOT2: i32 = 69100004;
const MSG_RESUMMON: i32 = 69100005;
const MSG_BACK: i32 = 69100006;
const MSG_FRIENDLY: i32 = 69100007;
/// 二级菜单里的「队友 AI（点击进入）」。
const MSG_AI_MENU: i32 = 69100008;
/// 三级菜单「队友 AI」的三个号位。
const MSG_AI_SLOT0: i32 = 69100020;
const MSG_AI_SLOT1: i32 = 69100021;
const MSG_AI_SLOT2: i32 = 69100022;
/// 三级菜单的「返回」：回二级菜单（不是回赐福根列表）。
const MSG_AI_BACK: i32 = 69100006;

/// `EzState::EnterState` 的调用点 AOB（1.16.1/1.17.2 同形；`??` 用 mask 表示）。
/// 形状：`cmp byte [rsi+0x18],0; jz +0x15; lea r8,[rsp+0x40]; mov rdx,rsi;
///        mov rcx,[rsi+0x20]; call EzState::EnterState`
const ENTER_STATE_CALL: &[u8] = &[
    0x80, 0x7E, 0x18, 0x00, // cmp byte ptr [rsi+0x18], 0
    0x74, 0x15, // jz +0x15
    0x4C, 0x8D, 0x44, 0x24, 0x40, // lea r8, [rsp+0x40]
    0x48, 0x8B, 0xD6, // mov rdx, rsi
    0x48, 0x8B, 0x4E, 0x20, // mov rcx, [rsi+0x20]
    0xE8, 0xFF, 0xFF, 0xFF, 0xFF, // call rel32（4 字节通配）
];

/// 上面 AOB 里每个字节是否参与比较（false = 通配）。
const ENTER_STATE_MASK: &[bool] = &[
    true, true, true, true, true, true, true, true, true, true, true, true, true, true, true, true,
    true, true, true, false, false, false, false,
];

/// 1.17.2 `EzState::EnterState` 入口 15 字节（要原样搬进 trampoline）。
const ENTER_STATE_PROLOGUE: [u8; 15] = [
    0x48, 0x8B, 0xC4, // mov rax, rsp
    0x57, // push rdi
    0x41, 0x56, // push r14
    0x41, 0x57, // push r15
    0x48, 0x81, 0xEC, 0x20, 0x04, 0x00, 0x00, // sub rsp, 0x420
];

// ESD 表达式字节（逐字节抄 elden-ring-transmog 的 talkscript_utils.hpp）

/// `true`
const EXPR_TRUE: &[u8] = &[0x41, 0xA1];

/// `not (CheckSpecificPersonMenuIsOpen(1,0) == 1 and CheckSpecificPersonGenericDialogIsOpen(0) == 0)`
/// —— 通用 talk 菜单关闭判断。
const EXPR_MENU_CLOSED: &[u8] = &[
    0x7B, 0x41, 0x40, 0x86, 0x41, 0x95, // CheckSpecificPersonMenuIsOpen(1, 0) == 1
    0x7A, 0x40, 0x85, 0x40, 0x95, // CheckSpecificPersonGenericDialogIsOpen(0) == 0
    0x98, // &&
    0x40, 0x95, // == 0
    0xA1,
];

// ---------------------------------------------------------------------------
// 原生结构
// ---------------------------------------------------------------------------

#[repr(C)]
#[derive(Clone, Copy)]
struct Command {
    bank: i32,
    id: i32,
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct Expression {
    ptr: *const u8,
    len: usize,
}

/// 对应 C++ `std::span<T>`：`{ T* ptr; size_t len; }`。
#[repr(C)]
pub struct SpanMut<T> {
    ptr: *mut T,
    len: usize,
}

// 手写 Clone/Copy：derive 会给 T 加上 Copy/Clone 约束，而 State/Event 不满足。
impl<T> Clone for SpanMut<T> {
    fn clone(&self) -> Self {
        *self
    }
}

impl<T> Copy for SpanMut<T> {}

impl<T> SpanMut<T> {
    fn empty() -> Self {
        Self {
            ptr: ptr::null_mut(),
            len: 0,
        }
    }

    unsafe fn as_slice<'a>(&self) -> &'a [T] {
        if self.ptr.is_null() || self.len == 0 {
            &[]
        } else {
            std::slice::from_raw_parts(self.ptr, self.len)
        }
    }
}

#[repr(C)]
#[derive(Clone, Copy)]
pub struct Event {
    command: Command,
    args: SpanMut<Expression>,
}

#[repr(C)]
pub struct Transition {
    target_state: *mut State,
    pass_events: SpanMut<Event>,
    sub_transitions: SpanMut<*mut Transition>,
    evaluator: Expression,
}

#[repr(C)]
pub struct State {
    id: i32,
    transitions: SpanMut<*mut Transition>,
    entry_events: SpanMut<Event>,
    exit_events: SpanMut<Event>,
    while_events: SpanMut<Event>,
}

#[repr(C)]
pub struct StateGroup {
    id: i32,
    states: SpanMut<State>,
    initial_state: *mut State,
}

impl StateGroup {
    fn x_number(&self) -> i32 {
        0x7FFF_FFFFi32.wrapping_sub(self.id)
    }
}

// 常用命令（bank/id，见 elden-x `talk_commands.hpp`）
const CMD_SHOW_SHOP_MESSAGE: Command = Command { bank: 1, id: 10 };
const CMD_SET_EVENT_FLAG: Command = Command { bank: 1, id: 11 };
const CMD_CLOSE_SHOP_MESSAGE: Command = Command { bank: 1, id: 12 };
const CMD_ADD_TALK_LIST_DATA: Command = Command { bank: 1, id: 19 };
const CMD_CLEAR_TALK_LIST_DATA: Command = Command { bank: 1, id: 20 };
const CMD_OPEN_REPOSITORY: Command = Command { bank: 1, id: 30 };
const CMD_ADD_TALK_LIST_DATA_IF: Command = Command { bank: 5, id: 19 };
const CMD_ADD_TALK_LIST_DATA_ALT: Command = Command { bank: 5, id: 149 };

// ---------------------------------------------------------------------------
// 全局状态
// ---------------------------------------------------------------------------

static HOOKED: AtomicBool = AtomicBool::new(false);
static ENABLED: AtomicBool = AtomicBool::new(false);
static TARGET: AtomicUsize = AtomicUsize::new(0);
static TRAMPOLINE: AtomicUsize = AtomicUsize::new(0);
static INJECT: AtomicUsize = AtomicUsize::new(0);
static PATCHED_GROUP: AtomicUsize = AtomicUsize::new(0);
static PATCHED_INITIAL: AtomicUsize = AtomicUsize::new(0);
static GROUP_OFFSET: AtomicUsize = AtomicUsize::new(usize::MAX);
/// 首次在 `machine+0x28` 验证到合法 state_group 后置真；
/// 之后热路径直接裸读指针，不再每帧做 VirtualQuery（提示类 talk machine
/// 每秒会进很多次 EnterState，VirtualQuery 会拖出可见卡顿）。
static LAYOUT_OK: AtomicBool = AtomicBool::new(false);
static SLOW_LOGS: AtomicUsize = AtomicUsize::new(0);
/// 负缓存：同一个非赐福 group 只做一次 `group_is_grace`。
static LAST_GROUP: AtomicUsize = AtomicUsize::new(0);
static LAST_GROUP_IS_GRACE: AtomicBool = AtomicBool::new(false);
static PATCH_COUNT: AtomicUsize = AtomicUsize::new(0);
static DUMP_REQUESTED: AtomicBool = AtomicBool::new(false);
static LAST_ERROR: AtomicUsize = AtomicUsize::new(0);
static SCAN_LOGGED: AtomicBool = AtomicBool::new(false);
/// 性能计数（每 300 帧被 lib.rs 取走一次并清零）。
static DETOUR_CALLS: AtomicUsize = AtomicUsize::new(0);
static DETOUR_MICROS: AtomicUsize = AtomicUsize::new(0);

// ---------------------------------------------------------------------------
// Win32
// ---------------------------------------------------------------------------

#[link(name = "kernel32")]
unsafe extern "system" {
    fn GetModuleHandleA(name: *const u8) -> *mut c_void;
    fn VirtualProtect(addr: *mut c_void, size: usize, new_protect: u32, old: *mut u32) -> i32;
    fn VirtualAlloc(addr: *mut c_void, size: usize, alloc_type: u32, protect: u32) -> *mut c_void;
    fn VirtualQuery(
        addr: *const c_void,
        info: *mut MemoryBasicInformation,
        len: usize,
    ) -> usize;
    fn FlushInstructionCache(process: *mut c_void, addr: *const c_void, size: usize) -> i32;
    fn GetCurrentProcess() -> *mut c_void;
}

#[repr(C)]
struct MemoryBasicInformation {
    base_address: *mut c_void,
    allocation_base: *mut c_void,
    allocation_protect: u32,
    partition_id: u16,
    _pad: u16,
    region_size: usize,
    state: u32,
    protect: u32,
    type_: u32,
}

const MEM_COMMIT: u32 = 0x1000;
const MEM_RESERVE: u32 = 0x2000;
const PAGE_NOACCESS: u32 = 0x01;
const PAGE_GUARD: u32 = 0x100;
const PAGE_EXECUTE_READWRITE: u32 = 0x40;

/// 一段内存是否可读（逐 region 用 VirtualQuery 验证，避免盲读坏指针崩游戏）。
fn memory_readable(addr: usize, size: usize) -> bool {
    if addr == 0 || size == 0 {
        return false;
    }
    let end = match addr.checked_add(size) {
        Some(v) => v,
        None => return false,
    };
    let mut cur = addr;
    let mut guard = 0;
    while cur < end {
        guard += 1;
        if guard > 4096 {
            return false;
        }
        let mut info = MemoryBasicInformation {
            base_address: ptr::null_mut(),
            allocation_base: ptr::null_mut(),
            allocation_protect: 0,
            partition_id: 0,
            _pad: 0,
            region_size: 0,
            state: 0,
            protect: 0,
            type_: 0,
        };
        let rc = unsafe {
            VirtualQuery(
                cur as *const c_void,
                &mut info,
                std::mem::size_of::<MemoryBasicInformation>(),
            )
        };
        if rc == 0 || info.state != MEM_COMMIT {
            return false;
        }
        if info.protect & (PAGE_NOACCESS | PAGE_GUARD) != 0 {
            return false;
        }
        let base = info.base_address as usize;
        let region_end = match base.checked_add(info.region_size) {
            Some(v) => v,
            None => return false,
        };
        if region_end <= cur {
            return false;
        }
        cur = region_end;
    }
    true
}

unsafe fn read_ptr(addr: usize) -> usize {
    if !memory_readable(addr, 8) {
        return 0;
    }
    ptr::read_unaligned(addr as *const usize)
}

// ---------------------------------------------------------------------------
// 表达式 / 事件构造（全部 Box::leak，活到进程结束）
// ---------------------------------------------------------------------------

fn leak_slice<T>(values: Vec<T>) -> &'static mut [T] {
    Box::leak(values.into_boxed_slice())
}

fn expr_bytes(bytes: &[u8]) -> Expression {
    let leaked = leak_slice(bytes.to_vec());
    Expression {
        ptr: leaked.as_mut_ptr(),
        len: leaked.len(),
    }
}

/// 4 字节整数常量：`0x82 <i32 LE> 0xA1`。
fn int_expr(value: i32) -> Expression {
    let b = value.to_le_bytes();
    expr_bytes(&[0x82, b[0], b[1], b[2], b[3], 0xA1])
}

/// `GetTalkListEntryResult() == value`：`0x57 (23) 0x84 <int> 0x95 0xA1`。
fn talk_result_expr(value: i32) -> Expression {
    let b = value.to_le_bytes();
    expr_bytes(&[
        0x57, 0x84, 0x82, b[0], b[1], b[2], b[3], 0x95, 0xA1,
    ])
}

/// callback state 的放行条件：`GetCurrentStateElapsedTime() > 0.25`。
///
/// ESD 置标志和 DLL 轮询不在同一帧：如果 callback 立刻回二级菜单，菜单会用**旧文本**
/// 建列表（实测「人数 2→3」后菜单仍显示 2）。等 0.25 秒（约 15 帧）再回，
/// `poll_roster_flags()` 已经把 roster 改完并 `refresh_texts()` 过，标签就是新值。
///
/// 早先试过用事件标志 6729 做回执 + `GetEventFlag(6729)==1`，实测 ESD 侧没看见
/// DLL 置的标志（仍然是 2.5 秒超时后才返回），所以改成固定延时——足够且不写存档。
fn callback_ready_expr() -> Expression {
    let mut b: Vec<u8> = Vec::new();
    // GetCurrentStateElapsedTime()：函数 id 103（> 63，用 0x82 + i32 编码）
    b.push(0x82);
    b.extend_from_slice(&103i32.to_le_bytes());
    b.push(0x84); // call 0 args
    b.push(0x80); // float 常量
    b.extend_from_slice(&0.25f32.to_le_bytes());
    b.push(0x94); // >
    b.push(0xA1);
    expr_bytes(&b)
}

fn args_of(values: Vec<Expression>) -> SpanMut<Expression> {
    let leaked = leak_slice(values);
    SpanMut {
        ptr: leaked.as_mut_ptr(),
        len: leaked.len(),
    }
}

fn event(command: Command, values: Vec<Expression>) -> Event {
    Event {
        command,
        args: args_of(values),
    }
}

fn events_of(values: Vec<Event>) -> SpanMut<Event> {
    let leaked = leak_slice(values);
    SpanMut {
        ptr: leaked.as_mut_ptr(),
        len: leaked.len(),
    }
}

fn transition(target: *mut State, evaluator: Expression) -> *mut Transition {
    Box::leak(Box::new(Transition {
        target_state: target,
        pass_events: SpanMut::empty(),
        sub_transitions: SpanMut::empty(),
        evaluator,
    }))
}

fn transitions_of(values: Vec<*mut Transition>) -> SpanMut<*mut Transition> {
    let leaked = leak_slice(values);
    SpanMut {
        ptr: leaked.as_mut_ptr(),
        len: leaked.len(),
    }
}

fn new_state() -> *mut State {
    Box::leak(Box::new(State {
        id: 0,
        transitions: SpanMut::empty(),
        entry_events: SpanMut::empty(),
        exit_events: SpanMut::empty(),
        while_events: SpanMut::empty(),
    }))
}

fn add_talk(index: i32, message: i32) -> Event {
    event(
        CMD_ADD_TALK_LIST_DATA,
        vec![int_expr(index), int_expr(message), int_expr(-1)],
    )
}

fn set_flag(flag: u32) -> Event {
    set_flag_value(flag, true)
}

fn set_flag_value(flag: u32, on: bool) -> Event {
    event(
        CMD_SET_EVENT_FLAG,
        vec![
            int_expr(flag as i32),
            int_expr(if on { 1 } else { 0 }),
        ],
    )
}

// ---------------------------------------------------------------------------
// 注入对象
// ---------------------------------------------------------------------------

/// 注入时反复用到的指针；`return_transition` 的 target 在 patch 时指向
/// 赐福根菜单的循环入口 state（每个 ESD 实例不同）。
struct Inject {
    menu_state: *mut State,
    ai_menu_state: *mut State,
    root_transition: *mut Transition,
    return_transition: *mut Transition,
}

/// 一个「点一下 → SetEventFlag → 等 DLL 处理 → 回 `back` 菜单」的 callback state。
fn callback_state(flag: u32, back: *mut State) -> *mut State {
    let callback = new_state();
    unsafe {
        (*callback).entry_events = events_of(vec![set_flag(flag)]);
        (*callback).transitions = transitions_of(vec![transition(back, callback_ready_expr())]);
    }
    callback
}

fn build_inject() -> *mut Inject {
    let menu_state = new_state();
    let branch_state = new_state();
    let return_transition = transition(ptr::null_mut(), expr_bytes(EXPR_TRUE));
    let root_transition = transition(menu_state, talk_result_expr(ROOT_SLOT));

    // 三级「队友 AI」菜单：menu_state 的第 5 项进入；它的「返回」回 menu_state。
    let ai_menu_state = new_state();
    let ai_branch_state = new_state();
    let ai_transition = transition(ai_menu_state, talk_result_expr(5));
    let ai_back_transition = transition(menu_state, expr_bytes(EXPR_TRUE));
    let mut ai_option_transitions: Vec<*mut Transition> = Vec::new();
    for (i, flag) in roster::FLAG_AI_SLOT.iter().enumerate() {
        ai_option_transitions.push(transition(
            callback_state(*flag, ai_menu_state),
            talk_result_expr(i as i32 + 1),
        ));
    }
    ai_option_transitions.push(ai_back_transition);
    unsafe {
        (*ai_branch_state).transitions = transitions_of(ai_option_transitions);
        (*ai_menu_state).transitions = transitions_of(vec![transition(
            ai_branch_state,
            expr_bytes(EXPR_MENU_CLOSED),
        )]);
        (*ai_menu_state).entry_events = events_of(vec![
            event(CMD_CLOSE_SHOP_MESSAGE, Vec::new()),
            event(CMD_CLEAR_TALK_LIST_DATA, Vec::new()),
            add_talk(1, MSG_AI_SLOT0),
            add_talk(2, MSG_AI_SLOT1),
            add_talk(3, MSG_AI_SLOT2),
            add_talk(99, MSG_AI_BACK),
            event(CMD_SHOW_SHOP_MESSAGE, vec![int_expr(1)]),
        ]);
    }

    // 6 个 callback state：SetEventFlag(...) → 回二级菜单。
    // 选项下标（AddTalkListData 的 index）必须和这里 push 的顺序一致：
    // 1=人数、2..4=号位、5=队友 AI、6=立即重召、7=友伤、99=返回。
    let mut option_transitions: Vec<*mut Transition> = Vec::new();
    option_transitions.push(transition(
        callback_state(roster::FLAG_COUNT_CYCLE, menu_state),
        talk_result_expr(1),
    ));
    for (i, flag) in roster::FLAG_SLOT.iter().enumerate() {
        option_transitions.push(transition(
            callback_state(*flag, menu_state),
            talk_result_expr(i as i32 + 2),
        ));
    }
    option_transitions.push(ai_transition);
    option_transitions.push(transition(
        callback_state(roster::FLAG_APPLY, menu_state),
        talk_result_expr(6),
    ));
    option_transitions.push(transition(
        callback_state(roster::FLAG_FRIENDLY_FIRE, menu_state),
        talk_result_expr(7),
    ));
    option_transitions.push(return_transition);
    unsafe {
        (*branch_state).transitions = transitions_of(option_transitions);
        (*menu_state).transitions = transitions_of(vec![transition(
            branch_state,
            expr_bytes(EXPR_MENU_CLOSED),
        )]);
        (*menu_state).entry_events = events_of(vec![
            event(CMD_CLOSE_SHOP_MESSAGE, Vec::new()),
            event(CMD_CLEAR_TALK_LIST_DATA, Vec::new()),
            add_talk(1, MSG_COUNT),
            add_talk(2, MSG_SLOT0),
            add_talk(3, MSG_SLOT1),
            add_talk(4, MSG_SLOT2),
            add_talk(5, MSG_AI_MENU),
            add_talk(6, MSG_RESUMMON),
            add_talk(7, MSG_FRIENDLY),
            add_talk(99, MSG_BACK),
            // TalkOptionsType::Regular = 1（原版赐福菜单同款）
            event(CMD_SHOW_SHOP_MESSAGE, vec![int_expr(1)]),
        ]);
    }

    Box::leak(Box::new(Inject {
        menu_state,
        ai_menu_state,
        root_transition,
        return_transition,
    }))
}

// ---------------------------------------------------------------------------
// 扫描 / 校验
// ---------------------------------------------------------------------------

fn image_size(base: *mut u8) -> Option<usize> {
    unsafe {
        if *base != b'M' || *base.add(1) != b'Z' {
            return None;
        }
        let e_lfanew = *(base.add(0x3c) as *const i32) as usize;
        let nt = base.add(e_lfanew);
        if *nt != b'P' || *nt.add(1) != b'E' {
            return None;
        }
        let opt = nt.add(24);
        Some(*(opt.add(0x38) as *const u32) as usize)
    }
}

fn find_pattern(hay: &[u8], pat: &[u8], mask: &[bool]) -> Option<usize> {
    if pat.is_empty() || hay.len() < pat.len() || mask.len() != pat.len() {
        return None;
    }
    'outer: for i in 0..=hay.len() - pat.len() {
        for (j, &b) in pat.iter().enumerate() {
            if mask[j] && hay[i + j] != b {
                continue 'outer;
            }
        }
        return Some(i);
    }
    None
}

unsafe fn arg_int(args: SpanMut<Expression>, index: usize) -> Option<i32> {
    if args.ptr.is_null() || index >= args.len || args.len > 8 {
        return None;
    }
    if !memory_readable(args.ptr as usize, args.len * std::mem::size_of::<Expression>()) {
        return None;
    }
    let e = ptr::read_unaligned(args.ptr.add(index));
    if e.ptr.is_null() || e.len == 0 || e.len > 64 {
        return None;
    }
    if !memory_readable(e.ptr as usize, e.len) {
        return None;
    }
    let bytes = std::slice::from_raw_parts(e.ptr, e.len);
    if bytes.len() == 2 {
        return Some(bytes[0] as i32 - 64);
    }
    if bytes.len() == 6 && bytes[0] == 0x82 {
        return Some(i32::from_le_bytes([
            bytes[1], bytes[2], bytes[3], bytes[4],
        ]));
    }
    None
}

/// `AddTalkListData(...)` 的 textId；bank 5 的两个变体 textId 在 args[2]。
unsafe fn add_talk_message(ev: &Event) -> Option<i32> {
    if ev.command.bank == CMD_ADD_TALK_LIST_DATA.bank
        && ev.command.id == CMD_ADD_TALK_LIST_DATA.id
    {
        if ev.args.len == 3 {
            return arg_int(ev.args, 1);
        }
    } else if ev.command.bank == CMD_ADD_TALK_LIST_DATA_IF.bank
        && (ev.command.id == CMD_ADD_TALK_LIST_DATA_IF.id
            || ev.command.id == CMD_ADD_TALK_LIST_DATA_ALT.id)
    {
        if ev.args.len >= 3 {
            return arg_int(ev.args, 2);
        }
    }
    None
}

unsafe fn is_add_talk(ev: &Event) -> bool {
    (ev.command.bank == CMD_ADD_TALK_LIST_DATA.bank
        && ev.command.id == CMD_ADD_TALK_LIST_DATA.id)
        || (ev.command.bank == CMD_ADD_TALK_LIST_DATA_IF.bank
            && (ev.command.id == CMD_ADD_TALK_LIST_DATA_IF.id
                || ev.command.id == CMD_ADD_TALK_LIST_DATA_ALT.id))
}

/// 校验一个候选 `state_group*`：结构可读、states 数组合理、initial_state 在数组内。
unsafe fn group_is_plausible(group: usize) -> bool {
    if group == 0 || !memory_readable(group, std::mem::size_of::<StateGroup>()) {
        return false;
    }
    let g = &*(group as *const StateGroup);
    let states = g.states;
    if states.ptr.is_null() || states.len == 0 || states.len > 1024 {
        return false;
    }
    let bytes = match states.len.checked_mul(std::mem::size_of::<State>()) {
        Some(v) => v,
        None => return false,
    };
    if !memory_readable(states.ptr as usize, bytes) {
        return false;
    }
    let initial = g.initial_state as usize;
    let start = states.ptr as usize;
    if initial < start || initial >= start + bytes {
        return false;
    }
    true
}

/// 赐福 talk script `t000001000` 的主 state group 名是 `x31`，
/// 即 `id = 0x7fffffff - 31`。先用 id 做 O(1) 判断：非赐福的 talk machine
/// （交互提示等）会在 EnterState 里被频繁进入，逐个 state 扫事件会卡死游戏
/// （2026-11-16 实测：90 次调用烧掉 0.9 秒、单帧 600ms）。
const GRACE_GROUP_ID: i32 = 0x7FFF_FFFFi32.wrapping_sub(31);

/// 赐福 state group：id 必须是 x31，且某个 state 的 entry_events 里有
/// `AddTalkListData(_, 15000395, _)`（「整理木箱」）。
///
/// 先判 id，再做有上限的事件扫描；两道保险都很快。
unsafe fn group_is_grace(group: *mut StateGroup) -> bool {
    if group.is_null() {
        return false;
    }
    let g = &*group;
    // 先比 id（O(1)）：非赐福的 talk machine 会被高频进入，不能再对每个 group
    // 做 memory_readable + states 扫描（那会拖出每帧 ~1ms 的卡顿）。
    if g.id != GRACE_GROUP_ID {
        return false;
    }
    if !group_is_plausible(group as usize) {
        return false;
    }
    let states = g.states;
    if states.len > 512 {
        return false;
    }
    if !memory_readable(states.ptr as usize, states.len * std::mem::size_of::<State>()) {
        return false;
    }
    let mut examined = 0usize;
    for i in 0..states.len {
        let state = &*states.ptr.add(i);
        let list = state.entry_events;
        if list.ptr.is_null() || list.len == 0 || list.len > 64 {
            continue;
        }
        if !memory_readable(
            list.ptr as usize,
            list.len * std::mem::size_of::<Event>(),
        ) {
            continue;
        }
        examined += list.len;
        if examined > 512 {
            return false;
        }
        for ev in std::slice::from_raw_parts(list.ptr, list.len) {
            if let Some(msg) = add_talk_message(ev) {
                if msg == SORT_CHEST_MSG {
                    return true;
                }
            }
        }
    }
    false
}

/// 已知 1.17.2 的 machine 布局：`state_group*` 在 `+0x28`。
const KNOWN_GROUP_OFFSETS: [usize; 1] = [0x28];

unsafe fn read_ptr_raw(addr: usize) -> usize {
    ptr::read_unaligned(addr as *const usize)
}

/// 从 machine 对象里找 `state_group*`。
///
/// 第一次走完整校验（`group_is_plausible`），确认布局后置 `LAYOUT_OK`，
/// 之后热路径只做一次裸指针读 —— 提示类 talk machine 每秒会进很多次
/// `EnterState`，每次 VirtualQuery 会拖出肉眼可见的卡顿。
/// 版本升级后如果 `+0x28` 不再是 state_group，校验会失败并保持 passive。
unsafe fn group_of(machine: *mut u8) -> Option<*mut StateGroup> {
    if machine.is_null() {
        return None;
    }
    let off = GROUP_OFFSET.load(Ordering::Acquire);
    let off = if off == usize::MAX { KNOWN_GROUP_OFFSETS[0] } else { off };
    if LAYOUT_OK.load(Ordering::Acquire) {
        let ptr = read_ptr_raw(machine as usize + off);
        if ptr == 0 {
            return None;
        }
        return Some(ptr as *mut StateGroup);
    }
    let ptr = read_ptr(machine as usize + off);
    if group_is_plausible(ptr) {
        GROUP_OFFSET.store(off, Ordering::Release);
        LAYOUT_OK.store(true, Ordering::Release);
        log::info!(
            "ezstate: machine->state_group at +{off:#x} (group={ptr:#x}, x{})",
            (*(ptr as *const StateGroup)).x_number()
        );
        return Some(ptr as *mut StateGroup);
    }
    if !SCAN_LOGGED.swap(true, Ordering::AcqRel) {
        log::warn!(
            "ezstate: no state_group at machine+{off:#x} ({:#x}) — hook stays passive \
             (game version changed?)",
            machine as usize
        );
    }
    None
}

unsafe fn dump_group(group: *mut StateGroup) {
    let g = &*group;
    let states = g.states;
    log::info!(
        "menu_dump: group={:#x} x{} states={} initial={:#x}",
        group as usize,
        g.x_number(),
        states.len,
        g.initial_state as usize
    );
    for i in 0..states.len.min(256) {
        let state = &*states.ptr.add(i);
        let mut evs = Vec::new();
        if !state.entry_events.ptr.is_null() {
            for ev in state.entry_events.as_slice().iter().take(24) {
                let mut detail = format!("{}/{}", ev.command.bank, ev.command.id);
                for a in 0..ev.args.len.min(4) {
                    if let Some(v) = arg_int(ev.args, a) {
                        detail.push_str(&format!(",{v}"));
                    }
                    // 原始表达式字节（辨认 GetEventFlag 等函数编码用）
                    let ex = ptr::read_unaligned(ev.args.ptr.add(a));
                    if !ex.ptr.is_null() && ex.len > 0 && ex.len <= 64 {
                        if memory_readable(ex.ptr as usize, ex.len) {
                            let raw = std::slice::from_raw_parts(ex.ptr, ex.len);
                            detail.push_str(&format!(
                                "[{}]",
                                raw.iter()
                                    .map(|b| format!("{b:02X}"))
                                    .collect::<Vec<_>>()
                                    .join("")
                            ));
                        }
                    }
                }
                evs.push(detail);
            }
        }
        log::info!(
            "  state[{i}] ptr={:#x} id={} trans={} entry_events=[{}]",
            states.ptr.add(i) as usize,
            state.id,
            state.transitions.len,
            evs.join(" ")
        );
    }
}

// ---------------------------------------------------------------------------
// 注入
// ---------------------------------------------------------------------------

unsafe fn state_has_clear_list(state: &State) -> bool {
    let list = state.entry_events;
    if list.ptr.is_null() || list.len == 0 {
        return false;
    }
    std::slice::from_raw_parts(list.ptr, list.len)
        .iter()
        .any(|ev| {
            ev.command.bank == CMD_CLEAR_TALK_LIST_DATA.bank
                && ev.command.id == CMD_CLEAR_TALK_LIST_DATA.id
        })
}

/// 从初始 state 做 BFS，找赐福根列表里**第一个加菜单项**的 state，以及它的
/// 「清空列表 + 循环入口」祖先 state（「返回」要跳到这里，菜单才会重新长出来）。
///
/// 赐福根菜单不是由单个 state 一次性建好：state 1 只 `ClearTalkListData`，
/// state 2 加头几项（时间/消磨时间…），state 17 再加 4..9 项，最后 state 3
/// `ShowShopMessage`。想让「战友」排在最上面，就必须插到 state 2 的 entry_events
/// 开头，而不是 state 17（那样会排在「圣杯瓶」后面，实测如此）。
unsafe fn find_list_start_state(g: &StateGroup) -> Option<(*mut State, usize, *mut State)> {
    let states = g.states;
    if states.ptr.is_null() || states.len == 0 {
        return None;
    }
    let state_size = std::mem::size_of::<State>();
    let base = states.ptr as usize;
    let initial = g.initial_state as usize;
    if initial < base || initial >= base + states.len * state_size {
        return None;
    }
    let start_idx = (initial - base) / state_size;
    let mut visited = vec![false; states.len];
    let mut parent = vec![usize::MAX; states.len];
    let mut queue = std::collections::VecDeque::new();
    visited[start_idx] = true;
    queue.push_back(start_idx);
    let mut budget = 0usize;
    while let Some(idx) = queue.pop_front() {
        budget += 1;
        if budget > 256 {
            break;
        }
        let state = &*states.ptr.add(idx);
        let list = state.entry_events;
        let mut has_add = false;
        let mut clear_idx = usize::MAX;
        if !list.ptr.is_null() && list.len > 0 {
            for (ei, ev) in std::slice::from_raw_parts(list.ptr, list.len)
                .iter()
                .enumerate()
            {
                if is_add_talk(ev) {
                    has_add = true;
                }
                if ev.command.bank == CMD_CLEAR_TALK_LIST_DATA.bank
                    && ev.command.id == CMD_CLEAR_TALK_LIST_DATA.id
                {
                    clear_idx = ei;
                }
            }
        }
        if has_add {
            let at = if clear_idx != usize::MAX {
                clear_idx + 1
            } else {
                0
            };
            // 沿 BFS 父链找最近的「清空列表」state（= 根菜单循环入口 L0）
            let mut return_state = g.initial_state;
            let mut cur = idx;
            let mut guard = 0usize;
            while cur != usize::MAX && guard < states.len {
                guard += 1;
                let ancestor = &*states.ptr.add(cur);
                if state_has_clear_list(ancestor) {
                    return_state = states.ptr.add(cur);
                    break;
                }
                cur = parent[cur];
            }
            return Some((states.ptr.add(idx), at, return_state));
        }
        let trs = state.transitions;
        if trs.ptr.is_null() || trs.len == 0 {
            continue;
        }
        for &tr in std::slice::from_raw_parts(trs.ptr, trs.len).iter() {
            if tr.is_null() {
                continue;
            }
            let target = (*tr).target_state as usize;
            if target < base || target >= base + states.len * state_size {
                continue;
            }
            let ti = (target - base) / state_size;
            if ti < states.len && !visited[ti] {
                visited[ti] = true;
                parent[ti] = idx;
                queue.push_back(ti);
            }
        }
    }
    None
}

/// 在赐福 group 上打补丁。返回是否成功。
unsafe fn patch_group(group: *mut StateGroup) -> bool {
    let inject_ptr = INJECT.load(Ordering::Acquire);
    if inject_ptr == 0 {
        LAST_ERROR.store(1, Ordering::Release);
        return false;
    }
    let inject = &*(inject_ptr as *const Inject);
    let g = &*group;
    let states = g.states;
    if states.ptr.is_null() || states.len == 0 {
        LAST_ERROR.store(2, Ordering::Release);
        return false;
    }

    let mut result_state: *mut State = ptr::null_mut();
    let mut result_idx = usize::MAX;
    let mut already = false;

    for i in 0..states.len {
        let state_ptr = states.ptr.add(i);
        let state = &*state_ptr;

        // 已经注入过？（同一个 ESD 实例被重复进入时）
        let list = state.entry_events;
        if !list.ptr.is_null() && list.len > 0 {
            for ev in std::slice::from_raw_parts(list.ptr, list.len).iter() {
                if add_talk_message(ev) == Some(ROOT_MSG) {
                    already = true;
                }
            }
        }

        // transitions：找指向 OpenRepository state 的那一条（= 整理木箱的结果分支）
        let trs = state.transitions;
        if !trs.ptr.is_null() && trs.len > 0 && result_state.is_null() {
            for (ti, &tr) in std::slice::from_raw_parts(trs.ptr, trs.len)
                .iter()
                .enumerate()
            {
                if tr.is_null() {
                    continue;
                }
                let target = (*tr).target_state;
                if target.is_null() {
                    continue;
                }
                if !memory_readable(target as usize, std::mem::size_of::<State>()) {
                    continue;
                }
                let entry = (*target).entry_events;
                if entry.ptr.is_null() || entry.len == 0 {
                    continue;
                }
                let first = &*entry.ptr;
                if first.command.bank == CMD_OPEN_REPOSITORY.bank
                    && first.command.id == CMD_OPEN_REPOSITORY.id
                {
                    result_state = state_ptr;
                    result_idx = ti;
                    break;
                }
            }
        }
    }

    if already {
        log::info!("ezstate: grace group already has 战友 item, skip patch");
        return true;
    }

    let Some((add_state, insert_idx, return_state)) = (unsafe { find_list_start_state(g) }) else {
        log::warn!("ezstate: cannot find grace root list start state");
        LAST_ERROR.store(3, Ordering::Release);
        return false;
    };
    if result_state.is_null() {
        log::warn!(
            "ezstate: grace group patch anchors missing (result_state={:#x})",
            result_state as usize
        );
        LAST_ERROR.store(4, Ordering::Release);
        return false;
    }

    // 1) 根列表 entry_events 插入「战友」
    let old_events = (*add_state).entry_events;
    let old_slice = old_events.as_slice();
    let mut new_events: Vec<Event> = old_slice.to_vec();
    let at = insert_idx.min(new_events.len());
    new_events.insert(at, add_talk(ROOT_SLOT, ROOT_MSG));
    let leaked_events = leak_slice(new_events);
    (*add_state).entry_events = SpanMut {
        ptr: leaked_events.as_mut_ptr(),
        len: leaked_events.len(),
    };

    // 2) 结果分支 transitions 插入「result == 60 → 二级菜单」
    let old_trs = (*result_state).transitions;
    let old_tr_slice = old_trs.as_slice();
    let mut new_trs: Vec<*mut Transition> = old_tr_slice.to_vec();
    let at_tr = result_idx.min(new_trs.len());
    new_trs.insert(at_tr, inject.root_transition);
    let leaked_trs = leak_slice(new_trs);
    (*result_state).transitions = SpanMut {
        ptr: leaked_trs.as_mut_ptr(),
        len: leaked_trs.len(),
    };

    // 3) 「返回」回到根菜单循环入口（清空列表那个 state，不是 initial_state：
    //    直接跳 initial_state 不会重新 ShowShopMessage，菜单会消失）
    (*inject.return_transition).target_state = return_state;

    // 4) 「立即重新召唤」之后 DLL 会 dismiss + 重召；菜单留在原地即可。

    PATCHED_GROUP.store(group as usize, Ordering::Release);
    PATCHED_INITIAL.store(g.initial_state as usize, Ordering::Release);
    PATCH_COUNT.fetch_add(1, Ordering::AcqRel);
    log::info!(
        "ezstate: patched grace group x{} ({:#x}): item at state {:#x} (id {}) event[{at}], \
         transition at state {:#x} [{result_idx}], initial={:#x}, return={:#x}, \
         events {} -> {}, transitions {} -> {}",
        g.x_number(),
        group as usize,
        add_state as usize,
        (*add_state).id,
        result_state as usize,
        g.initial_state as usize,
        return_state as usize,
        old_events.len,
        (*add_state).entry_events.len,
        old_trs.len,
        (*result_state).transitions.len
    );
    true
}

unsafe fn on_enter_state(state: *mut State, machine: *mut u8) {
    if state.is_null() || machine.is_null() {
        return;
    }
    // 已注入后直接放行：不再做 VirtualQuery / group 扫描。
    // 正常游戏里 ESD 只加载一次；万一整份重载，用 menu_reset 清掉标记再坐火。
    if PATCHED_GROUP.load(Ordering::Acquire) != 0 {
        return;
    }
    let Some(group) = group_of(machine) else {
        return;
    };
    let g = &*group;
    if DUMP_REQUESTED.swap(false, Ordering::AcqRel) {
        dump_group(group);
    }
    // 调试：二级菜单 state 的进入时间，用来验证 callback 的 0.25 秒延时。
    let inject_ptr = INJECT.load(Ordering::Acquire);
    if inject_ptr != 0 {
        let inject = &*(inject_ptr as *const Inject);
        if state == inject.menu_state {
            log::info!("ezstate: entered menu state");
        }
        if state == inject.ai_menu_state {
            log::info!("ezstate: entered AI menu state");
        }
    }
    // 只在该 group 的初始 state 被进入时打补丁（此时还没开始跑 entry events）。
    if state != g.initial_state {
        return;
    }
    if PATCHED_GROUP.load(Ordering::Acquire) == group as usize
        && PATCHED_INITIAL.load(Ordering::Acquire) == g.initial_state as usize
    {
        return;
    }
    // 负缓存：非赐福 group（NPC 对话 / 交互提示）只检查一次，避免每次 EnterState
    // 都跑一遍 group_is_grace。
    let group_addr = group as usize;
    if LAST_GROUP.load(Ordering::Acquire) == group_addr {
        if !LAST_GROUP_IS_GRACE.load(Ordering::Acquire) {
            return;
        }
    } else {
        let is_grace = group_is_grace(group);
        LAST_GROUP.store(group_addr, Ordering::Release);
        LAST_GROUP_IS_GRACE.store(is_grace, Ordering::Release);
        if !is_grace {
            return;
        }
    }
    if patch_group(group) {
        LAST_ERROR.store(0, Ordering::Release);
    }
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

type EnterStateFn = unsafe extern "system" fn(*mut State, *mut u8, *mut c_void);

unsafe extern "system" fn enter_state_detour(
    state: *mut State,
    machine: *mut u8,
    unk: *mut c_void,
) {
    if ENABLED.load(Ordering::Relaxed) {
        let t = std::time::Instant::now();
        // 钩子里不 panic / 不 unwind：panic 穿过 FFI 会直接 abort 游戏。
        let _ = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| unsafe {
            on_enter_state(state, machine);
        }));
        let dt = t.elapsed();
        DETOUR_CALLS.fetch_add(1, Ordering::Relaxed);
        DETOUR_MICROS.fetch_add(dt.as_micros() as usize, Ordering::Relaxed);
        if dt.as_micros() > 2000 && SLOW_LOGS.fetch_add(1, Ordering::Relaxed) < 8 {
            log::warn!(
                "ezstate: slow EnterState {dt:?} (state={:#x}, machine={:#x})",
                state as usize,
                machine as usize
            );
        }
    }
    let tramp = TRAMPOLINE.load(Ordering::Acquire);
    if tramp != 0 {
        let f: EnterStateFn = std::mem::transmute(tramp);
        f(state, machine, unk);
    }
}

pub fn perf_take() -> (usize, usize) {
    (
        DETOUR_CALLS.swap(0, Ordering::Relaxed),
        DETOUR_MICROS.swap(0, Ordering::Relaxed),
    )
}

/// 安装 `EzState::EnterState` 入口钩子。幂等；失败返回 false（不影响游戏）。
pub unsafe fn install() -> bool {
    if HOOKED.load(Ordering::Acquire) {
        return true;
    }
    let module = GetModuleHandleA(b"eldenring.exe\0".as_ptr());
    if module.is_null() {
        log::warn!("ezstate: GetModuleHandleA(eldenring.exe) failed");
        return false;
    }
    let base = module as *mut u8;
    let Some(size) = image_size(base) else {
        log::warn!("ezstate: cannot read image size");
        return false;
    };
    let image = std::slice::from_raw_parts(base, size);
    let Some(pat_off) = find_pattern(image, ENTER_STATE_CALL, ENTER_STATE_MASK) else {
        log::warn!("ezstate: EnterState call-site AOB not found (game version changed?)");
        return false;
    };
    let match_addr = base as usize + pat_off;
    let call_addr = match_addr + 18;
    let rel = *((call_addr + 1) as *const i32);
    let target = call_addr
        .wrapping_add(5)
        .wrapping_add(rel as isize as usize);
    let entry = target as *const u8;
    let head = std::slice::from_raw_parts(entry, ENTER_STATE_PROLOGUE.len());
    if head != &ENTER_STATE_PROLOGUE[..] {
        log::warn!(
            "ezstate: EnterState prologue mismatch at {target:#x}: {}",
            head.iter()
                .map(|b| format!("{b:02X}"))
                .collect::<Vec<_>>()
                .join(" ")
        );
        return false;
    }

    // trampoline：入口 15 字节 + 跳回 target+15
    let tramp = VirtualAlloc(
        ptr::null_mut(),
        0x1000,
        MEM_COMMIT | MEM_RESERVE,
        PAGE_EXECUTE_READWRITE,
    ) as *mut u8;
    if tramp.is_null() {
        log::warn!("ezstate: VirtualAlloc(trampoline) failed");
        return false;
    }
    let abs_jmp = |dst: usize| -> Vec<u8> {
        let mut v = vec![0xFF, 0x25, 0, 0, 0, 0];
        v.extend_from_slice(&(dst as u64).to_le_bytes());
        v
    };
    let mut code = vec![0u8; 0x1000];
    code[..15].copy_from_slice(&ENTER_STATE_PROLOGUE);
    code[15..15 + 14].copy_from_slice(&abs_jmp(target + 15));
    ptr::copy_nonoverlapping(code.as_ptr(), tramp, 0x40);

    // 入口：14 字节绝对跳转 + 1 NOP（正好 15 字节）
    let mut patch = abs_jmp(enter_state_detour as *const () as usize);
    patch.push(0x90);
    let mut old = 0u32;
    if VirtualProtect(
        entry as *mut c_void,
        15,
        PAGE_EXECUTE_READWRITE,
        &mut old,
    ) == 0
    {
        log::warn!("ezstate: VirtualProtect(EnterState) failed");
        return false;
    }
    ptr::copy_nonoverlapping(patch.as_ptr(), entry as *mut u8, 15);
    VirtualProtect(entry as *mut c_void, 15, old, &mut old);
    FlushInstructionCache(GetCurrentProcess(), entry as *const c_void, 15);

    if INJECT.load(Ordering::Acquire) == 0 {
        INJECT.store(build_inject() as usize, Ordering::Release);
    }
    TARGET.store(target, Ordering::Release);
    TRAMPOLINE.store(tramp as usize, Ordering::Release);
    HOOKED.store(true, Ordering::Release);
    log::info!(
        "ezstate: EnterState hook installed at {target:#x} (rva {:#x}, call site {match_addr:#x})",
        target - base as usize
    );
    true
}

/// 开关注入（ini `[ui] nested_menu`；false 时钩子只做一次原子读就放行）。
pub fn set_enabled(enabled: bool) {
    ENABLED.store(enabled, Ordering::Release);
}

pub fn is_enabled() -> bool {
    ENABLED.load(Ordering::Acquire)
}

pub fn request_dump() {
    DUMP_REQUESTED.store(true, Ordering::Release);
}

/// 让下一次进入赐福初始 state 时重新打补丁（ESD 重载 / 调试用）。
pub fn reset_patch() {
    PATCHED_GROUP.store(0, Ordering::Release);
    PATCHED_INITIAL.store(0, Ordering::Release);
}

pub fn status() -> String {
    format!(
        "ezstate enabled={} hooked={} target={:#x} group_offset={:#x} patched={:#x} initial={:#x} patches={} err={}",
        is_enabled(),
        HOOKED.load(Ordering::Acquire),
        TARGET.load(Ordering::Acquire),
        GROUP_OFFSET.load(Ordering::Acquire),
        PATCHED_GROUP.load(Ordering::Acquire),
        PATCHED_INITIAL.load(Ordering::Acquire),
        PATCH_COUNT.load(Ordering::Acquire),
        LAST_ERROR.load(Ordering::Acquire)
    )
}
