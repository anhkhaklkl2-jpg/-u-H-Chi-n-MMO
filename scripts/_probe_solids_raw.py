"""Inspect raw cave_area1.solids.json structure and claims at gate cells."""
import json
from pathlib import Path

p = Path("assets/maps/ekonia/cave_area1.solids.json")
raw = json.loads(p.read_text(encoding="utf-8"))

print("keys:", list(raw.keys()))
sc = raw["solid_cells"]
pc = raw["poly_cells"]
print("solid_cells type:", type(sc).__name__, "len:", len(sc))
print("poly_cells type:", type(pc).__name__, "len:", len(pc))
print("solid_cells[0:3]:", sc[:3] if isinstance(sc, list) else list(sc.items())[:3])
print("poly_cells[0:3]:", pc[:3] if isinstance(pc, list) else list(pc.items())[:3])

if isinstance(sc, list):
    # could be flat w*h bitmap or list of pairs
    first = sc[0]
    if isinstance(first, (list, tuple)) and len(first) == 2:
        claims = {(x, y) for x, y in sc}
    else:
        print("unknown list format, sample:", sc[:10])
        claims = set()
    pcclaims = set()
    if isinstance(pc, list) and pc and isinstance(pc[0], (list, tuple)):
        pcclaims = {(c[0], c[1]) for c in pc if len(c) >= 2}

CELLS = [(78, 54), (79, 54), (80, 54), (81, 54), (82, 54), (83, 54),
         (77, 54), (84, 54), (79, 55), (82, 55), (75, 54), (85, 54)]
print("\nclaims at gate cells:")
for (x, y) in CELLS:
    s = (x, y) in claims if claims else "?"
    pp = (x, y) in pcclaims if pcclaims else "?"
    print(f"({x},{y}): solid={s} poly={pp}")
