"""Zone-grid spawn ecosystem (game/zombies.py) — game rules.

Luật cần pin:
- Per-zone cap: không zone nào chứa quá ZOMBIES_PER_ZONE mob sống.
- Spacing: mob mới không spawn sát (>= ZOMBIE_SPAWN_SPACING) mob cũ.
- Phân bố: nhiều lần spawn phải rải ra NHIỀU zone, không dồn 1 chỗ.
- An toàn cũ giữ nguyên: cách người chơi >= min dist, không spawn trong
  viewport, không spawn trên ô void/không art.
"""
import random

import pytest

from game.collision import Collision
from game.map_loader import MapData
from game.state import GameState
from game.zombies import (
    AMBIENT_PER_ZONE,
    SPAWN_ZONE_TILES,
    WEB_ZOMBIE_MIN_SPAWN_DIST,
    ZOMBIE_SPAWN_SPACING,
    ZOMBIES_PER_ZONE,
    _spawn_zone_map,
    _zone_key,
    _zone_spawn_tile,
    spawn_animal_one,
    spawn_one,
    web_spawn_one,
    _web_zombies,
)

W, H = 64, 64  # 4x4 zones of 16x16


@pytest.fixture
def big_world():
    map_data = MapData(
        map_id="zone-test",
        width=W,
        height=H,
        collision=[[0] * W for _ in range(H)],
        spawn=(W // 2, H // 2),
    )
    state = GameState(1, map_data.map_id)
    collision = Collision(map_data, state.blocks)
    return state, collision


def _add_web_mob(state, x, y, ambient=False):
    from game.zombies import Zombie, _add_web_zombie

    z = Zombie(f"z{len(_web_zombies(state)) + 1}", x, y)
    z.x_f = float(x) + 0.5
    z.y_f = float(y) + 0.5
    z.ambient = ambient
    _add_web_zombie(state, z)
    return z


def test_zone_map_covers_all_walkable_tiles(big_world):
    state, collision = big_world
    zones = _spawn_zone_map(collision)
    total = sum(len(t) for t in zones.values())
    assert total == W * H  # all-open test map: every tile is legal
    assert set(zones) == {
        (zx, zy) for zx in range(W // SPAWN_ZONE_TILES)
        for zy in range(H // SPAWN_ZONE_TILES)
    }


def test_zone_spawn_respects_per_zone_cap(big_world):
    state, collision = big_world
    players_xy = [(32.0, 32.0)]
    # Fill zone (0,0) to its cap with hostile mobs.
    existing = []
    for i in range(ZOMBIES_PER_ZONE):
        existing.append(((0, 0), 2 + i, 2))
    tile = _zone_spawn_tile(
        _spawn_zone_map(collision), existing, players_xy, random.Random(1),
        min_player_dist=WEB_ZOMBIE_MIN_SPAWN_DIST,
        per_zone=ZOMBIES_PER_ZONE,
        spacing=ZOMBIE_SPAWN_SPACING,
    )
    assert tile is not None
    assert _zone_key(*tile) != (0, 0), "capped zone must never receive more"


def test_zone_spawn_respects_spacing(big_world):
    state, collision = big_world
    players_xy = [(32.0, 32.0)]
    existing = [(_zone_key(30, 30), 30, 30)]
    rng = random.Random(7)
    for _ in range(20):
        tile = _zone_spawn_tile(
            _spawn_zone_map(collision), existing, players_xy, rng,
            min_player_dist=WEB_ZOMBIE_MIN_SPAWN_DIST,
            per_zone=ZOMBIES_PER_ZONE,
            spacing=ZOMBIE_SPAWN_SPACING,
        )
        if tile is None:
            continue
        x, y = tile
        assert max(abs(x - 30), abs(y - 30)) >= ZOMBIE_SPAWN_SPACING


def test_spawns_spread_across_multiple_zones(big_world):
    state, collision = big_world
    players = [type("P", (), {"x_f": 32.0, "y_f": 32.0, "x": 32, "y": 32,
                              "alive": True})()]
    rng = random.Random(42)
    zones_hit = set()
    for _ in range(ZOMBIES_PER_ZONE + 2):
        z = web_spawn_one(state, collision, players, rng)
        if z is not None:
            zones_hit.add(_zone_key(int(z.x_f), int(z.y_f)))
    assert len(zones_hit) >= 3, (
        f"packs must spread across zones, got {zones_hit}"
    )


def test_web_spawn_never_too_close_to_player(big_world):
    state, collision = big_world
    players = [type("P", (), {"x_f": 32.0, "y_f": 32.0, "x": 32, "y": 32,
                              "alive": True})()]
    rng = random.Random(5)
    for _ in range(10):
        z = web_spawn_one(state, collision, players, rng)
        assert z is not None
        assert max(abs(z.x_f - 32.0), abs(z.y_f - 32.0)) >= WEB_ZOMBIE_MIN_SPAWN_DIST


def test_ambient_cap_counts_only_ambient(big_world):
    state, collision = big_world
    players = [type("P", (), {"x_f": 32.0, "y_f": 32.0, "x": 32, "y": 32,
                              "alive": True})()]
    rng = random.Random(3)
    # Fill one zone with HOSTILE mobs — must not block ambient spawns there.
    for i in range(ZOMBIES_PER_ZONE):
        _add_web_mob(state, 2 + i, 2, ambient=False)
    z = spawn_animal_one(state, collision, players, rng)
    assert z is not None, "hostile cap must not block the ambient pool"
    assert z.ambient is True


def test_discord_spawn_never_in_viewport(big_world):
    state, collision = big_world
    state.add_player(1, "A", 32, 32)
    view = {1: (24, 24, 39, 39)}  # half-open rect (x0, y0, x1, y1)
    rng = random.Random(9)
    for _ in range(10):
        z = spawn_one(state, collision, view, rng)
        if z is None:
            continue
        assert not (24 <= z.x < 39 and 24 <= z.y < 39)
        assert max(abs(z.x - 32), abs(z.y - 32)) >= 8
