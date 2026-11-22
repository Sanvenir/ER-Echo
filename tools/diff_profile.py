"""对比「运行时 dump_profile（当前登录角色）」与「离线 .sl2 导出的 profile」。

用法：
  python tools/diff_profile.py                       # 默认 er_echo_profile.json vs May
  python tools/diff_profile.py dump.json profile.json
"""
import json
import sys

rt_path = sys.argv[1] if len(sys.argv) > 1 else 'er_echo_profile.json'
off_path = sys.argv[2] if len(sys.argv) > 2 else 'er-echo/tools/from_save_account/sl2/slot1_May.json'

rt = json.load(open(rt_path, encoding='utf-8'))
off = json.load(open(off_path, encoding='utf-8'))
fails = []


def check(label, ok, detail=''):
    print(f"  {'OK ' if ok else 'DIF'}  {label}{('  ' + detail) if detail else ''}")
    if not ok:
        fails.append(label)


print(f"runtime dump = {rt_path}\noffline profile = {off_path} ({off.get('name')})")

# 名字（新 DLL 才 dump 出来）
if 'name' in rt:
    check(f"name: {rt['name']!r} vs {off.get('name')!r}", rt['name'] == off['name'])

check(f"level: {rt['level']} vs {off['level']}", rt['level'] == off['level'])

bad = {k: (rt['stats'][k], v) for k, v in off['stats'].items() if rt['stats'][k] != v}
check("stats 8/8", not bad, str(bad) if bad else '')

e_rt, e_off = rt['equipment_param_ids'], off['equipment_param_ids']
diff_slots = {i: (a, b) for i, (a, b) in enumerate(zip(e_rt, e_off)) if a != b}
check("equipment 22/22", not diff_slots, str(diff_slots) if diff_slots else '')

fh = off['face_hex']
payload_ok = fh[0x10 * 2:0x124 * 2] == rt['face']['payload_hex']
check(f"face payload 276B (block {len(fh)//2}B)", payload_ok)

# 三围上限：离线解析出来的就是引擎算好的值
if off.get('pools'):
    pools = off['pools']
    for key in ('hp', 'fp', 'stamina'):
        part = rt.get(key) or {}
        mx = part.get('max')
        if mx is None:
            continue
        check(f"{key} max: {mx} vs {pools[key]}", mx == pools[key])

print("\n" + ("ALL MATCH" if not fails else f"{len(fails)} mismatch: {fails}"))
sys.exit(0 if not fails else 1)
