# -*- coding: utf-8 -*-
"""So sanh font pixel co tieng Viet cho box thoai — xuat fonts_preview.html."""
import base64, os, sys
sys.stdout.reconfigure(errors="replace")
from PIL import Image, ImageDraw, ImageFont

OUT = r"Nơilấyassetsngoài/_demo_dialog"
FDIR = os.path.join(OUT, "fonts")
BOX = Image.open(r"Nơilấyassetsngoài/Ninja Adventure - Asset Pack/Ninja Adventure - Asset Pack/Ui/Dialog/DialogBox.png").convert("RGBA")

SAMPLE = "Chào mừng đến Chợ Bà! Gạc Đặc ơư ẵế — bán 3x Sushi = 15 xu?"

FONTS = [
    ("VT323 (RECOMMENDED)", "VT323-Regular.ttf", 22,
     "DU 100% dau tieng Viet - dang thin bitmap gan giong font thoai goc"),
]

STRIP_W, STRIP_H = 624, 116
rows = []
for name, fname, size, note in FONTS:
    cv = Image.new("RGBA", (STRIP_W, STRIP_H), (0, 0, 0, 0))
    box2 = BOX.resize((STRIP_W - 24, 116), Image.NEAREST)
    cv.alpha_composite(box2, (12, 0))
    f = ImageFont.truetype(os.path.join(FDIR, fname), size)
    d = ImageDraw.Draw(cv)
    d.text((36, 38), SAMPLE, font=f, fill=(63, 40, 50))
    rows.append((name, note, cv))

# dong tham chieu: font compose hien tai
ref = Image.new("RGBA", (STRIP_W, STRIP_H), (0, 0, 0, 0))
ref.alpha_composite(BOX.resize((STRIP_W - 24, 116), Image.NEAREST), (12, 0))
sys.path.insert(0, OUT)
import importlib.util
spec = importlib.util.spec_from_file_location("bd", os.path.join(OUT, "build_demo.py"))
bd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bd)
x = 36
for ch in SAMPLE:
    g = bd.glyph_vn(ch)
    g2 = g.resize((16, 28), Image.NEAREST)
    tint = Image.new("RGBA", g2.size, (63, 40, 50, 255))
    tint.putalpha(g2.getchannel("A"))
    ref.alpha_composite(tint, (x, 44))
    x += 16
rows.append(("HIEN TAI (compose)", "Dau tu ghep - chua sach nhu ban thay", ref))

# chu thich: cac font khac da bi loai vi thieu glyph co dau (tofu)
NOTE_LINE = "Da kiem tra 13 font pixel khac (Tiny5, Jersey, Pixelify, Silkscreen, PressStart2P, DotGothic16, Micro5, Jacquard...) - TAT CA thieu glyph co dau tieng Viet (tofu). Chi VT323 du 100%."

def b64img(im):
    p = os.path.join(OUT, "_tmp_font.png")
    im.convert("RGB").save(p)
    with open(p, "rb") as fh:
        return base64.b64encode(fh.read()).decode()

items = []
for name, note, cv in rows:
    items.append('{name:"%s",note:"%s",img:"data:image/png;base64,%s"}'
                 % (name, note, b64img(cv)))

html = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>So sanh font tieng Viet cho box thoai</title>
<style>
 body { background:#141425; margin:0; padding:16px; font-family:system-ui; color:#cfd2e8; }
 .wrap { max-width:680px; margin:0 auto; }
 h2 { font-size:20px; margin:4px 0 8px; }
 .card { background:#1c2033; border:1px solid #343a5c; border-radius:10px; padding:10px; margin-bottom:12px; }
 .card:hover { border-color:#5b6ee1; }
 .card img { width:100%; height:auto; image-rendering:pixelated; border-radius:6px; display:block; background:#000; }
 .card b { color:#fff; }
 .card span { color:#9aa0c0; font-size:12px; margin-left:8px; }
 .ref { opacity:.8; }
</style>
<body><div class="wrap">
<h2>&#128300; Chon font tieng Viet cho box thoai</h2>
<div style="opacity:.7;font-size:12px;margin-bottom:4px">Render dung cau demo tren DialogBox goc (CC0). Dong cuoi = font compose hien tai de doi chieu.</div>
<div style="color:#e8a; font-size:12px;margin-bottom:12px">__NOTE__</div>
<div id="list"></div>
</div>
<script>
const items = [__ITEMS__];
document.getElementById("list").innerHTML = items.map((it, i) =>
  '<div class="card' + (i === items.length - 1 ? ' ref' : '') + '"><img src="' + it.img + '"><div style="margin-top:6px"><b>' + i + '. ' + it.name + '</b><span>' + it.note + '</span></div></div>'
).join("");
</script>
"""
html = html.replace("__ITEMS__", ",".join(items)).replace("__NOTE__", NOTE_LINE)
p = os.path.join(OUT, "fonts_preview.html")
with open(p, "w", encoding="utf-8") as f:
    f.write(html)
print("wrote", p, os.path.getsize(p), "bytes,", len(items), "fonts")
