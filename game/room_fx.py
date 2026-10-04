"""Room FX anchors (fireplace fire + window light shafts) for indoor maps.

Data-driven like the trader marker: the map author paints marker tiles on
dedicated Tiled layers (ANY non-zero tile works — a floor tile keeps the
marker invisible since every layer renders):

- ``fx lua`` (alias ``fx fire``): one tile per fireplace, ON the fire cell
  (where the flames rise from).
- ``fx cua so`` (alias ``fx window``): one tile per window, ON the window
  cell (the light shaft falls downward from it).

Input layers are the REMAPPED ``MapData.tile_layers`` (post-bbox), so the
returned cells are GAME coords — the same space NPCs, collision and the
client all use. Marker layers never block (no blocking keyword matches)
and never shift the bbox when painted inside the art area.
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from game.map_loader import _normalize_layer_name

# (canonical kind, accepted normalized layer names)
_MARKERS = (
    ("fires", ("fx lua", "fx fire")),
    ("windows", ("fx cua so", "fx window")),
)


def is_fx_marker_layer(name: str) -> bool:
    """True for fx marker layers (metadata, never map art)."""
    nl = _normalize_layer_name(name or "")
    return any(nl == m or nl.startswith(m + " ") for _k, ms in _MARKERS for m in ms)


def detect_room_fx(
    tile_layers: Sequence[Tuple[str, List[List[int]]]],
) -> Dict[str, List[List[int]]]:
    """Collect FX anchor cells from marker layers -> game-coord cells.

    Returns ``{"fires": [[x, y], ...], "windows": [[x, y], ...]}`` with
    empty lists omitted entirely (caller sends nothing when no markers).
    """
    out: Dict[str, List[List[int]]] = {}
    for kind, names in _MARKERS:
        cells: List[List[int]] = []
        for name, grid in tile_layers:
            nl = _normalize_layer_name(name or "")
            if not any(nl == m or nl.startswith(m + " ") for m in names):
                continue
            for y, row in enumerate(grid):
                for x, gid in enumerate(row):
                    if gid:
                        cells.append([x, y])
        if cells:
            out[kind] = cells
    return out
