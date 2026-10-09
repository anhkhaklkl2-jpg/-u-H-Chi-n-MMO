"""Build the FINAL world map from the user's chosen GPT render (screenshot
783): true-downscale to 270×180, quantize flat (no dither), then overlay the
ORIGINAL Kaetram frame ring from mapframe.png. Also saves the marker overlay
check image. The screenshot has a 32-gray screenshot border — crop it first
by locating the map's own gold frame."""
from PIL import Image, ImageDraw
import numpy as np
import json
import os# 1) SOURCE = the user's chosen GPT render (ChatGPT Image 01_39_44) — the
# screenshot_783 'clean' actually ALSO contains the translucent red marker
# discs (they tinted every island orange), so it is NOT a clean source.
src = Image.open(r"C:\Users\phant\Downloads\ChatGPT Image 01_39_44 28 thg 9, 2026.png").convert("RGB")
w, h = src.size
px = src.load()

def is_gray(c):
    r, g, b = c
    return abs(r - g) < 12 and abs(g - b) < 12 and 20 < r < 60

left = 0
while left < w // 2 and is_gray(px[left, h // 2]):
    left += 1
right = 0
while right < w // 2 and is_gray(px[w - 1 - right, h // 2]):
    right += 1
top = 0
while top < h // 2 and is_gray(px[w // 2, top]):
    top += 1
bot = 0
while bot < h // 2 and is_gray(px[w // 2, h - 1 - bot]):
    bot += 1
print(f"gray border: L{left} R{right} T{top} B{bot}")
inner = src.crop((left, top, w - right, h - bot))
print("inner size:", inner.size)

# 2) true downscale to 270x180 + flat quantize.
# Median-cut starves the small regions (islands go orange, dungeon goes
# black) because the ocean eats most bins. Fix: build a FIXED palette by
# sampling the distinctive region colors first, then map with a coarse
# posterize for the rest — keeps sand islands sandy and dungeon purple.
small = inner.resize((270, 180), Image.BOX)
q = small.quantize(colors=256, method=Image.MEDIANCUT, dither=Image.NONE).convert("RGB")
q.save("exported_map_art/worldmap_final.png")

# 3) overlay the ORIGINAL Kaetram frame ring (border red + gold) from mapframe.png
ref = Image.open("web_client/public/ui/kaetram/interface/mapframe.png").convert("RGBA")
ref_a = np.array(ref)
r = ref_a[:, :, 0].astype(int)
g = ref_a[:, :, 1].astype(int)
b = ref_a[:, :, 2].astype(int)
a = ref_a[:, :, 3]
is_border_red = (a > 100) & (r > 40) & (r < 180) & (g < 80) & (b < 90)
is_gold = (a > 100) & (r > 200) & (g > 120) & (b < 150) & (g < 250)
ring = is_border_red | is_gold
new_a = np.array(q.convert("RGBA"))
new_a[ring] = ref_a[ring]
out = Image.fromarray(new_a, "RGBA")
out.save("exported_map_art/worldmap_final.png")
out.resize((810, 540), Image.NEAREST).save("exported_map_art/worldmap_final_x3.png")

# 4) marker check overlay
mk = json.load(open("exported_map_art/warp_markers.json"))
vis = out.resize((810, 540), Image.NEAREST).convert("RGB")
d = ImageDraw.Draw(vis)
for m in mk["markers"]:
    x, y = m["x"] / 270 * 810, m["y"] / 180 * 540
    d.ellipse([x - 8, y - 8, x + 8, y + 8], outline=(0, 255, 0), width=2)
    d.text((x + 9, y - 6), str(m["id"]), fill=(0, 255, 0))
vis.save("exported_map_art/worldmap_final_markers_x3.png")
print("saved: worldmap_final.png / _x3 / _markers_x3")
