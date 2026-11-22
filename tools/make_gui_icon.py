#!/usr/bin/env python3
"""Generate the app icon (build/icon.ico) without external assets."""

from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFont

OUT = pathlib.Path(__file__).resolve().parents[1] / "build" / "icon.ico"
SIZE = 256


def draw(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = round(size * 0.06)
    d.rounded_rectangle(
        (pad, pad, size - pad, size - pad),
        radius=round(size * 0.18),
        fill=(18, 20, 24, 255),
        outline=(198, 168, 96, 255),
        width=max(2, round(size * 0.02)),
    )
    font_path = r"C:\Windows\Fonts\segoeuib.ttf"
    try:
        font = ImageFont.truetype(font_path, round(size * 0.42))
    except OSError:
        font = ImageFont.load_default()
    text = "ER"
    box = d.textbbox((0, 0), text, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((size - w) / 2 - box[0], (size - h) / 2 - box[1] - size * 0.06),
           text, font=font, fill=(232, 226, 214, 255))
    # small green "echo" dot
    r = round(size * 0.055)
    cx, cy = round(size * 0.5), round(size * 0.78)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(120, 200, 140, 255))
    return img


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    base = draw(SIZE)
    base.save(OUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"[ok] {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
