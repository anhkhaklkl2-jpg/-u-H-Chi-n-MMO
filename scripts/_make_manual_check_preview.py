# Embed the manual marker check image into a preview page.
from PIL import Image, ImageDraw
import base64
import io

src = Image.open(r"C:\Users\phant\Downloads\ChatGPT Image 01_39_44 28 thg 9, 2026.png").convert("RGB")
pts = [[195, 61], [247, 27], [230, 157], [242, 123], [132, 150], [187, 113],
       [126, 40], [90, 42], [22, 25], [51, 77], [39, 155], [86, 111],
       [119, 66], [247, 85]]
W, H = src.size
sx, sy = W / 270, H / 180
vis = src.copy()
d = ImageDraw.Draw(vis)
for i, (mx, my) in enumerate(pts):
    x, y = mx * sx, my * sy
    r = 22
    d.ellipse([x - r, y - r, x + r, y + r], outline=(0, 255, 60), width=5)
    d.text((x + r + 6, y - 10), str(i), fill=(0, 255, 60))

buf = io.BytesIO()
vis.save(buf, "PNG")
b64 = base64.b64encode(buf.getvalue()).decode()

html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Marker thủ công — kiểm tra</title>
<style>body{{background:#1a1c23;color:#dde;font-family:system-ui;padding:20px;margin:0}}
h1{{font-size:18px}}p{{color:#99a;font-size:13px}}img{{max-width:100%;border:1px solid #333}}</style></head>
<body>
<h1>14 marker khoanh thủ công (mã của bạn) — kiểm tra</h1>
<p>Đã lưu vào exported_map_art/warp_markers.json. Đúng hết là chốt.</p>
<img src="data:image/png;base64,{b64}">
</body></html>"""

with open("exported_map_art/markers_manual_check.html", "w", encoding="utf-8") as f:
    f.write(html)
print("ok")
