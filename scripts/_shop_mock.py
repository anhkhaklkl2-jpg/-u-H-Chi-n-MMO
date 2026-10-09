# One-off v2: re-compose the two PICKED shop mockups (Kaetram + Rainbow-cat)
# with fixed spacing/alignment (v1 had text overlapping icons, clipped button).
from PIL import Image, ImageDraw, ImageFont

FONT = ImageFont.truetype("C:/Windows/Fonts/verdana.ttf", 13)
FONT_B = ImageFont.truetype("C:/Windows/Fonts/verdanab.ttf", 13)
FONT_S = ImageFont.truetype("C:/Windows/Fonts/verdana.ttf", 11)

k = "kaetram_extract/10_interface/"


def load(p, scale=3):
    im = Image.open(p).convert("RGBA")
    return im.resize((im.width * scale, im.height * scale), Image.NEAREST)


menu = load(k + "slices/menu-fancy.png", 2)
inner = load(k + "slices/inner-container.png", 4)
btnGreen = load(k + "slices/button-green.png", 3)
tab = load(k + "slices/tab.png", 3)
tabA = load(k + "slices/tab-active.png", 3)
listItem = load(k + "slices/list-item.png", 3)


def item(name, scale=2):
    im = Image.open(f"kaetram_extract/04_items/sprites/{name}.png").convert("RGBA")
    return im.resize((im.width * scale, im.height * scale), Image.NEAREST)


def stretch9(im, w, h):
    sw, sh = im.size
    mw, mh = sw // 3, sh // 3
    if w <= 2 * mw or h <= 2 * mh or mw == 0 or mh == 0:
        return im.resize((w, h), Image.NEAREST)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(im.crop((0, 0, mw, mh)), (0, 0))
    out.paste(im.crop((sw - mw, 0, sw, mh)), (w - mw, 0))
    out.paste(im.crop((0, sh - mh, mw, sh)), (0, h - mh))
    out.paste(im.crop((sw - mw, sh - mh, sw, sh)), (w - mw, h - mh))
    out.paste(im.crop((mw, 0, sw - mw, mh)).resize((w - 2 * mw, mh), Image.NEAREST), (mw, 0))
    out.paste(im.crop((mw, sh - mh, sw - mw, sh)).resize((w - 2 * mw, mh), Image.NEAREST), (mw, h - mh))
    out.paste(im.crop((0, mh, mw, sh - mh)).resize((mw, h - 2 * mh), Image.NEAREST), (0, mh))
    out.paste(im.crop((sw - mw, mh, sw, sh - mh)).resize((mw, h - 2 * mh), Image.NEAREST), (w - mw, mh))
    out.paste(im.crop((mw, mh, sw - mw, sh - mh)).resize((w - 2 * mw, h - 2 * mh), Image.NEAREST), (mw, mh))
    return out


def txt(dr, xy, s, color=(240, 230, 200), font=None, anchor=None):
    dr.text(xy, s, fill=color, font=font or FONT, anchor=anchor)


def coin(dr, x, y, r=5):
    """Small gold coin dot: yellow circle + darker rim."""
    dr.ellipse([x - r, y - r, x + r, y + r], fill=(255, 200, 60), outline=(150, 110, 20), width=2)


ROWS = [("burger", "Burger", "450 xu"), ("flask", "Bình máu", "100 xu"),
        ("manaflask", "Bình mana", "85 xu"), ("knife", "Dao", "500 xu"),
        ("arrow", "Mũi tên", "5 xu")]

# ================= MOCK 1 — KAETRAM (fixed) =================
# Layout grid: panel 480x340; title y26; tabs y46-76; list x38-290 y88..;
# detail x306-452 y88-210; qty y220-252; buy y262-296 (all inside panel).
W, H = 510, 372
m1 = Image.new("RGBA", (W, H))
dr0 = ImageDraw.Draw(m1)
for y in range(H):
    v = int(30 + 15 * (y / H))
    dr0.line([(0, y), (W, y)], fill=(v, v - 6, v - 14))
PX, PY = 18, 16  # panel offset
m1.alpha_composite(stretch9(menu, 474, 340), (PX, PY))
dr = ImageDraw.Draw(m1)
cx = PX + 237
txt(dr, (cx, PY + 22), "SHOP — Gạc Đặc", (255, 228, 150), FONT_B, anchor="mm")
# tabs (left-aligned pair) + coin chip (right)
tx = PX + 24
m1.alpha_composite(stretch9(tabA, 92, 30), (tx, PY + 40))
m1.alpha_composite(stretch9(tab, 92, 30), (tx + 100, PY + 40))
txt(dr, (tx + 46, PY + 55), "Mua", (255, 240, 200), FONT_S, anchor="mm")
txt(dr, (tx + 146, PY + 55), "Bán", (205, 195, 175), FONT_S, anchor="mm")
coin(dr, W - PX - 92, PY + 55)
txt(dr, (W - PX - 80, PY + 55), "120 xu", (255, 215, 110), FONT_S, anchor="lm")
# list rows
ly = PY + 84
for key, name, price in ROWS:
    m1.alpha_composite(stretch9(listItem, 252, 36), (PX + 20, ly))
    m1.alpha_composite(item(key), (PX + 27, ly + 4))
    txt(dr, (PX + 60, ly + 18), name, (235, 225, 205), FONT_S, anchor="lm")
    txt(dr, (PX + 262, ly + 18), price, (255, 215, 110), FONT_S, anchor="rm")
    ly += 40
# detail panel (icon centered TOP, texts BELOW — no overlap)
dx, dy = PX + 292, PY + 84
m1.alpha_composite(stretch9(inner, 160, 168), (dx, dy))
big = item("burger", 4)
m1.alpha_composite(big, (dx + 80 - big.width // 2, dy + 10))
txt(dr, (dx + 80, dy + 62), "Burger", (255, 235, 170), FONT_B, anchor="mm")
txt(dr, (dx + 80, dy + 84), "Hồi 50 HP", (195, 185, 165), FONT_S, anchor="mm")
txt(dr, (dx + 80, dy + 104), "Giá: 450 xu", (255, 215, 110), FONT_S, anchor="mm")
txt(dr, (dx + 80, dy + 124), "Đang có: 2", (195, 185, 165), FONT_S, anchor="mm")
# quantity row
m1.alpha_composite(stretch9(inner, 160, 30), (dx, dy + 178))
txt(dr, (dx + 12, dy + 193), "Số lượng", (235, 225, 205), FONT_S, anchor="lm")
dr.rounded_rectangle([dx + 108, dy + 182, dx + 152, dy + 204], radius=4,
                     fill=(20, 24, 22), outline=(90, 110, 100))
txt(dr, (dx + 130, dy + 193), "1", (245, 240, 225), FONT_S, anchor="mm")
# buy button
m1.alpha_composite(stretch9(btnGreen, 160, 34), (dx, dy + 218))
txt(dr, (dx + 80, dy + 235), "MUA", (255, 255, 240), FONT_B, anchor="mm")
m1.save("temp_shop_mock_kaetram.png")

# ================= MOCK 3 — RAINBOW-CAT (fixed) =================
W, H = 500, 350
m3 = Image.new("RGBA", (W, H))
dr0 = ImageDraw.Draw(m3)
for y in range(H):
    v = int(28 + 14 * (y / H))
    dr0.line([(0, y), (W, y)], fill=(v, v - 4, v + 10))
card = Image.new("RGBA", (W - 20, H - 16), (24, 22, 30, 248))
ImageDraw.Draw(card).rounded_rectangle([0, 0, card.width - 1, card.height - 1],
                                       radius=12, outline=(96, 86, 120), width=2)
m3.alpha_composite(card, (10, 8))
dr = ImageDraw.Draw(m3)
# header: title left, tabs center, gold chip right — evenly spaced, no overlap
txt(dr, (30, 30), "SHOP", (255, 200, 90), FONT_B, anchor="lm")
txt(dr, (86, 30), "— Gạc Đặc", (205, 196, 176), FONT_S, anchor="lm")
for i, (label, act) in enumerate([("Mua", True), ("Bán", False)]):
    x = 196 + i * 94
    dr.rounded_rectangle([x, 16, x + 86, 42], radius=9,
                         fill=(64, 58, 88) if act else (36, 33, 46),
                         outline=(255, 190, 90) if act else (70, 64, 90), width=2)
    txt(dr, (x + 43, 29), label, (255, 232, 165) if act else (170, 160, 150),
        FONT_S, anchor="mm")
coin(dr, W - 96, 29)
txt(dr, (W - 84, 29), "120 xu", (255, 215, 110), FONT_S, anchor="lm")
# left list panel (header row + 5 rows, generous 36px rows)
lx, ly0 = 26, 56
lp = Image.new("RGBA", (238, 250), (30, 28, 40, 255))
ImageDraw.Draw(lp).rounded_rectangle([0, 0, 237, 249], radius=9, outline=(70, 64, 90), width=2)
m3.alpha_composite(lp, (lx, ly0))
dr = ImageDraw.Draw(m3)
txt(dr, (lx + 14, ly0 + 16), "Items", (255, 200, 120), FONT_S, anchor="lm")
txt(dr, (lx + 148, ly0 + 16), "Kho", (255, 200, 120), FONT_S, anchor="mm")
txt(dr, (lx + 222, ly0 + 16), "Giá", (255, 200, 120), FONT_S, anchor="rm")
y = ly0 + 34
for key, name, _stock, *rest in [(r[0], r[1], r[2]) for r in
                                 [("burger", "Burger", "∞"), ("flask", "Bình máu", "∞"),
                                  ("manaflask", "Bình mana", "∞"), ("knife", "Dao", "1"),
                                  ("arrow", "Mũi tên", "∞")]]:
    price = dict((r[1], r[2]) for r in ROWS)[name]
    dr.rounded_rectangle([lx + 8, y, lx + 226, y + 34], radius=6,
                         fill=(40, 38, 52), outline=(56, 52, 72))
    m3.alpha_composite(item(key), (lx + 14, y + 6))
    txt(dr, (lx + 44, y + 17), name, (225, 218, 200), FONT_S, anchor="lm")
    txt(dr, (lx + 148, y + 17), "∞" if name != "Dao" else "1", (180, 175, 160), FONT_S, anchor="mm")
    txt(dr, (lx + 222, y + 17), price, (255, 215, 110), FONT_S, anchor="rm")
    y += 40
# right detail panel
rx, ry = 276, 56
rp = Image.new("RGBA", (196, 250), (30, 28, 40, 255))
ImageDraw.Draw(rp).rounded_rectangle([0, 0, 195, 249], radius=9, outline=(70, 64, 90), width=2)
m3.alpha_composite(rp, (rx, ry))
dr = ImageDraw.Draw(m3)
big = item("burger", 4)
m3.alpha_composite(big, (rx + 98 - big.width // 2, ry + 12))
txt(dr, (rx + 98, ry + 66), "Burger", (255, 235, 170), FONT_B, anchor="mm")
txt(dr, (rx + 98, ry + 90), "Hồi 50 HP. No lâu.", (185, 178, 160), FONT_S, anchor="mm")
txt(dr, (rx + 98, ry + 110), "Đang có: 2", (185, 178, 160), FONT_S, anchor="mm")
# quantity row
dr.rounded_rectangle([rx + 12, ry + 136, rx + 184, ry + 166], radius=6,
                     fill=(40, 38, 52), outline=(70, 64, 90))
txt(dr, (rx + 24, ry + 151), "Số lượng", (200, 192, 175), FONT_S, anchor="lm")
dr.rounded_rectangle([rx + 116, ry + 141, rx + 176, ry + 161], radius=4,
                     fill=(24, 22, 30), outline=(90, 82, 110))
txt(dr, (rx + 146, ry + 151), "1", (240, 235, 220), FONT_S, anchor="mm")
# buy button
dr.rounded_rectangle([rx + 12, ry + 176, rx + 184, ry + 208], radius=9,
                     fill=(64, 120, 60), outline=(110, 200, 100), width=2)
txt(dr, (rx + 98, ry + 192), "MUA", (255, 255, 240), FONT_B, anchor="mm")
# sell hint row (tab Bán preview note)
txt(dr, (rx + 98, ry + 228), "Tab Bán: kéo đồ từ túi vào đây",
    (140, 134, 155), FONT_S, anchor="mm")
m3.save("temp_shop_mock_rainbowcat.png")

# sheet: side by side
a = Image.open("temp_shop_mock_kaetram.png")
b = Image.open("temp_shop_mock_rainbowcat.png")
W = a.width + b.width + 30
H = max(a.height, b.height) + 20
sheet = Image.new("RGBA", (W, H), (15, 14, 18, 255))
sheet.alpha_composite(a, (10, 10))
sheet.alpha_composite(b, (a.width + 20, 10))
sheet.save("temp_shop_mocks_all.png")
print("ok", sheet.size)
