import importlib.util, pathlib, struct
p = pathlib.Path("er-echo/tools/export_profile_from_save.py")
spec = importlib.util.spec_from_file_location("ex", p); ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
save = pathlib.Path(r"%APPDATA%\EldenRing\<SteamID>\ER0000.sl2")
entries = ex.parse_bnd4(save)
for slot in (0,1):
    d = entries[slot][1]
    pgd = ex.find_pgd(d); base = pgd["base"]
    n = len(d)//4 - 1
    hits = []
    for i in range(n):
        v = struct.unpack_from("<i", d, i*4)[0]
        if 50000000 <= v < 60000000:
            hits.append((i*4, v))
    print(f"=== slot{slot} {pgd['name']} base=0x{base:x} magic-range hits={len(hits)}")
    for off, v in hits[:40]:
        ctx = struct.unpack_from("<6i", d, max(0, off-8))
        print(f"  abs 0x{off:06x} rel_pgd 0x{(off-base)&0xffffff:x} v={v} ctx={ctx}")
