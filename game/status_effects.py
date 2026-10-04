"""Player status effects (debuffs) — pure rules, no discord / no IO.

Applied on WEB-pack mob bites (game/zombies.web_tick) and ticked by the
manager's 20 Hz web beat. Runtime-only state lives on the Player
(``status_effects``); it is never persisted (a restart clears debuffs, same
as ``dead_until``).

Spec (user, 25/09):
- ZOMBIE bite: 50% -> INFECTION (thối rửa) L1: 5 dmg / 2 s for 20 s;
  blocks NATURAL regen AND FOOD heals (potions still work); stamina
  drains x1.5 while active.
- SPIDER bite: 70% -> POISON L1: same DOT as infection (5/2s, 20s) but no
  stamina penalty. On REFRESH (re-bitten while already poisoned) a 50%
  chance upgrades to L2: 10 dmg / 1 s for 20 s and -20% HP from any
  food/potion heal.
- BAT bite: 25% -> POISON L1 (the light version; user: "dơi thì như bạn
  đã set" = the earlier proposal: 1 dmg / 3 s for 12 s).
- REFRESH (shared rule for every applier): a re-applied effect resets its
  duration to full and re-rolls upgrade chances — never stacks DOT.
- Damage-over-time splats render BLUE (the icon's colour).

State shape (on the Player): ``status_effects`` = list of dicts, each:
``{"id": "infection"|"poison", "level": int, "until": float(monotonic),
"next_tick": float, "dmg": int, "interval": float}`` — newest LAST (the
rail draws oldest rightmost).
"""

from __future__ import annotations

import time as _time
from typing import Dict, List, Optional

# ---- effect definitions ---------------------------------------------------
# duration_s / dmg / interval_s per level; "food_block" also blocks FOOD
# heals (potions bypass infection but are cut 20% by poison L2).
EFFECTS: Dict[str, dict] = {
    "infection": {
        "name": "Thối Rửa",
        "levels": {
            1: dict(duration_s=20.0, dmg=5, interval_s=2.0),
        },
        "block_regen": True,      # natural out-of-combat regen stops
        "block_food_heal": True,  # food heals rejected; potions still work
        "stamina_mult": 1.5,      # stamina costs x1.5 while active
    },
    "poison": {
        "name": "Độc",
        "levels": {
            1: dict(duration_s=20.0, dmg=5, interval_s=2.0),
            2: dict(duration_s=20.0, dmg=10, interval_s=1.0),
        },
        "block_regen": True,
        "block_food_heal": False,
        "stamina_mult": 1.0,
    },
}

# Poison L2 cuts every heal source (food + potions) by 20%.
POISON_L2_HEAL_CUT = 0.20

# Per-mob bite application: (chance, effect_id, level, on_refresh upgrade).
BITE_EFFECTS: Dict[str, dict] = {
    "zombie": dict(chance=0.50, effect="infection", level=1),
    "spider": dict(chance=0.70, effect="poison", level=1, upgrade=dict(level=2, chance=0.50)),
    "bat":    dict(chance=0.25, effect="poison", level=1, upgrade=dict(level=1, chance=0.0)),
    # Skeleton is pure melee damage — no status (its gimmick is elsewhere).
}

# Dơi's light poison: shorter + weaker than the standard poison L1.
BAT_POISON = dict(duration_s=12.0, dmg=1, interval_s=3.0)


def _now() -> float:
    return _time.monotonic()


def _levels(effect_id: str) -> dict:
    return EFFECTS.get(effect_id, {}).get("levels", {})


def _build(effect_id: str, level: int, duration_s: float, dmg: int, interval_s: float) -> dict:
    return {
        "id": effect_id,
        "level": level,
        "until": _now() + duration_s,
        "next_tick": _now() + interval_s,
        "dmg": dmg,
        "interval": interval_s,
    }


def get_effect(player, effect_id: str) -> Optional[dict]:
    """The player's active effect of this id (or None)."""
    for e in getattr(player, "status_effects", None) or []:
        if e.get("id") == effect_id:
            return e
    return None


def has_effect(player, effect_id: str) -> bool:
    return get_effect(player, effect_id) is not None


def apply_bite_effect(player, mob_kind: str, rng) -> Optional[dict]:
    """Roll one mob bite's status effect (the SHARED applier).

    Roll fails -> None (effect removed? no — untouched). Roll succeeds:
    - no active effect of that id -> apply fresh (upgrades may roll for
      spiders even on the first application? Spec ties the upgrade to
      REFRESH, so no — fresh applications always land at the base level).
    - already active -> REFRESH: duration resets to full, and the applier's
      upgrade chance rolls (spider 50% -> L2).
    Returns the effect dict (new/refreshed) or None.
    """
    spec = BITE_EFFECTS.get(mob_kind)
    if spec is None:
        return None
    if rng.random() >= spec["chance"]:
        return None
    effect_id = spec["effect"]
    level = spec["level"]
    existing = get_effect(player, effect_id)
    if existing is not None:
        # REFRESH (shared rule): reset the clock; roll the upgrade.
        up = spec.get("upgrade") or {}
        up_chance = float(up.get("chance", 0.0))
        if up_chance > 0.0 and rng.random() < up_chance:
            level = max(level, int(up.get("level", level)))
        return refresh_effect(player, effect_id, level)
    # Fresh application at the base level.
    return _apply_fresh(player, effect_id, level)


def _apply_fresh(player, effect_id: str, level: int) -> dict:
    if effect_id == "poison" and level == 1:
        # The caller's mob kind decides the poison flavour; the generic
        # fresh-poison path uses the STANDARD L1 numbers (spider). Bat's
        # light variant goes through apply_bat_poison below.
        cfg = _levels(effect_id).get(1)
        eff = _build(effect_id, 1, cfg["duration_s"], cfg["dmg"], cfg["interval_s"])
    else:
        cfg = _levels(effect_id).get(level) or next(iter(_levels(effect_id).values()))
        eff = _build(effect_id, level, cfg["duration_s"], cfg["dmg"], cfg["interval_s"])
    effects = getattr(player, "status_effects", None)
    if effects is None:
        effects = []
        player.status_effects = effects
    effects.append(eff)  # newest LAST (rail draws oldest rightmost)
    return eff


def apply_bat_poison(player) -> dict:
    """Bat's light poison L1 (12 s, 1 dmg / 3 s) — fresh OR refresh."""
    existing = get_effect(player, "poison")
    if existing is not None:
        existing["until"] = _now() + BAT_POISON["duration_s"]
        # A refresh never DOWNGRADES an existing poison (spider L2 stays L2);
        # it only re-arms the clock on the light numbers when already light.
        if existing["level"] <= 1:
            existing["dmg"] = BAT_POISON["dmg"]
            existing["interval"] = BAT_POISON["interval_s"]
        existing["next_tick"] = _now() + existing["interval"]
        return existing
    eff = _build("poison", 1, BAT_POISON["duration_s"], BAT_POISON["dmg"], BAT_POISON["interval_s"])
    effects = getattr(player, "status_effects", None)
    if effects is None:
        effects = []
        player.status_effects = effects
    effects.append(eff)
    return eff


def refresh_effect(player, effect_id: str, level: Optional[int] = None) -> Optional[dict]:
    """Reset an active effect's duration to full; optionally UPGRADE its
    level (re-arms the DOT with the new level's numbers). Never downgrades:
    a refresh roll that misses the upgrade keeps the current level."""
    eff = get_effect(player, effect_id)
    if eff is None:
        return None
    if level is not None and level > eff["level"]:
        cfg = _levels(effect_id).get(level)
        if cfg is not None:
            eff["level"] = level
            eff["dmg"] = cfg["dmg"]
            eff["interval"] = cfg["interval_s"]
            eff["next_tick"] = _now() + eff["interval"]
    eff["until"] = _now() + (_levels(effect_id).get(eff["level"], {}).get("duration_s", 20.0))
    return eff


def tick_effects(player, now: Optional[float] = None) -> List[tuple]:
    """One 20 Hz beat: fire due DOT ticks, expire dead effects.

    Returns the list of (effect_id, level, damage) ticks that LANDED (the
    caller feeds them into the damage splat stream) and mutates the player's
    HP + prunes expired entries. Damage never kills here — the caller (the
    same rule as bites) checks hp <= 0 and handles death.
    """
    now = now if now is not None else _now()
    effects = getattr(player, "status_effects", None) or []
    landed: List[tuple] = []
    for eff in list(effects):
        if now >= eff["until"]:
            effects.remove(eff)
            continue
        if now >= eff["next_tick"]:
            eff["next_tick"] = now + eff["interval"]
            dmg = int(eff["dmg"])
            before = player.hp
            player.hp = max(0, player.hp - dmg)
            if player.hp != before:
                # DOT re-arms the out-of-combat regen clock (same as bites).
                player.last_damaged_at = now
                player.regen_bank = 0.0
                landed.append((eff["id"], eff["level"], dmg))
    return landed


# ---- gating rules (called from the regen / eat / stamina paths) -----------

def blocks_natural_regen(player) -> bool:
    """True while infection OR poison is active: no out-of-combat regen."""
    return any(has_effect(player, eid) for eid in EFFECTS)


def stamina_cost_mult(player) -> float:
    """Cost multiplier for stamina spends (infection x1.5, else x1)."""
    mult = 1.0
    for eid, spec in EFFECTS.items():
        if has_effect(player, eid):
            mult = max(mult, float(spec.get("stamina_mult", 1.0)))
    return mult


def heal_multiplier(player, is_potion: bool) -> float:
    """How much of a heal lands: poison L2 cuts ALL sources 20%; infection
    additionally blocks FOOD (is_potion=False) entirely."""
    if is_potion and has_effect(player, "poison") and get_effect(player, "poison")["level"] >= 2:
        return 1.0 - POISON_L2_HEAL_CUT
    if not is_potion:
        if has_effect(player, "infection"):
            return 0.0  # infection: food heals rejected outright
        if has_effect(player, "poison") and get_effect(player, "poison")["level"] >= 2:
            return 1.0 - POISON_L2_HEAL_CUT
    return 1.0


def payload(player) -> list:
    """Snapshot rows: [effect_id, seconds_left, level] (newest LAST)."""
    now = _now()
    out = []
    for e in getattr(player, "status_effects", None) or []:
        secs = max(0, int(round(e["until"] - now)))
        out.append([e["id"], secs, int(e["level"])])
    return out
