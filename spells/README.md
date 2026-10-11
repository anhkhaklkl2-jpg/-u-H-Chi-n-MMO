# 🧙 Hệ thống Spell VFX — Sơ đồ mẫu + Template

> **Triết lý:** Mỗi spell = 1 thư mục trong `spells/<spell_id>/`. Có **preview HTML tự chứa** (không cần server, mở là chạy) để xem cơ chế TRƯỚC khi nhét vào game. Khi cần spell mới: chỉ cần tìm bộ frame icon (VFX pack), thay vào template là dùng được ngay — hitbox, damage, timing đã có sẵn.

---

## 1. Cấu trúc thư mục chuẩn

```
spells/
├── README.md                  ← file này (hướng dẫn hệ thống)
├── _template/                 ← TEMPLATE TRỐNG — copy khi làm spell mới
│   ├── preview/index.html     ← preview HTML (frames base64 tự chứa)
│   └── frames/                ← để trống, drop frame PNG vào đây
└── wood_vfx_01/               ← spell mẫu đầu tiên: khúc gỗ bay
    ├── preview/index.html     ← mở tab Preview là xem được, KHÔNG cần server
    ├── frames/                ← frame PNG gốc (32×32, đếm từng frame)
    │   ├── Wood VFX 01 Repeatable1..8.png   ← frame BAY (loop)
    │   └── Wood VFX 01 Hit1..7.png          ← frame IMPACT (play 1 lần)
    └── README.md              ← ghi chú riêng của spell này (xem §7)
```

---

## 2. Quy trình thêm spell mới (5 bước)

1. **Copy template:**
   ```bash
   cp -r spells/_template spells/<spell_id_moi>
   ```
2. **Drop frame PNG** vào `spells/<id>/frames/` — tên file tuỳ ý, chỉ cần biết:
   - Bộ nào là **BAY** (loop khi projectile bay)
   - Bộ nào là **IMPACT** (nổ/chạm, play 1 lần rồi mất)
3. **Nhúng frame vào preview HTML** (script Python, xem §8) — script tự đọc frames/, encode base64, ghi vào `preview/index.html`. Vì preview server Freebuff chỉ serve đúng 1 file HTML, frame NHẤT ĐỊNH phải base64 trong file, không load từ thư mục được.
4. **Chỉnh block `SPELL` config** trong preview (xem §4) — đây là chỗ chỉnh mọi thông số.
5. **Mở preview, click bấm xem**, chỉnh số cho ưng → spell "đã thiết kế xong", sau đó port sang web client (xem §6).

> ⚠️ Sau khi sửa `preview/index.html` bằng tay, cần rebuild lại base64? Chạy lại script ở §8 — nó chỉ thay phần `const FRAME_DATA = {...};` và các dòng `REPEATABLE`/`HIT`, không đụng logic.

---

## 3. Cơ chế spell chuẩn (3 giai đoạn)

Mọi spell theo pipeline giống nhau, preview template đã dựng sẵn:

```
CAST (0.1s)  →  FLY (bay theo đường thẳng)  →  IMPACT (nổ + damage)
 fade-in         sprite xoay theo atan2         play Hit frames 1 lần
 nạp lực         loop Repeatable frames         trừ HP mob trong bán kính
```

| Giai đoạn | Điều khiển bởi | Ý nghĩa |
|---|---|---|
| CAST | `CAST_MS` (ms) | Thời gian nạp trước khi bắn — sprite fade-in tại vị trí caster |
| FLY | `FLY_MS`, `FLY_FPS` | Tốc độ bay (thời gian tới đích) + fps animation bay |
| IMPACT | `IMPACT_FPS`, `SPELL.impact*` | fps animation nổ + các hiệu ứng chạm |

**Xoay hướng:** lúc cast tính `angle = atan2(ty - caster.y, tx - caster.x)` — áp cho CẢ projectile lẫn impact frame. Không dùng flip trái/phải vì spell có thể bắn chéo lên/xuống.

---

## 4. Block `SPELL` — schema config chuẩn

Đây là CHỈ 1 chỗ duy nhất cần chỉnh trong preview. Khi port sang game, block này map 1-1 sang file skill data của web client:

```js
const SPELL = {
  name: "Wood VFX 01",       // tên hiển thị
  dmg: 12,                   // damage mỗi phát (cơ bản)
  dmgVariance: 4,            // dmg thực tế = dmg ± random(dmgVariance) — tránh spam số đều
  impactRadius: 26,          // bán kính hitbox quanh điểm chạm (px, đơn vị canvas preview)
  impactShake: 2,            // độ rung màn hình khi impact (px, 0 = tắt)
  impactShakeMs: 120,        // thời gian rung
  impactScale: 1.0,          // phóng to frame impact (1 = kích thước gốc 32px)
  hitStopMs: 0,              // đóng băng projectile X ms lúc chạm (0 = tắt) — cho cảm giác đòn nặng
};
```

Và 3 hằng số thời gian ở trên block:
```js
const CAST_MS   = 100;  // nạp lực
const FLY_MS    = 500;  // thời gian bay tới đích
const FLY_FPS   = 6;    // fps animation bay (Repeatable loop)
const IMPACT_FPS = 6;   // fps animation impact (Hit play 1 lần)
```

> 💡 **Impact nhẹ hay nặng** = chỉnh `impactShake`, `hitStopMs`, `impactScale`. Spell nặng = tăng `hitStopMs` (30–80ms) + `impactShake` (3–5px). Spell nhẹ = giữ 0.

---

## 5. Preview HTML — có gì bên trong

Mỗi preview tự chứa, không phụ thuộc file ngoài:

- **`FRAME_DATA`** — object `{ "tên file.png": "base64..." }`, nhúng tất cả frame.
- **Canvas 480×270**, pixel-art, checkered background.
- **Caster** (ô vàng) cố định bên trái — vị trí xuất phát của spell.
- **2 mob giả** (ô đỏ + HP bar + số HP) để test damage — auto-cast 70% nhắm vào mob (jitter ±10px), 30% bắn random.
- **Click trên canvas** = cast tới điểm đó (bất kỳ góc nào, xoay tự động).
- **Damage number** bay lên màu vàng khi mob ăn đòn.
- **Vòng tròn đỏ** nhấp nháy tại điểm nổ = debug `impactRadius` (nhìn thấy hitbox).
- Nút: **Tự cast (loop)**, **Scale x2** (soi pixel).
- Log dòng dưới hiển thị: góc bắn, cast/fly ms, dmg ± variance.

---

## 6. Port sang web client (Phaser) — khi nào làm

Preview là **canvas 2D thuần** nhưng logic đã đúng hitbox/timing. Khi port:

| Preview | Phaser |
|---|---|
| `drawSprite(im, x, y, angle, scale)` | `sprite.setRotation(angle)`, `setScale(scale)` |
| `FLY_FPS` loop Repeatable frames | `this.anims.create({ frameRate: FLY_FPS, repeat: -1 })` |
| `IMPACT_FPS` play Hit 1 lần | `this.anims.create({ frameRate: IMPACT_FPS, repeat: 0 })` + `on('animationcomplete')` → destroy |
| `applyDamage(p)` kiểm tra khoảng cách tới `mobs` | dùng hit-test so với mob thật của game — **cùng công thức `dx*dx+dy*dy <= r*r`** |
| Block `SPELL` | copy nguyên vào file skill data của client |

⚠️ Nhớ quy tắc PC↔MOBILE SYNC (AGENTS.md §1b): nếu spell kích bằng click chuột, mobile phải có tap/long-press tương đương trong `src/mobile_controls.ts`.

⚠️ Đừng dùng `getBounds()` cho hit-test mob trong Phaser Container (gotcha AGENTS.md) — tự tính world box như `mobIdAtTile` trong `web_client/src/game.ts`.

---

## 7. Ghi chú riêng từng spell

Mỗi thư mục spell có `README.md` riêng ghi: nguồn VFX pack, số frame, thông số đã tinh chỉnh, cảm giác đòn. Ví dụ mẫu xem `spells/wood_vfx_01/README.md`.

---

## 8. Script nhúng frame vào preview

Chạy từ thư mục spell (ví dụ `wood_vfx_01`):

```bash
cd "D:/dự án mini build bot discord mmo event"
.venv/Scripts/python -c "
import base64, os, json, re, sys
spell = sys.argv[1] if len(sys.argv) > 1 else 'wood_vfx_01'
d = f'spells/{spell}/frames'
out = {}
for f in sorted(os.listdir(d)):
    if f.lower().endswith('.png'):
        out[f] = base64.b64encode(open(os.path.join(d,f),'rb').read()).decode()
p = f'spells/{spell}/preview/index.html'
html = open(p, encoding='utf-8').read()
js = 'const FRAME_DATA = ' + json.dumps(out, indent=0) + ';'
html = re.sub(r'const FRAME_DATA = .*?;\n', js + '\n', html, count=1, flags=re.S)
open(p, 'w', encoding='utf-8').write(html)
print('embedded', len(out), 'frames into', p)
"
```

> Script này **chỉ thay `FRAME_DATA`** — các dòng `REPEATABLE`/`HIT` và logic giữ nguyên. Nếu frame mới có tên khác, phải sửa 2 dòng `const REPEATABLE = [...]` / `const HIT = [...]` trong preview cho khớp tên file.

---

## 9. Checklist spell "sẵn sàng nhét vào game"

- [ ] Frame bay (Repeatable) + frame impact (Hit) đã trong `frames/`
- [ ] `FRAME_DATA` đã nhúng base64 vào preview
- [ ] Block `SPELL` đã chỉnh xong (dmg, radius, shake, scale...)
- [ ] Test preview: click đủ 8 hướng, xoay đúng, damage trừ HP mob đúng, số dmg hiện đúng
- [ ] Impact "nhẹ" hoặc "nặng" đúng vibe (shake/hitStop/scale)
- [ ] Ghi `README.md` trong thư mục spell (nguồn, thông số, cảm giác)
- [ ] Port sang Phaser: sprite sheet, anims, hit-test theo công thức `r*r`, block SPELL copy sang skill data
