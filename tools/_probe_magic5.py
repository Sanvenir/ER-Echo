import importlib.util, pathlib, struct
p = pathlib.Path("er-echo/tools/export_profile_from_save.py")
spec = importlib.util.spec_from_file_location("ex", p); ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
save = pathlib.Path(r"%APPDATA%\EldenRing\<SteamID>\ER0000.sl2")
entries = ex.parse_bnd4(save)
for slot in (0,1):
    d = entries[slot][1]
    pgd = ex.find_pgd(d); base = pgd["base"]; face = ex.find_face(d)
    print(f"=== slot{slot} {pgd['name']} int={pgd['stats']['intelligence']} base=0x{base:x} face=0x{face:x}")
    hi = face
    n = hi//4 - 2
    for i in range(4, n, 2):
        v = struct.unpack_from("<i", d, i*4)[0]
        if 50_000_000 <= v < 70_000_000 and v % 10000 == 0:
            # 8 字节 stride，取前后 14 项窗口
            win = [struct.unpack_from("<2i", d, i*4 + 8*k) for k in range(-2, 6)]
            print(f"  abs 0x{i*4:06x} rel0x{i*4-base:x} v={v} win={win}")
