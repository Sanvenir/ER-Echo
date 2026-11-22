import importlib.util, pathlib, struct
p = pathlib.Path("er-echo/tools/export_profile_from_save.py")
spec = importlib.util.spec_from_file_location("ex", p); ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
save = pathlib.Path(r"%APPDATA%\EldenRing\<SteamID>\ER0000.sl2")
entries = ex.parse_bnd4(save)
for slot in (0,1):
    d = entries[slot][1]
    pgd = ex.find_pgd(d); base = pgd["base"]
    print(f"=== slot{slot} {pgd['name']}")
    off = base + 0x9390
    for k in range(0, 0xD0, 4):
        rel = 0x9390 + k
        v = struct.unpack_from("<i", d, base+rel)[0]
        print(f"  rel0x{rel:05x} = {v:>12}")
