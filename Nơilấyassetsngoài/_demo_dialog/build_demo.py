# -*- coding: utf-8 -*-
"""Demo hoi thoai NPC — Ninja Adventure pack (CC0). Phien ban 3 (ASCII-safe).
+ Font pixel tieng Viet CO DAU: tu dong decompose bang unicodedata, compose
  len glyph font8x8 goc -> cell 8x14. Khong go truc tiep ky tu co dau trong file.
+ Nameplate bam sat canh tren box.
+ GIF animation: idle 4-frame, emote nari, arrow chop, typewriter.
Xuat: demo_step{i}.png/.gif, demo_all.png, font_vn_8x14.png, demo_dialog.html
"""
import base64, os, sys, unicodedata
sys.stdout.reconfigure(errors="replace")
from PIL import Image, ImageDraw, ImageFont

ROOT = "N\u01a1il\u1ea5yassetsngo\u00e0i/Ninja Adventure - Asset Pack/Ninja Adventure - Asset Pack"
OUT  = "N\u01a1il\u1ea5yassetsngo\u00e0i/_demo_dialog"
os.makedirs(OUT, exist_ok=True)
J = lambda *p: os.path.join(ROOT, *p)
def L(*p): return Image.open(J(*p)).convert("RGBA")

W, H = 624, 352

# ================= FONT 8x8 GOC =================
ORDER = (' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`'
         'abcdefghijklmnopqrstuvwxyz{|}~')
_sheet = L("Ui/Font", "font8x8.png")
CHARS = {}
for _i, _ch in enumerate(ORDER):
    _cx, _cy = (_i % 15) * 8, (_i // 15) * 8
    CHARS[_ch] = _sheet.crop((_cx, _cy, _cx + 8, _cy + 8))

# ================= COMPOSE TIENG VIET (cell 8x14) =================
CELL_W, CELL_H, BASE_Y = 8, 14, 5

# ------------------ dien dang dau: (x, dy) voi dy keo tu anchor (dinh chu) ------------------
# 2-row mark: dy=0 -> row anchor-2, dy=1 -> row anchor-1 (CHAM SAT dinh chu)
TONE2 = {
    'acute': [(3,1),(4,0)],           # sac: cao ben phai
    'grave': [(3,0),(4,1)],           # huyen: cao ben trai
    'hook':  [(2,1),(3,0),(4,1)],     # hoi
    'tilde': [(2,1),(3,0),(4,0),(5,1)],
}
SHELL2 = {
    'circ':  [(2,1),(3,0),(4,0),(5,1)],   # ^
    'breve': [(2,0),(3,1),(4,1),(5,0)],   # v (trang)
}
P_DOTBELOW = [(3,13),(4,13)]
P_HORN_O   = [(6,10),(7,10),(7,11)]
P_HORN_U   = [(6,9),(7,9),(7,10)]
HORN_PX = {'o': P_HORN_O, 'u': P_HORN_U}
COMB = {'\u0301': 'acute', '\u0300': 'grave', '\u0309': 'hook',
        '\u0303': 'tilde', '\u0323': 'dotbelow', '\u0302': 'circ',
        '\u0306': 'breve', '\u031b': 'horn'}

VN = {}
# dung cho tat ca ky tu Latin mo rong: Latin-1 (A\u00c0-\u00ff), \u0102\u0103, \u0110\u0111 + d\u1ea3i ti\u1ebfng Vi\u1ec7t U+1EA0-1EFF
for cp in list(range(0xC0, 0x0180)) + [0x1A0, 0x1A1, 0x1AF, 0x1B0] + list(range(0x1EA0, 0x1F00)):
    ch = chr(cp)
    d = unicodedata.normalize('NFD', ch)
    base, parts = d[0].lower(), [COMB[c] for c in d[1:] if c in COMB]
    if base not in 'aeiouy':
        continue
    if 'horn' in parts:
        tone = next((t for t in parts if t in TONE2), None)
        key = ('horn_' + base + ('_' + tone if tone else ''))
    elif 'circ' in parts:
        tone = next((t for t in parts if t in TONE2), 'none')
        key = 'circ_' + tone if tone != 'none' else 'circ'
    elif 'breve' in parts:
        tone = next((t for t in parts if t in TONE2), 'none')
        key = 'breve_' + tone if tone != 'none' else 'breve'
    else:
        key = parts[0] if parts else 'none'
    VN[ch] = (base, key)
VN['\u0111'] = ('d', 'bar')
VN['\u0110'] = ('D', 'bar')

def compose(ch):
    """Glyph RGBA 8x14 — dau TU DONG canh theo dinh that cua chu (bbox)."""
    g = Image.new('RGBA', (CELL_W, CELL_H), (0, 0, 0, 0))
    base, key = VN.get(ch, (ch, 'none'))
    src = CHARS.get(base) or CHARS.get(ch)
    if src is None:
        return g
    g.alpha_composite(src, (0, BASE_Y))
    d = ImageDraw.Draw(g)
    if key == 'bar':
        # \u0111/\u0110: G\u1ea0CH NGANG CROSS QUA GI\u1eeeA CH\u1eee (chu\u1ea9n Vi\u1ec7t),
        # t\u00ednh mid t\u1eeb bbox th\u1eadt c\u1ee7a ch\u1eef, nh\u00f4 1px m\u1ed7i ben
        bb = g.getbbox()
        # d thuong: gach cao hon 1px so voi mat chu; D hoa giu ngang mat chu
        mid = (bb[1] + bb[3]) // 2 - (2 if ch.islower() else 1)
        d.line((max(0, bb[0] - 1), mid, min(7, bb[2]), mid),
               fill=(255, 255, 255, 255), width=1)
        return g
    # anchor = row dau tien co pixel cua chu (bbox top)
    bb = g.getbbox()
    anchor = bb[1] if bb else BASE_Y
    if key.startswith('horn_'):
        parts = key.split('_')            # horn, o/u, [tone]
        for px in HORN_PX[parts[1]]:
            g.putpixel(px, (255, 255, 255, 255))
        if len(parts) > 2 and parts[2] in TONE2:
            for x, dy in TONE2[parts[2]]:
                g.putpixel((x, anchor - 2 + dy), (255, 255, 255, 255))
        return g
    if key == 'dotbelow':
        for px in P_DOTBELOW:
            g.putpixel(px, (255, 255, 255, 255))
        return g
    if '_' in key:                        # compound: circ/breve + tone
        shell, tone = key.split('_', 1)
        if shell in SHELL2:
            for x, dy in SHELL2[shell]:
                g.putpixel((x, anchor - 2 + dy), (255, 255, 255, 255))
            if tone in TONE2:
                for x, dy in TONE2[tone]:
                    g.putpixel((x, anchor - 4 + dy), (255, 255, 255, 255))
            elif tone == 'dotbelow':
                for px in P_DOTBELOW:
                    g.putpixel(px, (255, 255, 255, 255))
        return g
    if key in SHELL2:
        for x, dy in SHELL2[key]:
            g.putpixel((x, anchor - 2 + dy), (255, 255, 255, 255))
        return g
    if key in TONE2:
        for x, dy in TONE2[key]:
            g.putpixel((x, anchor - 2 + dy), (255, 255, 255, 255))
    return g

_GLYPH_CACHE = {}
def glyph_vn(ch):
    if ch not in _GLYPH_CACHE:
        _GLYPH_CACHE[ch] = compose(ch)
    return _GLYPH_CACHE[ch]

# ================= VE CHU =================
def _tint(g, color):
    solid = Image.new("RGBA", g.size, color)
    solid.putalpha(g.getchannel("A"))
    return solid

WHITE = (255, 255, 255, 255)
GOLD  = (240, 176, 80, 255)
INK   = (63, 40, 50, 255)
DARK  = (20, 27, 27, 255)

# ---- VT323: font pixel DU 100% dau tieng Viet (OFL) ----
# VT323 thiet ke tren luoi 16px: CHI dung size boi cua 16 (16/32/48) thi dau
# (nhat la dau chong: ang+nga, mu+nga) tach lop ro rang, khong bi dap nau.
VT_PATH = os.path.join(OUT, "fonts", "VT323-Regular.ttf")
VT32 = ImageFont.truetype(VT_PATH, 32)
VT24 = ImageFont.truetype(VT_PATH, 24)

def draw_vn(cv, xy, s, color=WHITE, scale=2):
    """Render chu tieng Viet bang VT323 24px — vua khop 3 dong trong box."""
    d = ImageDraw.Draw(cv)
    d.text(xy, s, font=VT24, fill=color)

def nameplate(cv, x, y_box_top, s, scale=2):
    """Bang ten nen toi vang: tab lun 6px vao vien box, rong theo do rong VT323."""
    w = int(VT24.getlength(s)) + 16
    h = 34
    y0 = y_box_top - h + 12  # xuong tong 6px (tab cam vao vien box)
    d = ImageDraw.Draw(cv)
    d.rectangle((x, y0, x + w, y0 + h), fill=DARK, outline=GOLD, width=2)
    d.text((x + 8, y0 + 2), s, font=VT24, fill=GOLD)

# ================= NEN + TAI SAN =================
field = L("Backgrounds/Tilesets", "TilesetField.png")
g1 = field.crop((16, 80, 32, 96))
g2 = field.crop((16, 96, 32, 112))
shop = Image.new("RGBA", (W, H))
for ty in range(0, H, 16):
    for tx in range(0, W, 16):
        shop.alpha_composite(g2 if (tx // 16 + ty // 16) % 2 else g1, (tx, ty))

fl = L("Backgrounds/Animated/Flower", "SpriteSheet16x16.png").crop((0, 0, 16, 16))

box     = L("Ui/Dialog", "DialogBoxFaceset.png")
# o chan dung = o TOI DAC (20,27,27) nua trai cua box, do bang tan suat hang/cot:
# rows 14..51 x cols 6..43 -> rect 38x38 (dung bang kich thuoc faceset 38x38)
WIN_BB = (6, 14, 44, 52)  # (x0, y0, x1, y1) trong he toa do cua box goc 300x58
choice  = L("Ui/Dialog", "ChoiceBox.png")
btn_yes = L("Ui/Dialog", "YesButton.png")
btn_no  = L("Ui/Dialog", "NoButton.png")
arrow   = L("Ui/Arrow.png")

EM = lambda i: L("Ui/Emote", "emote%d.png" % i).resize((28, 26), Image.NEAREST)
em_bang, em_sad, em_heart, em_ask = EM(1), EM(15), EM(29), EM(23)

chest = L("Items/Treasure", "LittleTreasureChest.png").resize((32, 32), Image.NEAREST)
bag   = L("Items/Object", "MoneyBag.png").resize((32, 32), Image.NEAREST)
crate = L("Items/Object", "CrateEmpty.png").resize((32, 32), Image.NEAREST)
sushi = L("Items/Food", "Sushi.png").convert("RGBA").resize((24, 24), Image.NEAREST)

def idle_frame(name, idx):
    sh = L("Actor/Character", name, "SpriteSheet.png")
    idx %= 4
    return sh.crop((0, idx * 16, 16, idx * 16 + 16))

NPC, PL = "MaskGoldRacoon", "NinjaRed"
npc_face = L("Actor/Character", NPC, "Faceset.png")
pl_face  = L("Actor/Character", PL,  "Faceset.png")

# ================= RENDER 1 FRAME =================
BOX_X, BOX_Y = 12, 232
TXT_X = 144

def render(face_img, who, lines, em_npc=None, em_pl=None, choices=False,
           has_arrow=True, reveal=None, bob=0, em_off=0, arrow_on=True):
    cv = Image.new("RGBA", (W, H))
    cv.alpha_composite(shop)
    for fx, fy in ((160, 120), (320, 88), (544, 140), (240, 60)):
        cv.alpha_composite(fl, (fx, fy))
    cv.alpha_composite(crate, (24, 168))
    cv.alpha_composite(bag, (320, 184))
    cv.alpha_composite(chest, (516, 176))
    cv.alpha_composite(sushi, (556, 196))
    # sprites DUNG GIUA san (khong cham bang ten vien vang)
    cv.alpha_composite(idle_frame(PL, bob).resize((48, 48), Image.NEAREST), (270, 164))
    cv.alpha_composite(idle_frame(NPC, bob).transpose(Image.FLIP_LEFT_RIGHT)
                       .resize((48, 48), Image.NEAREST), (372, 164))
    if em_pl:  cv.alpha_composite(em_pl, (280, 132 + em_off))
    if em_npc: cv.alpha_composite(em_npc, (382, 130 + em_off))
    box2  = box.resize((600, 116), Image.NEAREST)
    cv.alpha_composite(box2, (BOX_X, BOX_Y))
    # face KHIT o window: scale theo dung bbox vung trong suot * 2
    wx0, wy0, wx1, wy1 = WIN_BB
    fw, fh = (wx1 - wx0) * 2, (wy1 - wy0) * 2
    face2 = face_img.resize((fw, fh), Image.NEAREST)
    cv.alpha_composite(face2, (BOX_X + wx0 * 2, BOX_Y + wy0 * 2))
    nameplate(cv, 22, BOX_Y, who)   # trai 2px, xuong 3px
    if reveal is None:
        shown = list(lines)
    else:
        n = reveal
        shown = []
        for ln in lines:
            if n <= 0:
                break
            shown.append(ln[:n]); n -= len(ln)
    # interior trang cua box = y 260..335 (76px); 3 dong VT323 24px + spacing 26 = 76px vua khop
    y = 258 if len(lines) >= 3 else 272
    for ln in shown:
        draw_vn(cv, (TXT_X, y), ln, color=INK)
        y += 26
    if has_arrow and arrow_on:
        cv.alpha_composite(arrow.resize((26, 26), Image.NEAREST), (564, 300))
    if choices:
        cv.alpha_composite(choice.resize((128, 40), Image.NEAREST), (478, 292))
        cv.alpha_composite(btn_yes.resize((52, 32), Image.NEAREST), (484, 296))
        cv.alpha_composite(btn_no.resize((52, 32), Image.NEAREST), (548, 296))
    return cv

# ================= 4 BUOC (tieng Viet qua \u escape) =================
STEPS = [
    dict(face=npc_face,
         who="G\u1ea0C \u0110\u1eb6C",
         lines=["Ch\u00e0o m\u1eebng \u0111\u1ebfn Ch\u1ee3 B\u00e0!",
                "Ta l\u00e0 G\u1ea1c \u0110\u1eb7c, \u0111\u1ed5i th\u00fa",
                "h\u01a1n qu\u00e1i... tr\u1ea3 b\u1eb1ng xu!"],
         em_npc=em_bang,
         cap="Box g\u1ed1c + face d\u00e1n \u00f4 window + nameplate vi\u1ec1n v\u00e0ng b\u00e1m box + emote ! + Arrow"),
    dict(face=npc_face,
         who="G\u1ea0C \u0110\u1eb6C",
         lines=["Qu\u00e1i ch\u1ebft r\u01a1i hom ho\u1eb7c",
                "r\u01b0\u01a1ng? \u0110em \u0111\u1ebfn ta!",
                "C\u00e0ng hi\u1ebfm, c\u00e0ng nhi\u1ec1u xu"],
         em_pl=em_sad,
         cap="Emote kh\u00f3c g\u1eafn v\u00e0o ng\u01b0\u1eddi ch\u01a1i khi NPC \u0111ang n\u00f3i (bubble theo \u0111\u00fang nh\u00e2n v\u1eadt)"),
    dict(face=pl_face, who="NINJA \u0110\u1ecf",
         lines=["\u0110\u1ec3 t\u1edbi \u0111em th\u1eed!",
                "3 con Slime h\u00f4m nay,",
                "he he, ch\u1edd t\u1edbi 5 ph\u00fat!"],
         em_pl=em_heart,
         cap="\u0110\u1ed4I ch\u00e2n dung: faceset + t\u00ean chuy\u1ec3n sang ng\u01b0\u1eddi ch\u01a1i, emote tr\u00e1i tim"),
    dict(face=npc_face,
         who="G\u1ea0C \u0110\u1eb6C",
         lines=["B\u00e1n 3x Sushi = 15 xu?",
                "Ch\u1ed1t \u0111\u01a1n kh\u00f4ng?"],
         em_npc=em_ask, choices=True, has_arrow=False,
         cap="ChoiceBox + n\u00fat YES/NO s\u1eb5n ch\u1eef + emote ? \u2014 bu\u1ed9c confirm giao d\u1ecbch"),
]

def build_frames(spec, n=16):
    total = sum(len(l) for l in spec["lines"])
    frames = []
    for f in range(n):
        reveal = min(total, int(total * (f + 1) / max(1, n - 6)))
        em_off = [0, -1, -2, -1][f % 4]
        arrow_on = (not spec.get("has_arrow", True)) or (f >= 8 and (f // 2) % 2 == 0)
        frames.append(render(spec["face"], spec["who"], spec["lines"],
                             em_npc=spec.get("em_npc"), em_pl=spec.get("em_pl"),
                             choices=spec.get("choices", False),
                             has_arrow=spec.get("has_arrow", True),
                             reveal=reveal, bob=f % 4, em_off=em_off, arrow_on=arrow_on))
    return frames

gif_paths, png_paths = [], []
for i, spec in enumerate(STEPS, 1):
    frames = build_frames(spec)
    p_png = os.path.join(OUT, "demo_step%d.png" % i)
    frames[-1].convert("RGB").save(p_png)
    png_paths.append(p_png)
    p_gif = os.path.join(OUT, "demo_step%d.gif" % i)
    frames[0].convert("RGB").save(p_gif, save_all=True,
                                  append_images=[f.convert("RGB") for f in frames[1:]],
                                  duration=110, loop=0)
    gif_paths.append(p_gif)
    print("wrote step", i)

gap = 12
mont = Image.new("RGB", (W * 2 + gap * 3, H * 2 + gap * 3), (24, 20, 37))
for i, p in enumerate(png_paths):
    mont.paste(Image.open(p), (gap + (i % 2) * (W + gap), gap + (i // 2) * (H + gap)))
mont.save(os.path.join(OUT, "demo_all.png"))
print("wrote demo_all.png")

# ---- font VN sheet (ky tu co dau that, dung lam asset tai dung) ----
chars = sorted(set(list(VN.keys()) + list("ABCXYZabcxyz0123456789.,!?-:+/()")))
cols = 15
rows = (len(chars) + cols - 1) // cols
sheet = Image.new("RGBA", (cols * CELL_W, rows * CELL_H), (0, 0, 0, 0))
for i, ch in enumerate(chars):
    sheet.alpha_composite(glyph_vn(ch), ((i % cols) * CELL_W, (i // cols) * CELL_H))
sheet.save(os.path.join(OUT, "font_vn_8x14.png"))
print("wrote font_vn_8x14.png (%d glyphs)" % len(chars))

# ================= HTML self-contained =================
def b64(p):
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode()

steps_js = "[" + ",".join(
    '{gif:"data:image/gif;base64,%s",cap:"%s"}' % (b64(g), s["cap"])
    for g, s in zip(gif_paths, STEPS)
) + "]"

html = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Demo hoi thoai NPC - Ninja Adventure pack</title>
<style>
  body { background:#141425; margin:0; padding:16px; font-family:system-ui; color:#cfd2e8; }
  .wrap { max-width:660px; margin:0 auto; }
  h2 { margin:4px 0 2px; font-size:20px; }
  .sub { opacity:.7; font-size:12px; margin-bottom:10px; }
  .stage-box { background:#1c2033; border:1px solid #343a5c; border-radius:10px; padding:10px; }
  #stage { width:100%; height:auto; aspect-ratio: 624/352; image-rendering: pixelated; border-radius:6px; display:block; background:#000; }
  #cap { font-size:12px; color:#9aa0c0; margin-top:6px; min-height:16px; }
  .nav { display:flex; gap:6px; margin:10px 0 4px; align-items:center; flex-wrap:wrap; }
  .nav button { padding:7px 12px; border:0; border-radius:6px; color:#fff; cursor:pointer; background:#2a2f4a; font-size:13px; }
  .nav button:hover { background:#3a4064; }
  .nav button.cur { background:#5b6ee1; }
  label { font-size:12px; display:flex; align-items:center; gap:5px; margin-left:auto; opacity:.85; }
  h3 { margin:18px 0 6px; font-size:15px; }
  #grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:8px; }
  .cell { background:#1c2033; border:1px solid #343a5c; border-radius:8px; padding:6px; cursor:pointer; }
  .cell img { width:100%; height:auto; image-rendering:pixelated; border-radius:4px; display:block; }
  .cell div { font-size:10.5px; color:#9aa0c0; margin-top:4px; }
</style>
<body>
<div class="wrap">
<h2>&#127917; Demo h\u1ed9i tho\u1ea1i NPC \u2014 ch\u1ee3 B\u00e0 (monster trade base)</h2>
<div class="sub">GIF \u0111\u1ed9ng: idle nh\u00fan + emote n\u1ea3y + arrow ch\u1edbp + typewriter \u2014 font pixel ti\u1ebfng Vi\u1ec7t c\u00f3 d\u1ea5u t\u1ef1 compose t\u1eeb font8x8</div>
<div class="stage-box">
  <img id="stage" alt="frame">
  <div id="cap"></div>
</div>
<div class="nav">
  <button id="prev">&#9664; Tr\u01b0\u1edbc</button>
  <button class="s"></button><button class="s"></button><button class="s"></button><button class="s"></button>
  <button id="next">Sau &#9654;</button>
  <label><input type="checkbox" id="auto"> T\u1ef1 \u0111\u1ed9ng chuy\u1ec3n b\u01b0\u1edbc (4s)</label>
</div>
<h3>C\u1ea3 4 b\u01b0\u1edbc (GIF \u0111\u1ed9ng \u2014 click \u0111\u1ec3 xem)</h3>
<div id="grid"></div>
</div>
<script>
const steps = __STEPS__;
let cur = 0, timer = null;
const stage = document.getElementById("stage"), cap = document.getElementById("cap"),
      auto = document.getElementById("auto");
const dots = [...document.querySelectorAll(".nav .s")];
function show(i) {
  cur = (i + steps.length) % steps.length;
  stage.src = steps[cur].gif;
  cap.textContent = "B\u01b0\u1edbc " + (cur + 1) + ": " + steps[cur].cap;
  dots.forEach((b, j) => b.classList.toggle("cur", j === cur));
}
dots.forEach((b, i) => b.onclick = () => { show(i); restart(); });
prev.onclick = () => { show(cur - 1); restart(); };
next.onclick = () => { show(cur + 1); restart(); };
steps.forEach((s, i) => {
  const cell = document.createElement("div");
  cell.className = "cell";
  cell.innerHTML = '<img src="' + s.gif + '"><div>B\u01b0\u1edbc ' + (i + 1) + ' \u2014 ' + s.cap + '</div>';
  cell.onclick = () => { show(i); restart(); };
  grid.appendChild(cell);
});
function restart() {
  clearInterval(timer);
  if (auto.checked) timer = setInterval(() => show(cur + 1), 4000);
}
auto.onchange = restart;
show(0); restart();
</script>
"""
html = html.replace("__STEPS__", steps_js)
with open(os.path.join(OUT, "demo_dialog.html"), "w", encoding="utf-8") as f:
    f.write(html)
print("wrote demo_dialog.html")
