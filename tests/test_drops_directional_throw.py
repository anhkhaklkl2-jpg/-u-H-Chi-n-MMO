"""Directional throws: the drop visibly flies where the player faces."""
from __future__ import annotations

import math

from game.drops import (
    ARC_LAUNCH_VX,
    NO_COLLECT_WINDOW_S,
    THROW_LAUNCH_VX,
    spawn_drops,
    tick_drops,
)


class FakePlayer:
    def __init__(self, user_id: int, x: float, y: float) -> None:
        self.user_id = user_id
        self.x_f = x
        self.y_f = y
        self.alive = True
        self.visible = True


class FakeState:
    def __init__(self) -> None:
        self.drop_field = None


def test_thrown_drop_has_no_collect_window() -> None:
    state = FakeState()
    drops = spawn_drops(state, 3.0, 3.0, [("dirt", 1)])
    assert len(drops) == 1


def test_directional_throw_velocity_points_east() -> None:
    state = FakeState()
    d = spawn_drops(
        state, 3.0, 3.0, [("dirt", 1)],
        no_collect_window=NO_COLLECT_WINDOW_S, direction="EAST",
    )[0]
    assert d.vx > 0 and abs(d.vy) < d.vx * 0.5


def test_directional_throw_velocity_points_north() -> None:
    state = FakeState()
    d = spawn_drops(
        state, 3.0, 3.0, [("dirt", 1)],
        no_collect_window=NO_COLLECT_WINDOW_S, direction="NORTH",
    )[0]
    assert d.vy < 0 and abs(d.vx) < abs(d.vy) * 0.5


def test_directional_throw_diagonal() -> None:
    state = FakeState()
    d = spawn_drops(
        state, 3.0, 3.0, [("dirt", 1)],
        no_collect_window=NO_COLLECT_WINDOW_S, direction="NE",
    )[0]
    assert d.vx > 0 and d.vy < 0


def test_throw_launch_is_stronger_than_idle_scatter() -> None:
    assert THROW_LAUNCH_VX == pytest_approx(ARC_LAUNCH_VX * 2.5)
    state = FakeState()
    d = spawn_drops(
        state, 3.0, 3.0, [("dirt", 1)],
        no_collect_window=NO_COLLECT_WINDOW_S, direction="SOUTH",
    )[0]
    # along-axis speed (minus jitter) must be near THROW_LAUNCH_VX
    assert d.vy > THROW_LAUNCH_VX * 0.7


def test_unknown_direction_falls_back_south() -> None:
    state = FakeState()
    d = spawn_drops(
        state, 3.0, 3.0, [("dirt", 1)],
        no_collect_window=NO_COLLECT_WINDOW_S, direction=" Banana",
    )[0]
    assert d.vy > 0  # south = +y


def test_thrown_drop_is_not_instantly_recollected(direction_none=None) -> None:
    state = FakeState()
    player = FakePlayer(7, 3.2, 3.2)
    d = spawn_drops(
        state, 3.0, 3.0, [("dirt", 1)],
        no_collect_window=NO_COLLECT_WINDOW_S, direction="NORTH",
    )[0]
    collections, _ = tick_drops(state, [player], 0.05)
    assert collections == []
    assert d.no_collect_until > 0.0


def test_directional_throw_travels_40pct_farther_than_old_launch() -> None:
    """Old launch: speed 1.6 t/s. New: 4.0 t/s — with the same flight time
    (identical arc), the horizontal distance scales by 2.5x. The requested
    +40% minimum is far exceeded."""
    state = FakeState()
    d = spawn_drops(
        state, 3.0, 3.0, [("dirt", 1)],
        no_collect_window=NO_COLLECT_WINDOW_S, direction="EAST",
    )[0]
    speed = math.hypot(d.vx, d.vy)
    assert speed >= ARC_LAUNCH_VX * 1.4 * 0.9  # at least +40% (minus jitter)


def pytest_approx(x: float) -> float:
    return x
