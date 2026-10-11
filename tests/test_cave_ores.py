import random
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from game.actions import ChopAction
from game.inventory import Inventory
from game.map_loader import load_map
from game.resources import (
    COPPER_ORE_GID,
    IRON_ORE_GID,
    NODE_DEFS,
    ORE_VEIN_MAPS,
    ResourceGrid,
    apply_chop,
    is_ore_kind,
)
from game.state import GameState

ASSETS = pathlib.Path(__file__).resolve().parent.parent / "assets" / "maps"

CAVE_MAP_ID = "ekonia/cave_area1"


def _cave_grid() -> ResourceGrid:
    return ResourceGrid.from_map(load_map(CAVE_MAP_ID, ASSETS))


def test_cave_veins_are_minted_deterministically():
    assert CAVE_MAP_ID in ORE_VEIN_MAPS
    g1 = _cave_grid()
    g2 = _cave_grid()
    for grid in (g1, g2):
        kinds = [n.kind for n in grid.nodes.values()]
        assert kinds.count("copper_ore") == 10
        assert kinds.count("iron_ore") == 8
    # Deterministic per map: same anchors on every boot.
    a1 = sorted(
        (n.anchor, n.kind) for n in g1.nodes.values()
        if n.kind in ("copper_ore", "iron_ore")
    )
    a2 = sorted(
        (n.anchor, n.kind) for n in g2.nodes.values()
        if n.kind in ("copper_ore", "iron_ore")
    )
    assert a1 == a2


def test_veins_are_walkable_floor_tiles_with_separation():
    md = load_map(CAVE_MAP_ID, ASSETS)
    g = _cave_grid()
    tiles = [
        (n.anchor, n.kind) for n in g.nodes.values()
        if n.kind in ("copper_ore", "iron_ore")
    ]
    assert tiles
    anchors = {a for a, _k in tiles}
    for (x, y), kind in tiles:
        # On walkable floor (never in a wall) and never on another node.
        assert md.is_walkable(x, y), f"{kind} at {(x, y)} is inside a wall"
        # One tile of separation from every other vein: a vein must never
        # wall a corridor.
        for nx in range(x - 1, x + 2):
            for ny in range(y - 1, y + 2):
                if (nx, ny) != (x, y):
                    assert (nx, ny) not in anchors
    # Vein tiles carry the negative pseudo-gids (client node sprites).
    for (x, y), kind in tiles:
        gid = g._tile_gids.get((x, y))
        if kind == "copper_ore":
            assert gid == COPPER_ORE_GID
        else:
            assert gid == IRON_ORE_GID


def test_vein_kinds_are_pickaxe_ore_nodes():
    for kind in ("copper_ore", "iron_ore"):
        assert is_ore_kind(kind)
        assert kind in NODE_DEFS
        drops = {item for item, _c, _q in NODE_DEFS[kind].drops}
        assert kind in drops  # the vein always yields its own ore item
        assert "stone" in drops  # + stone rubble chance


def test_mine_copper_vein_with_wood_pickaxe():
    g = _cave_grid()
    inv = Inventory()
    inv.add("wood_pickaxe", 1)
    node = next(n for n in g.nodes.values() if n.kind == "copper_ore")
    tx, ty = node.anchor
    s = GameState(1, CAVE_MAP_ID)
    s.add_player(10, "A", tx, ty + 1)
    s.players[10].direction = "NORTH"
    rng = random.Random(7)
    # Copper rides the rock hit table (wood pickaxe = 12 swings).
    felled = None
    for i in range(20):
        r = apply_chop(s, ChopAction(10), g, inv, rng=rng, now=100.0, held_slot=None)
        if g.is_chopped(node.anchor):
            felled = r
            break
        assert r.success
    assert felled is not None
    assert felled.drops is not None
    item_ids = [item for item, _q in felled.drops]
    assert "copper_ore" in item_ids
    # Drop entities spawned (no direct bag add).
    from game.drops import get_drop_field

    dropped = [
        d for d in get_drop_field(s).drops.values() if d.item_id == "copper_ore"
    ]
    assert len(dropped) >= 1


def test_mine_iron_vein_bare_handed_slow():
    g = _cave_grid()
    inv = Inventory()  # bare hands: brutally slow but POSSIBLE
    node = next(n for n in g.nodes.values() if n.kind == "iron_ore")
    tx, ty = node.anchor
    s = GameState(1, CAVE_MAP_ID)
    s.add_player(10, "A", tx, ty + 1)
    s.players[10].direction = "NORTH"
    rng = random.Random(3)
    needed = round(65 * 1.3 * 3)  # bare-hand iron = 65 * scale * 3 (x3 user 12/10)
    for i in range(needed):
        r = apply_chop(s, ChopAction(10), g, inv, rng=rng, now=100.0)
        if g.is_chopped(node.anchor):
            break
        assert r.success
    assert g.is_chopped(node.anchor)
    assert any(
        d.item_id == "iron_ore"
        for d in __import__("game.drops", fromlist=["get_drop_field"])
        .get_drop_field(s).drops.values()
    )


def test_copper_ore_item_and_smelt_recipe_exist():
    from game.items import ITEM_REGISTRY, get_item

    assert get_item("copper_ore") is not None
    assert get_item("copper_ingot") is not None
    from game.smelting import SMELT_BY_INPUT

    recipe = SMELT_BY_INPUT["copper_ore"]
    assert recipe.output_item == "copper_ingot"
