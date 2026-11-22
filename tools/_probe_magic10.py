import importlib.util, pathlib, struct, json
p = pathlib.Path("er-echo/tools/export_profile_from_save.py")
spec = importlib.util.spec_from_file_location("ex", p); ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
magic = {int(r["id"]) for r in json.loads(pathlib.Path("er_echo_magic.json").read_text())["rows"]}
save = pathlib.Path(r"%APPDATA%\EldenRing\<SteamID>\ER0000.sl2")
entries = ex.parse_bnd4(save)
for slot in (0,1):
    d = entries[slot][1]
    pgd = ex.find_pgd(d); base = pgd["base"]
    hits = []
    for off in range(0, len(d)//4):
        v = struct.unpack_from("<i", d, off*4)[0]
        if v == -1: continue
        if (v & 0x0FFFFFFF) in magic:
            hits.append((off*4, v))
    print(f"=== slot{slot} {pgd['name']} masked-magic hits={len(hits)}")
    for off, v in hits[:30]:
        print(f"  abs0x{off:06x} rel0x{off-base:x} v=0x{v:08x} ({v & 0x0FFFFFFF})")
