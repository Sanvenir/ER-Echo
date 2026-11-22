import importlib.util, pathlib, struct
p = pathlib.Path("er-echo/tools/export_profile_from_save.py")
spec = importlib.util.spec_from_file_location("ex", p); ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
save = pathlib.Path(r"%APPDATA%\EldenRing\<SteamID>\ER0000.sl2")
entries = ex.parse_bnd4(save)
d = entries[1][1]
pgd = ex.find_pgd(d); face = ex.find_face(d); base = pgd["base"]
eq = ex.find_equip(d, face)
print("equip ids:", eq)
start = base + 0x9480
for off in range(start, base + 0x95d0, 0x10):
    rel = off - base
    row = struct.unpack_from("<4i", d, off)
    hx = d[off:off+0x10].hex()
    print(f"rel 0x{rel:04x} abs 0x{off:05x} {hx}  {row}")
