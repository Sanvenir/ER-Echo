#!/usr/bin/env python3
"""Wrap a talkesdbnd BND4 into the KRAK DCX container the game expects.

esdtool's -writebnd writes an uncompressed .talkesdbnd, while the vanilla
file is a DCX with Oodle Kraken.  We reuse the vanilla 76-byte DCX header and
only replace the uncompressed/compressed sizes and the compressed body.
"""

import ctypes
import os
import pathlib
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))  # 源码根 er-echo/（2026-11-21 已搬出游戏目录）
sys.path.insert(0, HERE)
try:
    import gamedir as _gamedir
    _found = _gamedir.game_dir(pathlib.Path(ROOT))
except Exception:  # noqa: BLE001
    _found = None
GAME = str(_found) if _found else os.path.abspath(os.path.join(ROOT, ".."))  # 含 oo2core 的 Game
BND = os.path.join(ROOT, "ui", "out_bnd", "m00_00_00_00.talkesdbnd")
RAW = os.path.join(ROOT, "ui", "talk", "m00_00_00_00.raw.dcx")
OUT = os.path.join(ROOT, "ui", "out_bnd", "m00_00_00_00.talkesdbnd.dcx")


def oodle_compress(data: bytes) -> bytes:
    dll = ctypes.WinDLL(os.path.join(GAME, "oo2core_6_win64.dll"))
    dll.OodleLZ_GetCompressedBufferSizeNeeded.restype = ctypes.c_uint
    dll.OodleLZ_GetCompressedBufferSizeNeeded.argtypes = [ctypes.c_longlong]
    dll.OodleLZ_Compress.restype = ctypes.c_longlong
    dll.OodleLZ_Compress.argtypes = [
        ctypes.c_uint,  # compressor: Kraken = 8
        ctypes.c_char_p,
        ctypes.c_longlong,
        ctypes.c_char_p,
        ctypes.c_uint,  # level: Normal = 4
        ctypes.c_longlong,
        ctypes.c_longlong,
        ctypes.c_longlong,
        ctypes.c_void_p,
        ctypes.c_longlong,
    ]
    needed = dll.OodleLZ_GetCompressedBufferSizeNeeded(len(data))
    out = ctypes.create_string_buffer(needed + 64)
    got = dll.OodleLZ_Compress(8, data, len(data), out, 4, 0, 0, 0, None, 0)
    if got <= 0 or got > needed:
        raise OSError(f"OodleLZ_Compress failed: {got}")
    return out.raw[:got]


def oodle_decompress(data: bytes, raw_size: int) -> bytes:
    dll = ctypes.WinDLL(os.path.join(GAME, "oo2core_6_win64.dll"))
    dll.OodleLZ_Decompress.restype = ctypes.c_longlong
    dll.OodleLZ_Decompress.argtypes = [
        ctypes.c_char_p,
        ctypes.c_longlong,
        ctypes.c_char_p,
        ctypes.c_longlong,
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.c_ulonglong,
        ctypes.c_void_p,
        ctypes.c_longlong,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_longlong,
        ctypes.c_uint,
    ]
    out = ctypes.create_string_buffer(raw_size)
    got = dll.OodleLZ_Decompress(data, len(data), out, raw_size, 0, 0, 0, None, 0, None, None, None, 0, 3)
    if got != raw_size:
        raise OSError(f"OodleLZ_Decompress failed: {got} != {raw_size}")
    return out.raw


def main() -> int:
    global BND, OUT
    # 可选：--bnd/--out 指向别的构建目录（vanilla / 根列表 fallback 各留一份）。
    argv = sys.argv[1:]
    if "--bnd" in argv:
        BND = os.path.abspath(argv[argv.index("--bnd") + 1])
    if "--out" in argv:
        OUT = os.path.abspath(argv[argv.index("--out") + 1])
    with open(BND, "rb") as f:
        bnd = f.read()
    with open(RAW, "rb") as f:
        original = f.read()
    header = bytearray(original[:76])
    if header[:4] != b"DCX\0":
        raise ValueError("RAW is not a DCX file")
    comp = oodle_compress(bnd)
    struct.pack_into(">i", header, 28, len(bnd))
    struct.pack_into(">i", header, 32, len(comp))
    out = bytes(header) + comp
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as f:
        f.write(out)
    # sanity check
    check = oodle_decompress(comp, len(bnd))
    if check != bnd:
        raise ValueError("roundtrip mismatch")
    print(f"{OUT}: bnd={len(bnd)} comp={len(comp)} total={len(out)} roundtrip=ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
