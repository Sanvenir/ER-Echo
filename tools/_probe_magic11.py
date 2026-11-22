import importlib.util, pathlib, struct, json
p = pathlib.Path("er-echo/tools/export_profile_from_save.py")
spec = importlib.util.spec_from_file_location("ex", p); ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
magic = {int(r["id"]) for r in json.loads(pathlib.Path("er_echo_magic.json").read_text())["rows"]}
small = {i for i in magic if 3000 <= i < 65536}
save = pathlib.Path(r"%APPDATA%\EldenRing\<SteamID>\ER0000.sl2")
entries = ex.parse_bnd4(save)
d = entries[1][1]
pgd = ex.find_pgd(d); base = pgd["base"]
print("small magic ids count", len(small), sorted(small)[:10])
hits = []
for off in range(0, len(d)-2):
    v = struct.unpack_from("<H", d, off)[0]
    if v in small:
        hits.append((off, v))
print("u16 hits:", len(hits))
for off, v in hits[:25]:
    ctx = d[max(0,off-8):off+16].hex()
    rel = off - base
    print(f"  abs0x{off:06x} rel0x{rel:x} v={v} ctx={ctx}")
