# Comparison sheet for the true-pixel world map variants (48/96/160 colors).
from PIL import Image, ImageDraw
import base64
import io

imgs = []
for n in (48, 96, 160):
    im = Image.open(f"exported_map_art/worldmap_true_{n}c_x3.png")
    imgs.append((n, im))

W = max(im.width for _, im in imgs)
H = sum(im.height + 40 for _, im in imgs)
sheet = Image.new("RGB", (W, H), (26, 28, 35))
d = ImageDraw.Draw(sheet)
y = 0
for n, im in imgs:
    d.text((8, y + 12), f"{n} mau (phien ban {n} colors)", fill=(220, 225, 235))
    sheet.paste(im, (0, y + 36))
    y += im.height + 40

buf = io.BytesIO()
sheet.save(buf, "PNG")
b64 = base64.b64encode(buf.getvalue()).decode()
html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>World map - true pixel</title>
<style>body{{background:#1a1c23;color:#dde;font-family:system-ui;padding:20px;margin:0}}h1{{font-size:18px}}p{{color:#99a;font-size:13px}}</style></head>
<body><h1>World map - downscale THAT ve luoi 270x180 + palette phang (x3 de xem)</h1>
<p>Cung 1 anh GPT ve, xu ly offline: giam ve dung luoi pixel 270x180 + rut gon palette (khong dither) = pixel art that 100%. Chon 1 trong 3 muc: 48 mau (so gian nhat, giong Kaetram nhat), 96, 160 (giu chi tiet hon).</p>
<img src="data:image/png;base64,{b64}" style="max-width:100%;image-rendering:pixelated"></body></html>"""
with open("exported_map_art/worldmap_true_preview.html", "w", encoding="utf-8") as f:
    f.write(html)
print("html ok")
