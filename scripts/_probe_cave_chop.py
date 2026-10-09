"""One-off probe: replicate the preview stack's chop flow on the cave map.

Creates a GameManager, creates the ekonia/cave_area1 runtime, joins a fake
web session, and dispatches ChopAction at the nearest copper vein — prints
each ActionResult reason, mirroring scripts/_local_game_stack.py.
"""
import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from game.actions import ChopAction, TurnAction
from game.inventory import Inventory
from game.manager import GameManager
from game.state import Direction


async def main() -> None:
    gm = GameManager(assets_dir=Path("assets/maps"))
    ch = 4242
    gm.create_runtime(ch, "ekonia/cave_area1")
    rt = gm.get_runtime(ch)
    uid = 777
    rt.inventories[uid] = Inventory()
    rt.inventories[uid].add("iron_pickaxe", 1)
    from game.state import GameState

    p = rt.state.add_player(uid, "probe", 61, 29)
    p.direction = Direction["EAST"]
    rt.held_slots = {uid: 0}
    rt.state.inventories = rt.inventories
    rt.state.held_slots = rt.held_slots

    node = next(n for n in rt.resources.nodes.values() if n.kind == "copper_ore")
    ax, ay = node.anchor
    print(f"copper vein anchor: {ax},{ay}; player tile: 61,29")

    dx, dy = ax - 61, ay - 29
    print("dx,dy =", dx, dy)
    r = await gm.dispatch(ch, TurnAction(user_id=uid, direction=Direction["EAST"]))
    for i in range(10):
        result = await gm.dispatch(ch, ChopAction(user_id=uid, dx=dx, dy=dy))
        print(f"swing {i + 1}: ok={result.state_changed} reason={result.reason!r} "
              f"needed={result.needed} drops={result.drops}")
        if rt.resources.is_chopped((ax, ay)):
            print("FELLED after", i + 1, "swings")
            break
    field_drops = [
        (d.item_id, d.qty)
        for d in getattr(rt.state, "drops", None) and [] or []
    ]
    from game.drops import get_drop_field

    field = get_drop_field(rt.state)
    print("drop entities:", [(d.item_id, d.qty) for d in field.drops.values()])


if __name__ == "__main__":
    asyncio.run(main())
