# Spell: Earth Wall — Tường đất 🧱

> Spell thứ 7 theo hệ thống template. **Cơ chế phòng thủ:** tường đất mọc lên, giữ hitbox chặn đạn địch, hết hạn thì thụt xuống; bị đạn quá mạnh thì vỡ ngay không frame end.

## Nguồn VFX pack

- **Tên pack:** Earth Effect 02 (`earth_wall`)
- **Đường dẫn gốc:** `C:\Users\phant\Downloads\vfx\Earth_Effect_02_frames\Earth_Effect_02_frames\earth_wall\`
- **Kích thước frame:** 48×48
- **Lưu ý mapping:** pack gốc có 13 frame đánh số `frame_02..14` (không có frame_01) — preview **giữ nguyên số gốc** vì user chỉ đích danh **frame_08 là FINAL**

## Frames

| Phân loại | Frame | Dùng cho |
|---|---|---|
| Grow (mọc lên) | `frame_02..07` | 6 frame khi tường mọc |
| **FINAL (đứng)** | `frame_08` | hold 2.5s — hitbox chặn đạn + HP |
| End (thụt xuống) | `frame_09..14` | play 1 lần khi hết hạn tự nhiên |

## Cơ chế (đã duyệt bởi user)

1. Kích hoạt → tường mọc (grow 6 frame, 12fps).
2. **Hold**: frame_08 đứng yên `finalHoldMs` (2500ms), là 1 **block hitbox thật** — chặn đạn bay qua; đạn trúng trừ HP, đạn bị nuốt và biến mất.
3. Hết hold → **end thụt xuống** (frame_09–14, play 1 lần) rồi mất.
4. **Bị đạn quá mạnh (HP ≤ 0)** → KHÔNG chạy frame end; thay bằng **mờ dần trong 0.5s** (`destroyedFadeMs`) rồi biến mất.

## Hitbox — ÔM SÁT tường (đã duyệt)

- Trước: box ước lệ 44×30 quanh điểm dựng → to quá, sai lệch.
- Sau (final): **bbox solid thật của frame_08** đo bằng PIL (alpha ≥ 128) = **15×24 px, gốc (16,15) trong frame 48×48**.
- `rectOf()` tính hitbox từ tọa độ bbox đó trong sprite (scale-aware theo x2) → chỉ phần thân tường đậm mới chặn đạn, mép alpha mỏng không tính.

## Config

```js
const SPELL = {
  fps: 12,
  finalHoldMs: 2500,     // tường sống bao lâu
  wallBlockW: 15,        // hitbox ngang = width bbox solid frame_08
  wallBlockH: 24,        // hitbox cao = height bbox solid
  wallMaxHp: 40,         // HP tường (đạn test dmg 25 → 2 phát vỡ)
  destroyedFadeMs: 500,  // fade khi bị phá
};
```

## Verify đã chạy (preview)

- Grow → hold → đạn 1 bị chặn (40→15) → đạn 2 vỡ tường (fade 0.5s, bỏ frame end) ✅
- Hết hạn tự nhiên → end thụt xuống 6 frame → mất sạch ✅
- Vòng/viền debug đã bỏ khi final (cả viền hitbox xanh) ✅

## Lưu ý port vào game

- State machine: `grow → hold(hitbox chặn) → end` / `grow|hold → destroy(fade tween 0.5s, bỏ END_FRAMES)`.
- Hitbox = bbox solid của final frame, scale-aware; chặn đạn bằng sweep đường bay mỗi frame (`min/max x + y-span`) — không getBounds.
- Anims Phaser: `wall_grow` (repeat 0, 12fps), `wall_end` (repeat 0, 12fps), destroy = tween alpha 0.5s.
- HP giảm = dmg tổng cộng cộng dồn; đạn bị nuốt khi chặn.
