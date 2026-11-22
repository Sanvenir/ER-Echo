import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_game_file as e

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ui", "out_bnd", "m00_00_00_00.talkesdbnd.dcx")
raw = open(p, "rb").read()
b = e.decompress_dcx(raw)
print("dcx", len(raw), "->", len(b), "sig", b[:4])
out = os.path.join(os.path.dirname(p), "check.bnd")
open(out, "wb").write(b)
print(out)
