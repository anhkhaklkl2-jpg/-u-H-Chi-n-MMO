# -*- coding: utf-8 -*-
"""
Convert Kaetram `world.json` (flattened format) into Tiled-ready JSON maps,
split into multiple layers like bigmap:

Per region (MAP_DIVISION_SIZE x MAP_DIVISION_SIZE tiles):
  - 00_ground           : bottommost flat tile of the flattened `data`
  - 01_overhang         : stacked tiles ABOVE the bottom (what was layer-on-layer)
  - 02_high             : `high` tiles (drawn above the player: canopies, roofs)
  - Trees / Rocks / Bushes / Mobs / NPCs / Other Entities : `entities` by kind
  - 03_plateau          : plateau levels (== 2, >= 3, ...)
  - 04_collision        : `collisions` rectangles as tile markers
  - warps / doors       : `areas` as Tiled object layers

Tileset: the 4 Kaetram tilesheets, gid ranges verified against client map.json
  sheet1: 0-4095, sheet2: 4096-10239, sheet3: 10240-14335,
  (gap 14336-14991 is unused in world.json), sheet4: 14992-19087.
Gids in world.json are Tiled-style (1-based, NOT shifted by -1).
"""
import json
import os
import re
import shutil
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "kaetram_extract", "06_maps", "world.json")
OUT = os.path.join(ROOT, "assets", "maps", "kaetram")
TILES_OUT = os.path.join(OUT, "tilesheets")
SHEETS_SRC = os.path.join(ROOT, "kaetram_extract", "07_tilesets", "sheets")

DIV = 48  # Kaetram MAP_DIVISION_SIZE

SHEETS = [  # (firstgid, lastgid) inclusive, Tiled firstgid after +1
    (0, 4095, "tilesheet-1.png"),
    (4096, 10239, "tilesheet-2.png"),
    (10240, 14335, "tilesheet-3.png"),
    (14992, 19087, "tilesheet-4.png"),
]

MARKER_LAYERS = {"Trees", "Rocks", "Bushes", "Mobs", "NPCs", "Other Entities"}


def empty_layer(name: str, w: int, h: int) -> dict:
    # marker layers (entities/plateau/collision) are hidden by default in Tiled
    # so their marker tiles don't cover the real art
    hidden = name.startswith("03_") or name.startswith("04_") or name in MARKER_LAYERS
    return {"data": [0] * (w * h), "height": h, "width": w,
            "id": 0, "name": name, "opacity": 1, "type": "tilelayer",
            "visible": not hidden, "x": 0, "y": 0}

# Entity classification by sprite folder / name pattern
def _names(path):
    d = os.path.join(ROOT, "kaetram_extract", path)
    if not os.path.isdir(d):
        return set()
    return {os.path.splitext(f)[0].lower() for f in os.listdir(d) if f.endswith(".png")}

TREES = _names("07_tilesets/trees")
ROCKS = _names("07_tilesets/rocks")
BUSHES = _names("07_tilesets/bushes")
MOBS = _names("01_mobs_sprites")
NPCS = _names("05_npcs/sprites")

ROCK_PAT = re.compile(r"rock$")


def classify(name: str) -> str:
    n = name.lower()
    if n in TREES:
        return "Trees"
    if n in ROCKS or ROCK_PAT.search(n):
        return "Rocks"
    if n in BUSHES:
        return "Bushes"
    if n in NPCS:
        return "NPCs"
    if n in MOBS:
        return "Mobs"
    return "Other Entities"


LAYER_ORDER = [
    "00_ground", "01_overhang", "01_overhang_2", "01_overhang_3", "02_high",
    "Trees", "Rocks", "Bushes", "Mobs", "NPCs", "Other Entities",
    "03_plateau", "04_collision",
]

# Tiled stores flip flags in the top 3 bits of the gid — mask them off to get
# the real tile id (parser.ts does the same via getFlippedTileId).
FLIP_MASK = 0x1FFFFFFF


def norm_stack(v) -> list:
    """Normalize one `data` cell into a list of 0-based tile ids, bottom→top."""
    stack = [v] if isinstance(v, int) else list(v)
    stack = [t & FLIP_MASK for t in stack if isinstance(t, int) and t > 0]
    return [t for t in stack if t > 0]


def build_tilesets():
    tss = []
    for first, last, img in SHEETS:
        w, h = 0, 0  # read via PIL lazily
        from PIL import Image
        im = Image.open(os.path.join(SHEETS_SRC, img))
        cols, rows = im.size[0] // 16, im.size[1] // 16
        tss.append({
            "firstgid": first + 1,
            "name": os.path.splitext(img)[0],
            "image": "tilesheets/" + img,
            "imagewidth": im.size[0],
            "imageheight": im.size[1],
            "tilewidth": 16, "tileheight": 16,
            "columns": cols, "tilecount": cols * rows,
        })
    return tss


def export_full(d, tilesets, ent_layers, high, plateau, colset):
    """Export the whole world as ONE Tiled map (1152x1008) — heavy but complete."""
    W, H, TS = d["width"], d["height"], d["tileSize"]
    data = d["data"]
    grids = {n: [0] * (W * H) for n in LAYER_ORDER}
    g_ground, g_over, g_high = grids["00_ground"], grids["01_overhang"], grids["02_high"]
    g_over2, g_over3 = grids["01_overhang_2"], grids["01_overhang_3"]
    g_pl = grids["03_plateau"]
    g_col = grids["04_collision"]

    for i, v in enumerate(data):
        stack = norm_stack(v)
        if not stack:
            continue
        g_ground[i] = stack[0] + 1
        # full stack: overhang holds layers 2..4 of the stack (parser stacks
        # tiles bottom→top, so stack[1] is the first tile above the ground)
        if len(stack) > 1:
            g_over[i] = stack[1] + 1
        if len(stack) > 2:
            g_over2[i] = stack[2] + 1
        if len(stack) > 3:
            g_over3[i] = stack[3] + 1
        # high & collisions are TILE-ID lists (0-based, same space as data)
        if any(t in high for t in stack):
            g_high[i] = stack[-1] + 1
        if colset and any(t in colset for t in stack):
            g_col[i] = 1

    for idx, lvl in plateau.items():
        g_pl[idx] = lvl + 1
    for kind, ents in ent_layers.items():
        g = grids[kind]
        for idx in ents:
            g[idx] = 1
    g_col = grids["04_collision"]
    if colset is None:
        for x, y, w, h in d["collisions"]:
            for yy in range(y, y + h):
                row = yy * W
                for xx in range(x, x + w):
                    g_col[row + xx] = 1

    layers = []
    for i, n in enumerate(LAYER_ORDER):
        hidden = n.startswith("03_") or n.startswith("04_") or n in MARKER_LAYERS
        layers.append({"data": grids[n], "height": H, "width": W, "id": i + 1,
                       "name": n, "opacity": 1, "type": "tilelayer",
                       "visible": not hidden, "x": 0, "y": 0})

    objs = []
    oid = 1
    for area in ("warps", "doors"):
        for a in d["areas"].get(area, []):
            objs.append({"height": a.get("height", 1) * TS, "width": a.get("width", 1) * TS,
                         "id": oid, "name": a.get("name", ""), "point": False, "rotation": 0,
                         "type": area, "visible": True,
                         "x": a["x"] * TS, "y": a["y"] * TS})
            oid += 1
    if objs:
        layers.append({"draworder": "topdown", "id": len(layers) + 1, "name": "Areas",
                       "objects": objs, "opacity": 1, "type": "objectgroup",
                       "visible": True, "x": 0, "y": 0})

    mp = {"compressionlevel": -1, "height": H, "width": W, "infinite": False,
          "layers": layers, "nextlayerid": len(layers) + 1, "nextobjectid": oid,
          "orientation": "orthogonal", "renderorder": "right-down",
          "tiledversion": "1.10.2", "tileheight": TS, "tilewidth": TS,
          "type": "map", "version": "1.10", "tilesets": tilesets}
    out = os.path.join(OUT, "world_full.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(mp, f, separators=(",", ":"))
    print("wrote", out, f"({os.path.getsize(out)/1e6:.1f} MB)")


def main():
    os.makedirs(TILES_OUT, exist_ok=True)
    for _, _, img in SHEETS:
        shutil.copy2(os.path.join(SHEETS_SRC, img), os.path.join(TILES_OUT, img))

    with open(SRC, encoding="utf-8") as f:
        d = json.load(f)
    W, H, TS = d["width"], d["height"], d["tileSize"]
    print(f"world {W}x{H} tile {TS}px")

    cols_n, rows_n = W // DIV, H // DIV
    data = d["data"]

    # ---- entities by kind (absolute tile index -> kind) ----
    ent_layers = {}  # kind -> {abs_idx: kind}
    for k, kind in d["entities"].items():
        kind = classify(kind)
        ent_layers.setdefault(kind, {})[int(k)] = kind

    # ---- high / plateau / collisions ----
    # high & collisions are TILE-ID lists (tile types), NOT cell positions
    high = set(d["high"])
    colset = set(d["collisions"]) if d["collisions"] and not isinstance(d["collisions"][0], list) else None
    plateau = {int(k): v for k, v in d["plateau"].items()}

    tilesets = build_tilesets()

    stats = Counter()
    for ry in range(rows_n):
        for rx in range(cols_n):
            ox, oy = rx * DIV, ry * DIV
            base = oy * W + ox
            layers, lid = [], 1
            grids = {}

            def grid(name):
                if name not in grids:
                    grids[name] = empty_layer(name, DIV, DIV)
                return grids[name]["data"]

            g_ground, g_over, g_high = grid("00_ground"), grid("01_overhang"), grid("02_high")
            g_pl = grid("03_plateau")
            g_col = grid("04_collision")

            # absolute tile indexes inside this region (unused for now; kept for
            # future layer-properties export)
            hi_local = set()
            pl_local = {}
            col_local = set()

            for yy in range(DIV):
                row = base + yy * W
                ly = yy * DIV
                for xx in range(DIV):
                    i = row + xx
                    if i >= len(data):
                        break
                    stack = norm_stack(data[i])
                    if not stack:
                        continue
                    # bottom tile -> ground; stack[1..3] -> overhang layers
                    g_ground[ly + xx] = stack[0] + 1
                    if len(stack) > 1:
                        g_over[ly + xx] = stack[1] + 1
                    if len(stack) > 2:
                        grid("01_overhang_2")[ly + xx] = stack[2] + 1
                    if len(stack) > 3:
                        grid("01_overhang_3")[ly + xx] = stack[3] + 1
                    # high = tile TYPE rendered above the player
                    if any(t in high for t in stack):
                        g_high[ly + xx] = stack[-1] + 1
                        hi_local.add((xx, yy))
                    # collision = cell contains a collision-type tile
                    # (collisions AND data are both 0-based tile ids — compare directly)
                    if colset and any(t in colset for t in stack):
                        g_col[ly + xx] = 1
                        col_local.add((xx, yy))

            for idx, lvl in plateau.items():
                xx = idx % W; yy = idx // W
                if ox <= xx < ox + DIV and oy <= yy < oy + DIV:
                    g_pl[(yy - oy) * DIV + (xx - ox)] = lvl + 1
                    pl_local[(xx - ox, yy - oy)] = lvl

            for kind, ents in ent_layers.items():
                g = grid(kind)
                for idx in ents:
                    xx = idx % W; yy = idx // W
                    if ox <= xx < ox + DIV and oy <= yy < oy + DIV:
                        # mark with a fixed marker tile from sheet1 (top-left grass) —
                        # real art comes from entity sprites, not tiles
                        g[(yy - oy) * DIV + (xx - ox)] = 1

            if colset is None:
                for c in d["collisions"]:
                    x, y, w, h = c
                    for yy in range(y, y + h):
                        for xx in range(x, x + w):
                            if ox <= xx < ox + DIV and oy <= yy < oy + DIV:
                                g_col[(yy - oy) * DIV + (xx - ox)] = 1
                                col_local.add((xx - ox, yy - oy))

            # object layers from areas
            objs = []
            for area in ("warps", "doors"):
                for a in d["areas"].get(area, []):
                    ax, ay = a["x"], a["y"]
                    if ox <= ax < ox + DIV and oy <= ay < oy + DIV:
                        objs.append({
                            "height": a.get("height", 1) * TS,
                            "width": a.get("width", 1) * TS,
                            "id": a.get("id", len(objs) + 1),
                            "name": a.get("name", ""),
                            "point": False, "rotation": 0,
                            "type": area,
                            "visible": True,
                            "x": (ax - ox) * TS, "y": (ay - oy) * TS,
                        })

            # assemble
            ordered = [n for n in LAYER_ORDER if n in grids]
            for i, n in enumerate(ordered):
                grids[n]["id"] = i + 1
            layers = [grids[n] for n in ordered]
            if objs:
                layers.append({"draworder": "topdown", "id": len(layers) + 1,
                               "name": "Areas", "objects": objs, "opacity": 1,
                               "type": "objectgroup", "visible": True, "x": 0, "y": 0})

            mp = {
                "compressionlevel": -1,
                "height": DIV, "width": DIV,
                "infinite": False,
                "layers": layers,
                "nextlayerid": len(layers) + 1,
                "nextobjectid": len(objs) + 1,
                "orientation": "orthogonal",
                "renderorder": "right-down",
                "tiledversion": "1.10.2",
                "tileheight": TS, "tilewidth": TS,
                "type": "map",
                "version": "1.10",
                "tilesets": tilesets,
            }
            name = f"world_r{rx}_c{ry}"
            with open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8") as f:
                json.dump(mp, f, separators=(",", ":"))
            stats["maps"] += 1
            stats["nonempty_ground"] += sum(1 for t in g_ground if t)
            stats["overhang"] += sum(1 for t in g_over if t)
            stats["high"] += sum(1 for t in g_high if t)
            stats["collision"] += sum(1 for t in g_col if t)
        print(f"row {ry+1}/{rows_n} done")

    print(stats)
    # entity kind summary
    kinds = Counter()
    for kind, ents in ent_layers.items():
        kinds[kind] = len(ents)
    print(dict(kinds))

    export_full(d, tilesets, ent_layers, high, plateau, colset)


if __name__ == "__main__":
    main()
