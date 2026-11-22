#!/usr/bin/env python3
"""诊断：谁把 `CSMsgRepository::LookupEntry` 的入口 detour 了？（只读，不写游戏内存）

用法（游戏运行中）：
    python tools/probe_msg_hook.py <pid> <module_base_hex>

module_base 用日志里的 `ezstate: EnterState hook installed at 0x... (rva 0x208be00)` 反推：
    base = 地址 - 0x208be00

输出：入口前 32 字节、E9/FF25 跳转目标、以及镜像里 `call rel32` 指向「原入口 / 跳转目标」
各有多少处 —— 用来决定文字钩子该挂哪儿。
"""

from __future__ import annotations

import ctypes
import struct
import sys

LOOKUP_RVA = 0x2671370
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = ctypes.c_void_p
k32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
k32.ReadProcessMemory.restype = ctypes.c_int
k32.ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.CloseHandle.argtypes = [ctypes.c_void_p]


def read(h, addr: int, n: int) -> bytes:
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got))
    if not ok:
        raise OSError(f"ReadProcessMemory({addr:#x}) failed: {ctypes.get_last_error()}")
    return buf.raw[: got.value]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    pid = int(argv[0])
    base = int(argv[1], 0x10)
    h = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, 0, pid)
    if not h:
        print(f"OpenProcess({pid}) failed: {ctypes.get_last_error()}")
        return 1
    try:
        target = base + LOOKUP_RVA
        head = read(h, target, 32)
        print(f"module base = {base:#x}")
        print(f"LookupEntry = {target:#x} (rva {LOOKUP_RVA:#x})")
        print("head:", " ".join(f"{b:02X}" for b in head))

        dest = None
        if head[0] == 0xE9:
            rel = struct.unpack_from("<i", head, 1)[0]
            dest = (target + 5 + rel) & 0xFFFFFFFFFFFFFFFF
            print(f"E9 rel32 -> {dest:#x}  (rva {dest - base:#x})")
            print("dest head:", " ".join(f"{b:02X}" for b in read(h, dest, 24)))
        elif head[0] == 0xFF and head[1] == 0x25:
            disp = struct.unpack_from("<i", head, 2)[0]
            slot = (target + 6 + disp) & 0xFFFFFFFFFFFFFFFF
            dest = struct.unpack("<Q", read(h, slot, 8))[0]
            print(f"FF25 -> [{slot:#x}] = {dest:#x}")

        # 扫 .text：统计 call rel32 指向「原入口 / 跳转目标」各多少处
        hits_orig = hits_dest = 0
        samples: list[str] = []
        chunk = 8 << 20
        addr = base
        end = base + (256 << 20)          # 上限 256MB，够覆盖 .text
        while addr < end:
            try:
                blob = read(h, addr, chunk)
            except OSError:
                break
            i = 0
            while i + 5 <= len(blob):
                if blob[i] == 0xE8:
                    rel = struct.unpack_from("<i", blob, i + 1)[0]
                    d = (addr + i + 5 + rel) & 0xFFFFFFFFFFFFFFFF
                    if d == target:
                        hits_orig += 1
                    elif dest is not None and d == dest:
                        hits_dest += 1
                        if len(samples) < 5:
                            samples.append(f"{addr + i:#x} -> {d:#x}")
                    i += 5
                    continue
                i += 1
            addr += len(blob)
        print(f"call -> 原入口: {hits_orig}")
        print(f"call -> 跳转目标: {hits_dest}")
        for s in samples:
            print("   ", s)
        return 0
    finally:
        k32.CloseHandle(h)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
