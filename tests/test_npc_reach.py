"""Per-NPC interact reach (game/npc.py npc_in_reach).

Default reach=1: standing next to the NPC. reach=2 (shopkeepers behind a
counter): also straight through ONE blocking layer — the staff area stays
sealed, no map edit needed.
"""
from game.npc import NPCDef, npc_in_reach


def _npc(x, y, reach=1):
    return NPCDef(id="t", name="T", emoji="X", x=x, y=y, reach=reach)


def test_adjacent_ok_default():
    n = _npc(9, 6)
    assert npc_in_reach(n, 8.0, 6.0)
    assert npc_in_reach(n, 9.0, 7.0)


def test_through_counter_rejected_default():
    n = _npc(9, 6)  # player (9,8): wall row between, distance 2
    assert not npc_in_reach(n, 9.0, 8.0)


def test_through_counter_ok_with_reach2():
    n = _npc(9, 6, reach=2)
    assert npc_in_reach(n, 9.0, 8.0)  # straight through the counter


def test_reach2_still_rejects_far():
    n = _npc(9, 6, reach=2)
    assert not npc_in_reach(n, 9.0, 9.0)   # two rows past the counter
    assert not npc_in_reach(n, 6.0, 6.0)   # three tiles sideways


def test_float_midstep_accepted():
    n = _npc(9, 6, reach=2)
    assert npc_in_reach(n, 9.4, 7.6)  # walking into the hatch, mid-step
