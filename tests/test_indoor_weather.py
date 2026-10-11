"""Indoor trade maps are WEATHER-IMMUNE on the web (user 28/09).

Snapshot weather for montertradebase / lobbytrade must always be a clear
"sun_clouds" — no rain/snow/storm INSIDE the market — while outdoor maps
keep the live key. Mirrors the cave-biome guard (_is_cave_map).
"""
from __future__ import annotations

from config import ASSETS_DIR
from game.manager import GameManager
from web_api.snapshots import _is_indoor_map, build_snapshot


def _runtime_for(map_id: str, weather_key: str):
    gm = GameManager(assets_dir=ASSETS_DIR)
    rt = gm.create_runtime(4242, map_id)
    rt.weather_key = weather_key
    rt.state.add_player(1, "A", 2, 2).is_web = True
    return rt


def test_trade_zone_maps_flag_as_indoor():
    assert _is_indoor_map(type("RT", (), {
        "map_data": type("MD", (), {"map_id": "montertradebase"})(),
    })())
    assert _is_indoor_map(type("RT", (), {
        "map_data": type("MD", (), {"map_id": "lobbytrade"})(),
    })())
    assert not _is_indoor_map(type("RT", (), {
        "map_data": type("MD", (), {"map_id": "bigmap"})(),
    })())


def test_snapshot_weather_clear_inside_market_regardless_of_pin():
    """Even with an admin rain pin, the interior snapshot is clear."""
    rt = _runtime_for("montertradebase", "rain")
    snap = build_snapshot(rt, 1, 1)
    assert snap["weather"] == "sun_clouds"

    rt2 = _runtime_for("lobbytrade", "storm")
    snap2 = build_snapshot(rt2, 1, 1)
    assert snap2["weather"] == "sun_clouds"


def test_outdoor_map_keeps_live_weather_key():
    rt = _runtime_for("bigmap", "rain")
    snap = build_snapshot(rt, 1, 1)
    assert snap["weather"] == "rain"
