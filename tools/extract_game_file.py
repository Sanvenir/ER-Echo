#!/usr/bin/env python3
"""Extract a single file from an Elden Ring Data*.bhd/Data*.bdt pair.

We only need a handful of small files (talk ESDs, message bundles) for the
in-game UI work, so unpacking the whole 40 GB with UXM is overkill.

BHD5 layout (Elden Ring variant, from BinderTool):
  char[4] "BHD5"; i32 version; i32 unknown; i32 size;
  i32 bucket_dir_count; i32 bucket_dir_offset; i32 salt_len; char[salt_len] salt;
  bucket_dir_count * (i32 entry_count; i32 bucket_offset)   # offsets absolute
  each bucket: entry_count * 40-byte entry:
      u64 name_hash; u32 padded_size; u32 file_size; i64 data_offset;
      i64 salted_hash_offset; i64 aes_key_offset

File name hash: start at 0, for each lowercase char: h = h * 133 + ord(c).
The hashable path includes the leading slash, e.g.
  /script/talk/m00_00_00_00.talkesdbnd.dcx

Usage:
  python extract_game_file.py list
  python extract_game_file.py extract /script/talk/m00_00_00_00.talkesdbnd.dcx out.bin
  python extract_game_file.py dump-hash /path/to/foo
"""

import base64
import ctypes
import os
import struct
import sys
import zlib

GAME_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ARCHIVES = ["Data0", "Data1", "Data2", "Data3", "DLC"]

# RSA "public" keys from BinderTool (they actually carry the decryption
# exponent; the BHD is encrypted block-wise with the matching private key).
ER_BHD_KEYS = {
    "Data0": """MIIBCwKCAQEA9Rju2whruXDVQZpfylVEPeNxm7XgMHcDyaaRUIpXQE0qEo+6Y36L
P0xpFvL0H0kKxHwpuISsdgrnMHJ/yj4S61MWzhO8y4BQbw/zJehhDSRCecFJmFBz
3I2JC5FCjoK+82xd9xM5XXdfsdBzRiSghuIHL4qk2WZ/0f/nK5VygeWXn/oLeYBL
jX1S8wSSASza64JXjt0bP/i6mpV2SLZqKRxo7x2bIQrR1yHNekSF2jBhZIgcbtMB
xjCywn+7p954wjcfjxB5VWaZ4hGbKhi1bhYPccht4XnGhcUTWO3NmJWslwccjQ4k
sutLq3uRjLMM0IeTkQO6Pv8/R7UNFtdCWwIERzH8IQ==""",
    "Data1": """MIIBCwKCAQEAxaBCHQJrtLJiJNdG9nq3deA9sY4YCZ4dbTOHO+v+YgWRMcE6iK6o
ZIJq+nBMUNBbGPmbRrEjkkH9M7LAypAFOPKC6wMHzqIMBsUMuYffulBuOqtEBD11
CAwfx37rjwJ+/1tnEqtJjYkrK9yyrIN6Y+jy4ftymQtjk83+L89pvMMmkNeZaPON
4O9q5M9PnFoKvK8eY45ZV/Jyk+Pe+xc6+e4h4cx8ML5U2kMM3VDAJush4z/05hS3
/bC4B6K9+7dPwgqZgKx1J7DBtLdHSAgwRPpijPeOjKcAa2BDaNp9Cfon70oC+ZCB
+HkQ7FjJcF7KaHsH5oHvuI7EZAl2XTsLEQIENa/2JQ==""",
    "Data2": """MIIBDAKCAQEA0iDVVQ230RgrkIHJNDgxE7I/2AaH6Li1Eu9mtpfrrfhfoK2e7y4O
WU+lj7AGI4GIgkWpPw8JHaV970Cr6+sTG4Tr5eMQPxrCIH7BJAPCloypxcs2BNfT
GXzm6veUfrGzLIDp7wy24lIA8r9ZwUvpKlN28kxBDGeCbGCkYeSVNuF+R9rN4OAM
RYh0r1Q950xc2qSNloNsjpDoSKoYN0T7u5rnMn/4mtclnWPVRWU940zr1rymv4Jc
3umNf6cT1XqrS1gSaK1JWZfsSeD6Dwk3uvquvfY6YlGRygIlVEMAvKrDRMHylsLt
qqhYkZNXMdy0NXopf1rEHKy9poaHEmJldwIFAP////8=""",
    "Data3": """MIIBCwKCAQEAvRRNBnVq3WknCNHrJRelcEA2v/OzKlQkxZw1yKll0Y2Kn6G9ts94
SfgZYbdFCnIXy5NEuyHRKrxXz5vurjhrcuoYAI2ZUhXPXZJdgHywac/i3S/IY0V/
eDbqepyJWHpP6I565ySqlol1p/BScVjbEsVyvZGtWIXLPDbx4EYFKA5B52uK6Gdz
4qcyVFtVEhNoMvg+EoWnyLD7EUzuB2Khl46CuNictyWrLlIHgpKJr1QD8a0ld0PD
PHDZn03q6QDvZd23UW2d9J+/HeBt52j08+qoBXPwhndZsmPMWngQDaik6FM7EVRQ
etKPi6h5uprVmMAS5wR/jQIVTMpTj/zJdwIEXszeQw==""",
}


def hash_path(path: str) -> int:
    h = 0
    for ch in path.replace("\\", "/").lower():
        h = (h * 133 + ord(ch)) & 0xFFFFFFFFFFFFFFFF
    return h


class Entry:
    __slots__ = ("hash", "padded", "size", "offset", "salted", "aes", "aes_key", "ranges")

    def __init__(self, hash_, padded, size, offset, salted, aes, aes_key=None, ranges=None):
        self.hash = hash_
        self.padded = padded
        self.size = size
        self.offset = offset
        self.salted = salted
        self.aes = aes
        self.aes_key = aes_key
        self.ranges = ranges or []

    def __repr__(self):
        return f"Entry(size={self.size}, offset=0x{self.offset:x}, aes={self.aes})"


def aes_ecb_decrypt(data: bytes, key: bytes) -> bytes:
    """AES-128-ECB decrypt through Windows CNG (no external Python deps)."""
    import ctypes
    from ctypes import wintypes

    bcrypt = ctypes.WinDLL("bcrypt.dll")
    bcrypt.BCryptOpenAlgorithmProvider.argtypes = [
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.ULONG,
    ]
    bcrypt.BCryptOpenAlgorithmProvider.restype = ctypes.c_long
    bcrypt.BCryptSetProperty.argtypes = [
        ctypes.c_void_p,
        wintypes.LPCWSTR,
        ctypes.c_char_p,
        wintypes.ULONG,
        wintypes.ULONG,
    ]
    bcrypt.BCryptSetProperty.restype = ctypes.c_long
    bcrypt.BCryptGenerateSymmetricKey.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_void_p,
        wintypes.ULONG,
        ctypes.c_char_p,
        wintypes.ULONG,
        wintypes.ULONG,
    ]
    bcrypt.BCryptGenerateSymmetricKey.restype = ctypes.c_long
    bcrypt.BCryptDecrypt.argtypes = [
        ctypes.c_void_p,
        ctypes.c_char_p,
        wintypes.ULONG,
        ctypes.c_void_p,
        ctypes.c_char_p,
        wintypes.ULONG,
        ctypes.c_char_p,
        wintypes.ULONG,
        ctypes.POINTER(wintypes.ULONG),
        wintypes.ULONG,
    ]
    bcrypt.BCryptDecrypt.restype = ctypes.c_long

    alg = ctypes.c_void_p()
    key_handle = ctypes.c_void_p()
    status = bcrypt.BCryptOpenAlgorithmProvider(
        ctypes.byref(alg), "AES", None, 0
    )
    if status != 0:
        raise OSError(f"BCryptOpenAlgorithmProvider: {status:#x}")
    try:
        mode = "ChainingModeECB".encode("utf-16-le") + b"\0\0"
        status = bcrypt.BCryptSetProperty(
            alg, "ChainingMode", mode, len(mode), 0
        )
        if status != 0:
            raise OSError(f"BCryptSetProperty: {status:#x}")
        status = bcrypt.BCryptGenerateSymmetricKey(
            alg, ctypes.byref(key_handle), None, 0, key, len(key), 0
        )
        if status != 0:
            raise OSError(f"BCryptGenerateSymmetricKey: {status:#x}")
        out = ctypes.create_string_buffer(len(data))
        out_len = wintypes.ULONG()
        status = bcrypt.BCryptDecrypt(
            key_handle,
            data,
            len(data),
            None,
            None,
            0,
            out,
            len(data),
            ctypes.byref(out_len),
            0,
        )
        if status != 0:
            raise OSError(f"BCryptDecrypt: {status:#x}")
        return out.raw[: out_len.value]
    finally:
        if key_handle:
            bcrypt.BCryptDestroyKey(key_handle)
        bcrypt.BCryptCloseAlgorithmProvider(alg, 0)


def _read_der_tlv(data, pos):
    tag = data[pos]
    length = data[pos + 1]
    pos += 2
    if length & 0x80:
        n = length & 0x7F
        length = int.from_bytes(data[pos : pos + n], "big")
        pos += n
    return tag, data[pos : pos + length], pos + length


def _rsa_public_key(b64):
    """Return (n, exponent) from a PKCS#1 RSAPublicKey PEM body."""
    der = base64.b64decode(b64)
    _tag, seq, _end = _read_der_tlv(der, 0)
    _tag, n_bytes, pos = _read_der_tlv(seq, 0)
    _tag, e_bytes, _ = _read_der_tlv(seq, pos)
    return int.from_bytes(n_bytes, "big"), int.from_bytes(e_bytes, "big")


def decrypt_bhd(data: bytes, archive: str) -> bytes:
    """Decrypt an Elden Ring .bhd.

    The archive is split into 256-byte RSA blocks; each block decrypts to a
    255-byte data chunk preceded by a single zero byte.  The final block is
    zero-padded, so we trim to the size stored in the header.
    """
    key = ER_BHD_KEYS.get(archive)
    if not key:
        raise ValueError(f"no BHD key for {archive}")
    n, e = _rsa_public_key(key)
    out = bytearray()
    for pos in range(0, len(data), 256):
        block = data[pos : pos + 256]
        if len(block) < 256:
            block = block + b"\0" * (256 - len(block))
        m = pow(int.from_bytes(block, "big"), e, n)
        out += m.to_bytes(256, "big")[1:]
    size = struct.unpack_from("<i", out, 12)[0]
    if size > len(out):
        raise ValueError(f"{archive}.bhd: bad size {size} > {len(out)}")
    return bytes(out[:size])


def read_bhd(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] != b"BHD5":
        archive = os.path.splitext(os.path.basename(path))[0]
        data = decrypt_bhd(data, archive)
    if data[:4] != b"BHD5":
        raise ValueError(f"{path}: not BHD5 after decryption")
    (version, _unknown, _size, bucket_count, bucket_offset, salt_len) = struct.unpack_from(
        "<6i", data, 4
    )
    buckets = []
    pos = bucket_offset
    for _ in range(bucket_count):
        count, off = struct.unpack_from("<ii", data, pos)
        pos += 8
        entries = []
        p = off
        for _ in range(count):
            h, padded, size, offset, salted, aes = struct.unpack_from("<QIIqqq", data, p)
            p += 40
            aes_key = None
            ranges = []
            if aes:
                try:
                    aes_key = data[aes : aes + 16]
                    range_count = struct.unpack_from("<i", data, aes + 16)[0]
                    for k in range(range_count):
                        start, end = struct.unpack_from("<qq", data, aes + 20 + k * 16)
                        ranges.append((start, end))
                except struct.error:
                    aes_key = None
                    ranges = []
            entries.append(Entry(h, padded, size or padded, offset, salted, aes, aes_key, ranges))
        buckets.append(entries)
    return version, buckets


def all_entries():
    for name in ARCHIVES:
        bhd = os.path.join(GAME_DIR, name + ".bhd")
        if not os.path.exists(bhd):
            continue
        try:
            _version, buckets = read_bhd(bhd)
        except Exception as exc:
            print(f"skip {name}: {exc}", file=sys.stderr)
            continue
        for bucket in buckets:
            for e in bucket:
                yield name, e


def decompress_dcx(data: bytes) -> bytes:
    if data[:4] != b"DCX\0":
        return data
    # Common header: 4 sig, 4 unk, 4 header_size (BE), 12 unk
    header_size = struct.unpack_from(">i", data, 8)[0]
    assert header_size == 24, header_size
    # DCS header: sig, uncompressed size, compressed size
    assert data[24:28] == b"DCS\0"
    uncompressed = struct.unpack_from(">i", data, 28)[0]
    compressed = struct.unpack_from(">i", data, 32)[0]
    # DCP header
    assert data[36:40] == b"DCP\0"
    kind = data[40:44]
    # compression-specific header is 24 bytes for KRAK/DFLT (header size + level + 16)
    # then DCA\0 + i32 8
    body_at = 76
    body = data[body_at : body_at + compressed]
    if kind == b"DFLT":
        out = zlib.decompress(body)
    elif kind == b"KRAK":
        out = oodle_decompress(body, uncompressed)
    else:
        raise ValueError(f"unsupported DCX compression {kind!r}")
    if len(out) != uncompressed:
        raise ValueError(f"DCX size mismatch: got {len(out)}, want {uncompressed}")
    return out


def oodle_decompress(data: bytes, raw_size: int) -> bytes:
    dll_path = os.path.join(GAME_DIR, "oo2core_6_win64.dll")
    if not os.path.exists(dll_path):
        raise FileNotFoundError(dll_path)
    oodle = ctypes.WinDLL(dll_path)
    fn = oodle.OodleLZ_Decompress
    fn.restype = ctypes.c_longlong
    fn.argtypes = [
        ctypes.c_char_p,
        ctypes.c_longlong,
        ctypes.c_char_p,
        ctypes.c_longlong,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_longlong,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_longlong,
        ctypes.c_int,
    ]
    out = ctypes.create_string_buffer(raw_size)
    got = fn(data, len(data), out, raw_size, 0, 0, 0, None, 0, None, None, None, 0, 0)
    if got != raw_size:
        raise ValueError(f"Oodle decompress failed: got {got}, want {raw_size}")
    return out.raw


def read_entry(archive_name: str, entry: Entry) -> bytes:
    bdt = os.path.join(GAME_DIR, archive_name + ".bdt")
    with open(bdt, "rb") as f:
        f.seek(entry.offset)
        raw = bytearray(f.read(entry.padded if entry.size == 0 else entry.size))
    if entry.aes_key:
        for start, end in entry.ranges:
            if start < 0 or end < 0 or end <= start:
                continue
            chunk = bytes(raw[start:end])
            padded_len = (len(chunk) + 15) & ~15
            if padded_len != len(chunk):
                chunk += b"\0" * (padded_len - len(chunk))
            plain = aes_ecb_decrypt(chunk, entry.aes_key)
            raw[start:end] = plain[: end - start]
    return bytes(raw)


def cmd_extract(path: str, out_path: str, raw_mode: bool = False) -> int:
    h = hash_path(path)
    for archive_name, entry in all_entries():
        if entry.hash == h:
            raw = read_entry(archive_name, entry)
            data = raw if raw_mode else decompress_dcx(raw)
            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(data)
            print(
                f"{archive_name}: hash={h:#018x} stored={len(raw)} -> {len(data)} bytes -> {out_path}"
            )
            return 0
    print(f"not found: {path} (hash={h:#018x})")
    return 1


def cmd_list() -> int:
    total = 0
    for name in ARCHIVES:
        bhd = os.path.join(GAME_DIR, name + ".bhd")
        if not os.path.exists(bhd):
            continue
        _version, buckets = read_bhd(bhd)
        count = sum(len(b) for b in buckets)
        total += count
        print(f"{name}: {count} entries, {len(buckets)} buckets")
    print(f"total: {total}")
    return 0


def cmd_find_size(size: int) -> int:
    for archive_name, entry in all_entries():
        if entry.size == size:
            print(f"{archive_name} {entry.hash:#018x} {entry}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    cmd = sys.argv[1]
    if cmd == "list":
        sys.exit(cmd_list())
    if cmd == "extract":
        sys.exit(cmd_extract(sys.argv[2], sys.argv[3], False))
    if cmd == "extract-raw":
        sys.exit(cmd_extract(sys.argv[2], sys.argv[3], True))
    if cmd == "hash":
        print(hex(hash_path(sys.argv[2])))
        sys.exit(0)
    if cmd == "find-size":
        sys.exit(cmd_find_size(int(sys.argv[2])))
    print(__doc__)
    sys.exit(2)
