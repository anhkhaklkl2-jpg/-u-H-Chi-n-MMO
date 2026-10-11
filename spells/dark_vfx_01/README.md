# Spell: Dark VFX 01 — Đạn bóng tối 🌑

> Spell thứ 4 theo hệ thống template. **Cơ chế:** spawn cạnh player → trượt ra ~18px → bay tới ĐIỂM BẮN; trúng địch giữa đường thì nổ luôn; tới đích trống thì tìm địch gần đích, bay lại rồi nổ.

## Nguồn VFX pack

- **Tên pack:** Dark VFX 01 (`dark_vfx_01`, trong `Dark_VFX_01_02_frames`)
- **Đường dẫn gốc:** `C:\Users\phant\Downloads\vfx\Dark_VFX_01_02_frames\dark_vfx_01\`
- **Kích thước frame:** 40×32 (hơi rộng hơn 32×32 — có vệt đuôi bay)

## Cơ chế (đã duyệt bởi user)

1. **Spawn** tại vị trí player, fade-in 100ms.
2. **Trượt ra** `EMERGE_PX` (18px) khỏi player trong `EMERGE_MS` (150ms), theo hướng click/nhắm ban đầu.
3. **Bay tới điểm bắn** trong `FLY_MS` (500ms).
4. **Trúng địch giữa đường** — nếu có địch sống trong bán kính `collideRadius` (16px) quanh đạn → nổ ngay tại chỗ.
5. **Tới đích trống** → tìm địch GẦN ĐÍCH nhất (euclid, chỉ mob còn sống), bay chặng 2 rồi nổ. Không có địch → nổ tại điểm bắn.

> **Fix sprite:** đầu lâu bị lộn ngược khi bắn sang trái — đã flip quanh trục bay (`ctx.scale(1,-1)` khi `|angle| > 90°`) trong `drawSprite`, CHỈ áp cho frame BAY.
>
> **Frame NỔ luôn 1 chiều mặt định — KHÔNG xoay theo hướng bay** (draw với angle = 0).

## Frames

| Bộ | Số frame | File | Dùng cho |
|---|---|---|---|
| Bay | 10 | `frame_01..10.png` | **BAY** — loop trong lúc đạn bay |
| Chạm | 6 | `frame_11..16.png` | **IMPACT** — play 1 lần rồi mất |

(user xác nhận: 01–10 = đạn bay, 11–16 = impact; pack không có gì khác dùng được)

## Thông số hiện tại (chưa tinh chỉnh — chờ user xem preview)

```js
const SPELL = {
  name: "Dark VFX 01",
  dmg: 12,
  dmgVariance: 4,
  impactRadius: 26,
  impactShake: 2,
  impactShakeMs: 120,
  impactScale: 1.0,
  hitStopMs: 0,
};
const CAST_MS = 100, EMERGE_MS = 150, EMERGE_PX = 18,
      FLY_MS = 500, FLY_FPS = 6, IMPACT_FPS = 6;
// SPELL.collideRadius = 16 — bán kính nổ-giữa-đường
```

## Port sang game (todo)

- [x] User duyệt cơ chế (trượt 18px → bay tới điểm bắn → nổ giữa đường / seek gần đích)
- [ ] Copy SPELL block + các hằng timing sang skill data
- [ ] Anims Phaser: `dark01_fly` (repeat -1, 6fps, 10 frame), `dark01_hit` (repeat 0, 6fps, 6 frame)
- [ ] State machine projectile: `emerge → fly(leg1, collide-check) → seek(nearest to destination) → fly(leg2) → impact`
- [ ] Flip sprite CHỈ lúc bay: `scale(1,-1)` khi `|angle| > 90°` (setFlipY trong Phaser)
- [ ] Frame impact KHÔNG xoay (angle = 0, mặt định 1 chiều)
- [ ] Hit-test `dx*dx+dy*dy <= r*r` (không getBounds)
