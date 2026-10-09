"""Final marker detection: the annotated map has 14 translucent red circles.
The overlay shifts covered pixels toward red uniformly, so we diff the marked
image against the clean one, then find CIRCLES via a template-matching score
(sum of diff inside a disc, normalized by the disc area — a disc fully inside
a marker scores maximum). Centers are saved to warp_markers.json in 270×180
map space, numbered left-to-right, top-to-bottom (0-13)."""
import math
import json
from PIL import Image, ImageDraw

mark = Image.open("_tmp_marked.png").convert("RGB")
clean = Image.open("_tmp_clean.png").convert("RGB").resize(mark.size)
w, h = mark.size

# diff strength per pixel (positive = shifted toward red by the overlay)
diff = [[0.0] * w for _ in range(h)]
for y in range(h):
    for x in range(w):
        r1, g1, b1 = mark.getpixel((x, y))
        r2, g2, b2 = clean.getpixel((x, y))
        diff[y][x] = ((r1 - g1) - (r2 - g2)) / 2.0

# integral image for fast disc sums
II = [[0.0] * (w + 1) for _ in range(h + 1)]
for y in range(h):
    rowsum = 0.0
    for x in range(w):
        rowsum += diff[y][x]
        II[y + 1][x + 1] = II[y][x + 1] + rowsum

def disc_sum(cx, cy, r):
    x0, x1 = max(0, cx - r), min(w - 1, cx + r)
    y0, y1 = max(0, cy - r), min(h - 1, cy + r)
    return II[y1 + 1][x1 + 1] - II[y0][x1 + 1] - II[y1 + 1][x0] + II[y0][x0]

# marker radius in screenshot px: ~13-15. Score disc of r=10.
R = 10
AREA = math.pi * R * R
cands = []
for cy in range(R, h - R, 2):
    for cx in range(R, w - R, 2):
        s = disc_sum(cx, cy, R)
        cands.append((s / AREA, cx, cy))
cands.sort(reverse=True)

# greedy pick: peaks separated by >= 30px
chosen = []
for score, cx, cy in cands:
    if score < 4:  # disc-average: markers are flat ~20-40, noise averages ~0
        break
    if all(math.hypot(cx - a, cy - b) >= 30 for a, b in chosen):
        chosen.append((cx, cy))
        if len(chosen) == 14:
            break

print(f"found {len(chosen)} markers (target 14)")
# number left-to-right, top-to-bottom
chosen.sort(key=lambda p: (p[1] // 40, p[0]))
res = []
for i, (cx, cy) in enumerate(chosen):
    mx, my = cx / w * 270, cy / h * 180
    res.append({"id": i, "x": round(mx, 1), "y": round(my, 1)})
    print(f"  #{i}: screen=({cx},{cy}) -> map=({mx:.1f},{my:.1f})")

json.dump({"source_size": [w, h], "markers": res},
          open("exported_map_art/warp_markers.json", "w"), indent=2)

vis = mark.copy()
d = ImageDraw.Draw(vis)
for m in res:
    sx, sy = m["x"] / 270 * w, m["y"] / 180 * h
    d.ellipse([sx - 11, sy - 11, sx + 11, sy + 11], outline=(0, 255, 0), width=2)
    d.text((sx + 12, sy - 6), str(m["id"]), fill=(0, 255, 0))
vis.save("_tmp_markers_final.png")
print("saved -> exported_map_art/warp_markers.json + _tmp_markers_final.png")
