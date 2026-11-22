"""看 dump_equip 导出的参数表：某个 id 是否存在、周边 id 是否成「一套」。"""
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "er_echo_equip.json")
data = json.loads(path.read_text(encoding="utf-8"))
prot = sorted(data["protectors"])
wep = data["weapons"]
acc = data["accessories"]
print(f"weapons={len(wep)} protectors={len(prot)} accessories={len(acc)}")
print(f"protector range: {prot[0]} .. {prot[-1]}")

ids = [int(x, 0) if isinstance(x, str) else x for x in sys.argv[2:]] or [10000, 10200, 660000, 660100, 660200, 660300]
pset = set(prot)
for i in ids:
    near = [p for p in prot if abs(p - i) <= 0x400]
    same_hi = [p for p in prot if (p >> 16) == (i >> 16)]
    print(f"  {i} ({i:#x}): exists={i in pset}  same_hi_block={len(same_hi)}  near={near[:12]}")

print("\nprotector ids below 200000:", [p for p in prot if p < 200000][:30])
print("\ncount by 0x10000 bucket (first 20):")
buckets = {}
for p in prot:
    buckets[p >> 16] = buckets.get(p >> 16, 0) + 1
for k in sorted(buckets)[:20]:
    print(f"  {k:#04x}xxxx: {buckets[k]}")
