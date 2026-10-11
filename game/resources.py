"""Harvestable map nodes (trees / bushes) — pure game logic, no discord.

The resource nodes live in the Tiled layers whose name matches
``RESOURCE_LAYER_NAMES`` (the bigmap ships one named "cây"). A node is a
small tile cluster: a Pipoya big tree is a 2x2 block (gids 9,10 top row /
17,18 bottom row) and a bush is a single tile (gid 41). Chopping works per
NODE (anchor tile), never per coordinate — rule 17 (no hard-coded coords).

State per scenario: chop progress and regrow deadlines. Persistence and
Discord UI live in other layers (persistence/, discord_ui/).
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from game.actions import ChopAction
from game.state import ActionResult, Direction, GameState

# Tiled layers that hold harvestable nodes (matched case/space-insensitively).
RESOURCE_LAYER_NAMES = {
    "cây", "cay", "tree", "trees", "resources",
    # Ore/rock veins live on the bigmap's misc-item layer.
    "vật phẩm ko liên quan", "vat pham ko lien quan", "ore", "ores", "mine",
    # Mineable rock nodes (bigmap layers "tảng đá nhỏ" / "tảng đá lớn").
    "tảng đá nhỏ", "tang da nho", "tảng đá lớn", "tang da lon",
    # Field forage (user 15/09): mushrooms, grass tufts, flowers — one-hit
    # nodes that shatter into sand grains on the client.
    "nấm nâu", "nam nau", "nấm tím", "nam tim", "cỏ", "co",
    "hoa trắng", "hoa xanh", "hoa tím", "hoa vàng", "hoa", "flower", "flowers",
    # NOTE: the dead-tree layer ("cây chết") is deliberately NOT here — its
    # art reuses the same Pipoya gids as the misc-item layer, so scanning it
    # would resurrect the minable-dead-tree bug (gid 47/48).
    # "cây cầu(đi qua được)" (the lobbytrade bridge) must never match "cây":
    # it is decor art on a walkable carve, not harvestable nodes.
    # Ekonia cave props (user 30/09: "đá và nấm trong cave đập được như ngoài
    # thảo nguyên"): the cave's decor layer is named "Props".
    "props", "props2",
}

# Data-driven tile registry: resource-layer GID -> (kind, dx, dy from anchor).
# _FORAGE_NODE_KINDS: node kinds the map loader CARVES as walkable in the
# static collision grid (the lobbytrade tree layer carries decor plants on
# tiles the "tree" layer marks solid; the node layer owns those tiles).
_FORAGE_NODE_KINDS = frozenset({
    "mushroom_brown", "mushroom_purple", "grass", "flower",
})

# Meteor-ore special tiles (spawned at meteor craters, game/manager.py):
# NEGATIVE gids never collide with real Tiled tilesets — the client maps
# "res--77" to the bundled meteor-ore sprite instead of a tileset crop.
# The node covers 2x2 tiles like a tree ("to hơn, kiểu như cây") but mines
# like a rock: pickaxe + stone drops ("đập rớt ra đá, tương tác y như đá").
METEOR_ORE_GID = -77

# Cave ore veins (ekonia/cave_area1): runtime-minted nodes like the meteor
# ore — no Tiled gid exists for them on the cave's baked sheet, so negative
# pseudo-gids map to bundled node sprites (assets/node/<id>.png).
COPPER_ORE_GID = -78
IRON_ORE_GID = -79

# Maps whose runtimes get a deterministic scatter of cave ore veins
# (minted in ResourceGrid.from_map — see spawn_ore_veins).
ORE_VEIN_MAPS = {"ekonia/cave_area1"}

TILE_NODE_PARTS: Dict[int, Tuple[str, int, int]] = {
    9: ("tree", 0, 0),
    10: ("tree", 1, 0),
    17: ("tree", 0, 1),
    18: ("tree", 1, 1),
    41: ("bush", 0, 0),
    # ---- Field forage tiles (bigmap layers nấm/cỏ/hoa): one-hit nodes.
    # 57 = brown mushroom, 58 = purple mushroom (verified pixel colors),
    # 49/50/52 = grass tufts, 53-56 = white/purple/blue/yellow flowers.
    57: ("mushroom_brown", 0, 0),
    58: ("mushroom_purple", 0, 0),
    49: ("grass", 0, 0),
    50: ("grass", 0, 0),
    52: ("grass", 0, 0),
    53: ("flower", 0, 0),
    54: ("flower", 0, 0),
    55: ("flower", 0, 0),
    56: ("flower", 0, 0),
    # ---- lobbytrade decor plants (user 15/09: "mấy cái cỏ, hoa, nấm đấy
    # là đập được" — same forage rules as the bigmap field). Pixel-audit
    # of [Base]BaseChip_pipo (firstgid 577): small floating blobs with a
    # transparent bottom row = waist-high plants; green hue = grass,
    # grey/white = flowers, 643/648 = taller flower bushes. The FULL-height
    # Pipoya gids (585/586/593/594/609/610/617) stay unmapped: they are the
    # forest trees (solid, not harvestable here).
    625: ("grass", 0, 0),
    630: ("grass", 0, 0),
    641: ("grass", 0, 0),
    642: ("grass", 0, 0),
    621: ("grass", 0, 0),
    629: ("mushroom_brown", 0, 0),
    626: ("flower", 0, 0),
    640: ("flower", 0, 0),
    643: ("flower", 0, 0),
    648: ("flower", 0, 0),
    # ---- Ekonia cave props (layer "Props", baked-sheet firstgid 1):
    # pixel-audited from the contact sheet — brown mushrooms with stems
    # (forage) and boulders (mineable rocks). The sharp wall spikes
    # (247-250) and ground scatter (3365/3366) stay unmapped: pure decor.
    157: ("mushroom_brown", 0, 0),
    292: ("mushroom_brown", 0, 0),
    293: ("mushroom_brown", 0, 0),
    309: ("mushroom_brown", 0, 0),
    3379: ("mushroom_brown", 0, 0),
    331: ("rock_big", 0, 0),
    3368: ("rock_small", 0, 0),
    168: ("rock_small", 0, 0),
    # Ore/rock vein tiles ("vật phẩm ko liên quan" layer on the bigmap):
    # mined with the ⛏️ pickaxe morph instead of the axe.
    # Gids 47/48 also draw dead-tree tiles on the "cây chết" layer (same
    # Pipoya art reused), so mapping them made dead trees minable by mistake.
    # Only keep the clearly-ore-only gids (44, 46).
    44: ("ore", 0, 0),
    46: ("ore", 0, 0),
    # Mineable rocks (bigmap layers "tảng đá nhỏ/gross"):
    # 65 = small rock, 66 = big rock (yields 1.5x stone, 1.4x hits).
    65: ("rock_small", 0, 0),
    66: ("rock_big", 0, 0),
    # Meteor-ore crater node: a 2x2 cluster minted at runtime (no Tiled gid
    # exists for it), so every tile carries the same negative pseudo-gid and
    # the anchor part marks the top-left corner.
    METEOR_ORE_GID: ("meteor_ore", 0, 0),
    # Cave ore veins (runtime-minted, 1 tile each): copper + iron.
    COPPER_ORE_GID: ("copper_ore", 0, 0),
    IRON_ORE_GID: ("iron_ore", 0, 0),
}


@dataclass
class ResourceDef:
    """One harvestable node kind. Data-driven: tune without touching logic."""

    kind: str
    name: str
    hits: int  # axe presses needed to fell the node
    respawn_s: float  # seconds until the node regrows
    drops: List[Tuple[str, float, int]]  # (item_id, chance 0..1, qty)


# Ore/rock vein tiles ("vật phẩm ko liên quan") + mineable rocks.
NODE_DEFS: Dict[str, ResourceDef] = {
    "ore": ResourceDef(
        "ore",
        "Quặng",
        hits=5,
        respawn_s=420.0,
        # Always 1 stone, +60% for a second; smelting chain adds iron ore and
        # coal (game/smelting.py) plus the rare key_stone bonus.
        drops=[
            ("stone", 1.0, 1),
            ("stone", 0.6, 1),
            ("iron_ore", 0.4, 1),
            ("coal", 0.25, 1),
            ("key_stone", 0.08, 1),
        ],
    ),
    # Small rock (gid 65): user tune 14/09 — 12 wood-pickaxe swings or 65
    # bare-hand swings. Recipe table intentionally EMPTY (coming later).
    "rock_small": ResourceDef(
        "rock_small",
        "Đá",
        hits=12,
        respawn_s=420.0,
        drops=[("stone", 1.0, 1)],
    ),
    # Big rock (gid 66): +0.4x hits (17) and 1.5x yield (user rule).
    "rock_big": ResourceDef(
        "rock_big",
        "Đá lớn",
        hits=17,  # round(12 * 1.4)
        respawn_s=420.0,
        drops=[
            ("stone", 1.0, 1),
            ("stone", 0.5, 1),
        ],
    ),
    # Meteor-ore (spawned at meteor craters): interaction mirrors rock_big
    # (pickaxe tiers / bare-hand slow path handled in apply_chop) but the
    # node is BIGGER — a 2x2 cluster — and yields more stone per fell.
    # Cave ore veins (ekonia/cave_area1): mined like rocks — pickaxe fast,
    # bare-hand brutally slow (65 swings scaled below). Copper is the soft
    # tier (intro ore), iron the step up.
    "copper_ore": ResourceDef(
        "copper_ore",
        "Quặng đồng",
        hits=65,
        respawn_s=420.0,
        # Always 1 copper ore, +50% stone rubble.
        drops=[
            ("copper_ore", 1.0, 1),
            ("stone", 0.5, 1),
        ],
    ),
    "iron_ore": ResourceDef(
        "iron_ore",
        "Quặng sắt",
        hits=85,
        respawn_s=420.0,
        # Always 1 iron ore, +35% for a second, +50% stone rubble.
        drops=[
            ("iron_ore", 1.0, 1),
            ("iron_ore", 0.35, 1),
            ("stone", 0.5, 1),
        ],
    ),
    "meteor_ore": ResourceDef(
        "meteor_ore",
        "Quặng thiên thạch",
        hits=17,
        respawn_s=420.0,
        drops=[
            ("stone", 1.0, 1),
            ("stone", 1.0, 1),
            ("stone", 0.5, 1),
        ],
    ),
    "tree": ResourceDef(
        "tree",
        "Cây",
        # Bare-hand swings to fell a tree (user tune 13/09: 12). Holding an
        # axe replaces this via axe_hits(material) — dirt 9, wood 6, stone 4,
        # iron 3 — so tools stay the fast path.
        hits=12,
        respawn_s=300.0,
        # Always 1 wood, +50% for a second; leaves/apples are chance rolls.
        drops=[("wood", 1.0, 1), ("wood", 0.5, 1), ("leaves", 0.6, 1), ("apple", 0.3, 1)],
    ),
    # Bushes give the same item KINDS but less (lower chances, no 2nd wood).
    "bush": ResourceDef(
        "bush",
        "Bụi cây",
        hits=3,
        respawn_s=180.0,
        drops=[("wood", 0.7, 1), ("leaves", 0.35, 1), ("apple", 0.12, 1)],
    ),
    # ---- Field forage (user 15/09): ONE hit shatters them; shatter anim
    # is client-side (sand-grain dissolve). Mushrooms always drop their
    # own item; grass has a 10% seed chance and otherwise nothing.
    "mushroom_brown": ResourceDef(
        "mushroom_brown",
        "Nấm nâu",
        hits=1,
        respawn_s=120.0,
        drops=[("mushroom_brown", 1.0, 1)],
    ),
    "mushroom_purple": ResourceDef(
        "mushroom_purple",
        "Nấm tím",
        hits=1,
        respawn_s=120.0,
        drops=[("mushroom_purple", 1.0, 1)],
    ),
    "grass": ResourceDef(
        "grass",
        "Cỏ dại",
        hits=1,
        respawn_s=90.0,
        # 10% seed — otherwise nothing (plain hit).
        drops=[("seed", 0.10, 1)],
    ),
    # Flowers: pure forage, one hit, no drops yet (table comes later).
    "flower": ResourceDef(
        "flower",
        "Hoa dại",
        hits=1,
        respawn_s=90.0,
        drops=[],
    ),
}


@dataclass
class ResourceNode:
    kind: str
    anchor: Tuple[int, int]  # top-left tile; chop progress is keyed by this
    tiles: List[Tuple[int, int]]  # every tile the sprite covers


# Cave ore vein scatter (per cave map): copper is the common vein, iron the
# rarer step-up. Deterministic per map_id — every boot/restart scatters the
# SAME veins, so a felled-and-regrown vein never teleports around the cave.
CAVE_ORE_COUNTS = {"copper_ore": 10, "iron_ore": 8}


def _ores_companion_path(map_data):
    """Companion file pinning the cave's vein anchors (like .solids.json).

    ``<map>.ores.json`` next to the map: [{kind, x, y}, ...]. Pins the
    scatter so every boot/process mines the SAME veins — the runtime
    walkable set can drift slightly between loads (cave carve refinement),
    and a hash-seeded scatter alone would teleport veins across restarts.
    """
    import json
    from pathlib import Path

    p = getattr(map_data, "image_path", None)
    if p is not None:
        return Path(p).with_suffix(".ores.json")
    # No baked-image companion (Tiled maps): fall back to the assets dir
    # convention (config.ASSETS_DIR / <map_id>.ores.json).
    map_id = getattr(map_data, "map_id", "")
    if not map_id:
        return None
    try:
        from config import ASSETS_DIR

        return Path(ASSETS_DIR) / f"{map_id}.ores.json"
    except Exception:
        return None


def _mint_vein(grid, kind: str, x: int, y: int) -> None:
    gid = COPPER_ORE_GID if kind == "copper_ore" else IRON_ORE_GID
    node = ResourceNode(kind, (x, y), [(x, y)])
    grid.nodes[(x, y)] = node
    grid._tile_index[(x, y)] = node
    grid._tile_gids[(x, y)] = gid


def spawn_ore_veins(grid: "ResourceGrid", map_data, rng=None) -> List[Tuple[int, int]]:
    """Mint the cave's copper/iron ore veins onto ``grid`` (runtime nodes).

    Same mechanism as the meteor-crater ore (game/meteors.py): 1-tile nodes
    carrying a negative pseudo-gid so both renderers draw the bundled
    sprites (client asset lane ``node/<id>.png``). Nodes land only on
    walkable floor tiles that are free of other nodes, keeping at least one
    tile between veins so a vein never walls a corridor.

    First run SCATTERS + pins the anchors into ``<map>.ores.json``; every
    later load reuses the pinned anchors (only skipping tiles that have
    become blocked).

    Returns the list of minted anchors (for tests / debug prints).
    """
    if grid is None or map_data is None:
        return []
    minted: List[Tuple[int, int]] = []
    # ART PRESENCE set (computed once): a candidate must carry a non-zero
    # gid on SOME layer. The cave's interior black-void cells pass
    # is_walkable (the carve opens no-art cells) but draw NOTHING — a vein
    # there renders floating in the void, visually "bên ngoài map" (user
    # report).
    art = set()
    for _name, _grid in getattr(map_data, "tile_layers", None) or []:
        for _y, _row in enumerate(_grid):
            for _x, _gid in enumerate(_row):
                if _gid:
                    art.add((_x, _y))

    def _fits(x: int, y: int) -> bool:
        return (
            map_data.is_walkable(x, y)
            and (x, y) in art
            and (x, y) not in grid._tile_index
            and not any(
                (nx, ny) in grid._tile_index
                for nx in range(x - 1, x + 2)
                for ny in range(y - 1, y + 2)
            )
        )

    companion = _ores_companion_path(map_data)
    if companion is not None and companion.exists():
        try:
            import json

            rows = json.loads(companion.read_text(encoding="utf-8"))
            for row in rows:
                kind = str(row.get("kind", ""))
                x, y = int(row["x"]), int(row["y"])
                if kind not in CAVE_ORE_COUNTS or not _fits(x, y):
                    continue  # map changed under the pins: skip that vein
                _mint_vein(grid, kind, x, y)
                minted.append((x, y))
            return minted
        except Exception:
            pass  # corrupt companion: fall through to a fresh scatter

    rng = rng if rng is not None else random.Random(
        f"cave-ores-{getattr(map_data, 'map_id', '')}"
    )
    w, h = map_data.width, map_data.height
    # ART PRESENCE: a candidate must carry a non-zero gid on SOME layer.
    # The cave's interior black-void cells pass is_walkable (the carve opens
    # no-art cells) but draw NOTHING — a vein there renders floating in the
    # void, visually "bên ngoài map" (user report).
    art = set()
    for _name, _grid in getattr(map_data, "tile_layers", None) or []:
        for _y, _row in enumerate(_grid):
            for _x, _gid in enumerate(_row):
                if _gid:
                    art.add((_x, _y))
    # SORTED before the seeded shuffle: same walkable set -> same scatter
    # regardless of the iteration order that produced it.
    candidates = sorted(
        (x, y)
        for y in range(1, h - 1)
        for x in range(1, w - 1)
        if map_data.is_walkable(x, y) and (x, y) in art
        and (x, y) not in grid._tile_index
    )
    rng.shuffle(candidates)
    pins: List[dict] = []
    for kind, count in CAVE_ORE_COUNTS.items():
        placed = 0
        for (x, y) in candidates:
            if placed >= count:
                break
            if not _fits(x, y):
                continue
            _mint_vein(grid, kind, x, y)
            minted.append((x, y))
            pins.append({"kind": kind, "x": x, "y": y})
            placed += 1
    # Pin the scatter for every future load (best-effort write).
    if companion is not None and pins:
        try:
            import json

            companion.parent.mkdir(parents=True, exist_ok=True)
            companion.write_text(
                json.dumps(pins, ensure_ascii=False, indent=1), encoding="utf-8"
            )
        except Exception:
            pass  # read-only assets: the per-process scatter still works
    return minted
class ResourceGrid:
    """Per-scenario harvestable-node state. Pure, no IO.

    Nodes are indexed once from the map (``from_map``); chopping progress and
    regrow deadlines are keyed by the node anchor tile.
    """

    def __init__(self):
        self.nodes: Dict[Tuple[int, int], ResourceNode] = {}
        self._tile_index: Dict[Tuple[int, int], ResourceNode] = {}
        self._tile_gids: Dict[Tuple[int, int], int] = {}
        # Lower-cased names of the resource layers found in the map (the
        # renderer excludes exactly these layers from its ground base).
        self.layer_names: set = set()
        self.progress: Dict[Tuple[int, int], int] = {}
        self.chopped_at: Dict[Tuple[int, int], float] = {}
        # Durability regen (user rule 13/09): a node nobody hits for
        # PROGRESS_REGEN_DELAY_S seconds slowly "rewinds" its chop progress
        # (one hit lost every PROGRESS_REGEN_STEP_S). Timestamps per anchor:
        # ``progress_hit_at`` = last hit (drives the delay),
        # ``progress_checked_at`` = last regen step (drives the drain).
        self.progress_hit_at: Dict[Tuple[int, int], float] = {}
        self.progress_checked_at: Dict[Tuple[int, int], float] = {}

    @classmethod
    def from_map(cls, map_data) -> "ResourceGrid":
        g = cls()
        for name, grid in getattr(map_data, "tile_layers", None) or []:
            if (name or "").strip().lower() not in RESOURCE_LAYER_NAMES:
                continue
            if "cau" in name:  # "cây cầu(đi qua được)" — bridge decor, not nodes
                continue
            g.layer_names.add((name or "").strip().lower())
            for y, row in enumerate(grid):
                for x, gid in enumerate(row):
                    if not gid:
                        continue
                    part = TILE_NODE_PARTS.get(gid)
                    if part is None:
                        continue
                    kind, dx, dy = part
                    anchor = (x - dx, y - dy)
                    if anchor not in g.nodes:
                        if kind == "tree":
                            ax, ay = anchor
                            tiles = [
                                (ax, ay), (ax + 1, ay),
                                (ax, ay + 1), (ax + 1, ay + 1),
                            ]
                        else:
                            tiles = [anchor]
                        g.nodes[anchor] = ResourceNode(kind, anchor, tiles)
                        for t in tiles:
                            g._tile_index[t] = g.nodes[anchor]
                    g._tile_gids[(x, y)] = gid
        # Cave ore veins: runtime-minted scatter (deterministic per map).
        if getattr(map_data, "map_id", "") in ORE_VEIN_MAPS:
            spawn_ore_veins(g, map_data)
        return g

    # ----- lookups -----

    def node_at(self, x: int, y: int) -> Optional[ResourceNode]:
        return self._tile_index.get((x, y))

    def is_chopped(self, anchor: Tuple[int, int]) -> bool:
        return anchor in self.chopped_at

    def progress_at(self, anchor: Tuple[int, int]) -> int:
        return self.progress.get(anchor, 0)

    def visible_tiles(self) -> List[Tuple[int, int, int]]:
        """(x, y, gid) for every resource tile NOT on a chopped node."""
        out = []
        for (x, y), node in self._tile_index.items():
            if node.anchor in self.chopped_at:
                continue
            out.append((x, y, self._tile_gids.get((x, y), 0)))
        return out

    def node_tiles_gids(self, node: ResourceNode) -> List[Tuple[int, int, int]]:
        """(x, y, gid) for every tile of a node — lets the UI fade the EXACT
        sprite that was chopped (rule 17: no hard-coded tile lists)."""
        out = []
        for x, y in node.tiles:
            gid = self._tile_gids.get((x, y), 0)
            if gid:
                out.append((x, y, gid))
        return out

    # ----- state changes -----

    def chop(self, anchor: Tuple[int, int], ts: float) -> None:
        self.chopped_at[anchor] = float(ts)
        self.progress.pop(anchor, None)
        self.progress_hit_at.pop(anchor, None)
        self.progress_checked_at.pop(anchor, None)

    def note_progress_hit(self, anchor: Tuple[int, int], now: float) -> None:
        """Record a landed hit on ``anchor`` (restarts the 5 s regen delay)."""
        self.progress_hit_at[anchor] = float(now)

    def decay_progress(self, now: Optional[float] = None) -> None:
        """Durability regen beat (call every tick): after PROGRESS_REGEN_DELAY_S
        without a hit, a node's chop progress "rewinds" — one hit lost every
        PROGRESS_REGEN_STEP_S (smooth reverse, not a sudden wipe).
        """
        if not self.progress:
            return
        if now is None:
            now = time.time()
        for anchor in list(self.progress.keys()):
            hit = self.progress_hit_at.get(anchor)
            if hit is None:
                # Restored-from-DB progress without a hit stamp: just arm the
                # clock (never wipe it on the first beat).
                self.progress_hit_at[anchor] = now
                self.progress_checked_at[anchor] = now
                continue
            if now - hit <= PROGRESS_REGEN_DELAY_S:
                continue
            checked = self.progress_checked_at.get(anchor, hit + PROGRESS_REGEN_DELAY_S)
            start = max(checked, hit + PROGRESS_REGEN_DELAY_S)
            steps = int((now - start) // PROGRESS_REGEN_STEP_S)
            if steps <= 0:
                continue
            remaining = self.progress.get(anchor, 0) - steps
            if remaining <= 0:
                self.progress.pop(anchor, None)
                self.progress_hit_at.pop(anchor, None)
                self.progress_checked_at.pop(anchor, None)
            else:
                self.progress[anchor] = remaining
                self.progress_checked_at[anchor] = start + steps * PROGRESS_REGEN_STEP_S

    def mark_chopped(self, anchor: Tuple[int, int], ts: float) -> None:
        """Restore a persisted chop (boot recovery) without touching progress."""
        self.chopped_at[anchor] = float(ts)

    def regrow(self, anchor: Tuple[int, int]) -> None:
        self.chopped_at.pop(anchor, None)
        self.progress.pop(anchor, None)
        self.progress_hit_at.pop(anchor, None)
        self.progress_checked_at.pop(anchor, None)

    def regrow_ready(self, now: float) -> List[Tuple[int, int]]:
        """Anchors whose respawn deadline has elapsed at unix ``now``."""
        out = []
        for anchor, ts in list(self.chopped_at.items()):
            node = self.nodes.get(anchor)
            if node is None or now >= ts + NODE_DEFS[node.kind].respawn_s:
                out.append(anchor)
        return out

    def reset(self) -> None:
        self.progress.clear()
        self.chopped_at.clear()
        self.progress_hit_at.clear()
        self.progress_checked_at.clear()


def _facing_tile(player) -> Tuple[int, int]:
    dx, dy = Direction[player.direction].vector
    return player.x + dx, player.y + dy


CHOP_RANGE = 3
# Web mouse-tile offset clamp (mirrors rules.AIM_RANGE without a cycle).
AIM_RANGE = 3

# Node durability regen (user rule 13/09): after PROGRESS_REGEN_DELAY_S
# without a landed hit, chop progress "rewinds" one hit every
# PROGRESS_REGEN_STEP_S (a 5-hit node fully resets 5 s + 5 s later). Tune
# here without touching logic.
PROGRESS_REGEN_DELAY_S = 5.0
PROGRESS_REGEN_STEP_S = 1.0  # one hit lost per this many seconds

# Node kinds harvested with a PICKAXE instead of the axe (ore/rock veins).
ORE_NODE_KINDS = {"ore", "rock", "stone_node", "iron_ore", "coal",
                  "rock_small", "rock_big", "meteor_ore",
                  "copper_ore", "iron_ore"}

# Cave ore veins scale the rock hit table (wood pickaxe 12 swings baseline):
# copper = rock-equivalent, iron = 1.3x. Bare-hand = 65 swings scaled the
# same way ("vẫn tay không đập được nhưng mà cực lâu").
ORE_VEIN_SCALE = {"copper_ore": 1.0, "iron_ore": 1.3}


def is_ore_kind(kind: str) -> bool:
    """True when a node kind is mined with the pickaxe (⛏️) tool morph."""
    return kind in ORE_NODE_KINDS


# Pickaxe swings to mine ONE rock, per pickaxe material (user tune 14/09:
# wood = 12, NOT the generic pickaxe ladder's 5). Big rock scales 1.4x.
# stone = 12/1.3 (TIER_MULT) — bug 30/09: missing stone tier made the stone
# pickaxe fall back to wood's 12 (identical swing count, user report).
ROCK_PICKAXE_HITS = {"wood": 12, "stone": 9, "iron": 8, "gold": 5, "steel": 3}


def _target_tile(player) -> Tuple[int, int]:
    """The square the player aims at: the Build-Mode aim cursor tile while one
    is active (the renderer highlights exactly this square), otherwise the
    facing tile."""
    if getattr(player, "aim_active", False):
        return player.x + player.aim_dx, player.y + player.aim_dy
    return _facing_tile(player)


def _nearest_node_in_range(grid: ResourceGrid, player, max_range: int):
    nodes = [
        node for node in grid.nodes.values()
        if not grid.is_chopped(node.anchor)
        and any(
            max(abs(x - player.x), abs(y - player.y)) <= max_range
            for x, y in node.tiles
        )
    ]
    return min(
        nodes,
        key=lambda node: min(
            max(abs(x - player.x), abs(y - player.y)) for x, y in node.tiles
        ),
        default=None,
    )


def apply_chop(state: GameState,
    action: ChopAction,
    grid: Optional[ResourceGrid],
    inventory,
    rng=None,
    now: Optional[float] = None,
    tired: bool = False,
    held_slot: Optional[int] = None,
) -> ActionResult:
    """One swing at the node on the target tile.

    The tool family follows the node kind: ore/rock veins are mined with a
    PICKAXE, trees/bushes are felled with an AXE. The strongest held tool of
    that family (action.tool_id when explicitly given) decides the number of
    presses: each tier up cuts the required hits (game/tools.py).

    STONE GATE (user rule): ore nodes can only be mined while the player
    holds a pickaxe of dirt tier or better — anyone else gets the
    "too_hard" reason and the UI shows "Quá cứng để đập bằng tay".

    Each landed press adds progress (``state_changed=True`` so the UI can
    refresh the % label). At ``hits`` the node is felled: its tiles are
    hidden until the respawn deadline elapses and the drop table rolls into
    the player's bag (``drops`` is set only on the felling swing).
    """
    player = state.get_player(action.user_id)
    if player is None:
        return ActionResult(False, "no_player")
    if not player.alive:
        return ActionResult(False, "dead")
    if not player.visible:
        return ActionResult(False, "invisible")
    if grid is None:
        return ActionResult(False, "no_node")

    # Chop acts on the TARGET square only (the highlighted tile): the
    # aim-cursor tile while Build Mode aims elsewhere, the mouse tile when
    # the web client passes an offset, otherwise the facing tile — never
    # "nearest node in range".
    cdx = getattr(action, "dx", None)
    cdy = getattr(action, "dy", None)
    if cdx is not None or cdy is not None:
        dx = int(cdx or 0)
        dy = int(cdy or 0)
        if max(abs(dx), abs(dy)) > AIM_RANGE:
            return ActionResult(False, "out_of_range")
        tx, ty = player.x + dx, player.y + dy
    else:
        tx, ty = _target_tile(player)
    node = grid.node_at(tx, ty)
    if node is None:
        return ActionResult(False, "no_node")
    if grid.is_chopped(node.anchor):
        now = time.time() if now is None else now
        return ActionResult(False, "regrowing")

    from game import tools as tool_mod
    from game.tools import parse_tool_id

    ore = is_ore_kind(node.kind)
    family = "pickaxe" if ore else "axe"
    # TOOL = WHAT THE HAND HOLDS (user bug 29/09: "cầm cúp rồi đổi sang tay
    # khác đập vẫn nhanh như cầm cúp"). The old code fell back to
    # best_tool_of_family(inventory) — the best pickaxe/axe ANYWHERE in the
    # bag — so swapping hotbar slots changed nothing. Now: the tool only
    # counts when it sits in the HELD hotbar slot (the slot the client
    # selects); anything else swings bare-handed. ``held_slot=None`` (Discord
    # path / legacy callers) keeps the old best-in-bag behaviour.
    tool_id = action.tool_id
    if tool_id is not None:
        td = parse_tool_id(tool_id)
        if td is None or td.family != family or inventory.count(tool_id) <= 0:
            tool_id = None
    if tool_id is None and held_slot is not None:
        held_id = None
        try:
            held_id = inventory.hotbar().get(int(held_slot))
        except Exception:
            held_id = None
        if held_id:
            td = parse_tool_id(held_id)
            if (
                td is not None and td.family == family
                and inventory.count(held_id) > 0
            ):
                tool_id = held_id
    if tool_id is None and held_slot is None:
        tool_id = tool_mod.best_tool_of_family(inventory, family)

    # Pickaxe GATE applies to ORE veins only: rocks (rock_small/rock_big)
    # are mineable BARE-HANDED — just brutally slow (65/91 swings, user rule
    # 14/09: "vẫn tay không đập được nhưng mà cực lâu").
    if node.kind == "ore" and not tool_mod.has_pickaxe_tier(inventory, "wood"):
        return ActionResult(False, "too_hard")

    tool = parse_tool_id(tool_id) if tool_id else None
    if node.kind in ("rock_small", "rock_big"):
        # Rocks use their OWN per-kind hit table (user tune 14/09: 12 swings
        # with a WOOD pickaxe, 65 bare-hand) — NOT the generic pickaxe ladder
        # (whose wood tier is 5). Each tier up still mines faster.
        scale = 1.4 if node.kind == "rock_big" else 1.0
        if tool is not None:
            hits = round(ROCK_PICKAXE_HITS.get(tool.material, 12) * scale)
        else:
            # Bare hand x3 (user 12/10): đập tay không phải tốn gấp 3 thời gian.
            hits = round((65 if node.kind == "rock_small" else 65 * 1.4) * 3)
    elif node.kind in ORE_VEIN_SCALE:
        # Cave ore veins ride the SAME rock table (pickaxe fast, bare-hand
        # slow) — copper at rock_small cost, iron 1.3x.
        scale = ORE_VEIN_SCALE[node.kind]
        if tool is not None:
            hits = round(ROCK_PICKAXE_HITS.get(tool.material, 12) * scale)
        else:
            hits = round(65 * scale * 3)
    elif node.kind == "meteor_ore":
        if tool is not None:
            hits = round(ROCK_PICKAXE_HITS.get(tool.material, 12) * 1.4)
        else:
            hits = round(65 * 1.4 * 3)
    else:
        hits_fn = tool_mod.pickaxe_hits if ore else tool_mod.axe_hits
        if tool is not None:
            hits = hits_fn(tool.material)
        else:
            # Bare hand x3 (user 12/10): cây/bụi cứng tay không phải đập gấp 3.
            hits = round(NODE_DEFS[node.kind].hits * 3)

    now = time.time() if now is None else now
    rng = rng if rng is not None else random
    # Out of stamina (user rule): still swings, HALF progress per hit —
    # the node falls eventually, just twice as slow. Progress is a float;
    # the tired bank re-syncs to whole numbers on the felling hit.
    gain = 0.5 if tired else 1.0
    grid.progress[node.anchor] = grid.progress_at(node.anchor) + gain
    # Durability regen: stamp the hit so the 5 s rewind clock restarts.
    grid.note_progress_hit(node.anchor, now)
    if grid.progress[node.anchor] < hits:
        return ActionResult(
            True, state_changed=True, pos=(tx, ty), block_id=node.kind, needed=hits,
        )

    grid.chop(node.anchor, now)
    drops: List[Tuple[str, int]] = []
    for item_id, chance, qty in NODE_DEFS[node.kind].drops:
        if rng.random() < chance:
            drops.append((item_id, qty))
    # Felled: the loot pops out as "linh khí" drop entities at the node
    # centre (the manager grants the bag only when a player collects them).
    from game.drops import spawn_drops

    if drops:
        cx = sum(x for x, _y in node.tiles) / len(node.tiles)
        cy = sum(y for _x, y in node.tiles) / len(node.tiles)
        spawn_drops(state, cx, cy, drops, rng=rng)
    return ActionResult(
        True, state_changed=True, pos=(tx, ty), block_id=node.kind, drops=drops,
        needed=hits,
    )


def render_kwargs(rt) -> dict:
    """Extra renderer kwargs so every screen render hides chopped nodes.

    UI-agnostic on purpose: ``rt`` is duck-typed (needs ``.resources``).
    """
    grid = getattr(rt, "resources", None)
    if grid is None:
        return {}
    return {
        "resource_tiles": grid.visible_tiles(),
        "resource_layer_names": grid.layer_names,
    }