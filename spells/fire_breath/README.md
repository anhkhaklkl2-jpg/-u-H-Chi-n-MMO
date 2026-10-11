# Spell: Fire Breath — Thổi lửa 🔥

> Spell thứ 8 theo hệ thống template. **Cơ chế channel (giữ để thổi):** player thổi lửa theo hướng con trỏ — row_01 mở miệng → row_02 loop khi NHẤN GIỮ → thả tay = end bằng row_03. Dmg mỗi 0.2s; mỗi tick hit hiện ngẫu nhiên trên hitbox địch (lệch ≥10px so với tick trước). **XOAY MỌI HƯỚNG** — row + hit luôn cùng trục xoay.

## Nguồn VFX pack

- **Pack:** Fire Effect 1 (`Fire_Effect_1_frames`)
- **Gốc:** `C:\Users\phant\Downloads\vfx\Fire_Effect_1_frames\Fire_Effect_1_frames\`
- **Frame:** 48×48

## Frames

| Bộ | Số frame | Nguồn | Dùng cho |
|---|---|---|---|
| row_01 | 3 | `fire_breath_row_01/frame_001..003` | **MỞ** — start thổi |
| row_02 | 4 | `fire_breath_row_02/frame_001..004` | **LOOP** — khi giữ chuột (replay liên tục) |
| row_03 | 7 | `fire_breath_row_03/frame_001..007` | **END** — khi thả tay, play 1 lần |
| hit | 4 | `fire_breath_hit/frame_001..004` | mỗi tick dmg, hiện trên địch |

(preview rename `frame_001` → key `fire_breath_row_01_01.png` v.v. để tránh overlap tên bộ)

## UPDATE theo feedback user (vòng 4 — chốt)

- **Hướng KHÓA lúc kích hoạt** (user: "khi thổi thì không tự xoay nữa"): `breath.angle = angleOf()` chỉ ở `start()`, trong loop KHÔNG cập nhật theo chuột — hết cảm giác "cố thổi vào địch" (giật).
- **Xịm lửa từ chấm vàng**: draw origin = caster (mRep = 0), căn trục lửa theo trục: solid flame frame 48×48 core y=15..38 (đo PIL) → `alignY` dịch lõi lửa về ngang gốc — phần nhọn của lửa nằm ngay trên chấm vàng.
- **Đồng bộ origin (chốt lệch)**: tam giác cone + hit-test dmg + hình lửa CẢ BA dùng chung origin `caster` (cone đỉnh tại caster, range dài thêm 28 để mở đầu từ miệng lửa; hit-test như vậy luôn) — hết lệch giữa 3 thứ.
- Tam giác cone debug + hitbox debug đã BỎ khi final.
- Lerp 0.08 giữ nguyên cho các tình huống khác (không còn ái đáng kể session này vì angle đã khoá).
- **Mũi lửa anchoring** (fix cuối): drawImage `(-tipX*s + pushOut*s, -tipY*s)` với tip = (3, 34) trong frame + `pushOut = 8` (x2 → lửa cách mồm ~16px) — user yêu cầu "cách xa khỏi mồm ra tý" (verify `firstFireOffset [17, −2]` trên tab).

## UPDATE theo feedback user

- **Nguồn sprite ĐÃ ĐO**: frame row_02 solid flame bắt đầu x=1, kết thúc x=39 (mũi lửa trong frame chỉ về PHẢI). flipBase mặc định OFF.
- **Lật khi xoay qua trái**: `scale(1,-1)` khi `|angle|>90°` (cả row + hit) — sprite gốc юрист hướng phải thì lật Y đảo chiều hịt chạm nên đọc hợp lý.
- **Ngọn lửa sát đầu player**: draw origin caster + `mRep` (x2:14, x1:7) — gần hơn trước (28) để mặt lửa CHẠM miệng, không lơ lửng trên đầu.
- **Xoay mượt**: angle lerp 0.08/frame (chậm hơn 0.25 trước) + wrap ±π — giảm giật cảm giác khi con trỏ chạy nhanh.
-

1. **Giữ chuột** = bắt đầu channel: play row_01 một lần → vào row_02 LẶP khít liên tục.
2. **Thả tay** → chuyển row_03 play 1 lần rồi channel kết thúc.
3. **Dmg mỗi `dmgIntervalMs` (0.2s)** khi ở giai đoạn loop; hit-test cone từ miệng player dọc trục angle, trả về mob trong `range` (90px) và `beamW` (40px).
4. **Mỗi tick dmg**: hit frame (4t, 12fps) hiện tại vị trí ngẫu nhiên **trên hitbox địch**, áp theo pháp tuyến của trục thổi: offset ngẫu nhiên trong [-MOB_R-4, +MOB_R+4], **đảm bảo lệch ≥10px so với offset tick trước** (đã verify min gap 14.2px Euclid). Hit cùng trục xoay `breath.angle` — lệch nhiêu breath thì hit lệch nhiêu.
5. **Xoay mọi hướng** (khác earth_bump lật trái/phải): row và hit đều rotate theo `atan2` từ player tới con trỏ — thổi hướng nào cũng được.

## Config

```js
const SPELL = {
  fps: 12,
  dps: 8,               // dmg mỗi tick
  dmgIntervalMs: 200,   // 0.2s/tick
  range: 90,            // tầm thổi
  spreadDeg: 18,        // (hiện chỉ dùng debug cone)
  beamW: 40,            // bề dày hitbox ngọn lửa
};
```

## Lưu ý port vào game

- **Input**: giữ chuột/quay hướng bằng cách kéo con trỏ==góc thổi; giữ A khối mobile parity (`mobile_controls` tap/long-press).
- State machine: `start(row01 once) → loop(hit tick mỗi 200ms) → end(row03 once)` + idle.
- Offset tick dùng biến `lastHitOffset` remember per-breath (reset mỗi lần thổi mới!) — cần reset khi start.
- Hit frame hiện đè lên mob — vẽ theo góc breath; cùng transform với projectile (rotate `angle`).
- Anims Phaser: `fire_row01` (repeat 0), `fire_row02` (repeat -1), `fire_row03` (repeat 0), `fire_hit` (repeat 0), 12fps; tất cả frame 48×48. Xoay mọi hướng: `setRotation(angle)`; KHÔNG flip.
- Hit = offset theo pháp tuyến: `offset = [-sin(a), cos(a)] * pick`.
