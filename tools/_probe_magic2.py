import importlib.util, pathlib, struct
p = pathlib.Path("er-echo/tools/export_profile_from_save.py")
spec = importlib.util.spec_from_file_location("ex", p); ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
save = pathlib.Path(r"%APPDATA%\EldenRing\<SteamID>\ER0000.sl2")
entries = ex.parse_bnd4(save)
for slot in (0,1):
    d = entries[slot][1]
    pgd = ex.find_pgd(d); face = ex.find_face(d); base = pgd["base"]
    lo, hi = base, face
    print(f"=== slot{slot} {pgd['name']} region 0x{lo:x}..0x{hi:x}")
    v = struct.unpack_from(f"<{(hi-lo)//4}i", d, lo)
    # 30 连续 -1 的跑（stride 4）附近，往前看是否有 6 位数字
    run = 0
    for i, x in enumerate(v):
        if x == -1:
            run += 1
        else:
            if run >= 12:
                j = i - run
                ctx = v[max(0,j-6):min(len(v), i+2)]
                print(f"  -1 run len={run} at rel 0x{j*4:x} abs 0x{lo+j*4:x} before={ctx}")
            run = 0
