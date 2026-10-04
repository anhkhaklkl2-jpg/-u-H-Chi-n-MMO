"""Death reasons (lý do chết) — pure data + one helper, no discord / no IO.

Every death path stamps ``player.death_reason`` (str, ngôn ngữ hiển thị cho
người chơi) before scheduling the respawn. The web snapshot carries the
string verbatim to the client's death overlay.

The catalogue (user 29/09: "mik cần bạn build 1 số lý do chết") — VN hiển thị:

- per mob kind: "Bị <tên quái> tấn công" (zombie, skeleton, wolf, bear…)
- status DOT: "Chết vì <tên hiệu ứng>" (Thối Rửa / Độc — game/status_effects.py)
- self-kill (/kill): "Tự kết thúc để hồi sinh"

``stamp(player, kind)`` is the ONLY writer the death paths call: it also
stamps ``player.died_at`` (unix seconds, wall clock) — the client uses it to
restart its death overlay + dissolve animation exactly once per death
(instead of guessing from the boolean ``dead`` flag flipping at 20 Hz).
"""

from __future__ import annotations

import time as _time
from typing import Optional

# Per mob kind -> VN name used in "Bị <name> tấn công". Aliases fold the
# variant mobs (skeleton2 / deer2) into their base name.
_MOB_DEATH_NAMES = {
    "zombie": " zombie",
    "skeleton": " bộ xương",
    "skeleton2": " bộ xương",
    "spider": " nhện",
    "slime": " slime",
    "bat": " dơi",
    "rat": " chuột",
    "spectre": " spectre",
    "goblin": " hobgoblin nhỏ",
    "hobgoblin": " hobgoblin",
    "bunny": " thỏ rừng",
    "deer": " con hươu",
    "deer2": " con hươu",
    "bird": " chim",
    "boar": " heo rừng",
    "bear": " gấu",
    "fox": " cáo",
    "wolf": " sói",
}

# Status-effect ids -> "Chết vì <tên>" (EFFECTS names in game/status_effects.py).
_STATUS_DEATH_NAMES = {
    "infection": "chết vì thối rửa",
    "poison": "chết vì trúng độc",
}

SELF_KILL_REASON = "Tự kết thúc để hồi sinh"
DEFAULT_REASON = "gục ngã vì kích thương"


def death_reason_for_mob(mob_kind: str) -> str:
    name = _MOB_DEATH_NAMES.get(mob_kind, mob_kind)
    return f"Bị{name} tấn công"


def death_reason_for_status(effect_id: str) -> str:
    return _STATUS_DEATH_NAMES.get(effect_id, DEFAULT_REASON)


def stamp(player, reason: str, kind: Optional[str] = None) -> None:
    """Write the death reason + died_at on the player.

    ``kind`` is the damage source tag ("zombie" / "status" / "self") — the
    client uses it to pick the death-overlay flavour. ``died_at`` is unix
    wall-clock seconds (server time, same clock as the snapshot loop).
    """
    player.death_reason = reason
    player.death_kind = kind
    player.died_at = _time.time()
