"""在某个槽里搜参数值，看它们出现在哪些位置（chr_asm / inventory / FaceData 附近）。"""
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import export_profile_from_save as ex  # noqa: E402

save = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != '-' else ex.pick_default_save()
slot = int(sys.argv[2]) if len(sys.argv) > 2 else 0
targets = [int(x, 0) for x in sys.argv[3:]] or [660000, 660100, 660200, 660300, 10000, 10200]

entries = ex.parse_bnd4(save)
payload = None
for name, d in entries:
    if name == f"USER_DATA{slot:03d}":
        payload = d[0x10:]
if payload is None:
    raise SystemExit("slot not found")

pgd = ex.find_pgd(payload)
face = ex.find_face(payload)
print(f"slot {slot} {pgd['name']} base={pgd['base']:#x} face={face:#x}")

for t in targets:
    pats = [("param", t.to_bytes(4, "little")),
            ("param+2^28", (t + 0x10000000).to_bytes(4, "little"))]
    for label, pat in pats:
        hits = []
        i = payload.find(pat)
        while i >= 0 and len(hits) < 12:
            hits.append(i)
            i = payload.find(pat, i + 1)
        if hits:
            shown = ", ".join(f"{h:#x}" for h in hits)
            print(f"  {t:>8d} ({label:>10s}) hits: {shown}")
