"""Compose the new world map with the ORIGINAL Kaetram frame on top.

mapframe.png structure (measured): ~2px transparent margin, then a 2-3px
red-brown/gold border ring, then the map content (ocean). We take the frame
ring from mapframe.png (everything outside the inner content window) and
paste it OVER the new world map. The ring is thin, so the new map keeps
nearly the full 270x180 canvas — but to preserve the ENTIRE decorative ring
(corners bulge inward more), we instead paste the new map's ocean area UNDER
the ring: scale the new map slightly and center it so its edges are covered
by the ring.

Simpler robust approach: paste the ring pixels from mapframe.png over the
new map 1:1 (both are 270x180). The ring only covers 2-6px at the edges —
the new map's ocean edge gets clipped slightly, which is invisible since
the new map is all ocean at its border too.
"""
import numpy as np
from PIL import Image

ref = Image.open("web_client/public/ui/kaetram/interface/mapframe.png").convert("RGBA")
new = Image.open("exported_map_art/worldmap_true_96c.png").convert("RGBA")
assert new.size == (270, 180), new.size

ref_a = np.array(ref)
new_a = np.array(new)

# Frame ring mask: opaque in ref AND (red-brown border OR gold accent).
# Border colors measured: dark red (112,24,8), darker red (64,0,0),
# gold (248,176,40 / 248,232,104 / 248,240,136).
r = ref_a[:, :, 0].astype(int)
g = ref_a[:, :, 1].astype(int)
b = ref_a[:, :, 2].astype(int)
a = ref_a[:, :, 3]
is_border_red = (a > 100) & (r > 40) & (r < 180) & (g < 80) & (b < 90)
is_gold = (a > 100) & (r > 200) & (g > 120) & (b < 150) & (g < 250)
ring = is_border_red | is_gold
print("ring px:", ring.sum())

# Composite: new map, then ring pixels on top.
out = new_a.copy()
out[ring] = ref_a[ring]
img = Image.fromarray(out, "RGBA")
img.save("exported_map_art/worldmap_framed.png")
print("saved -> exported_map_art/worldmap_framed.png")

# x3 view version
img.resize((810, 540), Image.NEAREST).save("exported_map_art/worldmap_framed_x3.png")

# markers visualization on the framed map
import json
mk = json.load(open("exported_map_art/warp_markers.json"))
vis = img.resize((810, 540), Image.NEAREST).convert("RGB")
from PIL import ImageDraw
d = ImageDraw.Draw(vis)
for m in mk["markers"]:
    x, y = m["x"] / 270 * 810, m["y"] / 180 * 540
    d.ellipse([x - 8, y - 8, x + 8, y + 8], outline=(0, 255, 0), width=2)
    d.text((x + 9, y - 6), str(m["id"]), fill=(0, 255, 0))
vis.save("exported_map_art/worldmap_framed_markers_x3.png")
print("saved marker visualization")
