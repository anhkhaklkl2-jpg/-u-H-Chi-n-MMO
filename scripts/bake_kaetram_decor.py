# -*- coding: utf-8 -*-
"""
PASS 2 for Kaetram world conversion: bake entity SPRITES (trees, rocks, bushes)
into a visible `Decor` layer (multi-cell, 16px grid), like the Ekonia pipeline.

Entity kinds come from world.json `entities` (index -> kind); sprites come from
07_tilesets/{trees,rocks,bushes}/<kind>.png. The sprite's BOTTOM-CENTER anchors
at the entity tile's bottom edge (Kaetram client y-sorting convention), so big
trees overlap cells ABOVE their anchor. Each 16px slice alpha-composites over
whatever is already there (paint order: ground < overhang < decor).

Usage:
  python scripts/bake_kaetram_decor.py                # world_full.json
  python scripts/bake_kaetram_decor.py world_r13_c8   # single region(s)
"""
import json
import os
import sys
from collections import Counter

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS = os.path.join(ROOT, "assets", "maps", "kaetram")
TS = 16


def load_atlas(folder):
    out = {}
    d = os.path.join(ROOT, "kaetram_extract", "07_tilesets", folder)
    if not os.path.isdir(d):
        return out
    for f in os.listdir(d):
        if f.endswith(".png"):
            out[os.path.splitext(f)[0].lower()] = Image.open(os.path.join(d, f)).convert("RGBA")
    return out


ATLAS = {"Trees": load_atlas("trees"), "Rocks": load_atlas("rocks"), "Bushes": load_atlas("bushes")}
MISSING = Counter()

# Official sprite metadata from Kaetram-Open client (data/sprites.json):
# each sheet packs FRAMES of the given width x height in a grid; frame 0 is
# the complete tree/rock/bush (canopy + trunk together).
def _load_official():
    p = os.path.join(ROOT, "kaetram_extract", "sprites_official.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        entries = json.load(f)
    return {e["id"]: e for e in entries if "width" in e}


OFFICIAL = _load_official()


def kind_atlas(kind: str):
    for group, atlas in ATLAS.items():
        if kind in atlas:
            return group, atlas[kind]
    MISSING[kind] += 1
    return None, None


def bands(img: Image.Image, gap: int = 8):
    """Split a sprite sheet into vertical content bands (separated by alpha gaps)."""
    a = img.getchannel("A")
    w, h = img.size
    rows = [y for y in range(h) if a.crop((0, y, w, y + 1)).getbbox()]
    if not rows:
        return []
    out, start, prev = [], rows[0], rows[0]
    for y in rows[1:]:
        if y - prev > gap:
            out.append((start, prev))
            start = y
        prev = y
    out.append((start, prev))
    return out


def hsplit(img: Image.Image, gap: int = 4):
    """Split a band horizontally into pieces (left-to-right by alpha gaps)."""
    a = img.getchannel("A")
    w, h = img.size
    cols = [x for x in range(w) if a.crop((x, 0, x + 1, h)).getbbox()]
    if not cols:
        return []
    out, start, prev = [], cols[0], cols[0]
    for x in cols[1:]:
        if x - prev > gap:
            out.append((start, prev))
            start = x
        prev = x
    out.append((start, prev))
    return [img.crop((x0, 0, x1 + 1, h)) for x0, x1 in out]


def tight(im: Image.Image) -> Image.Image:
    """Crop to the visible (alpha) content."""
    bbox = im.getchannel("A").getbbox()
    return im.crop(bbox) if bbox else im


# Kinds whose official frame 0 is a bare canopy with NO trunk — these need
# the root piece from the sheet's last band re-attached. All other kinds
# already have a complete tree in frame 0 (verified visually per kind).
CANOPY_ONLY = {"zondul", "zoncil", "alkythn", "heliphatit", "aquasillius", "snowoak"}


def bottom_is_trunk(im: Image.Image, frac: float = 0.35) -> bool:
    """True when the sprite's last rows are narrow (a trunk) rather than a
    rounded canopy edge. Used to tell 'canopy already includes its trunk'
    (oak/bloodwood/pine…) from 'canopy only' (zondul/zoncil…).
    A round canopy's bottom rows also narrow, so also require that the
    widest row is in the UPPER half (trunk-included sprites are widest
    near the bottom of the canopy).
    """
    a = im.getchannel("A")
    w, h = im.size
    widths = []
    for y in range(h):
        b = a.crop((0, y, w, y + 1)).getbbox()
        widths.append((b[2] - b[0]) if b else 0)
    maxw = max(widths) or w
    last = max(i for i, wd in enumerate(widths) if wd > 0)  # last non-empty row
    tail = widths[max(0, last - 2):last + 1]
    narrow_tail = max(tail) < maxw * frac
    widest_upper = widths.index(max(widths)) < h // 2
    return narrow_tail and widest_upper


def first_band(img: Image.Image, kind: str = "") -> Image.Image:
    """Variant #1 of a tree/rock/bush sprite.

    Sheet layout: frame grid per the client's sprites.json (frame 0 = canopy),
    plus a LAST BAND below the grid holding separate root/trunk pieces — the
    client draws the base under the canopy. Canopy-only frames (zondul,
    zoncil…) get their root re-attached; canopies that already include a
    trunk (oak, bloodwood, pine…) are used as-is.
    """
    for prefix in ("trees/", "rocks/", "bushes/"):
        ent = OFFICIAL.get(prefix + kind)
        if ent:
            fw, fh = ent["width"], ent["height"]
            if 0 < fw <= img.size[0] and 0 < fh <= img.size[1]:
                frame = img.crop((0, 0, fw, fh))
                if frame.getchannel("A").getbbox():
                    if kind not in CANOPY_ONLY:
                        return frame  # frame 0 is a complete tree
                    # re-attach the root piece directly under the canopy's
                    # real alpha bottom (not the frame bottom — the canopy
                    # ends mid-frame for round-canopy kinds)
                    bs = bands(img)
                    if len(bs) >= 2:
                        y0, y1 = bs[-1]
                        pieces = hsplit(img.crop((0, y0, img.size[0], y1 + 1)))
                        if pieces:
                            base = tight(pieces[0])
                            bb = frame.getchannel("A").getbbox()  # (l, t, r, b)
                            cw = frame.size[0]
                            canopy_bottom = bb[3]
                            bw, bh = base.size
                            out = Image.new("RGBA", (max(cw, bw), canopy_bottom + bh))
                            out.alpha_composite(frame, (0, 0))
                            # centre the root on the canopy's bottom-row span
                            row_bb = frame.getchannel("A").crop((0, canopy_bottom - 1, cw, canopy_bottom)).getbbox()
                            cx = (row_bb[0] + row_bb[2]) // 2 if row_bb else cw // 2
                            out.alpha_composite(base, (cx - bw // 2, canopy_bottom))
                            return out
                    return frame
            break
    bs = bands(img)
    if not bs:
        return img
    canopy = tight(img.crop((0, bs[0][0], img.size[0], bs[0][1] + 1)))
    if len(bs) < 3 or bottom_is_trunk(canopy):
        return canopy
    # last band = base/trunk pieces (two side by side, one per canopy frame)
    y0, y1 = bs[-1]
    pieces = hsplit(img.crop((0, y0, img.size[0], y1 + 1)))
    if not pieces:
        return canopy
    base = tight(pieces[0])
    cw, ch = canopy.size
    bw, bh = base.size
    out = Image.new("RGBA", (max(cw, bw), ch + bh))
    out.alpha_composite(canopy, ((out.size[0] - cw) // 2, 0))
    out.alpha_composite(base, ((out.size[0] - bw) // 2, ch))
    return out


def official_meta(kind: str):
    for prefix in ("trees/", "rocks/", "bushes/"):
        ent = OFFICIAL.get(prefix + kind)
        if ent:
            return ent
    return None


class Sheet:
    """Baked tileset: unique 16px slices keyed by image bytes."""

    def __init__(self):
        self.slices = {}   # bytes -> gid (1-based within sheet)
        self.images = []   # gid -> PIL image

    def gid_for(self, im: Image.Image) -> int:
        key = im.tobytes()
        gid = self.slices.get(key)
        if gid is None:
            gid = len(self.images) + 1
            self.slices[key] = gid
            self.images.append(im)
        return gid

    def save(self, path: str):
        if not self.images:
            return 0
        cols = min(64, len(self.images))
        rows = (len(self.images) + cols - 1) // cols
        out = Image.new("RGBA", (cols * TS, rows * TS))
        for i, im in enumerate(self.images):
            out.paste(im, ((i % cols) * TS, (i // cols) * TS))
        out.save(path)
        return cols


def bake_map(mp: dict, ents_by_index: dict, name: str = "", names_all=(), packed_keys=False) -> None:
    W, H = mp["width"], mp["height"]
    layers = {l["name"]: l for l in mp["layers"]}
    decor = {}

    # y-sort: paint top-to-bottom so a lower tree's trunk overlaps the canopy
    # of the tree above it, exactly like the client's y-sorted drawing
    for idx, kind in sorted(ents_by_index.items()):
        if packed_keys:
            # packed key from region main(): (x+64) + (y+64)*512 — decode it
            gx, gy = (idx % 512) - 64, (idx // 512) - 64
        else:
            # raw absolute tile index (world_full): gx/gy are LOCAL map coords
            gx, gy = idx % W, idx // W
        group, sprite = kind_atlas(kind)
        if sprite is None:
            continue
        # spritesheet packs variants vertically: take the first band only
        sprite = first_band(sprite, kind)
        sw, sh = sprite.size
        meta = official_meta(kind)
        if meta and "offsetX" in meta:
            # client-drawn position: dx = gridX*16 + offsetX, dy = gridY*16 + offsetY
            ox = gx * TS + meta.get("offsetX", 0)
            oy = gy * TS + meta.get("offsetY", 0)
        else:
            ax = gx * TS                 # anchor: bottom-center of the tile
            ay = gy * TS + TS
            ox = ax - sw // 2            # top-left of sprite placement
            oy = ay - sh
        for yy in range(0, sh, TS):
            for xx in range(0, sw, TS):
                piece = sprite.crop((xx, yy, min(xx + TS, sw), min(yy + TS, sh)))
                if not piece.getbbox():
                    continue  # fully transparent slice
                cx, cy = (ox + xx) // TS, (oy + yy) // TS
                if not (0 <= cx < W and 0 <= cy < H):
                    continue
                decor.setdefault((cx, cy), []).append(piece)

    if not decor:
        print("  no decor sprites")
        return

    sheet = Sheet()
    data = [0] * (W * H)
    firstgid = max(ts["firstgid"] + ts["tilecount"] for ts in mp["tilesets"])  # after last sheet
    for (cx, cy), pieces in decor.items():
        im = Image.new("RGBA", (TS, TS))
        for p in pieces:
            im.alpha_composite(p)
        data[cy * W + cx] = sheet.gid_for(im) + firstgid - 1

    # per-map sheet name — a shared name gets overwritten by whichever map
    # bakes last, corrupting every other map's gids
    sheet_name = f"decor_{name}"
    cols = sheet.save(os.path.join(MAPS, "tilesheets", sheet_name + ".png"))
    # remove old decor tilesets if re-baking (any stale one shifts gids)
    mp["tilesets"] = [t for t in mp["tilesets"] if not t["name"].startswith("decor_")]
    mp["tilesets"].append({
        "firstgid": firstgid,
        "name": sheet_name,
        "image": f"tilesheets/{sheet_name}.png",
        "imagewidth": cols * TS,
        "imageheight": ((len(sheet.images) + cols - 1) // cols) * TS,
        "tilewidth": TS, "tileheight": TS,
        "columns": cols, "tilecount": len(sheet.images),
    })

    # remove old decor layer if re-baking
    mp["layers"] = [l for l in mp["layers"] if l.get("name") != "Decor"]
    insert_at = max(i for i, l in enumerate(mp["layers"]) if l["type"] == "tilelayer") + 1
    mp["layers"].insert(insert_at, {
        "data": data, "height": H, "width": W, "id": mp["nextlayerid"],
        "name": "Decor", "opacity": 1, "type": "tilelayer", "visible": True, "x": 0, "y": 0,
    })
    mp["nextlayerid"] += 1
    print(f"  decor cells: {len(decor)}, unique slices: {len(sheet.images)}")


def main():
    with open(os.path.join(ROOT, "kaetram_extract", "06_maps", "world.json"), encoding="utf-8") as f:
        w = json.load(f)
    W = w["width"]
    ents = {int(k): v for k, v in w["entities"].items()}

    names = sys.argv[1:] or ["world_full"]
    for name in names:
        p = os.path.join(MAPS, name + ".json")
        if not os.path.exists(p):
            print("missing", name)
            continue
        print(name)
        mp = json.load(open(p, encoding="utf-8"))
        if name == "world_full":
            # ents keys are RAW absolute tile indexes — bake_map decodes with
            # idx % W / idx // W (packed-key formula would scatter everything)
            bake_map(mp, ents, name, names, packed_keys=False)
        else:
            # regions: include every entity whose sprite REACHES into this
            # region (canopy/trunk overhang the 48x48 border), then clip
            # only the cells that fall outside the region
            rx, ry = int(name.split("_r")[1].split("_c")[0]), int(name.split("_c")[1])
            DIV = 48
            local = {}
            for k, v in ents.items():
                idx = int(k)
                cx0, cy0 = idx % W, idx // W
                if not (rx * DIV - 8 <= cx0 < (rx + 1) * DIV + 8
                        and ry * DIV - 8 <= cy0 < (ry + 1) * DIV + 8):
                    continue
                # pack (x,y) into a negative-safe key: shift by +64 so both
                # components stay positive through the round-trip
                local[(cx0 - rx * DIV + 64) + (cy0 - ry * DIV + 64) * 512] = v
            bake_map(mp, local, name, names, packed_keys=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(mp, f, separators=(",", ":"))
    print("missing sprite kinds:", dict(MISSING))


if __name__ == "__main__":
    main()
