# 🤖 AGENT MINI — Quy trình làm Spell VFX (cho mọi session học theo)

> Tài liệu "cách làm việc" đúc kết từ các session spell Wood VFX 01 → Earth Bump.
> ĐỌC FILE NÀY ĐẦU TIÊN khi user gửi 1 pack VFX mới để làm thành spell.

## 🎯 Mục tiêu

Từ 1 folder frame PNG trong `Downloads/vfx/...` → 1 **spell hoàn chỉnh** trong vài phút:
1. Preview HTML chạy được (tự chứa, base64) — user xem + duyệt
2. README ghi cơ chế + config + checklist port
3. Sau khi user duyệt → xuất vào `C:\Users\phant\Downloads\vfx\vfx done\<Tên Spell>\`

## 📂 Cấu trúc 2 nơi (luôn giữ đồng bộ)

```
DỰ ÁN (source of truth):            D:\dự án mini build bot discord mmo event\spells\
  spells/_template/                   ← template trống, cấu trúc preview chuẩn
  spells/<spell_name>/
    ├── frames/frame_01..N.png        ← frame gốc (rename về frame_01..N nếu pack đánh số lân dụng)
    ├── preview/index.html            ← preview base64 (thả vào tab Preview chạy ngay)
    └── README.md

ASSET USER:                        C:\Users\phant\Downloads\vfx\vfx done\
  <Tên Spell>/
    ├── frame_01..N.png
    ├── preview.html                  ← bản copy của preview/index.html
    └── README.md
```

⚠️ Tên folder user-side là **`vfx done`** (không còn "vfx đã hoàn thiện" như trước đây).

## 🔁 Quy trình 6 bước

1. **Inspect pack**: `ls` + đọc size từng frame PIL. Ghi kích thước thật (32×32, 48×48...), đếm số frame, chú ý pack có thể THIẾU frame_01 (earth_bump bắt đầu từ 02) hoặc đặt tên khác (wood dùng "Repeatable 1-8 / Hit 1-7").
2. **Hỏi user phân loại frame** (nếu không rõ): đâu là frame bay / impact / nhịp riêng (emerge, debuff...). User sẽ chỉ "01–10 là đạn, 11–16 là impact."
3. **Copy frames** vào `spells/<name>/frames/`, rename `frame_01..` chuẩn.
4. **Sinh preview**: copy `_template/preview/index.html` hoặc spell cùng cơ chế gần nhất, nhúng base64 bằng script (mục "Script nhúng"), sửa:
   - `REPEATABLE` (frame bay, loop) / `HIT` (frame impact, play 1 lần) — hoặc cơ chế riêng
   - tiêu đề `<h1>` + `document.title` cho khớp tên spell
   - block `SPELL` config
5. **Verify bằng PROBE (không chụp ảnh!)**: `register_preview` → `preview_evaluate`:
   - canvas render khác nền (đếm pixel ≠ màu bg ~60–70k)
   - gọi trực tiếp `cast(...)` trong evaluate → đọc state (`projectiles`, `phase`, `log`, HP mob) sau vài trăm ms
   - console logs sạch (cảnh báo getImageData từ probe là của tool, bỏ qua)
6. **Chờ user duyệt** → chỉnh theo feedback (thường vài vòng: fps, khoảng cách, thêm dmg, bỏ debug circle...) → **xuất `vfx done`** bằng `cp` 3 loại file.

## 🧠 Cơ chế spell đã làm (tham khảo nhanh)

| Spell | Bộ frames | Cơ chế | Ghi chú đặc biệt |
|---|---|---|---|
| Wood VFX 01 | 15 (32×32): Repeatable 1–8 / Hit 1–7 | cast 0.1s → bay 0.5s auto-rotate atan2 → impact | spell mẫu gốc |
| Earth Projectile | 10 (48×32): 1–6 bay / 7–10 hit | như wood | accumulator anim RIÊNG từng projectile (fix "fps khác nhau theo khoảng cách") |
| Earth Rock Lift | 6+11 (rock/impact) | vận chiêu: 6 frame nhấc đá từ chân player lên ~5px, rồi ném tới đích; frame 7–11 + impact/ lồng chạy đồng thời bên dưới | |
| Dark VFX 01 | 16 (40×32): 1–10 bay / 11–16 hit | trượt khỏi player (EMERGE_PX) → bay tới ĐIỂM BẮN; trúng địch giữa đường (collideRadius) → nổ luôn; trống → tới đích → tìm địch GẦN ĐÍCH → bay chặng 2 → nổ | flip ngang quanh trục bay khi \|angle\|>90° (sprite đầu lâu không lộn ngược); frame NỔ KHÔNG xoay (angle=0) |
| Dark VFX 02 | 15 (48×64) | DEBUFF: kích hoạt hiển thị ngay trên địch, play 1 loop rồi tắt, spam guard 200ms, anchor chân-mob | không damage mặc định |
| Earth Bump | 13 (48×48), pack gốc 02–13 | bump mọc cách player `emergePx` (40) về phía mục tiêu; CHỈ lật trái/phải (flip ngang), KHÔNG xoay; địch trong knockRadius bị ĐẨY ra xa theo vị trí đứng | bỏ vòng đỏ debug khi final |

## ⌨️ Script nhúng base64 (dùng ngay)

```python
import base64, glob, re
entries = []
for f in sorted(glob.glob('spells/<name>/frames/frame_*.png')):
    k = f.split('/')[-1].split('\\')[-1]
    entries.append(f'"{k}": "{base64.b64encode(open(f,"rb").read()).decode()}"')
block = 'const FRAME_DATA = {\n' + ',\n'.join(entries) + '\n};'
html = open('spells/<name>/preview/index.html', encoding='utf-8').read()
html = re.sub(r'const FRAME_DATA = \{.*?\};', block, html, flags=re.S)
open('spells/<name>/preview/index.html','w',encoding='utf-8').write(html)
```

## 📋 Schema block SPELL (đảm bảo "vibe code dễ chỉnh")

Mọi spell giữ block config ở ĐẦU file, tách khỏi engine:

```js
const SPELL = {
  name: "...",
  dmg: 12, dmgVariance: 4,
  impactRadius: 26,          // hitbox nổ
  impactShake: 2, impactShakeMs: 120,
  impactScale: 1.0,
  hitStopMs: 0,              // 0 = tắt
  // riêng từng spell: EMERGE_PX, SEEK_DELAY_MS, collideRadius, knockRadius, knockForce, FPS, LOOPS...
};
```

## 🛑 Luật bất di bất dịch

1. **KHÔNG chụp ảnh preview nhiều vòng** (screenshot→đoán→sửa→chụp lại). Verify bằng `preview_evaluate` (state/probe pixel) hoặc hỏi user. Tối đa 1–2 chụp khi lỗi render mà DOM không thấy.
2. **Preview phải tự chứa** — mọi frame nhúng base64 `FRAME_DATA`, KHÔNG load file PNG ngoài (preview server không serve được thư mục).
3. **Hit-test** luôn `dx*dx+dy*dy <= r*r`, KHÔNG dùng getBounds().
4. **Lỗi chơi nghiêm**:accumulator animation PHẢI per-projectile (`p.animAcc`), không dùng biến chung.
5. **Flip vs Rotate**: xoay theo hướng bay = `rotate(atan2(dy,dx))`. Lật trái/phải = `scale(-1,1)` / Phaser `setFlipX`. Lộn dọc = `scale(1,-1)` / `setFlipY`. HỎI user khi không rõ loại lật nào.
6. **Debug circle/hitbox visual**: hiện khi tinh chỉnh, BỎ trước khi xuất `vfx done` (user đã bỏ vòng đỏ earth + vòng vàng earth_bump). Đừng quên cả chữ hướng dẫn nhắc tới vòng — cũng phải sửa.
7. **Không xoay frame impact** trừ khi user yêu cầu — nổ luôn 1 chiều mặt định (lượt Dark VFX 01).
8. **Import phải cả 2 nơi**: sau khi duyệt, cp frames + preview.html + README sang `vfx done` và soi `cmp`/`ls` khớp.
9. **Mỗi spell 1 README riêng** — nguồn pack, size frame, bảng phân loại frame, cơ chế từng bước, config block, checklist port Phaser (anims repeat/fps, setFlipX/Y, anchor).
10. **Người dùng duyệt = chụp lời vào README** ; chưa duyệt thì chưa xuất `vfx done`.

## ✅ Checklist port sang web client (Phaser) — cada spell ghi ở cuối README

- [ ] Copy SPELL block sang skill data game
- [ ] Anims: `"<spell>_fly"` (repeat -1) / `"<spell>_hit"` (repeat 0), fps đúng
- [ ] Flip: `setFlipX` (trái/phải), `setFlipY` (tùy spell), impact KHÔNG rotate (trừ khi spell yêu cầu)
- [ ] Per-projectile state machine (emerge → fly → seek → impact...) như preview
- [ ] Hit-test `dx*dx+dy*dy <= r*r`
