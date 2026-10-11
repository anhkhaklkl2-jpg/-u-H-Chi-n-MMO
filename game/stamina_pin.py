"""Stamina pin for the exhausted-attack gate test (preview + web).

``pin_stamina(rt, user_id, on)`` sets ``rt.web_sessions[uid].stamina_lock``
so GameManager._stamina_regen_beat skips the player's refill. Import-lean:
tolerates a missing web_sessions map (no-op).
"""
from __future__ import annotations


def pin_stamina(rt, user_id: int, on: bool) -> None:
    """Pin (on) or release (off) the stamina regen lock for one session."""
    sessions = getattr(rt, "web_sessions", None)
    if not isinstance(sessions, dict):
        return
    sess = sessions.get(user_id)
    if sess is None:
        return
    sess.stamina_lock = bool(on)
