"""Generate Nexus-ready placeholder media from existing dev screenshots.

These are *placeholders*: real promo shots must be re-captured in-game (see
nexus/shotlist.md). What this does:
  * strips the RTSS/FPS overlay row at the top,
  * crops to 16:9 for the gallery (1920x1080) and 3.5:1 for the header banner
    (1400x400),
  * re-encodes as JPEG well under Nexus' 2 MB per-image limit.
"""

import json
import pathlib

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]   # er-echo/
SHOTS = ROOT / "shots"
OUT = ROOT / "nexus" / "media"
OUT.mkdir(parents=True, exist_ok=True)

# 3440x1440 captures have a ~40 px overlay strip at the top (RTSS).
TOP = 44


def load(name: str) -> Image.Image:
    img = Image.open(SHOTS / name).convert("RGB")
    if img.width < 3000:
        raise SystemExit(f"unexpected size for {name}: {img.size}")
    return img.crop((0, TOP, img.width, img.height))


def crop_16x9(img: Image.Image, anchor: str = "left") -> Image.Image:
    h = img.height
    w = round(h * 16 / 9)
    if w >= img.width:
        # too narrow: crop vertically instead
        w = img.width
        h = round(w * 9 / 16)
        y = max(0, (img.height - h) // 2)
        return img.crop((0, y, w, y + h))
    if anchor == "left":
        x = min(160, img.width - w)
    else:
        x = (img.width - w) // 2
    return img.crop((x, 0, x + w, h))


def crop_banner(img: Image.Image, ratio: float = 3.5) -> Image.Image:
    h = round(img.width / ratio)
    if h > img.height:
        h = img.height
    y = min(90, max(0, img.height - h))
    return img.crop((0, y, img.width, y + h))


def save_jpg(img: Image.Image, path: pathlib.Path, quality: int = 88) -> dict:
    img.save(path, "JPEG", quality=quality, optimize=True, progressive=True)
    return {"file": path.name, "size": list(img.size), "bytes": path.stat().st_size}


manifest = []

banner = load("menu_sublist.png")
manifest.append(save_jpg(crop_banner(banner), OUT / "00-banner-1400x400.jpg", quality=90))
# crop_banner returns 3440x983; resize for the actual header slot
img = Image.open(OUT / "00-banner-1400x400.jpg")
img = img.resize((1400, 400), Image.LANCZOS)
img.save(OUT / "00-banner-1400x400.jpg", "JPEG", quality=90, optimize=True, progressive=True)
manifest[-1] = {"file": "00-banner-1400x400.jpg", "size": [1400, 400],
                "bytes": (OUT / "00-banner-1400x400.jpg").stat().st_size}

for src, dst, anchor in [
    ("menu_root_nested.png", "01-grace-menu.jpg", "left"),
    ("menu_sublist.png", "02-party-menu.jpg", "left"),
    ("ui_allup.png", "03-companions.jpg", "center"),
]:
    frame = crop_16x9(load(src), anchor).resize((1920, 1080), Image.LANCZOS)
    manifest.append(save_jpg(frame, OUT / dst, quality=88))

(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
for item in manifest:
    print(f"{item['file']:<24} {item['size'][0]}x{item['size'][1]}  {item['bytes']/1024:.0f} KB")
