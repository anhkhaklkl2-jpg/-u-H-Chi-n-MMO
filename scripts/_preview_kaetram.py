# -*- coding: utf-8 -*-
"""Render preview PNGs for converted Kaetram maps (uses map's own tilesets)."""
import json, os, sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "maps", "kaetram")
PREV = os.path.join(ROOT, "docs", "_kaetram_previews")
os.makedirs(PREV, exist_ok=True)


def render(mp_path):
    mp = json.load(open(mp_path, encoding="utf-8"))
    W, H, TS = mp["width"], mp["height"], mp["tilewidth"]
    sheets = {}
    for ts in mp["tilesets"]:
        sheets[ts["firstgid"]] = Image.open(os.path.join(OUT, ts["image"])).convert("RGBA")
    firsts = sorted(sheets)

    def draw(canvas, layer):
        data = layer["data"]
        for i, g in enumerate(data):
            if not g:
                continue
            fg = max(f for f in firsts if f <= g)
            sh = sheets[fg]
            lg = g - fg
            cols = sh.size[0] // TS
            sx, sy = (lg % cols) * TS, (lg // cols) * TS
            canvas.alpha_composite(sh.crop((sx, sy, sx + TS, sy + TS)), ((i % W) * TS, (i // W) * TS))

    canvas = Image.new("RGBA", (W * TS, H * TS))
    for layer in mp["layers"]:
        if layer.get("type") != "tilelayer" or not layer.get("visible", True):
            continue
        draw(canvas, layer)
    return canvas


if __name__ == "__main__":
    sel = sys.argv[1:] or ["world_r10_c5", "world_r0_c0", "world_r13_c8", "world_r5_c10"]
    for name in sel:
        p = os.path.join(OUT, name + ".json")
        if not os.path.exists(p):
            print("missing", name)
            continue
        im = render(p)
        im.thumbnail((768, 768))
        im.save(os.path.join(PREV, name + ".png"))
        print("ok", name)
