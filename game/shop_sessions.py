"""Wandering-merchant SHOP SESSIONS (Stardew-cart × Terraria-merchant blend).

The "thương nhân lang thang" is NOT always in the world: he opens market
sessions on a schedule. Outside a session he is GONE from the map — players
must catch the market window (Stardew's "Fr/Su only" rhythm, compressed to a
30-min real in-game day). Every session rolls a fresh stock from a
rarity-weighted pool (Terraria's random 4-10 items per visit) plus a chance
of a MISPRICED deal (Stardew's occasional cheap line, -50%).

Data-driven config lives in the map's ``<map>.npcs.json`` on the NPC:

    "sessions": {
      "windows": [[6, 12], [14, 19]],   # in-game hours (day = 30 real min)
      "deal_chance": 0.15,              # one stock row may be mispriced
      "deal_discount": 0.5,
      "min_items": 4, "max_items": 6,
      "walk_out_seconds": 25            # visible exit walk at session end
    }

Session phases (NPCDef.shop_phase): "closed" -> "open" -> "leaving" (walks
to the map edge / spawn-despawn tile, visible!) -> "closed". While closed
the server DROPS the NPC from welcome/snapshot payloads — the client never
sees him, so no client changes are needed for the disappear act.

Prices/stock only refresh at session START: every player in the world sees
the SAME market this session (a shared event, not per-player rerolls).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# In-game seconds helpers (daynight clock): h*3600 + m*60.
from rendering.daynight import ingame_seconds


@dataclass
class ShopSessionState:
    """Runtime session bookkeeping for ONE wandering merchant NPC."""
    phase: str = "closed"          # closed | open | leaving
    session_id: int = 0            # bumps each new session (stock refresh key)
    last_window_index: int = -1    # which window produced the current/last session
    leave_deadline: float = 0.0    # wall-clock (monotonic) when "leaving" ends
    leave_target: Optional[tuple] = None  # (tx, ty) walk-out destination
    deal_key: Optional[str] = None  # item key of the current mispriced deal


def parse_sessions(npc) -> Optional[dict]:
    """The NPC's raw sessions config (None when it's not a session merchant)."""
    cfg = getattr(npc, "sessions", None)
    return cfg if isinstance(cfg, dict) and cfg.get("windows") else None


def _in_window(sec_of_day: int, windows: List[List[int]]) -> int:
    """Index of the session window containing ``sec_of_day`` (-1 = none)."""
    h = sec_of_day / 3600.0
    for i, (a, b) in enumerate(windows):
        if a <= h < b:
            return i
    return -1


def session_active(npc, state: ShopSessionState, now_mono: float,
                   sec_of_day: Optional[int] = None) -> bool:
    """Advance the session state machine; True when the NPC is IN WORLD.

    open    : inside a window -> present, walking, shop payload live.
    leaving : window ended -> present but WALKING OUT (visible exit); the
              shop is CLOSED for business (shop_open answers 'hết phiên').
    closed  : nowhere in the world.
    """
    cfg = parse_sessions(npc)
    if cfg is None:
        return True  # not a session merchant: always present
    windows = cfg.get("windows") or []
    idx = _in_window(sec_of_day if sec_of_day is not None else ingame_seconds(), windows)

    if state.phase == "closed":
        if idx >= 0 and idx != state.last_window_index:
            # NEW SESSION: roll a fresh stock signature. The stock itself is
            # re-rolled in shops.py keyed by session_id; here we just open.
            state.phase = "open"
            state.session_id += 1
            state.last_window_index = idx
            state.deal_key = None
        return state.phase == "open"

    if state.phase == "open":
        if idx < 0 or idx != state.last_window_index:
            # WINDOW ENDED: switch to the visible walk-out. Target = the
            # NPC's despawn tile (config "walk_out_tile" as [x, y]) or the
            # spawn point (walks home, then vanishes there — reads natural
            # either way).
            wo = cfg.get("walk_out_tile")
            state.leave_target = tuple(wo) if wo else (npc.x, npc.y)
            state.phase = "leaving"
            state.leave_deadline = now_mono + float(cfg.get("walk_out_seconds", 25.0))
        return True

    # leaving: vanish when the deadline passes (the walk itself is just the
    # sprite gliding toward leave_target via the normal wander lane).
    if now_mono >= state.leave_deadline:
        state.phase = "closed"
        state.last_window_index = -1  # allow the SAME window next day
        return False
    return True


def roll_deal(stock: List[dict], cfg: dict, rng: random.Random) -> Optional[str]:
    """Maybe mark ONE stocked item as a mispriced deal (-50%) for this
    session (Stardew's occasional cheap line). Mutates the item price in
    place and returns its key (None = no deal this session)."""
    chance = float(cfg.get("deal_chance", 0.15))
    discount = float(cfg.get("deal_discount", 0.5))
    if stock and rng.random() < chance:
        item = rng.choice(stock)
        item["price"] = max(1, int(item["price"] * discount))
        return item["key"]
    return None
