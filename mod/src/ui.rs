//! 原生赐福菜单的文本 + 一次性消息钩子。
//!
//! ESD 菜单里的文字 ID（69100000..）在游戏里并不存在；这里挂 `CSMsgRepository`
//! 的查找函数，命中这些 ID 时返回我们自己生成的 UTF-16 字符串（队伍人数 / 档案名）。
//!
//! 钩子位置很讲究：目标函数是 `(this, bnd, msg, lang) -> *const u16` 的叶子函数，
//! 开头 15 字节是两次边界检查：
//!   cmp edx, [rcx+0x10] ; jae fail
//!   cmp r8d, [rcx+0x14] ; jae fail
//!   mov rax, [rcx+8]
//! 我们的 ID 比原版 FMG 的条目大，若在检查之后挂钩会被 `jae fail` 直接挡掉，
//! 所以必须从函数第一条指令接住。整段入口没有栈帧/push，复制 15 字节即可；
//! 两条 `jae` 都跳到 `+0x2e`（xor eax,eax; ret），在 trampoline 的 +0x2e 放
//! 一个绝对跳转就能保持原语义。
//!
//! ## 入口被别的 mod 占用时（Convergence）
//!
//! `ErdTools.dll` / `ertransmogrify.dll` 之类会把 `LookupEntry` 的入口改成
//! `E9 rel32`（jump 到它们自己的 detour），此时入口前 15 字节已不是原版指令，
//! 不能直接 inline hook。兜底做法：扫描 eldenring.exe 镜像里所有
//! `call rel32 -> LookupEntry` 的调用点，把那条 `E8` 换成 `E8 -> 我们的 detour`，
//! 5 字节一一对应、语义不变；detour 里没有命中我们的 ID 时再 `call` 回原函数
//! （原函数自己的 detour 照样生效）。日志会打印 `mode=call-site`。

use std::ffi::c_void;
use std::ptr;
use std::sync::atomic::{AtomicBool, AtomicPtr, AtomicU16, AtomicU8, AtomicUsize, Ordering};

use crate::i18n;

const BASE_ID: u32 = 69100000;
const ID_COUNT: usize = 256;
const MSGBND_EVENT_TEXT_FOR_TALK: u32 = 33;

/// `event_text_for_talk` 的查找函数 AOB（1.17.2 实测；函数入口在匹配点 -9）。
const LOOKUP_AOB: &[u8] = &[
    0x8B, 0xDA, 0x44, 0x8B, 0xCA, 0x33, 0xD2, 0x48, 0x8B, 0xF9, 0x44, 0x8D, 0x42, 0x6F,
];

static TEXT_PTRS: [AtomicPtr<u16>; ID_COUNT] =
    [const { AtomicPtr::new(ptr::null_mut()) }; ID_COUNT];
static HOOKED: AtomicBool = AtomicBool::new(false);
static TRAMPOLINE: AtomicUsize = AtomicUsize::new(0);
static TARGET: AtomicUsize = AtomicUsize::new(0);
/// 入口被别的 mod detour（首字节 `E9`/`FF 25`）时改用「给调用点打补丁」：
/// 这里存被调函数的真实地址，detour 里直接 call 它。
static CALL_ORIG: AtomicUsize = AtomicUsize::new(0);
/// 0 = 没装，1 = 入口 inline hook，2 = 调用点补丁，3 = 接替别人的入口 detour（链式）
static HOOK_MODE: AtomicU8 = AtomicU8::new(0);
/// 重入保护：链式模式下如果把「别的 mod 的 handler」call 回来又转进我们自己，直接放弃。
static DEPTH: AtomicUsize = AtomicUsize::new(0);
/// 靠近游戏镜像的 trampoline 地址（跳板：`jmp qword ptr [rip+0]` 到我们的 detour）。
static STUB: AtomicUsize = AtomicUsize::new(0);
static LAST_BND: AtomicU16 = AtomicU16::new(0);

#[link(name = "kernel32")]
unsafe extern "system" {
    fn GetModuleHandleA(name: *const u8) -> *mut c_void;
    fn VirtualProtect(addr: *mut c_void, size: usize, new_protect: u32, old: *mut u32) -> i32;
    fn VirtualAlloc(addr: *mut c_void, size: usize, alloc_type: u32, protect: u32) -> *mut c_void;
    fn FlushInstructionCache(process: *mut c_void, addr: *const c_void, size: usize) -> i32;
    fn GetCurrentProcess() -> *mut c_void;
}

const MEM_COMMIT: u32 = 0x1000;
const MEM_RESERVE: u32 = 0x2000;
const PAGE_EXECUTE_READWRITE: u32 = 0x40;

type LookupFn =
    unsafe extern "system" fn(*mut c_void, u32, u32, u32) -> *const u16;

fn set_text(id: u32, text: &str) {
    let idx = id.wrapping_sub(BASE_ID) as usize;
    if idx >= ID_COUNT {
        return;
    }
    let mut utf16: Vec<u16> = text.encode_utf16().collect();
    utf16.push(0);
    let leaked: &'static mut [u16] = Box::leak(utf16.into_boxed_slice());
    TEXT_PTRS[idx].store(leaked.as_mut_ptr(), Ordering::Release);
}

fn clear_texts() {
    for p in &TEXT_PTRS {
        p.store(ptr::null_mut(), Ordering::Release);
    }
}

fn text_for(msg_id: u32) -> Option<*const u16> {
    let idx = msg_id.wrapping_sub(BASE_ID) as usize;
    if idx >= ID_COUNT {
        return None;
    }
    let p = TEXT_PTRS[idx].load(Ordering::Acquire);
    if p.is_null() {
        None
    } else {
        Some(p as *const u16)
    }
}

/// 用当前名单重建所有菜单文字。名单变化后调用。
pub fn refresh_texts() {
    clear_texts();
    let profiles = crate::clone_profiles();
    let roster = crate::roster::get();
    let n = profiles.len();
    let count = roster.count.min(3) as usize;

    let count_s = count.to_string();
    let n_s = n.to_string();
    set_text(
        BASE_ID,
        &i18n::text("root", &[("count", &count_s), ("n", &n_s)]),
    );
    set_text(
        BASE_ID + 1,
        &i18n::text("count_row", &[("count", &count_s)]),
    );
    for i in 0..3 {
        let name = if n == 0 {
            "—".to_string()
        } else {
            let slot = roster.slots[i];
            if slot < 0 || slot as usize >= n {
                "—".to_string()
            } else {
                profiles[slot as usize].name.clone()
            }
        };
        let index = (i + 1).to_string();
        set_text(
            BASE_ID + 2 + i as u32,
            &i18n::text("slot", &[("i", &index), ("name", &name)]),
        );
    }
    set_text(BASE_ID + 5, &i18n::text("resummon", &[]));
    set_text(
        BASE_ID + 7,
        &i18n::text(
            if crate::friendly_fire_enabled() {
                "friendly_fire_on"
            } else {
                "friendly_fire_off"
            },
            &[("rate", &format!("{:.0}", crate::friendly_fire_rate() * 100.0))],
        ),
    );
    set_text(BASE_ID + 6, &i18n::text("back", &[]));
    // 二级菜单入口 + 三级菜单「队友 AI」的三个号位（显示该号位档案自己的 AI 预设）。
    set_text(BASE_ID + 8, &i18n::text("ai_menu", &[]));
    let mut ai_labels = Vec::with_capacity(3);
    for i in 0..3 {
        let slot = roster.slots[i];
        let (name, preset_key) = if slot < 0 || slot as usize >= n {
            ("—".to_string(), "ai_default")
        } else {
            let p = &profiles[slot as usize];
            (
                p.name.clone(),
                p.ai.map(|a| a.label_key()).unwrap_or("ai_default"),
            )
        };
        let preset = i18n::text(preset_key, &[]);
        ai_labels.push(preset.clone());
        set_text(
            BASE_ID + 20 + i as u32,
            &i18n::text(
                "ai_slot",
                &[
                    ("i", &(i + 1).to_string()),
                    ("name", &name),
                    ("preset", &preset),
                ],
            ),
        );
    }
    for i in 0..4u32 {
        let label = if i == 0 {
            i18n::text("count_none", &[])
        } else {
            i18n::text("count_n", &[("count", &i.to_string())])
        };
        set_text(BASE_ID + 10 + i, &label);
    }
    for (i, p) in profiles.iter().take(16).enumerate() {
        set_text(
            BASE_ID + 100 + i as u32,
            &i18n::text(
                "profile",
                &[("name", &p.name), ("level", &p.level.to_string())],
            ),
        );
    }
    log::info!(
        "ui: menu texts rebuilt (lang={}, profiles={n}, count={count}, slots={:?}, ai={:?}, friendly_fire={})",
        i18n::current(),
        roster.slots,
        ai_labels,
        crate::friendly_fire_enabled()
    );
}

unsafe extern "system" fn lookup_detour(
    this: *mut c_void,
    lang: u32,
    bnd: u32,
    msg: u32,
) -> *const u16 {
    // 参数顺序是 (this, language, bnd, msg)：rdx 是语言/表索引，r8 是 bundle，
    // r9 是 msg。transmog 的 `get_message(repository, unknown, bnd_id, msg_id)`
    // 也是这个顺序；`unknown` 实际是语言索引（0 = 当前语言）。
    LAST_BND.store(bnd as u16, Ordering::Relaxed);
    // 链式模式下「call 回别人的 handler」有可能再转回我们，别递归
    let depth = DEPTH.fetch_add(1, Ordering::AcqRel);
    if depth > 0 {
        DEPTH.fetch_sub(1, Ordering::AcqRel);
        return ptr::null();
    }
    let result = if bnd == MSGBND_EVENT_TEXT_FOR_TALK {
        text_for(msg).filter(|p| !p.is_null())
    } else {
        None
    };
    let out = if let Some(p) = result {
        p
    } else {
        let tramp = TRAMPOLINE.load(Ordering::Acquire);
        if tramp != 0 {
            let f: LookupFn = std::mem::transmute(tramp);
            f(this, lang, bnd, msg)
        } else {
            let orig = CALL_ORIG.load(Ordering::Acquire);
            if orig != 0 {
                let f: LookupFn = std::mem::transmute(orig);
                f(this, lang, bnd, msg)
            } else {
                ptr::null()
            }
        }
    };
    DEPTH.fetch_sub(1, Ordering::AcqRel);
    out
}

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

fn find_pattern(hay: &[u8], pat: &[u8]) -> Option<usize> {
    if pat.is_empty() || hay.len() < pat.len() {
        return None;
    }
    hay.windows(pat.len()).position(|w| w == pat)
}

/// 读入口处的跳转，返回它的真实目标（别人的 detour / IAT 桩都认）。
///
/// Convergence 里 `LookupEntry` 的入口是 `E9 rel32` → 一个 `FF 25 [rip+0]` 桩 → 别的
/// mod 的 DLL（`0x7FFCA…`）。我们的 DLL 也被加载到 `0x7FFC…`，离游戏镜像 `0x7FF6…`
/// 超过 ±2GB，所以**相对 call/jmp 都够不着**，必须借一块近处的跳板。
unsafe fn resolve_jump(target: usize) -> Option<usize> {
    let p = target as *const u8;
    let b0 = *p;
    if b0 == 0xE9 {
        let rel = *((target + 1) as *const i32);
        return Some((target + 5).wrapping_add(rel as isize as usize));
    }
    if b0 == 0xFF && *p.add(1) == 0x25 {
        let disp = *((target + 2) as *const i32);
        let slot = (target + 6).wrapping_add(disp as isize as usize) as *const usize;
        return Some(*slot);
    }
    None
}

/// 在 `base` 附近（±~1.5GB，64KB 粒度）申请一页可执行内存，写成跳板：
/// `FF 25 00 00 00 00` + `<u64 dest>`（`jmp qword ptr [rip+0]`，共 14 字节）。
unsafe fn alloc_stub_near(base: usize, dest: usize) -> Option<usize> {
    if let 0 = STUB.load(Ordering::Acquire) {
        let mut delta: usize = 0x1_0000;
        let limit: usize = 0x6000_0000; // ~1.5GB 内找
        while delta < limit {
            for cand in [base.wrapping_sub(delta), base.wrapping_add(delta)] {
                let p = VirtualAlloc(cand as *mut c_void, 0x1000,
                                     MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
                if p.is_null() {
                    continue;
                }
                let stub = p as usize;
                // 距离必须塞得进 rel32（给 1.9GB 留余量）
                let far = (stub as isize - base as isize).unsigned_abs();
                if far > 0x7000_0000 {
                    continue;
                }
                let mut code = [0u8; 14];
                code[0] = 0xFF;
                code[1] = 0x25;
                code[6..14].copy_from_slice(&(dest as u64).to_le_bytes());
                ptr::copy_nonoverlapping(code.as_ptr(), p as *mut u8, 14);
                FlushInstructionCache(GetCurrentProcess(), p as *const c_void, 14);
                STUB.store(stub, Ordering::Release);
                log::info!("ui: stub allocated at {stub:#x} (jmp -> {dest:#x})");
                return Some(stub);
            }
            delta += 0x1_0000;
        }
        log::warn!("ui: no free page near image for stub (tried ±1.5GB)");
        return None;
    }
    Some(STUB.load(Ordering::Acquire))
}

/// 把 `target` 开头的 5 字节换成 `E9 rel32 -> stub`，抢下别人的 detour。
unsafe fn patch_entry_jump(target: usize, stub: usize) -> bool {
    let rel = stub as isize - (target as isize + 5);
    if rel < i32::MIN as isize || rel > i32::MAX as isize {
        log::warn!("ui: stub {stub:#x} too far from entry {target:#x}");
        return false;
    }
    if *(target as *const u8) != 0xE9 {
        return false;
    }
    let mut patch = [0u8; 5];
    patch[0] = 0xE9;
    patch[1..5].copy_from_slice(&(rel as i32).to_le_bytes());
    let mut old = 0u32;
    if VirtualProtect(target as *mut c_void, 5, PAGE_EXECUTE_READWRITE, &mut old) == 0 {
        log::warn!("ui: VirtualProtect(entry) failed");
        return false;
    }
    ptr::copy_nonoverlapping(patch.as_ptr(), target as *mut u8, 5);
    VirtualProtect(target as *mut c_void, 5, old, &mut old);
    FlushInstructionCache(GetCurrentProcess(), target as *const c_void, 5);
    true
}

/// 把游戏镜像里所有「直呼 `target` 的 `call rel32`」改成 `call 我们的 detour`。
///
/// 只扫 eldenring.exe 自己的镜像：别的 mod 的 detour 代码在它们自己的 DLL 里，
/// 不会被误伤，也就不会出现「我们的 detour 又被它们 call 回来」的递归。
/// 我们的 detour 离镜像超过 ±2GB 时，改指向近处的 stub。
unsafe fn patch_call_sites(image: &[u8], base: usize, target: usize) -> usize {
    let detour = lookup_detour as *const () as usize;
    let mut sites: Vec<usize> = Vec::new();
    let mut i = 0usize;
    while i + 5 <= image.len() {
        if image[i] == 0xE8 {
            let rel = i32::from_le_bytes([image[i + 1], image[i + 2], image[i + 3], image[i + 4]]);
            let dest = ((base + i + 5) as isize).wrapping_add(rel as isize) as usize;
            if dest == target {
                sites.push(i);
                i += 5;
                continue;
            }
        }
        i += 1;
    }
    if sites.is_empty() {
        return 0;
    }
    let near = (detour as isize - base as isize).unsigned_abs() <= 0x7000_0000;
    let dest = if near {
        detour
    } else {
        match alloc_stub_near(base, detour) {
            Some(s) => s,
            None => return 0,
        }
    };

    let mut patched = 0usize;
    for off in sites {
        let site = base + off;
        let new_rel = dest as isize - (site as isize + 5);
        if new_rel < i32::MIN as isize || new_rel > i32::MAX as isize {
            continue;
        }
        let mut patch = [0u8; 5];
        patch[0] = 0xE8;
        patch[1..5].copy_from_slice(&(new_rel as i32).to_le_bytes());
        let mut old = 0u32;
        if VirtualProtect(site as *mut c_void, 5, PAGE_EXECUTE_READWRITE, &mut old) == 0 {
            continue;
        }
        ptr::copy_nonoverlapping(patch.as_ptr(), site as *mut u8, 5);
        VirtualProtect(site as *mut c_void, 5, old, &mut old);
        FlushInstructionCache(GetCurrentProcess(), site as *const c_void, 5);
        patched += 1;
    }
    patched
}

/// 安装消息钩子。返回目标地址（失败返回 None）。
pub unsafe fn install_msg_hook() -> Option<usize> {
    if HOOKED.load(Ordering::Acquire) {
        return Some(TARGET.load(Ordering::Acquire));
    }
    let module = GetModuleHandleA(b"eldenring.exe\0".as_ptr());
    if module.is_null() {
        log::warn!("ui: GetModuleHandleA(eldenring.exe) failed");
        return None;
    }
    let base = module as *mut u8;
    let size = image_size(base)?;
    let image = std::slice::from_raw_parts(base, size);
    let Some(pat_off) = find_pattern(image, LOOKUP_AOB) else {
        log::warn!("ui: message lookup AOB not found (game version changed?)");
        return None;
    };
    // AOB 在 thunk 的 `lea r8d,[rdx+0x6f]` 处；+14 是 call rel32，目标才是 LookupEntry。
    let match_addr = base as usize + pat_off;
    let call_addr = match_addr + 14;
    let rel = *((call_addr + 1) as *const i32);
    let target = (call_addr + 5).wrapping_add(rel as isize as usize);
    let entry = target as *const u8;
    let head = std::slice::from_raw_parts(entry, 15);
    if head[0] != 0x3B || head[1] != 0x51 || head[2] != 0x10 || head[5] != 0x44 {
        log::warn!(
            "ui: LookupEntry prologue mismatch at {target:#x}: {}",
            head.iter().map(|b| format!("{b:02X}")).collect::<Vec<_>>().join(" ")
        );
        // 入口已经被别的 mod detour 掉了（Convergence 里 ErdTools/ertransmogrify 就会，
        // 首字节变成 `E9 rel32`）。入口没法安全接管，但游戏自己的 `call rel32` 还是干净的：
        // 把所有直呼 LookupEntry 的 call 改成 call 我们的 detour，逻辑等价、只占 5 字节。
        let n = patch_call_sites(image, base as usize, target);
        if n == 0 {
            // 再试「接替别人的 detour」：入口 5 字节本来就已经是 `E9`，把它改指到近处
            // 跳板（跳板再绝对跳到我们的 detour），然后把原来的目标当作"原函数"链下去。
            if let Some(handler) = resolve_jump(target) {
                if let Some(stub) = alloc_stub_near(base as usize, lookup_detour as *const () as usize) {
                    if patch_entry_jump(target, stub) {
                        CALL_ORIG.store(handler, Ordering::Release);
                        HOOK_MODE.store(3, Ordering::Release);
                        TARGET.store(target, Ordering::Release);
                        HOOKED.store(true, Ordering::Release);
                        log::info!(
                            "ui: message hook installed by taking over existing detour \\
                             (entry {target:#x} -> stub {stub:#x}, chained to {handler:#x})"
                        );
                        return Some(target);
                    }
                }
            }
            log::warn!("ui: could not hook LookupEntry; menu texts will show EventTextForTalk");
            return None;
        }
        CALL_ORIG.store(target, Ordering::Release);
        HOOK_MODE.store(2, Ordering::Release);
        TARGET.store(target, Ordering::Release);
        HOOKED.store(true, Ordering::Release);
        log::info!(
            "ui: message hook installed via call-site patch ({n} call(s) -> detour, orig={target:#x})"
        );
        return Some(target);
    }

    // trampoline: 复制入口 15 字节；fallthrough -> target+15；
    // 两条 jae 的目标都是 target+0x2e，把 trampoline 的 +0x2e 也接到那里。
    let tramp = VirtualAlloc(
        ptr::null_mut(),
        0x1000,
        MEM_COMMIT | MEM_RESERVE,
        PAGE_EXECUTE_READWRITE,
    ) as *mut u8;
    if tramp.is_null() {
        log::warn!("ui: VirtualAlloc(trampoline) failed");
        return None;
    }
    let mut code = vec![0u8; 0x1000];
    code[..15].copy_from_slice(head);
    let abs_jmp = |dst: usize| -> Vec<u8> {
        let mut v = vec![0xFF, 0x25, 0, 0, 0, 0];
        v.extend_from_slice(&(dst as u64).to_le_bytes());
        v
    };
    code[0x0f..0x0f + 14].copy_from_slice(&abs_jmp(target + 15));
    code[0x2e..0x2e + 14].copy_from_slice(&abs_jmp(target + 0x2e));
    ptr::copy_nonoverlapping(code.as_ptr(), tramp, 0x40);

    // 入口：14 字节绝对跳转 + 1 NOP（共 15 字节，正好覆盖入口 5 条指令）。
    let mut patch = abs_jmp(lookup_detour as *const () as usize);
    patch.push(0x90);
    let mut old = 0u32;
    if VirtualProtect(entry as *mut c_void, 15, PAGE_EXECUTE_READWRITE, &mut old) == 0 {
        log::warn!("ui: VirtualProtect(LookupEntry) failed");
        return None;
    }
    ptr::copy_nonoverlapping(patch.as_ptr(), entry as *mut u8, 15);
    VirtualProtect(entry as *mut c_void, 15, old, &mut old);
    FlushInstructionCache(GetCurrentProcess(), entry as *const c_void, 15);

    TRAMPOLINE.store(tramp as usize, Ordering::Release);
    TARGET.store(target, Ordering::Release);
    HOOKED.store(true, Ordering::Release);
    log::info!(
        "ui: message hook installed at {target:#x} (rva {:#x}, thunk {match_addr:#x})",
        target - base as usize
    );
    Some(target)
}

/// `MsgRepository` 单例指针的 AOB（transmog 同款；`??` 用 0 通配）。
const MSG_REPO_AOB: &[u8] = &[
    0x48, 0x8B, 0x3D, 0, 0, 0, 0, 0x44, 0x0F, 0xB6, 0x30, 0x48, 0x85, 0xFF, 0x75,
];

fn find_mask(hay: &[u8], pat: &[u8]) -> Option<usize> {
    if pat.is_empty() || hay.len() < pat.len() {
        return None;
    }
    'outer: for i in 0..=hay.len() - pat.len() {
        for (j, &p) in pat.iter().enumerate() {
            if p != 0 && hay[i + j] != p {
                continue 'outer;
            }
        }
        return Some(i);
    }
    None
}

/// 直接调用（已挂钩的）消息查找函数，用来验证钩子和自定义文本。
///
/// 不需要打开任何菜单：拿 `MsgRepository` 单例，用 bnd 33 + 我们的 ID 调一次。
pub unsafe fn test_lookup(msg_id: u32) -> Result<String, String> {
    let module = GetModuleHandleA(b"eldenring.exe\0".as_ptr());
    if module.is_null() {
        return Err("no module".into());
    }
    let base = module as *mut u8;
    let size = image_size(base).ok_or("no image size")?;
    let image = std::slice::from_raw_parts(base, size);
    let off = find_mask(image, MSG_REPO_AOB).ok_or("MsgRepository AOB not found")?;
    let match_addr = base as usize + off;
    let rel = *((match_addr + 3) as *const i32);
    let ptr_addr = (match_addr + 7).wrapping_add(rel as isize as usize);
    let repo = *(ptr_addr as *const usize);
    if repo == 0 {
        return Err("MsgRepository is null (still loading?)".into());
    }
    let target = TARGET.load(Ordering::Acquire);
    if target == 0 {
        return Err("message hook not installed".into());
    }
    let f: LookupFn = std::mem::transmute(target);
    let p = f(repo as *mut c_void, 0, MSGBND_EVENT_TEXT_FOR_TALK, msg_id);
    if p.is_null() {
        return Ok("<null>".into());
    }
    let mut len = 0usize;
    while len < 512 && *p.add(len) != 0 {
        len += 1;
    }
    Ok(String::from_utf16_lossy(std::slice::from_raw_parts(p, len)))
}

/// 诊断：钩子是否生效、装法（入口 / 调用点）、最近一次 bnd id。
pub fn hook_status() -> String {
    let mode = match HOOK_MODE.load(Ordering::Acquire) {
        1 => "entry",
        2 => "call-site",
        3 => "entry-chain",
        _ => "none",
    };
    format!(
        "msg_hook={} mode={mode} target={:#x} last_bnd={}",
        HOOKED.load(Ordering::Acquire),
        TARGET.load(Ordering::Acquire),
        LAST_BND.load(Ordering::Relaxed)
    )
}
