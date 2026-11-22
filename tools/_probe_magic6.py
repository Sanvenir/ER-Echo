import importlib.util, pathlib, struct
p = pathlib.Path("er-echo/tools/export_profile_from_save.py")
spec = importlib.util.spec_from_file_location("ex", p); ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
save = pathlib.Path(r"%APPDATA%\EldenRing\<SteamID>\ER0000.sl2")
entries = ex.parse_bnd4(save)
for slot in (0,1):
    d = entries[slot][1]
    pgd = ex.find_pgd(d); base = pgd["base"]; eq = ex.find_equip(d, ex.find_face(d))
    print(f"=== slot{slot} {pgd['name']} int={pgd['stats']['intelligence']} equip@rel 0x{(ex.find_face(d)-0xA8-base):x}")
    eqoff = ex.find_face(d)-0xA8
    for k in range(-8, 2):
        off = eqoff + 8*k
        print(f"  rel 0x{off-base:04x} {struct.unpack_from('<2i', d, off)}")
