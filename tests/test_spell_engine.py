import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from game.inventory import Inventory
from game.rules import apply_spell, resolve_pending_spells
from game.state import GameState
from game.zombies import Zombie, _add_web_zombie


def test_rocklift_auto_acquires_nearest_mob_when_aim_misses():
    state = GameState(1, "test-map")
    # Preview-mode flag: our tests exercise the FREE-cast path (no wand gate).
    state.preview_mode = True
    player = state.add_player(7, "Caster", 5, 5)
    player.sync_float_from_int()
    player.mana = 50

    inventory = Inventory()
    inventory.add("magic_wand", 1)
    state.inventories = {7: inventory}
    state.held_slots = {7: 0}

    # Mob is ~4.2 tiles SE of player while the cast is aimed north. The
    # directed flight misses it; rocklift's 9-tile acquisition should not.
    mob = Zombie("wz-rocklift-test", 9, 8)
    mob.x_f, mob.y_f = 9.5, 8.5
    mob.hp = mob.max_hp = 90
    _add_web_zombie(state, mob)

    result = apply_spell(state, 7, "rocklift", 0, -4)

    assert result.state_changed is True
    assert result.target_id == mob.zombie_id
    assert result.damage > 0
    # DISTANCE-PROPORTIONAL FLIGHT (user 13/10): flight = base 400 + 220/ô
    # × quãng đường thật clamp 4.75 (player (5.5,5.5) -> mob (9.5,8.5) = 5 ô
    # clamped về 4.75 = 1445ms). A fixed 1800 kept near casts sluggish and
    # far casts speeding.
    assert result.impact_delay_ms == 400 + 220 * 4.75  # flight duration echo
    assert mob.hp == 90  # damage NOT applied at cast time (pending)
    # After the flight elapses, resolve lands the damage exactly once.
    hits = resolve_pending_spells(state, now=state.pending_spells[0]["at"])
    assert len(hits) == 1 and hits[0]["target_id"] == mob.zombie_id
    assert mob.hp == 90 - result.damage
    assert resolve_pending_spells(state) == []  # no double-apply
    assert result.pos == (9, 8)


def test_projectile_spell_auto_acquires_when_click_line_misses():
    state = GameState(2, "test-map")
    state.preview_mode = True
    player = state.add_player(8, "Caster", 5, 5)
    player.sync_float_from_int()
    player.mana = 50

    inventory = Inventory()
    inventory.add("magic_wand", 1)
    state.inventories = {8: inventory}
    state.held_slots = {8: 0}

    # The click aims north, far from this hostile; a normal projectile should
    # still acquire it inside the forgiving default radius.
    mob = Zombie("wz-projectile-test", 14, 8)
    mob.x_f, mob.y_f = 14.5, 8.5
    mob.hp = mob.max_hp = 90
    _add_web_zombie(state, mob)

    # wood01 has no flight_ms → damage still lands instantly (unchanged).
    result = apply_spell(state, 8, "wood01", 0, -4)

    assert result.target_id == mob.zombie_id
    assert result.damage > 0
    assert mob.hp == 90 - result.damage
