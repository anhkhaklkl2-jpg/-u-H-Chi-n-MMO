"""Wildlife stand-and-stare tell plays ONCE per encounter (user 29/09:
"đuổi quái thì bọn nó chạy được 1 đoạn lại ! rồi tiếp tục chạy")."""
from __future__ import annotations

import random

from game.collision import Collision
from game.map_loader import MapData
from game.state import GameState
from game.zombies import spawn_animal_one, web_tick


def _world():
    map_data = MapData(
        map_id="bigmap",
        width=40,
        height=40,
        collision=[[0] * 40 for _ in range(40)],
        spawn=(20, 20),
    )
    state = GameState(1, map_data.map_id)
    player = state.add_player(1, "A", 20, 20)
    player.is_web = True
    collision = Collision(map_data, state.blocks)
    return state, collision, player


def test_alert_tell_plays_once_per_encounter():
    state, collision, player = _world()
    rng = random.Random(11)
    z = spawn_animal_one(state, collision, [player], rng, kind="bunny")
    assert z is not None

    import time

    # 1) First detection inside flee_vision -> freeze + "!" (alert clock set).
    z.x_f, z.y_f = player.x_f + 2.0, player.y_f
    z.sync_int_from_int() if hasattr(z, "sync_int_from_int") else None
    z.x, z.y = int(z.x_f), int(z.y_f)
    web_tick(state, collision, True, 0.05, rng=rng)
    assert z.alert_until > 0.0, "first detection must arm the stare"
    first_alert = z.last_alert_at
    assert first_alert > 0.0

    # 2) The stare lapses, the animal calms mid-flight (panic expired) but
    #    the player is STILL right there -> re-detection inside the repeat
    #    cooldown must NOT re-freeze: straight into panic instead.
    z.alert_until = 0.0
    z.panic_until = 0.0
    web_tick(state, collision, True, 0.05, rng=rng)
    assert z.alert_until == 0.0, "re-detection must skip the second stare"
    assert z.panic_until > 0.0, "re-detection must bolt straight into panic"

    # 3) Long after the cooldown a fresh encounter plays the tell again.
    z.last_alert_at -= 60.0
    z.panic_until = 0.0
    z.alert_until = 0.0
    web_tick(state, collision, True, 0.05, rng=rng)
    assert z.alert_until > 0.0, "a fresh encounter must stare again"
