"""多槽对照：把每个角色的 base+0x00..0x140 打成 u32，找「current/max/base」三元组。"""
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import export_profile_from_save as ex  # noqa: E402

save = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != '-' else ex.pick_default_save()
entries = ex.parse_bnd4(save)
print(f"[save] {save}")

for name, d in entries:
    if not name.startswith("USER_DATA") or len(d) < ex.SLOT_SIZE:
        continue
    slot = int(name[len("USER_DATA"):])
    if slot >= 10:
        continue
    payload = d[0x10:]
    pgd = ex.find_pgd(payload)
    if pgd is None:
        print(f"slot {slot}: no pgd")
        continue
    base = pgd['base']
    vals = [struct.unpack_from('<I', payload, base + o)[0] for o in range(0x08, 0x34, 4)]
    print(f"slot {slot} {pgd['name']!r:10s} lv{pgd['level']:<4d} "
          f"0x08..0x30={vals}")
    # 抗性区 0x70..0x90
    res = [struct.unpack_from('<I', payload, base + o)[0] for o in range(0x70, 0x8c, 4)]
    print(f"         resist[{len(res)}]={res}")
    # 名字之后一直到装备表之前
    tail = payload[base + 0x90: base + 0x140]
    print("         raw 0x90..0x140: " + " ".join(f"{b:02x}" for b in tail))
