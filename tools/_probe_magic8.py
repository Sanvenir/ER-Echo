import importlib.util, pathlib, struct, json
p = pathlib.Path("er-echo/tools/export_profile_from_save.py")
spec = importlib.util.spec_from_file_location("ex", p); ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
magic = {int(r["id"]) for r in json.loads(pathlib.Path("er_echo_magic.json").read_text())["rows"]}
small = {i for i in magic if i < 200000}
save = pathlib.Path(r"%APPDATA%\EldenRing\<SteamID>\ER0000.sl2")
entries = ex.parse_bnd4(save)
for slot in (0,1):
    d = entries[slot][1]
    pgd = ex.find_pgd(d); base = pgd["base"]; face = ex.find_face(d)
    print(f"=== slot{slot} {pgd['name']} int={pgd['stats']['intelligence']} len=0x{len(d):x}")
    hits = []
    for off in range(0, len(d)//4 - 60):
        o = off*4
        v = struct.unpack_from("<i", d, o)[0]
        if v not in small: continue
        # 后面 9 个 8 字节槽
        tail = [struct.unpack_from("<2i", d, o + 8*k) for k in range(1, 12)]
        non = [t for t in tail if t[0] != -1]
        if len(non) > 4: continue
        empty = sum(1 for t in tail if t[0] == -1)
        if empty < 6: continue
        hits.append((o, base, v, tail[:6]))
    for o, base, v, tail in hits[:12]:
        print(f"  abs0x{o:06x} rel0x{o-base:x} v={v} tail={tail}")
    print(f"  candidates={len(hits)}")
