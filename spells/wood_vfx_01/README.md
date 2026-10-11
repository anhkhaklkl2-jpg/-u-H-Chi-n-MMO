# Spell: Wood VFX 01 — Khúc gỗ bay 🪵

> Spell mẫu đầu tiên của hệ thống. Ảnh chụp cơ chế: cast 0.1s → khúc gỗ bay 0.5s → impact nhẹ.

## Nguồn VFX pack

- **Tên pack:** Wood VFX 01 (bộ `Wood VFX 01 - 02`, chỉ dùng VFX 01)
- **Đường dẫn gốc:** `C:\Users\phant\Downloads\vfx\Wood VFX 01 - 02\Wood VFX 01 - 02\Wood VFX 01\`
- **Loại:** pixel-art 32×32, PNG trong suốt
- Cùng pack có **Wood VFX 02** (14 frame, dạng single sprite) — chưa dùng, có thể làm spell khác sau

## Frames

| Bộ | Số frame | File | Dùng cho |
|---|---|---|---|
| Repeatable | 8 | `Wood VFX 01 Repeatable1..8.png` | **BAY** — loop trong lúc khúc gỗ bay |
| Hit | 7 | `Wood VFX 01 Hit1..7.png` | **IMPACT** — play 1 lần rồi mất |

## Thông số đã tinh chỉnh (block `SPELL` trong preview)

```js
const SPELL = {
  name: "Wood VFX 01",
  dmg: 12,
  dmgVariance: 4,
  impactRadius: 26,
  impactShake: 2,       // nhẹ
  impactShakeMs: 120,
  impactScale: 1.0,
  hitStopMs: 0,         // nhẹ — không đóng băng
};
const CAST_MS = 100;    // 0.1s nạp lực
const FLY_MS = 500;
const FLY_FPS = 6;
const IMPACT_FPS = 6;
```

## Cảm giác đòn

- **Nhẹ, nhanh, không trầm** — phù hợp làm skill cơ bản spam được.
- Impact chỉ rung 2px/120ms, không hit-stop.
- Khúc gỗ bay 32px, đủ to thấy nhưng không che map.
- Damage number bay lên màu vàng, 700ms lifetime.

## Đã test trong preview

- ✅ Click đủ 8 hướng — sprite xoay đúng theo atan2, không cần flip
- ✅ Damage trừ HP mob thật (2 mob giả ăn cùng lúc nếu cùng bán kính 26px)
- ✅ Auto-cast loop không rò rỉ projectile (filter sau impact done)
- ✅ Chạy offline, frames base64 nhúng trong file HTML

## Port sang game (todo khi tích hợp)

- [ ] Copy `SPELL` block sang skill data của web client
- [ ] Build 2 anims Phaser: `wood01_fly` (repeat: -1, frameRate 6), `wood01_hit` (repeat: 0, frameRate 6)
- [ ] Projectile = Container sprite + `setRotation(angle)` mỗi lần cast
- [ ] Hit-test: `dx*dx+dy*dy <= 26*26` so với mob thật (KHÔNG dùng `getBounds()` — gotcha AGENTS.md)
- [ ] Damage number dùng cùng hệ thống floaters của game
- [ ] Mobile: tap lên mob = cast tới mob đó (mobile_controls.ts)
