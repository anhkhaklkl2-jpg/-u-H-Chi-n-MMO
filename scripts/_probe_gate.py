"""Probe gate collision exactly as production computes it (no preview).

Prints, for every tile around each gate: walkable?, mask present?, mask
block-fraction. Then simulates can_move_float crossings both directions.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import ASSETS_DIR as ASSETS  # production assets dir (assets/maps)

from game.map_loader import load_map
from game.collision import Collision, FLOAT_BOX_HALF

BIGMAP_GATE = range(77, 86)   # cols around 80-82
CAVE_GATE = range(75, 87)     # cols around 78-83


def frac(mask) -> str:
    if mask is None:
        return "  -  "
    bits = bin(mask).count("1")
    return f"{bits/64:4.0%}"


def dump(md, rows, cols, label):
    print(f"\n=== {label} ({md.map_id}) rows {rows} cols {cols} ===")
    tm = md.tile_masks
    header = "      " + "".join(f"{c:>7}" for c in cols)
    print(header)
    for r in rows:
        line = [f"r{r:>3} "]
        for c in cols:
            w = md.is_walkable(c, r)
            mask = tm.grid[r][c] if tm and 0 <= r < tm.height and 0 <= c < tm.width else None
            if w:
                cell = "walk" if mask is None else f"w+{frac(mask)}"
            else:
                cell = "SOL" if mask is None else f"m{frac(mask)}"
            line.append(f"{cell:>7}")
        print("".join(line))


def try_move(md, x, y, dx, dy, label):
    col = Collision(md)
    ok, npair = col.can_move_float(x, y, dx, dy)
    print(f"{label}: from ({x},{y}) d=({dx},{dy}) -> ok={ok} to={npair}")


def main():
    big = load_map("bigmap", ASSETS)
    cave = load_map("ekonia/cave_area1", ASSETS)

    dump(big, range(0, 8), BIGMAP_GATE, "BIGMAP top gate (cols 80-82 x rows 2-3)")
    dump(cave, range(50, 56), CAVE_GATE, "CAVE bottom exit (trigger row 55, cols 78-83)")

    print("\n--- simulated crossings (FLOAT_BOX_HALF=%.2f) ---" % FLOAT_BOX_HALF)
    # bigmap: arrive (80,4)/(81,4); try to walk UP into/out of the gate
    for x, y in [(80.5, 4.5), (81.5, 4.5)]:
        try_move(big, x, y, 0.0, -1.0, "bigmap up into gate")
    # cave: arrive (80,54)/(81,54); try to walk DOWN to the exit trigger row 55
    for x, y in [(80.5, 54.5), (81.5, 54.5)]:
        try_move(cave, x, y, 0.0, 1.0, "cave down to exit  ")
    # lateral approach along the gate mouth on bigmap row 4
    try_move(big, 79.5, 4.5, 1.0, 0.0, "bigmap row4 right ")
    try_move(big, 82.5, 4.5, -1.0, 0.0, "bigmap row4 left  ")


if __name__ == "__main__":
    main()
