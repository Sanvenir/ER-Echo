import importlib.util, pathlib, struct, json
p = pathlib.Path("er-echo/tools/export_profile_from_save.py")
spec = importlib.util.spec_from_file_location("ex", p); ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
magic = {int(r["id"]) for r in json.loads(pathlib.Path("er_echo_magic.json").read_text())["rows"]}
save = pathlib.Path(r"%APPDATA%\EldenRing\<SteamID>\ER0000.sl2")
entries = ex.parse_bnd4(save)
N = 14
for slot in (0,1):
    d = entries[slot][1]
    pgd = ex.find_pgd(d); base = pgd["base"]; face = ex.find_face(d)
    print(f"=== slot{slot} {pgd['name']} int={pgd['stats']['intelligence']} face@rel0x{face-base:x}")
    hits = []
    for stride in (4,):
        for off in range(base & ~3, face - stride*N, 4):
            ids = [struct.unpack_from("<i", d, off + stride*k)[0] for k in range(N)]
            non = [v for v in ids if v != -1]
            if not non: continue
            if any(v not in magic for v in non): continue
            if len(non) > 8: continue
            hits.append((off-base, stride, ids))
    for rel, stride, ids in hits[:20]:
        print(f"  stride{stride} rel0x{rel:x} ids={ids}")
    print(f"  total candidates={len(hits)}")
