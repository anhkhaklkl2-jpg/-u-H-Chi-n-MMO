# One-off: generate cave ore-vein node sprites (copper + iron) in the same
# 32x32 pixel-art style as the bundled meteor-ore node (assets/node/).
# Rock blob base (grey, meteor-ore silhouette family) with copper-orange /
# iron-silver ore specks. Run once from the project root:
#   .venv/Scripts/python scripts/make_ore_node_sprites.py
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# Ore speck colours (2 shades each: bright + dark for depth).
SPECKS = {
    "copper_ore": [(224, 123, 57), (176, 84, 34)],
    "iron_ore": [(216, 220, 228), (150, 156, 168)],
}
# Rock body shading (grey family, slightly darker than the meteor ore base).
BODY = (104, 100, 112)
BODY_DARK = (78, 74, 86)
OUTLINE = (40, 36, 48)


def make_rock(kind: str) -> Image.Image:
    im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # Chunky rounded rock silhouette (2x2 px "pixels" for the pixel-art feel).
    body_boxes = [
        (10, 6, 21, 7),
        (7, 8, 24, 10),
        (5, 11, 26, 16),
        (4, 17, 27, 20),
        (6, 21, 25, 23),
        (9, 24, 22, 25),
    ]
    for box in body_boxes:
        d.rectangle(box, fill=BODY)
    # Bottom shading.
    d.rectangle((5, 19, 26, 23), fill=BODY_DARK)
    d.rectangle((9, 24, 22, 25), fill=BODY_DARK)
    # Outline.
    for box in body_boxes:
        d.rectangle(box, outline=OUTLINE)
    d.line((4, 21, 27, 21), fill=OUTLINE)
    d.line((9, 26, 22, 26), fill=OUTLINE)
    # Ore specks: scattered clusters, bright core + dark rim.
    clusters = {
        "copper_ore": [((12, 11), 3), ((20, 14), 3), ((9, 19), 2), ((17, 21), 2)],
        "iron_ore": [((13, 10), 2), ((21, 13), 3), ((8, 18), 2), ((16, 21), 3)],
    }[kind]
    bright, dark = SPECKS[kind]
    for (cx, cy), r in clusters:
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=dark)
        d.ellipse((cx - r + 1, cy - r + 1, cx + r - 1, cy + r - 1), fill=bright)
    # Top highlight for readability on dark cave floors.
    d.line((9, 8, 14, 7), fill=(140, 136, 150))
    return im


def main() -> None:
    out_dir = ROOT / "assets" / "node"
    out_dir.mkdir(parents=True, exist_ok=True)
    for kind in SPECKS:
        out = out_dir / f"{kind}.png"
        make_rock(kind).save(out)
        print("wrote", out)


if __name__ == "__main__":
    main()
