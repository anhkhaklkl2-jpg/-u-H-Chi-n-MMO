"""Probe the forest gate area inside cave_area1 (rows 0-9, cols 13-23):
walkable/mask dump + layer art for any SOLID cell near the trigger.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import ASSETS_DIR as ASSETS  # noqa: E402
from game.map_loader import load_map  # noqa: E402


def frac(mask):
    if mask is None:
        return "  -  "
    bits = bin(mask).count("1")
    return f"{bits / 64:4.0%}"


cave = load_map("ekonia/cave_area1", ASSETS)
tm = cave.tile_masks
rows, cols = range(0, 10), range(13, 24)

print("=== CAVE forest gate (trigger rows 1-3, cols 16-20) ===")
header = "      " + "".join(f"{c:>7}" for c in cols)
print(header)
for r in rows:
    line = [f"r{r:>3} "]
    for c in cols:
        w = cave.is_walkable(c, r)
        mask = tm.grid[r][c] if tm else None
        if w:
            cell = "walk" if mask is None else f"w+{frac(mask)}"
        else:
            cell = "SOL" if mask is None else f"m{frac(mask)}"
        line.append(f"{cell:>7}")
    print("".join(line))

print("\n--- layer art at solid cells rows 4-7, cols 15-21 ---")
for r in range(4, 8):
    for c in range(15, 22):
        if cave.is_walkable(c, r):
            continue
        parts = []
        for name, grid in cave.tile_layers:
            parts.append(f"{name}={grid[r][c]}")
        print(f"({c},{r}) SOLID: {' '.join(parts)}")
