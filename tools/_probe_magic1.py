import importlib.util, pathlib, struct
p = pathlib.Path("er-echo/tools/export_profile_from_save.py")
spec = importlib.util.spec_from_file_location("ex", p); ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
save = pathlib.Path(r"%APPDATA%\EldenRing\<SteamID>\ER0000.sl2")
entries = ex.parse_bnd4(save)
for slot in (0,1):
    d = entries[slot][1]
    pgd = ex.find_pgd(d); face = ex.find_face(d)
    base = pgd["base"]
    eq = ex.find_equip(d, face)
    print(f"slot{slot} '{pgd['name']}' lv{pgd['level']} base=0x{base:x} face=0x{face:x} rel=0x{face-base:x} equip_ok={eq is not None} equip_off=0x{face-0xA8:x} rel=0x{face-0xA8-base:x}")
