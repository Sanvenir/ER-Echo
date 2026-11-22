"""把存档 slot 里 PlayerGameData 附近的结构按 u32 打印出来，
用于把「运行时已知真值」映射回存档偏移（这样离线也能拿到 HP/FP/耐力等派生值）。"""
import json
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import export_profile_from_save as ex  # noqa: E402

save = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != '-' else ex.pick_default_save()
slot = int(sys.argv[2]) if len(sys.argv) > 2 else 1
known_path = sys.argv[3] if len(sys.argv) > 3 else 'er_echo_profile.json'

entries = ex.parse_bnd4(save)
data = None
for name, d in entries:
    if name == f"USER_DATA{slot:03d}" and len(d) >= ex.SLOT_SIZE:
        data = d[0x10:]
if data is None:
    raise SystemExit(f"slot {slot} not found in {save}")
print(f"save={save} slot={slot} payload={len(data):#x}")

pgd = ex.find_pgd(data)
base = pgd['base']
print(f"pgd base={base:#x} stats_off={pgd['stats_off']:#x} level={pgd['level']} name={pgd['name']!r}")

known = json.load(open(known_path, encoding='utf-8'))
targets = {
    'hp_max': known['hp']['max'], 'hp_cur': known['hp']['current'],
    'fp_max': known['fp']['max'], 'fp_cur': known['fp']['current'],
    'st_max': known['stamina']['max'], 'st_cur': known['stamina']['current'],
    'level': known['level'],
}
print("known runtime targets:", targets)

lo, hi = base - 0x80, base + 0x220
print("\n== u32 map around base ==")
for off in range(-0x40, 0x1C0, 4):
    i = base + off
    if i < 0 or i + 4 > len(data):
        continue
    v = struct.unpack_from('<I', data, i)[0]
    mark = ''.join(f'  <== {n}' for n, t in targets.items() if t != 0 and v == t)
    print(f"  base{off:+#06x}  {v:10d}  {v:#010x}{mark}")

print("\n== byte map 0x00-0x100 rel base (u8) ==")
for off in range(0, 0x100, 16):
    bs = data[base + off: base + off + 16]
    print(f"  base{off:+#05x}  " + " ".join(f"{b:02x}" for b in bs))
