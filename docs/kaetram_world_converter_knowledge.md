# Kaetram `world.json` → Tiled + decor baking (kiến thức session)

> **🚨 LƯU Ý TO ĐÙNG:** Discord client đang TẠM NGƯNG PHÁT TRIỂN. Mọi tính năng
> preview/map mới đều là cho WEB CLIENT — xem preview bằng web client (các lệnh
> `/previewmap`/`/startmap` là cầu nối vào map, dùng được cho cả hai).

Nguồn: `kaetram_extract/` (extract từ repo `Kaetram/Kaetram-Open`).
Không có repo `.tmx` map gốc công khai (org Kaetram chỉ có 5 repo, không có `Kaetram-Maps`)
→ phải dựng lại layer từ file đã **flatten**.

## Pipeline

| Script | Việc |
|---|---|
| `scripts/convert_kaetram_world.py` | `world.json` → 504 region 48×48 (`world_r<c>_<r>.json`) **+ `world_full.json`** (1152×1008) |
| `scripts/bake_kaetram_decor.py` (pass 2) | bake **sprite** cây/đá/bụi thành layer `Decor` (visible) |
| `scripts/_preview_kaetram.py` | render PNG preview từ JSON |
| `scripts/build_kaetram_gallery.py` | dựng `docs/_kaetram_world_preview.html` (zoom/pan) |

Deploy: `assets/maps/kaetram/` (~59 MB) + `tilesheets/` (4 sheet gốc + `decor_*.png`).

## Bảng gid (quan trọng)

`world.json.data` lưu gid **+1 so với tile id** (parser Kaetram trừ 1 khi export):
gid = sheet_firstgid + 1. Mapping 4 sheet (lấy từ `client_maps/map.json`, đã verify):

- sheet1 `0–4095` → Tiled firstgid 1
- sheet2 `4096–10239` → 4097
- sheet3 `10240–14335` → 10241
- **gap `14336–14991` không dùng** (0 ô) → an toàn
- sheet4 `14992–19087` → 14993
- 29 ô có gid > 19087 (rác) → bỏ

`high` và `collisions` là **danh sách TILE-ID (loại tile)**, KHÔNG phải vị trí ô:
- `02_high`: ô nào có tile thuộc `high` → vẽ trên đầu player (5.067 ô)
- `04_collision`: ô chứa tile thuộc `collisions` (id **0-based**, nên so `t-1`) → 66.722 ô
- `plateau` và `entities` thì **là vị trí** (index → level / kind)

## Layer xuất ra

`00_ground` (tile đáy) · `01_overhang` (tile trên cùng của stack) · `02_high` ·
`Trees/Rocks/Bushes/Mobs/NPCs/Other Entities` (marker) · `03_plateau` · `04_collision` ·
**`Decor`** (visible — sprite bake) · object layer `Areas` (warps/doors, 284 object).
Các layer marker `visible:false` để không đè art khi mở Tiled.

## Sprite cây/đá/bụi — metadata chính thức (bản cập nhật sau)

Nguồn chân ái: **`kaetram_extract/sprites_official.json`** (copy của
`packages/client/data/sprites.json` trên GitHub Kaetram-Open). Mỗi loài khai báo
`width×height` (frame size thật) + `offsetX/offsetY`. Ví dụ: bloodwood 64×96,
sheet 128×288 = **lưới frame 2 cột × 3 hàng** (KHÔNG phải band dọc!), frame 0 = cây hoàn chỉnh.

- **Vị trí đặt sprite (luật client gốc):** `x = tileX*16 + offsetX`, `y = tileY*16 + offsetY`
  (tile top-left + offset, KHÔNG trừ chiều cao). Converter phải dùng đúng offset này,
  đừng tự canh "đáy-giữa ô".
- **Quy tắc frame:** ưu tiên frame size chính thức từ sprites.json;
  fallback `first_band()` (nhóm hàng alpha liền nhau) chỉ cho loài không có metadata.
- **Loài "canopy-only"** (tán tròn KHÔNG có thân trong frame 0): zondul, zoncil,
  alkythn, heliphatit, aquasillius, snowoak. Phần **gốc/thân nằm ở band cuối của sheet**
  (mỗi canopy 1 miếng gốc). Phải ghép gốc vào **đáy vùng alpha thật của tán** (không phải
  đáy frame 96px). Fix bằng danh sách loài tường minh — heuristic "hàng đáy hẹp = có thân"
  đã thất bại (ghép nhầm 2 gốc cho oak/bloodwood).
- **Cây vắt biên region:** entity anchor nằm ngoài region 48×48 vẫn phải bake phần sprite
  lòi vào (quét vùng đệm ±8 tile, nới guard index âm), rồi cắt từng ô ngoài region.
- **Key entity phải encode 2 chiều an toàn:** `(x+64) + (y+64)*512` — key `x + y*48`
  decode bằng `% 48` sai vị trí với x≥48 (bug 2113 % 48 = 1).
- **Indent của vòng lặp bake:** từng có dòng `local[...]` bị tuột ra khỏi `for` → mỗi map
  chỉ bake 1 entity cuối. Check bằng sweep: so tập ô decor kỳ vọng (world.json + offset)
  với JSON của cả 504 region — phải khớp 100%.

## Bug đã dẫm (đừng lặp lại)

1. **`high`/`collisions` hiểu là vị trí ô** → layer sai bản chất. Đúng: chúng là tile-id.
2. **Marker tile gid 1** vẽ ra ô art sai (tile đầu sheet1) — phải để layer ẩn.
3. **Entities là SPRITE, không phải tile** — cây/đá/bụi nằm ở `07_tilesets/{trees,rocks,bushes}/`.
   Không bake → map "trống trãi / thiếu assets".
4. **Sprite = nhiều biến thể xếp dọc, phân cách bằng khoảng alpha trống**
   (bloodwood 128×288: cây#1 rows 4–67, cây#2 100–163, gốc cây nhỏ 254+).
   Cắt `h//2` → lấy cây#1 + nửa cây#2 ⇒ **cây mất gốc, tán lìa thân**.
   Fix: `first_band()` — nhóm hàng alpha liền nhau, cắt **band đầu tiên**.
5. **Quên cộng `firstgid` cho gid của Decor** → gid 1..N trỏ vào tilesheet-1 → rác
   window/crate rải khắp map. Đúng: `gid_for(slice) + firstgid - 1`.
6. **Sheet decor dùng tên chung** giữa nhiều map → map bake sau **ghi đè** file, gid map
   trước hỏng. Fix: `decor_<tên map>.png` riêng từng map, và re-bake phải **xóa tileset
   decor cũ** (nếu không `firstgid` bị đẩy lên và cũ lẫn mới cùng tồn tại).
7. **Local index region tính sai** (`i - (ry*DIV*W + rx*DIV)`) → cây rơi sai chỗ.
   Đúng: `(i%W - rx*DIV) + (i//W - ry*DIV)*DIV`.
8. **Trật tự vẽ**: client **y-sort** entity ⇒ bake phải `sorted(ents)` (trên→dưới) để thân
   cây dưới đè lên tán cây trên, không thì "thân lìa khỏi tán".
9. **Preview hardcode 4 sheet** → sau khi thêm `decor_baked` thì map gid sai ⇒ rác.
   Preview phải đọc `mp["tilesets"]` động.
10. Sửa script bằng `str_replace` cẩn thận: từng chèn `def empty_layer` vào **giữa thân
    `main()`** làm hàm kết thúc sớm (script chạy 0.5s rồi exit 0 mà không làm gì).
11. **Ảnh preview cũ trong gallery:** gallery nhúng PNG từ `docs/_kaetram_previews/` —
    sau mỗi lần bake mới PHẢI xóa + render lại toàn bộ PNG region rồi mới build gallery,
    nếu không user nhìn ảnh của bản lỗi cũ tưởng bug chưa fix. Đánh dấu version rõ trong
    tiêu đề gallery để phân biệt cache.
12. **"Cây bị xén" ở mép region là bản chất của cắt 48×48** — cây vắt biên luôn trông
    cắt khi xem từng region riêng; dữ liệu đầy đủ, ghép 2 region kề nhau (hoặc xem
    `world_full`) là liền. Không phải bug. Tiled sẽ thấy giống vậy.
13. **`world_full` dùng RAW index, region dùng packed key** — `bake_kaetram_decor.py`
    nhận entity theo 2 dạng: region truyền key nén `(x+64)+(y+64)*512`, còn world_full
    truyền index thô `y*W+x`. Truyền nhầm dạng → decode sai → cây/đá rải LOẠN khắp map,
    biome này đè lên biome khác (flag `packed_keys=` quyết định cách decode).
14. **Stack ≥3 tầng mất tầng giữa** — parser gốc xếp data bottom→top; giữ chỉ đáy+đỉnh
    làm mất art. Fix: tách `01_overhang_2` (stack[2], 6.504 ô) + `01_overhang_3`
    (stack[3], 115 ô).
15. **Collision so id lệch 1** — parser.ts trừ 1 lúc parse nên data đã 0-based:
    so TRỰC TIẾP `t in colset` (111.117 ô); so `(t-1)` chỉ ra 69.001 ô → thiếu tường.
    Tiled gid vẫn là `t+1`.
16. **Tile flip-flag** — 20 ô có id kiểu 3221227029 (bit 0xC0000000 = cờ flip Tiled);
    mask `& 0x1FFFFFFF` trước khi dùng, nếu không stack parse bỏ ô đó.
17. **Quy ước tên region**: `world_r{rx}_c{ry}` — rx 0..23 (trục X), ry 0..20 (trục Y).
    Quét vòng lặp nhầm trục sẽ bake thiếu 63 region mà không báo lỗi rõ.

## Trạng thái cuối session

- 504 region + `world_full.json` đều có layer `Decor` (sheet riêng `decor_<tên>.png`).
- **Nguồn chính thức đã fetch**: `kaetram_extract/_parser.ts` (packages/tools/map/parser/parser.ts)
  + `_exporter.ts` từ GitHub Kaetram-Open — đây là chân ái cho mọi quy ước format.
- Layers world_full: 00_ground, 01_overhang, 01_overhang_2, 01_overhang_3, 02_high,
  markers, 03_plateau, 04_collision, Decor, Areas (objects).
- Gallery `docs/_kaetram_world_preview.html` v11 (zoom wheel/pan, Fit/1x/2x/4x).
- **Vấn đề còn mở (user sẽ fix tay trong Tiled):** 1–2 loài cây (zondul/zoncil trong
  rừng máu r13_c8) vẫn thiếu/mất gốc khi bake — user chấp nhận vào Tiled đặt thủ công.
  Nếu đụng lại: soi band cuối sheet của loài đó, kiểm tra anchor gốc có khít đáy tán không.

## Kiểm chứng

- So pixel độc lập: render tile layer thẳng từ `world.json` (composite đủ stack) rồi diff
  với render từ JSON convert → chỉ còn vài ô chênh ở góc (khác thứ tự stack) ⇒ tile layer khớp.
- Preview: `docs/_kaetram_world_preview.html` (v4) — 8 viewer có zoom (wheel), pan (drag),
  nút Fit/1x/2x/4x. Ảnh: `docs/_kaetram_previews/*.png`.

## Chưa làm

- **Mobs/NPCs (171 loại)** không bake — là nhân vật/quái động (animated, không phải decor tĩnh).
- `01_overhang` chỉ giữ tile **trên cùng** của stack; ô có ≥3 tile thì mất tầng giữa
  (muốn đủ thì tách thành nhiều layer overhang theo độ sâu).
- Chưa wire vào gameplay (`/startmap`, collision từ `04_collision`, scale 16→32px).
