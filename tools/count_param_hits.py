"""数一数某个 param id 在存档槽里出现多少次（用来区分「装备表引用」和「背包里真的拥有」）。"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import export_profile_from_save as ex  # noqa: E402

save = pathlib.Path(sys.argv[1])
slot = int(sys.argv[2])
targets = [int(x, 0) for x in sys.argv[3:]]

entries = ex.parse_bnd4(save)
payload = None
for name, d in entries:
    if name == f"USER_DATA{slot:03d}":
        payload = d[0x10:]
if payload is None:
    raise SystemExit("slot not found")

for t in targets:
    forms = {
        "raw": t.to_bytes(4, "little"),
        "+2^28": (t + 0x10000000).to_bytes(4, "little"),
    }
    counts = {}
    for label, pat in forms.items():
        n = 0
        i = payload.find(pat)
        first = []
        while i >= 0:
            n += 1
            if len(first) < 6:
                first.append(hex(i))
            i = payload.find(pat, i + 1)
        counts[label] = (n, first)
    print(f"{t:>8d} ({t:#x})  " + "  ".join(f"{k}={v[0]} {v[1]}" for k, v in counts.items()))
