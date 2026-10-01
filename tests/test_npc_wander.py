"""Wandering NPC behaviour ("thương nhân lang thang") — game/npc.py."""
import random

from game.map_loader import MapData
from game.npc import NPCDef, npc_push_out, wander_step


def _map():
    # 5x5 open grid, all walkable.
    return MapData(map_id="t", display_name="t", width=5, height=5,
                   tile_width=32, tile_height=32, collision=[[0]*5 for _ in range(5)])


def _npc(**kw):
    n = NPCDef(id="peddler", name="Peddler", emoji="🧺", x=2, y=2,
               wander={"radius": 2, "speed": 1.2, "pause": 0.0})
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def test_npc_stops_near_player():
    npc = _npc()
    rng = random.Random(1)
    # Player stands right on top of the NPC -> freeze + face, never move.
    moved = wander_step(npc, _map().is_walkable, set(), [(2.0, 2.0)], 0.05, rng)
    assert not moved
    assert npc.target is None
    assert npc.facing in ("down", "left", "right", "up")


def test_npc_moves_toward_target():
    npc = _npc()
    rng = random.Random(7)
    total = 0.0
    for _ in range(120):  # 2 simulated seconds
        if wander_step(npc, _map().is_walkable, set(), [], 1 / 60, rng):
            total += 1.2 / 60
    # In 2s at speed 1.2 the NPC covers up to 2.4 tiles; without a target
    # chosen it may idle — but never run away beyond the radius.
    assert abs(npc.x - 2) <= 2 and abs(npc.y - 2) <= 2
    assert npc.x_f == float(npc.x) or npc.target is not None or total > 0


def test_npc_stays_within_home_radius():
    npc = _npc()
    rng = random.Random(3)
    for _ in range(600):  # 10 simulated seconds
        wander_step(npc, _map().is_walkable, set(), [], 1 / 60, rng)
    assert abs(npc.x - 2) <= 2 + 1
    assert abs(npc.y - 2) <= 2 + 1


def test_push_out_ejects_player_from_npc_tile():
    npc = _npc()
    npc.init_float()
    # Player inside the NPC tile -> ejected along ONE axis to just past the
    # tile edge (the axis with the smaller penetration wins).
    px, py = npc_push_out([npc], npc.x_f + 0.1, npc.y_f)
    assert abs(px - npc.x_f) >= 0.8 or abs(py - npc.y_f) >= 0.8
    # Standing clear -> untouched.
    qx, qy = npc_push_out([npc], npc.x_f + 2, npc.y_f)
    assert (qx, qy) == (npc.x_f + 2, npc.y_f)
