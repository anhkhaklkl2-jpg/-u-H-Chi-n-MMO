"""Cave chop via the web client must target the SIDE runtime's tiles.

Bug (user 06/10): ore veins rendered fine on production, but clicking one did
nothing — preview worked. Production enters the cave through a portal, so the
player's body lives in a SIDE runtime while ``manager.get_runtime(channel)``
returns the MAIN bigmap. The aim baseline in ``WebHub._handle_action`` used the
main runtime's player record (absent / stale there), so every chop computed a
wrong tile or out_of_range and silently missed the ore node.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from game.manager import GameManager
from game.resources import is_ore_kind
from web_api.core import ClientConnection, WebHub
from web_api.protocol import WebSession

ASSETS = pathlib.Path(__file__).resolve().parent.parent / "assets" / "maps"

CAVE_MAP = "ekonia/cave_area1"


def test_chop_ore_aims_from_side_runtime():
    """Click-to-mine an ore node while standing in the cave side runtime."""

    async def run():
        uid = 42
        gm = GameManager(ASSETS)
        gm.create_runtime(1, "bigmap")
        assert gm.register_web_session(1, uid, "tester"), "session must attach"
        hub = WebHub(gm)
        sess = hub.registry.create(user_id=uid, display_name="tester", channel_id=1)
        hub.connections[7] = ClientConnection(cid=7, session=sess, joined=True)

        await hub.handle_envelope({"type": "client_connected", "cid": 7})
        await hub.handle_envelope({
            "cid": 7,
            "frame": {"type": "join", "token": sess.token, "channel_id": 1},
        })

        # Travel to the cave the production way: portal fast-travel puts the
        # body in a SIDE runtime.
        rt, _msg = await gm.web_travel_portal(1, uid, "hang")
        assert rt is not None and rt.map_data.map_id == CAVE_MAP
        # The production shape: the main runtime no longer holds the player.
        assert gm.get_runtime(1).state.get_player(uid) is None
        assert rt.state.get_player(uid) is not None

        # Stand next to an ore vein and hold a pickaxe in the active slot.
        node = next(
            n for n in rt.resources.nodes.values()
            if is_ore_kind(n.kind)
        )
        nx, ny = node.anchor
        player = rt.state.get_player(uid)
        player.x, player.y = nx, ny + 1  # within AIM_RANGE
        inv = gm.get_inventory(1, uid)
        inv.add("iron_pickaxe", 1)
        inv.move_to("iron_pickaxe", 0)
        rt.held_slots[uid] = 0

        # Click the ore tile exactly like the web client does (absolute tx/ty).
        await hub.handle_envelope({
            "cid": 7,
            "frame": {"type": "action", "name": "chop", "tx": nx, "ty": ny},
        })
        await hub.stop()

        frames = []
        while not hub.outbox.empty():
            frames.append(await hub.outbox.get())
        results = [
            f["frame"] for f in frames
            if f.get("frame", {}).get("type") == "action_result"
        ]
        assert results, "the chop click must be answered with an action_result"
        r = results[-1]
        assert r["name"] == "chop"
        assert r.get("ok") or r.get("reason") == "regrowing", (
            f"the click must land on the ore node, got: {r}"
        )
        assert is_ore_kind(r.get("kind", "")) or r.get("reason") == "regrowing"

    asyncio.new_event_loop().run_until_complete(run())
