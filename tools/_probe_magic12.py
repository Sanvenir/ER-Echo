import importlib.util, pathlib, struct
p = pathlib.Path("er-echo/tools/export_profile_from_save.py")
spec = importlib.util.spec_from_file_location("ex", p); ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
save = pathlib.Path(r"%APPDATA%\EldenRing\<SteamID>\ER0000.sl2")
entries = ex.parse_bnd4(save)
d = entries[1][1]
pgd = ex.find_pgd(d); base = pgd["base"]
for lo, hi in ((0x92c0, 0x9420), (0x10880, 0x109a0)):
    print(f"--- slot1 rel 0x{lo:x}..0x{hi:x}")
    for off in range(base+lo, base+hi, 0x10):
        rel = off-base
        print(f"  rel0x{rel:05x} {struct.unpack_from('<4i', d, off)}")
