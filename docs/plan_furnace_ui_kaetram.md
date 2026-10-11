# Plan: Lò nung (Furnace UI) theo cơ chế Kaetram — web client

> Nguồn tham khảo: `_kaetram_src/packages/` — client `menu/crafting.ts` (316 dòng),
> server `controllers/crafting.ts`, data `crafting/smelting.json` + `smithing.json`,
> cursor `cursors/smelting.png` / `cursors/smithing.png`.

## 1. Kaetram có sẵn gì (tìm thấy)

| Thành phần | Vị trí | Dùng được gì |
|---|---|---|
| **UI crafting 1 panel duy nhất cho MỌI skill** | `client/src/menu/crafting.ts` | 1 menu: list option trái, requirement phải, result + level, nút craft **x1/x5/x10** |
| **Data smelting** | `server/data/crafting/smelting.json` | Mỗi recipe: `level`, `experience`, `chance` (% thành công), `requirements[]`, `result.count` |
| **Server controller** | `server/src/controllers/crafting.ts` | `open(player, skill)` → `select(key)` → `craft(key, count)`; craft XÁC MINH items trên server, **roll chance** từng lò, trừ fail |
| **Cách mở lò** | `player.ts` ~dòng 933: map cursor tile → `smelting`/`smithing` | Người chơi đứng gần **tile có cursor** (map data gán `tileId -> "smelting"`) → server mở panel theo skill |
| **Cursor pixel art** | `client/public/img/sprites/cursors/smelting.png`, `smithing.png` | PNG sẵn để làm cursor khi hover lò (web client đã dùng `cursors/crafting.png` cho bàn chế tạo — cùng pattern) |
| **XP/skill** | `skills.ts`, `Modules.Skills` màu mỗi skill | Dùng sau nếu muốn XP bar (chưa cần) |

**Kết luận:** Kaetram KHÔNG có "lò nung riêng" — nó tái dùng **đúng UI crafting** với data khác (`smelting.json` thay `crafting.json`). Cơ chế cốt lõi: *đứng gần lò → mở panel smelting → chọn recipe → server kiểm tra + trừ nguyên liệu + roll chance → nhận output*.

## 2. Plan triển khai (nhanh nhất, tận dụng code hiện có)

### Bước 1 — Server: mở rộng `game/smelting.py` theo model Kaetram (~30 phút)
- Thêm vào `SmeltDef`: `chance: int = 100` (Kaetram roll % thành công từng lượt — mình thêm y hệt).
- Data: `iron_ore→iron_ingot chance 90`, `gold_ore→gold_ingot chance 90`, `iron_ingot→steel_ingot chance 75` (đã có sẵn registry, chỉ thêm chance).
- Op web mới: `craft_op {op:"smelt", recipe_id, count}` trong `web_api/core.py` → manager check gần lò (đã có `nearest_furnace`) + đủ nguyên liệu → roll chance từng lượt → trả `{ok, made, failed}`.
- Không đổi giao thức Discord — chỉ thêm op web.

### Bước 2 — Client web: tái dùng panel craft hiện có (~1 giờ)
- Không làm UI mới. Panel craft hiện tại tự **đổi nội dung thành smelting khi đứng gần LÒ** (thay vì bàn chế tạo): list quick-craft = `SMELT_REGISTRY`, chọn recipe → requirement + result (đã có `makeCraftDescription`).
- Nút CREATE → gửi op `smelt` (thêm 3 nút nhỏ **x1/x5/x10** như Kaetram cạnh CREATE).
- **Cursor lò nung**: copy `cursors/smelting.png` + `smithing.png` từ Kaetram vào `web_client/public/ui/cursors/`, hover lò hiện cursor đó (giống `crafting.png` đang làm với bàn — vài dòng trong `game.ts`).
- **Kết quả**: dùng `craft_result` frame hiện có (parked result) — lò cũng park output vào result slot, click để lấy.

### Bước 3 — Animation lò nung (optional, ~45 phút)
- Kaetram không có animation lò riêng (lò chỉ là tile + cursor). Dùng được:
  - **Lửa**: particle emitter đã có pattern trong scene → lò đang nung phát particle lửa nhỏ trên block furnace.
  - **Progress ring trên lò**: rectangle fill đã có (zombie HP bar) → thanh tiến trình % trên block lò khi đang smelt (snapshot gửi furnace state tương tự `_craft_part`).
- Bỏ qua nếu muốn gấp — không animation vẫn chơi được.

### Bước 4 — Preview (~15 phút)
File HTML tĩnh `docs/furnace_preview.html` dựng đúng layout panel V5 hiện có (frame `craft_frame.png`) nhưng nội dung smelting:
- Trái: 3 recipe (Nung thỏi sắt / Nung thỏi vàng / Nung thép) với icon thật.
- Phải: requirement + result + 3 nút x1/x5/x10.
- Mở bằng trình duyệt trực tiếp, không cần server.

## 3. Thứ tự làm khi bạn OK

1. Preview HTML (bạn duyệt layout trước khi code thật) — 15'
2. Server: chance + op smelt + test — 30'
3. Client: nội dung smelting khi gần lò + cursor + x1/x5/x10 — 60'
4. Animation lửa + progress ring (nếu muốn) — 45'
5. Deploy + test thực tế

Tổng ~2h không tính animation, ~2h45 có animation.
