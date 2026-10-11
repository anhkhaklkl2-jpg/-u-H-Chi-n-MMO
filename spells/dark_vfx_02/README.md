# Spell: Dark VFX 02 — Debuff bóng tối 🌑

> Spell thứ 5 theo hệ thống template. **Cơ chế khác hoàn toàn các spell trước:** KHÔNG bắn ra — kích hoạt thì HIỂN THỊ NGAY effect tại vị trí địch (kiểu debuff/auROM). Frame hơi giống hiệu ứng nổ của dark_vfx_01.

## Nguồn VFX pack

- **Tên pack:** Dark VFX 02 (`dark_vfx_02`, trong `Dark_VFX_01_02_frames`)
- **Đường dẫn gốc:** `C:\Users\phant\Downloads\vfx\Dark_VFX_01_02_frames\dark_vfx_02\`
- **Kích thước frame:** 48×64 (cao hơn ngang — bồ hóng/nhánh tối phủ lên mob)

## Frames

15 frame `frame_01..15.png` — **một bộ duy nhất**, play trên địch từ frame 01 đến frame 15 rồi tắt (không phân chia bay/impact).

## Cơ chế (đã duyệt bởi user)

1. Kích hoạt (target 1 địch) → effect hiện ngay tại vị trí địch.
2. Play 15 frame ở `FPS` (6fps), **1 loop rồi tự tắt**.
3. Chỉ để hiển thị/debuff — không damage mặc định (thêm sau nếu user yêu cầu).
4. Spam guard `STACK_GAP_MS` (200ms) giữa 2 lần kích trên cùng 1 mob.

## Config (chỉnh nhanh khi vibe code)

```js
const FPS = 6;             // fps animation
const LOOPS = 1;           // số vòng play trước khi tắt
const STACK_GAP_MS = 200;  // chống spam trên cùng 1 mob
```

## Lưu ý port vào game

- Anchor: chân frame align chân mob, căn giữa theo X (`x:frameW/2, y: mob.bottom - frameH`).
- Scale: x2 nếu cần (frame 48×64 nên to hơn mob 32×32 ~1 chút, coi có cần chỉnh không).
- Không cần xoay/flip — effect 1 chiều mặt định.
- Anims Phaser: `dark02_debuff` (repeat 0, 6fps, 15 frame), tự destroy sau anims hoàn tất.
