"""Room FX marker detection (game/room_fx.py)."""
from game.room_fx import detect_room_fx


def _grid(cells, w=20, h=14):
    g = [[0] * w for _ in range(h)]
    for x, y in cells:
        g[y][x] = 289
    return g


def test_fires_detected_vietnamese_name():
    layers = [("sàn đất", _grid([(1, 1)])), ("fx lửa", _grid([(9, 6)]))]
    out = detect_room_fx(layers)
    assert out == {"fires": [[9, 6]]}


def test_aliases_and_windows():
    layers = [("fx fire", _grid([(2, 3)])), ("fx window", _grid([(4, 1), (5, 1)]))]
    out = detect_room_fx(layers)
    assert out == {"fires": [[2, 3]], "windows": [[4, 1], [5, 1]]}


def test_empty_when_no_markers():
    layers = [("sàn đất", _grid([(1, 1)])), ("tường", _grid([(0, 0)]))]
    assert detect_room_fx(layers) == {}


def test_blocking_layers_never_match():
    # A wall layer literally named with fire words is NOT an fx marker —
    # detection only fires on the fx marker names.
    layers = [("tường lửa", _grid([(3, 3)]))]
    assert detect_room_fx(layers) == {}
