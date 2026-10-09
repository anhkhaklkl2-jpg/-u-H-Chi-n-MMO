"""Dump art GIDs per layer at gate-adjacent cave cells: are the SOLID
cells (row 54, cols 78-79/82-83) real wall art or open floor wrongly
blocked? Also prints raw solids.json claims for those cells.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import ASSETS_DIR as ASSETS  # noqa: E402
from game.map_loader import load_map  # noqa: E402

md = load_map("ekonia/cave_area1", ASSETS)

CELLS = [(78, 54), (79, 54), (80, 54), (81, 54), (82, 54), (83, 54),
         (77, 54), (84, 54), (79, 55), (82, 55)]

print("--- layer GIDs at cave gate cells ---")
for name, grid in md.tile_layers:
    row = []
    for (x, y) in CELLS:
        row.append(f"({x},{y})={grid[y][x]}")
    print(f"{name:>20}: {'  '.join(row)}")

solids_path = Path(ASSETS) / "ekonia" / "cave_area1.solids.json"
raw = json.loads(solids_path.read_text(encoding="utf-8"))
print("\n--- raw solids.json keys ---")
print(list(raw.keys()))
solid_cells = raw.get("solid_cells") or {}
poly_cells = raw.get("poly_cells") or {}
print("\n--- raw solids claims at gate cells ---")
for (x, y) in CELLS:
    sc = solid_cells.get(str((x, y))) or solid_cells.get(f"{x},{y}")
    pc = poly_cells.get(str((x, y))) or poly_cells.get(f"{x},{y}")
    print(f"({x},{y}): solid={sc is not None} poly={'yes' if pc is not None else 'no'}")
