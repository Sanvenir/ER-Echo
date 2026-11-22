#!/usr/bin/env python3
"""从 `.sl2` **离线**导出角色档案（profile.json）——不需要进游戏、不需要切号。

原理（见 docs/design.md §7）：
  .sl2 是明文 BND4（PC 版未加密），12 个 entry；前 10 个是角色槽 `USER_DATA000..009`。
  每个槽 = 0x10 MD5 + 0x280000 数据，数据里含：
    * PlayerGameData：8 维属性（+0x34）、等级（+0x60）、卢恩、角色名（+0x94）…
    * ChrAsm 装备表（22 槽）+ FaceData（0x12F 自描述块，magic=FACE，size=0x120）

之所以能「不切号」：这些数据只是文件里的字节，跟当前登录的存档槽无关。
导出的 profile 直接给 er_echo.dll 用（见 docs/usage.md）。

用法：
  python tools/export_profile_from_save.py --list
  python tools/export_profile_from_save.py --save "C:\\...\\ER0000.sl2" --list
  python tools/export_profile_from_save.py --slot 2 -o tools/profile.slot2.json
  python tools/export_profile_from_save.py --all -d tools/from_save/   # 导出所有可解析角色

退出码：0 = 至少导出一个；2 = 没有可解析角色；1 = 文件/参数错误。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

SLOT_SIZE = 0x280010
FACE_SIZE = 0x12F
FACE_DATA_SIZE = 0x120  # magic(4)+ver(4)+size(4)+276
SLOT_COUNT = 22
STAT_KEYS = ["vigor", "mind", "endurance", "strength",
             "dexterity", "intelligence", "faith", "arcane"]
DEFAULT_SAVE_DIR = pathlib.Path.home() / "AppData" / "Roaming" / "EldenRing"


# ------------------------------------------------------------------ BND4

def parse_bnd4(path: pathlib.Path) -> list[tuple[str, bytes]]:
    """返回 [(entry_name, data_bytes)]，只含 user data。"""
    b = path.read_bytes()
    if b[:4] != b"BND4":
        raise SystemExit(f"not a BND4 file: {path} (magic={b[:4]!r})")
    count = struct.unpack_from("<i", b, 0x0C)[0]
    entries = []
    for i in range(count):
        e = 0x40 + i * 0x20
        _flags, _unk, size, offset, name_off, _pad = struct.unpack_from("<IIQIIQ", b, e)
        name = b[name_off:name_off + 0x40].decode("utf-16le", "ignore").split("\x00")[0]
        entries.append((name, b[offset:offset + size]))
    return entries


# ------------------------------------------------------------------ helpers

def u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def i32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<i", buf, off)[0]


def read_name(buf: bytes, off: int) -> str:
    raw = buf[off:off + 0x20]
    try:
        name = raw.decode("utf-16le").split("\x00")[0]
    except UnicodeDecodeError:
        return ""
    if not name or any(ord(c) < 32 for c in name):
        return ""
    return name


def find_pgd(data: bytes) -> dict | None:
    """定位 PlayerGameData：8 属性 + 等级 + 角色名。

    校验用 ER 的硬约束：`level == sum(stats) - 79`（所有出身成立：初始属性总和 = 等级 + 79）。
    这个约束能把绝大多数「一串小整数」的误报排除掉。
    """
    n = len(data) - 0x300
    for x in range(0, n):
        stats = struct.unpack_from("<8I", data, x)
        if any(v < 1 or v > 99 for v in stats):
            continue
        level = sum(stats) - 79
        if level < 1 or level > 713:
            continue
        if u32(data, x + 0x2C) != level:
            continue
        name = read_name(data, x + 0x60)
        if not name:
            continue
        base = x - 0x34
        # 存档里的 PGD 在属性前存了 3 组「当前/上限/基础」：
        #   +0x08 hp, +0x14 fp, +0x24 stamina（+0x20/+0x30 是保留位，实测恒 0）
        # 这几个值 = 引擎算好的派生值，离线直接读比按属性表重算更准。
        pools = {
            "hp": u32(data, base + 0x0C),
            "fp": u32(data, base + 0x18),
            "stamina": u32(data, base + 0x28),
        }
        if not (100 <= pools["hp"] <= 30000 and 20 <= pools["fp"] <= 3000
                and 30 <= pools["stamina"] <= 3000):
            pools = None  # 偏移对不上（旧版本存档），宁可不给也别给错
        resists = [u32(data, base + 0x70 + 4 * i) for i in range(7)] if base + 0x8C <= len(data) else None
        if resists is not None and any(v > 2000 for v in resists):
            resists = None
        return {
            "stats_off": x,
            "base": base,
            "level": level,
            "stats": dict(zip(STAT_KEYS, stats)),
            "name": name,
            "runes": u32(data, x + 0x30),
            "pools": pools,
            "resistances": resists,
            "body_type": data[base + 0xB6] if base + 0xB6 < len(data) else 0,
            "archetype": data[base + 0xB7] if base + 0xB7 < len(data) else 0,
            "scadutree": data[base + 0xF4] if base + 0xF4 < len(data) else 0,
        }
    return None


def find_face(data: bytes) -> int | None:
    """找 FaceData 块（ffffffff + FACE + ver + size=0x120），返回块起点。"""
    pat = b"\xff\xff\xff\xffFACE"
    start = 0
    while True:
        i = data.find(pat, start)
        if i < 0:
            return None
        if u32(data, i + 12) == FACE_DATA_SIZE:
            return i
        start = i + 1


def armor_family_ok(ids: list[int]) -> bool:
    """**没有参数表时**的兜底校验：四件防具至少要像「一套」。

    只在拿不到 `er_echo_equip.json`（游戏内 `dump_equip` 导出）时才用。
    这条规则会误杀混搭：实测 Sv 就是 head=10000 / hands=10200 + 骑士身体/腿，
    运行时 `dump_profile` 证实这就是他身上的真装备（见 docs §13.10）。
    所以有参数表时一律以「id 是否存在于对应 param 表」为准。
    """
    fam = [v for v in (ids[12], ids[13], ids[14], ids[15]) if v != -1]
    if len(fam) < 2:
        return False  # 连两件防具都找不到 → 这张表不是装备表
    return (max(fam) - min(fam) <= 0x800) and len({v >> 16 for v in fam}) == 1


def equip_ok(ids: list[int]) -> bool:
    """装备表合理性：22 槽、值 ∈ {-1} ∪ [0, 0x0FFFFFFF]，且（有参数表时）每个 id 都真实存在。"""
    if len(ids) != SLOT_COUNT:
        return False
    norm = [(-1 if v == -1 else v & 0x0FFFFFFF) for v in ids]
    for v in norm:
        if v != -1 and not (0 <= v <= 0x0FFFFFFF):
            return False
    if norm[12:16] and not any(v != -1 for v in norm):
        return False

    if EQUIP_TABLES:
        # 有真值：挨个查存在性 —— 这才是硬约束，能同时挡住错位表和不存在的 id
        for slot, v in enumerate(norm):
            if v == -1:
                continue
            table = slot_table(slot)
            if table is None:
                continue
            if v not in EQUIP_TABLES[table]:
                return False
        return any(v != -1 for v in norm)

    # 没有参数表：退回「区间 + 同一套防具」两条弱约束
    for v in norm[12:16]:
        if v != -1 and not (0x90000 <= v <= 0x400000):
            return False
    if not armor_family_ok(norm):
        return False
    return any(v != -1 for v in norm)


def norm_equip(ids: list[int]) -> list[int]:
    return [(-1 if v == -1 else v & 0x0FFFFFFF) for v in ids]


# 运行时 `dump_equip` 导出的参数表 id 集合（有它就能做「id 是否真实存在」的硬校验）
EQUIP_TABLES: dict[str, set[int]] = {}


def load_equip_tables(path: pathlib.Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    for key in ("weapons", "protectors", "accessories"):
        EQUIP_TABLES[key] = {int(v) for v in (data.get(key) or [])}
    ok = all(EQUIP_TABLES.get(k) for k in ("weapons", "protectors", "accessories"))
    print(f"[equip] loaded id tables from {path} "
          f"(w={len(EQUIP_TABLES['weapons'])} p={len(EQUIP_TABLES['protectors'])} "
          f"a={len(EQUIP_TABLES['accessories'])})" if ok else f"[!] {path} 参数表不完整")
    return ok


def _table_candidates(name: str) -> list[pathlib.Path]:
    """id 表（游戏内 dump_equip / dump_magic 导出）的候选位置。

    源码搬出游戏目录后，dump 落在**游戏根目录**（进程 CWD），不再在 er-echo 的父目录，
    所以这里按「仓库 → 当前目录 → 探测到的游戏目录」找。
    """
    here = pathlib.Path(__file__).resolve().parent
    cands = [here.parent / name, here / name, pathlib.Path(name)]
    try:
        sys.path.insert(0, str(here))
        import gamedir
        game = gamedir.game_dir(here.parent)
        if game is not None:
            cands.insert(0, game / name)
    except Exception:  # noqa: BLE001 - 探测失败就用上面的候选
        pass
    return cands


def find_equip_tables() -> pathlib.Path | None:
    for cand in _table_candidates("er_echo_equip.json"):
        if cand.exists():
            return cand
    return None


# ------------------------------------------------------- 记忆法术（14 槽）

MAGIC_SLOT_COUNT = 14
#: 记忆法术块相对 `PlayerGameData` 起点的偏移（实测 v1.17.2，两个角色都命中）。
#: 结构：14 × (param_id: i32, charges: i32)；空槽 = (-1, 0)，已装备 = (id, -1)。
MAGIC_BLOCK_OFF = 0x93B4
#: `dump_magic` 导出的 Magic 行 id 集合（有它才能硬校验「这真的是法术」）
MAGIC_TABLE: set[int] = set()


def find_magic_table_path() -> pathlib.Path | None:
    for cand in _table_candidates("er_echo_magic.json"):
        if cand.exists():
            return cand
    return None


def load_magic_table(path: pathlib.Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    MAGIC_TABLE.update(int(r["id"]) for r in (data.get("rows") or []))
    print(f"[magic] loaded {len(MAGIC_TABLE)} Magic row ids from {path}")
    return bool(MAGIC_TABLE)


def magic_ok(ids: list[int], charges: list[int], strict: bool) -> bool:
    """14 槽记忆法术块的基本合法性。

    * 槽 = (id, charges)：空槽 `(-1, 0)`，装了法术 `(id, -1)`；
    * id 必须存在于 `Magic` 表（没有表时退回区间判断）；
    * 不允许「全空」以外的高位垃圾（防止把别的表当法术表）。
    """
    if len(ids) != MAGIC_SLOT_COUNT or len(charges) != MAGIC_SLOT_COUNT:
        return False
    for cid, chg in zip(ids, charges):
        if chg not in (-1, 0):
            return False
        if cid == -1:
            continue
        if cid <= 0:
            return False
        if strict:
            if cid not in MAGIC_TABLE:
                return False
        elif not (cid < 0x20000 or 2_000_000 <= cid < 2_100_000):
            return False
    return True


def find_magic(data: bytes, base: int, equip_off: int | None) -> list[int] | None:
    """读 14 个记忆法术槽（`-1` = 空）。找不到返回 None。

    先按实测固定偏移读；校验不过再在「装备表之前」的一段里扫一遍
    （版本变化导致偏移整体平移时还能救回来）。
    """
    strict = bool(MAGIC_TABLE)
    off = base + MAGIC_BLOCK_OFF
    if 0 <= off < len(data) - 8 * MAGIC_SLOT_COUNT:
        ids = [i32(data, off + 8 * k) for k in range(MAGIC_SLOT_COUNT)]
        charges = [i32(data, off + 8 * k + 4) for k in range(MAGIC_SLOT_COUNT)]
        if magic_ok(ids, charges, strict):
            return ids

    if equip_off is None:
        return None
    lo = max(0, equip_off - 0x400)
    for cand in range(lo, max(lo, equip_off - 8 * MAGIC_SLOT_COUNT), 4):
        ids = [i32(data, cand + 8 * k) for k in range(MAGIC_SLOT_COUNT)]
        charges = [i32(data, cand + 8 * k + 4) for k in range(MAGIC_SLOT_COUNT)]
        if not magic_ok(ids, charges, strict):
            continue
        if not any(v != -1 for v in ids):
            continue  # 全空块谁都能匹配，交给固定偏移那条路
        print(f"[!] magic block found by scan at +0x{cand - base:x} (expected +0x{MAGIC_BLOCK_OFF:x})",
              file=sys.stderr)
        return ids
    return None


def slot_table(slot: int) -> str | None:
    """槽位 → 参数表名（与 mod/src/kit.rs 的 slot_category 一致）。"""
    if slot <= 11:
        return "weapons"
    if 12 <= slot <= 15:
        return "protectors"
    if 17 <= slot <= 21:
        return "accessories"
    return None


def find_equip(data: bytes, face_off: int) -> list[int] | None:
    """装备表通常在 FaceData 前 0xA8 处；版本差异会有偏移，就近搜索。

    返回**原始** i32 值（未掩码）——高位可能带强化等级/战灰信息，
    归一化留给 `norm_equip()`，原始值另外存进 profile 的 `equipment_raw`。
    """
    for delta in (0xA8, 0xAC, 0xA4, 0xB0, 0xB4, 0xA0, 0xB8, 0xBC, 0xC0):
        off = face_off - delta
        if off < 0:
            continue
        ids = list(struct.unpack_from("<22i", data, off))
        if equip_ok(ids):
            return ids
    return None


def char_from_slot(data: bytes) -> dict | None:
    pgd = find_pgd(data)
    if pgd is None:
        return None
    face = find_face(data)
    raw = find_equip(data, face) if face is not None else None
    pgd["face_off"] = face
    pgd["equip_raw"] = raw
    pgd["equip"] = norm_equip(raw) if raw is not None else None
    eq_off = (face - 0xA8) if face is not None else None
    pgd["magic"] = find_magic(data, pgd["base"], eq_off) if face is not None else None
    pgd["complete"] = face is not None and raw is not None
    return pgd


# ------------------------------------------------------------------ profile

def build_profile(slot: int, ch: dict, data: bytes, source: str) -> dict:
    face_hex = ""
    if ch["face_off"] is not None:
        block = data[ch["face_off"]:ch["face_off"] + FACE_SIZE]
        if len(block) == FACE_SIZE:
            face_hex = block.hex()
    equip = ch["equip"] or [-1] * SLOT_COUNT
    magic = ch.get("magic") or [-1] * MAGIC_SLOT_COUNT
    profile = {
        "v": 1,
        "source": {
            "slot": slot,
            "steam_id": source,
            "exported_by": "er-echo tools/export_profile_from_save.py (offline .sl2)",
        },
        "name": ch["name"],
        "level": ch["level"],
        "stats": ch["stats"],
        "equipment_param_ids": equip,
        # 记忆法术：不写这张表，克隆体的 AI 就只会平砍（见 log §16）
        "magic": magic,
        "unlocked_magic_slots": sum(1 for v in magic if v != -1),
        "face_hex": face_hex,
        "body_type": ch.get("body_type", 0),
        "scadutree_blessing": ch.get("scadutree", 0),
        "notes": f"offline export from slot {slot} (archetype={ch['archetype']} runes={ch['runes']})",
    }
    # 引擎算好的派生值（存档里直接有，不用重算）：写进克隆体能省掉 HP/FP 上限不对的问题
    if ch.get("pools"):
        profile["pools"] = ch["pools"]
    if ch.get("resistances"):
        profile["resistances"] = ch["resistances"]
    if ch.get("equip_raw"):
        profile["equipment_raw"] = ch["equip_raw"]
    return profile


def describe(ch: dict) -> str:
    eq = ch["equip"] or [-1] * SLOT_COUNT
    magic = [v for v in (ch.get("magic") or []) if v != -1]
    weapons = [hex(v) if v != -1 else "-" for v in eq[0:6]]
    armor = [hex(v) if v != -1 else "-" for v in eq[12:16]]
    flag = "" if ch["complete"] else f"  (incomplete: face={ch['face_off'] is not None} equip={ch['equip'] is not None})"
    return (f"lv{ch['level']:<3d} {ch['name']:<16s} runes={ch['runes']:<8d} "
            f"wpn={weapons} armor={armor} spells={magic or '-'}{flag}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", default=None, help="ER0000.sl2 路径（默认找 APPDATA\\EldenRing 下最新的）")
    ap.add_argument("--slot", type=int, default=None, help="只导出某个槽（0..9）")
    ap.add_argument("--all", action="store_true", help="导出所有可解析角色")
    ap.add_argument("--list", action="store_true", help="只列出角色，不写文件")
    ap.add_argument("-o", "--out", default=None, help="--slot 时的输出路径")
    ap.add_argument("-d", "--dir", default=None, help="--all 时的输出目录")
    ap.add_argument("--equip-ids", default=None,
                    help="dump_equip 导出的 er_echo_equip.json（默认自动找）；有它就能校验 id 是否真实存在")
    ap.add_argument("--magic-ids", default=None,
                    help="dump_magic 导出的 er_echo_magic.json（默认自动找）；有它才能校验记忆法术 id")
    args = ap.parse_args()

    ids_path = pathlib.Path(args.equip_ids) if args.equip_ids else find_equip_tables()
    if ids_path is not None:
        if not load_equip_tables(ids_path):
            print("[!] 参数表 id 不可用，退回「防具成一套」的弱校验", file=sys.stderr)
    else:
        print("[i] 没找到 er_echo_equip.json（进游戏跑一次 `ipc_client.py dump_equip` 会有）；"
              "本次只用弱校验", file=sys.stderr)

    magic_path = pathlib.Path(args.magic_ids) if args.magic_ids else find_magic_table_path()
    if magic_path is not None:
        load_magic_table(magic_path)
    else:
        print("[i] 没找到 er_echo_magic.json（进游戏跑一次 `ipc_client.py dump_magic` 会有）；"
              "记忆法术只能用区间弱校验", file=sys.stderr)

    save = pathlib.Path(args.save) if args.save else pick_default_save()
    entries = parse_bnd4(save)
    print(f"[save] {save}")
    print(f"[bnd4] {len(entries)} entries: {[n for n, _ in entries]}")

    found: list[tuple[int, dict, bytes]] = []
    for idx, (name, data) in enumerate(entries):
        if not name.startswith("USER_DATA") or len(data) < SLOT_SIZE:
            continue
        slot = int(name[len("USER_DATA"):])
        if slot >= 10:
            continue
        payload = data[0x10:]
        ch = char_from_slot(payload)
        if ch is None:
            continue
        found.append((slot, ch, payload))

    if not found:
        print("[!] no character data found", file=sys.stderr)
        raise SystemExit(2)

    print(f"[chars] {len(found)}")
    for slot, ch, _ in found:
        print(f"  slot {slot}: {describe(ch)}")

    if args.list:
        return

    if args.all:
        outdir = pathlib.Path(args.dir or "tools/from_save")
        outdir.mkdir(parents=True, exist_ok=True)
        exported = 0
        for slot, ch, payload in found:
            if not ch["complete"]:
                print(f"[skip] slot {slot} {ch['name']}: missing face/equip")
                continue
            profile = build_profile(slot, ch, payload, source=save.parent.name)
            out = outdir / f"slot{slot}_{sanitize(ch['name'])}.json"
            preserve_ai(out, profile)
            out.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"[ok] {out}  ({profile['name']} lv{profile['level']})")
            exported += 1
        if exported == 0:
            raise SystemExit(2)
        return

    slot = args.slot
    if slot is None:
        slot = found[0][0]
        print(f"[i] --slot not given, using first character (slot {slot})")
    match = [x for x in found if x[0] == slot]
    if not match:
        print(f"[!] slot {slot} has no character", file=sys.stderr)
        raise SystemExit(2)
    slot, ch, payload = match[0]
    if not ch["complete"]:
        print(f"[!] slot {slot} ({ch['name']}) incomplete: face={ch['face_off'] is not None} "
              f"equip={ch['equip'] is not None}", file=sys.stderr)
        raise SystemExit(2)
    profile = build_profile(slot, ch, payload, source=save.parent.name)
    out = pathlib.Path(args.out or f"tools/profile.slot{slot}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    preserve_ai(out, profile)
    out.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[ok] {out}  ({profile['name']} lv{profile['level']}, "
          f"{len(profile['face_hex'])//2} bytes face)")


def sanitize(name: str) -> str:
    keep = [c if c.isalnum() or c in "-_" else "_" for c in name]
    return "".join(keep)[:32] or "char"


# ---------------------------------------------------------------- 内置档案
#: 随包发布、固定追加在 `profiles=` 名单里的档案（彩蛋 / 备用角色）。
#: 用 `builtin_` 前缀而不是 `slot<N>_`：导出工具只会写/删 `slot*.json`，
#: 所以用户导出、切号、Convergence 清理都不会碰到内置档案。
BUILTIN_PREFIX = "builtin_"


def is_builtin_profile(path: str | pathlib.Path) -> bool:
    """是不是内置档案（按文件名判断：`builtin_*.json`）。"""
    name = pathlib.Path(str(path).replace("\\", "/")).name.lower()
    return name.startswith(BUILTIN_PREFIX) and name.endswith(".json")


def builtin_profiles(dirpath: str | pathlib.Path) -> list[pathlib.Path]:
    """`dirpath` 里的内置档案（按文件名排序）。"""
    folder = pathlib.Path(dirpath)
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.glob(BUILTIN_PREFIX + "*.json") if p.is_file())


def preserve_ai(out: pathlib.Path, profile: dict) -> None:
    """重新导出到同一路径时保留赐福菜单写进去的 `ai` 段（AI 存在 profile 里、不在存档里）。"""
    try:
        old = json.loads(out.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    ai = old.get("ai") if isinstance(old, dict) else None
    if isinstance(ai, dict):
        profile["ai"] = ai


def _save_files() -> list[pathlib.Path]:
    """所有存档主文件（`ER0000.sl2`、Convergence 的 `ER0000.cnv` …），按修改时间倒序。

    Convergence 用 me3 的 `savefile = "ER0000.cnv"` —— 文件名**没有** `.sl2` 后缀，
    但内容是同样的 SL2 格式，所以不能只按 `*.sl2` 找。
    """
    out: list[pathlib.Path] = []
    for p in DEFAULT_SAVE_DIR.glob("*/*"):
        if not p.is_file():
            continue
        name = p.name.lower()
        if not name.startswith("er0000"):
            continue
        if name.endswith((".bak", ".co2", ".tmp", ".vdf")) or ".bak" in name:
            continue
        out.append(p)
    out.sort(key=lambda p: p.stat().st_mtime if p.is_file() else 0.0, reverse=True)
    return out


def pick_default_save() -> pathlib.Path:
    candidates = _save_files()
    if not candidates:
        raise SystemExit(f"no ER0000* save under {DEFAULT_SAVE_DIR}; pass --save")
    return candidates[0]


if __name__ == "__main__":
    try:
        main()
    except (OSError, struct.error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
