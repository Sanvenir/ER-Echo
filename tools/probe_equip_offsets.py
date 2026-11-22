"""诊断：对每个 FaceData 前的候选偏移，打印 22×i32（原始+掩码）以及校验失败原因。"""
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import export_profile_from_save as ex  # noqa: E402

save = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != '-' else ex.pick_default_save()
want = int(sys.argv[2]) if len(sys.argv) > 2 else 0
entries = ex.parse_bnd4(save)
for name, d in entries:
    if name != f"USER_DATA{want:03d}" or len(d) < ex.SLOT_SIZE:
        continue
    payload = d[0x10:]
    pgd = ex.find_pgd(payload)
    face = ex.find_face(payload)
    print(f"{pgd['name']} lv{pgd['level']} base={pgd['base']:#x} face={face:#x}")
    for delta in (0xA8, 0xAC, 0xA4, 0xB0, 0xB4, 0xA0, 0xB8, 0xBC, 0xC0):
        off = face - delta
        raw = list(struct.unpack_from("<22i", payload, off))
        norm = [(-1 if v == -1 else v & 0x0FFFFFFF) for v in raw]
        reasons = []
        if not (0 <= off < len(payload)):
            reasons.append("oob")
        for slot, v in enumerate(norm):
            if v != -1 and not (0 <= v <= 0x0FFFFFFF):
                reasons.append(f"slot{slot} oob")
        for slot in range(12, 16):
            v = norm[slot]
            if v != -1 and not (0x90000 <= v <= 0x400000):
                reasons.append(f"slot{slot}={v} not protector")
        if not any(v != -1 for v in norm):
            reasons.append("all empty")
        ok = not reasons
        print(f"  delta {delta:#04x} off={off:#x} {'OK' if ok else 'FAIL: ' + ', '.join(reasons[:4])}")
        print(f"     raw = {raw}")
        print(f"     mask= {norm}")
        if ok:
            break
