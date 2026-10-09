# Preview = the user's ORIGINAL GPT map (untouched) + the 14 numbered
# markers. No recolor, no quantize, no frame swap.
from PIL import Image, ImageDraw
import base64
import io
import json

src = Image.open(r"C:\Users\phant\Downloads\ChatGPT Image 01_39_44 28 thg 9, 2026.png").convert("RGB")
mk = json.load(open("exported_map_art/warp_markers.json"))
W, H = src.size  # 1536x1024

vis = src.copy()
d = ImageDraw.Draw(vis)
sx = W / 270  # markers are stored in 270x180 space
sy = H / 180
for m in mk["markers"]:
    x, y = m["x"] * sx, m["y"] * sy
    r = 22
    d.ellipse([x - r, y - r, x + r, y + r], outline=(0, 255, 60), width=5)
    d.text((x + r + 6, y - 10), f"#{m['id']}", fill=(0, 255, 60))


def b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Map gốc + 14 marker</title>
<style>body{{background:#1a1c23;color:#dde;font-family:system-ui;padding:20px;margin:0}}
h1{{font-size:18px}}p{{color:#99a;font-size:13px}}img{{max-width:100%;border:1px solid #333}}</style></head>
<body>
<h1>Map GỐC của bạn + 14 marker (#0–13) — không sửa gì khác</h1>
<p>Vị trí chấm xanh = tọa độ đã lưu trong exported_map_art/warp_markers.json (hệ 270×180).</p>
<img src="data:image/png;base64,{b64(vis)}">
</body></html>"""

with open("exported_map_art/worldmap_preview.html", "w", encoding="utf-8") as f:
    f.write(html)
print("ok")
