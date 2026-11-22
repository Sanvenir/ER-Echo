import importlib.util, pathlib, struct, json
p = pathlib.Path("er-echo/tools/export_profile_from_save.py")
spec = importlib.util.spec_from_file_location("ex", p); ex = importlib.util.module_from_spec(spec); spec.loader.exec_module(ex)
magic = {int(r["id"]) for r in json.loads(pathlib.Path("er_echo_magic.json").read_text())["rows"]}
print("table size", len(magic), "sample", sorted(magic)[:8], sorted(magic)[-4:])
save = pathlib.Path(r"%APPDATA%\EldenRing\<SteamID>\ER0000.sl2")
entries = ex.parse_bnd4(save)
d = entries[1][1]
found = {}
for off in range(0, len(d)//4):
    v = struct.unpack_from("<i", d, off*4)[0]
    if v in magic:
        found.setdefault(v, []).append(off*4)
print("distinct magic ids present:", len(found))
for v, offs in list(found.items())[:20]:
    print(f"  id {v} at {[hex(o) for o in offs[:4]]}")
