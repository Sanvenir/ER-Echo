"""Turn the in-game captures in nexus/media/incoming/*.jpg into Nexus-ready images.

Inputs are the raw JPGs the game/Game Bar produced (1920x1080 or 2560x1440).
Outputs replace the placeholders in nexus/media/:

  00-banner-1400x400.jpg   3.5:1 header strip cut from hero.jpg
  01-grace-menu.jpg        grace root menu, "Comrades (3/3)" visible
  02-party-menu.jpg        Comrades submenu
  03-companions.jpg        hero shot, three companions in the field
  04-combat.jpg            a companion in a real fight
  05-closeup.jpg           face/armour close-up
  06-localisation.jpg      English / 简体中文 menu, side by side

Everything is re-encoded to JPEG (q88, progressive) and kept under Nexus'
2 MB per-image limit. Missing inputs are reported, not fatal -- re-run after
dropping the file into incoming/.

Usage:  python nexus/make_media.py
"""

from __future__ import annotations

import json
import pathlib

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
INCOMING = ROOT / "nexus" / "media" / "incoming"
OUT = ROOT / "nexus" / "media"

GALLERY = (1920, 1080)
BANNER = (1400, 400)
LIMIT = 2 * 1024 * 1024          # Nexus: <= 2 MB per image
SEP = 6                          # px between the two localisation panels

# (input, output, horizontal anchor when the source is wider than 16:9)
SHOTS = [
    ("menu-root.jpg", "01-grace-menu.jpg", "left"),
    ("menu-party.jpg", "02-party-menu.jpg", "left"),
    ("hero.jpg", "03-companions.jpg", "center"),
    ("combat.jpg", "04-combat.jpg", "center"),
    ("closeup.jpg", "05-closeup.jpg", "center"),
]
I18N = ["i18n-en.jpg", "i18n-zhcn.jpg"]
BANNER_SRC = "hero.jpg"


def load(name: str) -> Image.Image | None:
    path = INCOMING / name
    if not path.exists():
        print(f"  missing {path.relative_to(ROOT)}")
        return None
    img = Image.open(path)
    img = img.convert("RGB")
    print(f"  {name:<16} {img.width}x{img.height}")
    return img


def crop_to(img: Image.Image, ratio: float, anchor: str = "center") -> Image.Image:
    """Crop to `ratio` (w/h) without scaling, anchored like CSS object-fit."""
    w, h = img.size
    if abs(w / h - ratio) < 1e-3:
        return img
    if w / h > ratio:                      # too wide: drop sides
        nw = round(h * ratio)
        x = 0 if anchor == "left" else (w - nw) // 2
        return img.crop((x, 0, x + nw, h))
    nh = round(w / ratio)                  # too tall: drop top/bottom
    y = (h - nh) // 2
    return img.crop((0, y, w, y + nh))


def save(img: Image.Image, name: str, quality: int = 88) -> dict:
    path = OUT / name
    q = quality
    while True:
        img.save(path, "JPEG", quality=q, optimize=True, progressive=True)
        if path.stat().st_size <= LIMIT or q <= 60:
            break
        q -= 4
    kb = path.stat().st_size / 1024
    flag = "" if path.stat().st_size <= LIMIT else "  !! over 2 MB"
    print(f"  -> {name:<24} {img.width}x{img.height}  {kb:6.0f} KB  q{q}{flag}")
    return {"file": name, "size": list(img.size), "bytes": path.stat().st_size}


def build_banner() -> dict | None:
    src = load(BANNER_SRC)
    if src is None:
        return None
    # Cut a 3.5:1 strip (centred, so the horizon stays), then scale.
    strip = crop_to(src, BANNER[0] / BANNER[1])
    return save(strip.resize(BANNER, Image.LANCZOS), "00-banner-1400x400.jpg", quality=90)


def build_gallery() -> list[dict]:
    built = []
    for src_name, dst, anchor in SHOTS:
        src = load(src_name)
        if src is None:
            continue
        frame = crop_to(src, 16 / 9, anchor).resize(GALLERY, Image.LANCZOS)
        built.append(save(frame, dst))
    return built


def build_localisation() -> dict | None:
    # The English half must show the same menu level as the Chinese one: the submenu.
    # Prefer a dedicated i18n-en.jpg, then the English submenu shot.
    en_name = next((n for n in ("i18n-en.jpg", "menu-party.jpg") if (INCOMING / n).exists()), None)
    if en_name and en_name != "i18n-en.jpg":
        print(f"  note: no i18n-en.jpg, using {en_name} as the English half")
    zh = load(I18N[1])
    en = load(en_name) if en_name else None
    if en is None or zh is None:
        print("  -> 06-localisation.jpg skipped (need an English and a Chinese menu shot)")
        return None
    # Two tall panels side by side make a 16:9 1920x1080 frame (same as the rest of the
    # gallery) while keeping the menu text at its native pixel size. The menu lives on the
    # left of the screen, so crop each source from the left instead of shrinking the whole
    # 1920x1080 capture into half a frame (text became unreadable that way).
    w, h = GALLERY
    panel_w = (w - SEP) // 2
    canvas = Image.new("RGB", (w, h), (11, 11, 11))
    for i, panel in enumerate((en, zh)):
        frame = crop_to(panel, panel_w / h, "left").resize((panel_w, h), Image.LANCZOS)
        canvas.paste(frame, (i * (panel_w + SEP), 0))
    return save(canvas, "06-localisation.jpg")


def main() -> None:
    print(f"incoming: {INCOMING.relative_to(ROOT)}")
    root, party = INCOMING / "menu-root.jpg", INCOMING / "menu-party.jpg"
    if root.exists() and party.exists() and root.read_bytes() == party.read_bytes():
        print("  !! menu-root.jpg is a byte-for-byte copy of menu-party.jpg")
        print("     -> 01-grace-menu will show the submenu, not 'Comrades (3/3)'; re-shoot and re-run")
    manifest: list[dict] = []
    banner = build_banner()
    if banner:
        manifest.append(banner)
    manifest += build_gallery()
    localisation = build_localisation()
    if localisation:
        manifest.append(localisation)

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n{len(manifest)} images -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
