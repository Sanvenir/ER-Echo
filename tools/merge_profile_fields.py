"""把「已知正确」的旧导出（装备/脸/属性）和「当前重新解析」的新字段（pools/resistances）合并。

用途：主存档 slot 0 的装备表现在出现了 10000/10200 的可疑值（见 docs §13.9），
在拿运行时参数表确认之前，先用之前召唤验证过的那份装备表兜底。
"""
import json
import pathlib
import sys

old = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
new = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8"))

for key in ("name", "level", "stats", "face_hex"):
    if old[key] != new[key]:
        print(f"[!] {key} differs between old and new export — refusing to merge")
        raise SystemExit(1)

merged = dict(old)
for key in ("pools", "resistances"):
    if key in new:
        merged[key] = new[key]
merged["notes"] = (old.get("notes", "") + " | equipment kept from earlier verified export"
                   " (current save slot has placeholder ids 10000/10200)").strip(" |")

out = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else pathlib.Path(sys.argv[2])
out.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"[ok] {out}  {merged['name']} lv{merged['level']}  equip={merged['equipment_param_ids'][12:16]}")
