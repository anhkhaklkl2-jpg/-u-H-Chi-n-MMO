# Session 15-16/09: Converter map Godot (Ekonia) → Tiled JSON

> Nguồn map: `D:\D- RE du an build game mmo discord cho server rainbow cat`
> (game gốc tên **Ekonia**, repo Godot `SlayHorizon/godot-tiny-mmo` trên GitHub —
> bản GitHub mới hơn bản local vài commit, 23/07/2026).
> Tool: `scripts/convert_ekonia_maps.py`. Output: `assets/maps/ekonia/*.json`.

## Kết quả cuối

- **25 map** chuẩn Tiled JSON tại `assets/maps/ekonia/` + **1 tileset baked duy nhất**
  `assets/maps/ekonia/tiles/ekonia_baked.png` (~2500+ tile 16px unique).
  Tiled mở trực tiếp là đúng (path tileset = `tiles/*.png`, tương đối với file map).
- `*.solids.json` per map: `solid_cells` = **tọa độ ô tuyệt đối** (không phải gid).
- Preview: `docs/_ekonia_previews/` (ảnh PNG render từ chính JSON output) +
  `docs/_ekonia_maps_preview.html` (nhúng data-URI).
- `game/map_loader.py` đã patch `_resolve_tilesets` thử thêm thư mục của map
  (`map_dir`) → load `ekonia/dungeon`, `ekonia/overworld` OK. Tile size gốc **16px** —
  renderer game cần scale 2x nếu muốn 32px như map cũ.
- **Verify pixel-perfect**: có script render độc lập thẳng từ `.tscn` theo đúng
  công thức `TileMapLayer::draw_tile()` của Godot 4.3 rồi so pixel với render từ JSON
  — `dungeon`, `forest`, `trade_house_outside`, `guild_house_inside`... đều diff None.

## Các bug đã sửa (theo thứ tự phát hiện)

1. **Parse `.tres` sai** — tileset khai atlas qua `sources/N = SubResource("id")`;
   parser cũ đọc sub_resource theo thứ tự file → mất/misindex cả atlas
   (dungeon Ground 1695 ô resolve về 0). Fix: map đúng `sources/N → sub_resource`.
2. **Đánh gid tuần tự thay vì theo vị trí** — Tiled đọc gid theo vị trí trong lưới
   ảnh (`firstgid + row*columns + col`). Fix: gid positional.
3. **Đường dẫn tileset sai** — `image` phải là `tiles/<tên>.png` (tương đối với
   file JSON, không phải project root) nếu không Tiled hiện ô đỏ.
4. **Multi-cell tiles + `texture_origin`** — cây/núi/đá có `size_in_atlas` (2x2 →
   6x6, cây tới 12x14) và `texture_origin` (pixel). Godot vẽ:
   `dest = tâm_ô − size/2 − texture_origin`, flips H/V qua `alternative_tile`
   (bit 4096/8192). Converter phải **bake**: tính dest rect từng tile, cắt theo
   lưới 16px toàn cục. Đây là bug gây "thiếu assets trầm trọng" (mất tán cây...).
5. **`bake()` đọc `sizes`/`origins` từ cache texture sai nguồn** — dữ liệu thật nằm
   trong atlas dict của `.tres`. Bug này lại khiến mọi multi-cell tile bị cắt 1 ô.
   → Bài học: luôn truyền metadata thẳng vào hàm bake.
6. **Alpha composite thay vì last-write-wins** — mái nhà vẽ chồng nhiều layer
   (Lower_roof → Roof → Top_roof), Godot blend alpha; last-write gây "mái chẻ lớp".
   Cell composite giống nhau được dedupe thành 1 gid; gid gán **lazily**.
7. **Instance scenes (Sprite2D/nested .tscn) không phải tile** — nhà, quặng, herb
   trong Ekonia là **scene đặt bằng pixel position**, không nằm trong TileMapLayer.
   Converter expand: nested building .tscn (recursively bake layer con kèm
   `position` offset) + mineable nodes (đọc region verbatim từ
   `mineable_nodes/*.tres` — đừng hard-code, region là số thực lẻ).
8. **Layer con có `position` riêng** (Roof 0,43; Walls 0,−80; forest lệch (1,0)) —
   bỏ qua là mái lệch/mất cửa.
9. **Parent node offset** — `Questboard` là TileMapLayer con của Area2D có
   `position = (−267, −419)`; phải cộng offset node cha (bất kỳ Node2D) vào
   toạ độ tile. Fix các món "ghế/thùng/bàn đâm tường, lơ lửng ngoài map".
10. **Sid gap** — `buildings_outside_tileset.tres` khai sources `0,1,3` (thiếu 2):
    phải **giữ nguyên chỉ số Godot** (placeholder None), không nén lại.

## Quyết định layer order (đã qua thử–sai)

- Thử hạ `Props*` xuống dưới Ground → props biến mất dưới nền → **hoàn tác**.
- **Kết luận cuối: giữ thứ tự scene-tree tự nhiên** `Ground > Walls > Props`,
  `Objects`/`Questboard`/`Stairs` trên Props. Đồ nội thất "đâm tường" đúng ra là
  bug parent-offset (mục 9), không phải layer order.
- Cell trong suốt không đè; composite chỉ blend pixel alpha > 0.

## Việc còn treo / next step

- **Chưa wire vào gameplay**: muốn chơi thật thì register `ekonia/dungeon` /
  `ekonia/cave_area1` / `ekonia/overworld` làm lựa chọn `/startmap`, dùng
  `solid_cells` cho collision, scale 16→32px trong renderer, và **upload cả thư mục
  `assets/maps/ekonia/` lên cloud** (JSON + PNG baked) qua `scripts/upload_tree.py`.
- NPC/enemy/warper/spawn markers trong .tscn **chủ động bỏ qua** (gameplay entity,
  không phải art) — sau này có thể parse làm spawn/NPC data.
- Tailing props y-sorted (tán cây rìa rừng) có thể thiếu nhẹ nếu là entity riêng —
  nếu cần thì sprite-bake tương tự ore.

## Việc khác trong session (đã xong trước đó)

- Craft pattern: đã thêm `layout` payload từ client → `craft_from_inputs`
  (có lần crash `NameError: frame` trong `game/manager.py` — đã xử lý theo log),
  recipes trả kèm `pattern`, client tự fill ô craft theo pattern khi click recipe.
- Converter chỉ là **tool local** — sửa converter không cần deploy; sửa
  `game/map_loader.py` thì đã deploy bằng `scripts/deploy_files.py`.
