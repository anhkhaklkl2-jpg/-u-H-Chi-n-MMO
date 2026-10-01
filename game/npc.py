import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# ---- Wandering NPC ("thương nhân lang thang") ------------------------------
# NPCs with `wander` geometry move like a slow player: pick a random cardinal
# step inside the radius every few seconds, walk between tiles smoothly
# (x_f/y_f floats), and PAUSE when a player stands adjacent (talking). The
# NPC body is also a solid hitbox: the server clamps player moves that would
# enter the NPC's tile (Collision stays map-static; the clamp is applied by
# the web movement paths via npc_blocks).


@dataclass
class NPCDef:
    id: str
    name: str
    emoji: str
    x: int
    y: int
    dialogue: Optional[str] = None
    # WEB CLIENT ONLY: optional real sprite served through the assets
    # pipeline ("npcs/<stem>.png"). Discord ignores it (maintenance mode);
    # absent/None -> the client keeps drawing the emoji token.
    sprite: Optional[Dict[str, int]] = None
    # WANDERING NPC: {"radius": int, "speed": tiles/sec, "pause": secs}.
    # Absent/None -> a static NPC (signs/doors/statues never move).
    wander: Optional[Dict[str, float]] = None
    # Live float position (tile centers) for wandering NPCs. Kept in sync
    # with x/y by sync_int_from_float like web players.
    x_f: float = -1.0
    y_f: float = -1.0
    # Current walk target (int tiles) + busy flag while stepping between
    # tiles. None target = standing still.
    target: Optional[tuple] = None
    # Facing key ("down"|"left"|"right"|"up") for the client's walk anim.
    facing: str = "down"

    def init_float(self) -> None:
        if self.x_f < 0 or self.y_f < 0:
            self.x_f = float(self.x)
            self.y_f = float(self.y)

    def sync_int_from_float(self) -> None:
        self.x = int(round(self.x_f))
        self.y = int(round(self.y_f))


@dataclass
class DialogueOption:
    label: str
    next: Optional[str] = None
    effect: Dict[str, str] = field(default_factory=dict)


@dataclass
class DialogueNode:
    text: str
    options: List[DialogueOption] = field(default_factory=list)


@dataclass
class NpcMap:
    npcs: List[NPCDef]
    dialogues: Dict[str, DialogueNode]


def load_npcs(map_id: str, assets_dir: Path) -> NpcMap:
    path = assets_dir / f"{map_id}.npcs.json"
    if not path.exists():
        return NpcMap([], {})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return NpcMap([], {})
    npcs = [NPCDef(**n) for n in data.get("npcs", [])]
    dialogues: Dict[str, DialogueNode] = {}
    for k, v in data.get("dialogues", {}).items():
        opts = [
            DialogueOption(o.get("label", ""), o.get("next"), o.get("effect", {}))
            for o in v.get("options", [])
        ]
        dialogues[k] = DialogueNode(v.get("text", ""), opts)
    return NpcMap(npcs, dialogues)


def load_npcs_with_floats(npc_map: NpcMap) -> None:
    """Seed every NPC's float position from its int tile (runtime init)."""
    for n in npc_map.npcs:
        n.init_float()


def _walkable_for_npc(walkable_at, x: int, y: int, occupied: set) -> bool:
    """NPC pathing: same walkable rule as players minus the resources pass
    (an NPC never chops trees — the static map grid decides)."""
    return (x, y) not in occupied and walkable_at(x, y)


def wander_step(
    npc: NPCDef,
    walkable_at,
    occupied: set,
    player_positions: List[tuple],
    dt: float,
    rng: random.Random,
) -> bool:
    """Advance a wandering NPC by dt seconds. Returns True when it moved.

    Behaviour ("thương nhân lang thang"):
    - Player ADJACENT (Manhattan <= 1 on the float position) -> stand still
      and face the player (the "dừng lại khi player tương tác" rule).
    - Otherwise walk toward the current target tile at the configured speed;
      on arrival pick a NEW random walkable target within the wander radius
      (biased toward staying put — pause between legs reads more natural).
    """
    cfg = npc.wander or {}
    radius = int(cfg.get("radius", 3))
    speed = float(cfg.get("speed", 1.2))
    pause = float(cfg.get("pause", 1.5))
    npc.init_float()

    # Talking/player-near pause: freeze + face the nearest player.
    nearest = None
    best_d = 2.5
    for px, py in player_positions:
        d = math.hypot(npc.x_f - px, npc.y_f - py)
        if d < best_d:
            best_d = d
            nearest = (px, py)
    if nearest is not None:
        npc.target = None
        npc.facing = _face_toward(npc.x_f, npc.y_f, *nearest)
        return False

    if npc.target is None:        # Pick a new target INSIDE the radius around the SPAWN point
        # (not the current position) so the NPC keeps a home range.
        r = rng.randint(1, max(1, radius))
        if rng.random() < 0.35 * min(1.0, pause):
            npc.target = None
            return False
        for _try in range(12):
            tx = npc.x + rng.randint(-r, r)
            ty = npc.y + rng.randint(-r, r)
            if (abs(tx - int(cfg.get("home_x", npc.x))) > radius
                    or abs(ty - int(cfg.get("home_y", npc.y))) > radius):
                continue
            if _walkable_for_npc(walkable_at, tx, ty, occupied):
                npc.target = (tx, ty)
                break
        if npc.target is None:
            return False

    tx, ty = npc.target
    dx = tx - npc.x_f
    dy = ty - npc.y_f
    dist = math.hypot(dx, dy)
    if dist < 0.02:
        npc.x_f, npc.y_f = float(tx), float(ty)
        npc.sync_int_from_float()
        npc.target = None
        return False
    step = min(dist, speed * dt)
    npc.x_f += dx / dist * step
    npc.y_f += dy / dist * step
    npc.facing = _face_toward(npc.x_f, npc.y_f, tx, ty)
    npc.sync_int_from_float()
    return True


def _face_toward(x: float, y: float, tx: float, ty: float) -> str:
    dx = tx - x
    dy = ty - y
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"


def npc_blocks_tile(npcs: List[NPCDef], x: int, y: int) -> bool:
    """True when any NPC occupies this int tile — the player hitbox clamp."""
    for n in npcs:
        if n.x == x and n.y == y:
            return True
    return False


def npc_push_out(npcs: List[NPCDef], x_f: float, y_f: float) -> tuple:
    """Push a float player position out of any NPC tile it overlaps.

    The web player moves in FLOAT tiles with a small collision box; a moving
    NPC stepping ONTO the player's tile must eject it to the nearest edge
    of that tile (or the tile stays shared -> visual overlap + stuck F gate).
    Returns the corrected (x_f, y_f)."""
    for n in npcs:
        n.init_float()
        # Player box (FLOAT_BOX_HALF=0.3) overlaps the NPC tile?
        if abs(x_f - n.x_f) < 0.8 and abs(y_f - n.y_f) < 0.8:
            # Eject along the axis with the smaller penetration.
            if abs(x_f - n.x_f) <= abs(y_f - n.y_f):
                x_f = n.x_f + (0.85 if x_f >= n.x_f else -0.85)
            else:
                y_f = n.y_f + (0.85 if y_f >= n.y_f else -0.85)
    return x_f, y_f


def npc_adjacent(npcs: List[NPCDef], px: int, py: int) -> Optional[NPCDef]:
    """Return an NPC exactly one cardinal step away from (px, py)."""
    for n in npcs:
        if abs(n.x - px) + abs(n.y - py) == 1:
            return n
    return None


def get_node(npc_map: NpcMap, node_id: Optional[str]) -> Optional[DialogueNode]:
    if node_id is None:
        return None
    return npc_map.dialogues.get(node_id)
