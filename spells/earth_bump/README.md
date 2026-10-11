# Spell: Earth Bump — Cục đá dâng lên 🪨

> Spell thứ 6 theo hệ thống template. **Cơ chế khác:** KHÔNG bay — bump (cục đá nổi lên) xuất hiện cách player 10px về phía mục tiêu, chỉ LẬT TRÁI/PHẢI theo hướng (flip ngang), KHÔNG xoay. Địch trong bán kính bị đẩy ra xa.

## Nguồn VFX pack

- **Tên pack:** Earth Effect 02 (`earth_bump`)
- **Đường dẫn gốc:** `C:\Users\phant\Downloads\vfx\Earth_Effect_02_frames\Earth_Effect_02_frames\earth_bump\`
- **Kích thước frame:** 48×48
- **Lưu ý mapping:** pack gốc bắt đầu từ `frame_02..13` (không có frame_01) — đã copy đè lên `frame_01..13` với cùng số thứ tự (13 frame, không đổi mapping)

## Frames

13 frame `frame_01..13.png` — một bộ duy nhất play từ đầu đến cuối (đá dâng lên rồi lún xuống).

## Cơ chế (đã duyệt bởi user)

1. Kích hoạt về phía mục tiêu → bump mọc cách player `emergePx` (40px, gốc 10 — user yêu cầu gấp 4) theo hướng click.
2. **Chỉ lật trái/phải** (flip ngang `scale(-1,1)`): mục tiêu bên phải → mặt phải, bên trái → mặt trái. KHÔNG xoay, KHÔNG flip dọc.
3. **Đẩy địch** trong bán kính `knockRadius` (40px) quanh bump — đẩy ra xa theo vị trí đứng của địch, cường độ giảm theo khoảng cách (`knockForce` 30).
4. Play 13 frame ở `fps` = 12 rồi mất.

## Config

```js
const SPELL = {
  emergePx: 40,     // khoảng cách khỏi player (px) — user chỉnh từ 10 → 40
  fps: 12,
  knockRadius: 40,  // bán kính đẩy định (px)
  knockForce: 30,   // cường độ đẩy (px tổng)
};
```

## Lưu ý port vào game

- Draw: chân bump align ~ chân mob, flip ngang theo hướng mục tiêu (Phaser: `setFlipX`). KHÔNG `setRotation`.
- Đau: knock = vector đi ra từ tâm bump, chỉ áp với mob còn sống trong bán kính.
- (Đã bỏ vòng đỏ debug bán kính knock trong preview.)
