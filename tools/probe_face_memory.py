"""只读探针 v2：在运行中的 ELDENRING.exe 里定位 FaceData / 脸载荷的所有副本。

与 v1 的区别：
  * 先把 eldenring.exe 的模块地址范围取出来，用「vftable 是否落在模块内」区分
    **真 FaceData 结构**和「DLL 里 profile 的 Vec<u8> 副本」；
  * 读失败不再中断整个区域；扫描范围/进度可见；
  * 同时按「纯 payload」搜索，报告每处命中的上下文。
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import pathlib
import struct
import subprocess
import sys

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_GUARD = 0x100
PAGE_NOACCESS = 0x01
TH32CS_SNAPMODULE = 0x00000008


class MBI(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wt.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wt.DWORD),
        ("Protect", wt.DWORD),
        ("Type", wt.DWORD),
    ]


class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wt.DWORD),
        ("th32ModuleID", wt.DWORD),
        ("th32ProcessID", wt.DWORD),
        ("GlblcntUsage", wt.DWORD),
        ("ProccntUsage", wt.DWORD),
        ("modBaseAddr", ctypes.c_void_p),
        ("modBaseSize", wt.DWORD),
        ("hModule", wt.HMODULE),
        ("szModule", wt.CHAR * 256),
        ("szExePath", wt.CHAR * 260),
    ]


def open_proc(pid: int):
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        raise SystemExit(f"OpenProcess({pid}) failed: {ctypes.get_last_error()}")
    k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.POINTER(MBI), ctypes.c_size_t]
    k32.VirtualQueryEx.restype = ctypes.c_size_t
    k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                      ctypes.POINTER(ctypes.c_size_t)]
    k32.ReadProcessMemory.restype = wt.BOOL
    return k32, h


def modules(pid: int):
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid)
    out = []
    if snap == -1:
        return out
    me = MODULEENTRY32()
    me.dwSize = ctypes.sizeof(MODULEENTRY32)
    ok = k32.Module32First(snap, ctypes.byref(me))
    while ok:
        name = me.szModule.decode(errors="ignore")
        out.append((name, me.modBaseAddr or 0, me.modBaseSize or 0))
        ok = k32.Module32Next(snap, ctypes.byref(me))
    k32.CloseHandle(snap)
    return out


def read(k32, h, addr, size):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got)):
        return b""
    return buf.raw[:got.value]


def payloads(profile_dir: pathlib.Path):
    out = []
    dump = profile_dir.parent / "er_echo_profile.json"
    if dump.exists():
        j = json.loads(dump.read_text(encoding="utf-8"))
        out.append((f"player:{j.get('name')}", bytes.fromhex(j["face"]["payload_hex"])))
    for p in sorted(profile_dir.glob("slot*.json")):
        j = json.loads(p.read_text(encoding="utf-8"))
        block = bytes.fromhex(j["face_hex"].strip().removeprefix("0x"))
        if len(block) >= 0x124:
            out.append((f"profile:{j.get('name')}", block[0x10:0x124]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--profile-dir", default=r"D:\Games\Convergence3\ConvergenceER\er-echo\profiles")
    ap.add_argument("--module", default="eldenring.exe")
    args = ap.parse_args()

    pid = args.pid
    if not pid:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq eldenring.exe", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True).stdout
        for line in out.splitlines():
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) > 1 and parts[1].isdigit():
                pid = int(parts[1])
                break
        if not pid:
            raise SystemExit("eldenring.exe not running")

    mods = modules(pid)
    base, size = 0, 0
    for name, b, s in mods:
        if name.lower() == args.module.lower():
            base, size = b, s
            break
    print(f"pid={pid} module={args.module} base=0x{base:x} size=0x{size:x}")
    if not base:
        print("WARN: module not found; vftable check disabled")

    def in_module(v):
        return base <= v < base + size

    k32, h = open_proc(pid)
    wants = payloads(pathlib.Path(args.profile_dir))
    for name, p in wants:
        print(f"  {name:18s} payload[0xA0:0xA8]={p[0xA0:0xA8].hex()}")

    # 结果: (va_of_payload, tag, is_struct, vft, floats, tail)
    hits = []
    scanned = 0
    skipped = 0
    regions = []
    addr = 0
    while addr < 0x7FFFFFFF0000:
        mbi = MBI()
        if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        b = mbi.BaseAddress or 0
        s = mbi.RegionSize
        if s == 0:
            break
        if mbi.State == MEM_COMMIT and (mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS)) == 0:
            if s > 512 * 1024 * 1024:
                skipped += s
            else:
                regions.append((b, s, mbi.Type))
        addr = b + s
    print(f"regions={len(regions)} skipped_big_mb={skipped/1e6:.0f}")

    CHUNK = 4 * 1024 * 1024
    for b, s, t in regions:
        off = 0
        prev_tail = b""
        while off < s:
            n = min(CHUNK, s - off)
            data = read(k32, h, b + off, n)
            if not data:
                off += n
                prev_tail = b""
                continue
            scanned += len(data)
            padded = prev_tail + data
            for name, payload in wants:
                st = 0
                while True:
                    i = padded.find(payload, st)
                    if i < 0:
                        break
                    st = i + 1
                    va_payload = b + off - len(prev_tail) + i
                    hits.append((va_payload, name))
            prev_tail = data[-(0x120):]
            off += n
    print(f"scanned {scanned/1e6:.0f} MB, payload hits={len(hits)}")

    real = []
    for va, name in sorted(set(hits)):
        pre = read(k32, h, va - 0x20, 0x20 + 276 + 0x60)
        if len(pre) < 0x20 + 276:
            continue
        fd = va - 0x14
        vft = struct.unpack_from("<Q", pre, 4)[0]  # pre[0x20-0x14..] = va-0x14
        fd_vft = struct.unpack_from("<Q", pre, 0x20 - 0x14)[0]
        post = pre[0x20 + 276:]
        unk128 = struct.unpack_from("<Q", post, 0)[0] if len(post) >= 8 else 0
        floats = struct.unpack_from("<7f", post, 8) if len(post) >= 36 else ()
        tail = post[0x24:0x48] if len(post) >= 0x48 else b""
        is_struct = in_module(fd_vft) and (pre[4:8] == b"FACE")
        real.append((va, name, is_struct, fd, fd_vft, unk128, floats, tail))
    for va, name, is_struct, fd, vft, unk128, floats, tail in real:
        mark = "STRUCT" if is_struct else "copy  "
        print(f"  {mark} payload=0x{va:x} {name:18s} FaceData=0x{fd:x} vft=0x{vft:x} unk128=0x{unk128:x}")
        if floats:
            print(f"         unk130 f32[7] = " + " ".join(f"{f:.6f}" for f in floats))
        print(f"         unk14c[0x24]  = {tail.hex()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
