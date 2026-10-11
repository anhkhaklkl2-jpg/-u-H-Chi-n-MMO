# Spell: Earth Projectile — Đá bay 🪨

> Spell thứ 2 theo hệ thống template. Cùng cơ chế wood_vfx_01: cast 0.1s → bay 0.5s (auto-rotate) → impact + damage.

## Nguồn VFX pack

- **Tên pack:** Earth Effect 01 (`earth_projectile`)
- **Đường dẫn gốc:** `C:\Users\phant\Downloads\vfx\Earth_Effect_01_frames\Earth_Effect_01_frames\earth_projectile\`
- **Kích thước frame:** 48×32 (rộng hơn wood 32×32 — sprite đá có đuôi vệt bay)

## Frames

| Bộ | Số frame | File | Dùng cho |
|---|---|---|---|
| Bay | 6 | `frame_01..06.png` | **BAY** — loop trong lúc đá bay |
| Chạm | 4 | `frame_07..10.png` | **IMPACT** — play 1 lần rồi mất |

## Thông số hiện tại (chưa tinh chỉnh — chờ user xem preview)

```js
const SPELL = {
  name: "Earth Projectile",
  dmg: 12,
  dmgVariance: 4,
  impactRadius: 26,
  impactShake: 2,
  impactShakeMs: 120,
  impactScale: 1.0,
  hitStopMs: 0,
};
const CAST_MS = 100, FLY_MS = 500, FLY_FPS = 6, IMPACT_FPS = 6;
```

> ⚠️ Frame 48×32 nên khi xoay theo hướng chéo, sprite chiếm chỗ hơi rộng — nếu thấy đè lên mob lân cận khi impact, giảm `impactScale` hoặc tăng `impactRadius` để bù cảm giác.

## Port sang game (todo)

- [ ] Chờ user duyệt nhịp/hiệu ứng trong preview
- [ ] Copy SPELL block sang skill data
- [ ] Anims Phaser: `earth_fly` (repeat -1, 6fps), `earth_hit` (repeat 0, 6fps)
- [ ] Hit-test `dx*dx+dy*dy <= r*r` (không getBounds)
