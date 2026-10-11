"""Death inside the cave side runtime must not brick the player after reload.

Bug (user 10/10): die in the cave → the web client reloads → the world shows
the grassland, but NOTHING responds anymore (no attack, no chop, no move).
Reproduction shape: the player dies while standing in the SIDE runtime (cave),
the reload path detaches the session (drop_web_session) and rejoins
(_handle_join → register_web_session + ensure_player_world).

The suspicion: the rejoin welcome/snapshot resolves a runtime that does NOT
hold the player's body, so the client renders the main map while every action
targets a runtime where the player is missing ("no_player") — or vice versa.
"""

import asyncio
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from game.manager import GameManager
from web_api.core import ClientConnection, WebHub
from web_api.protocol import WebSession

ASSETS = pathlib.Path(__file__).resolve().parent.parent / "assets" / "maps"
CAVE_MAP = "ekonia/cave_area1"


def _frames(hub):
    frames = []
    while not hub.outbox.empty():
        frames.append(hub.outbox.get_nowait())
    return frames


def test_death_in_cave_then_reload_is_controllable():
    async def run():
        uid = 99
        import shutil
        d = pathlib.Path(tempfile.mkdtemp())
        from persistence.database import Database
        from persistence.migrations import migrate
        db = Database(str(d / "game.db"))
        await db.connect()
        await migrate(db)
        gm = GameManager(ASSETS)
        gm.db = db
        gm.create_runtime(1, "bigmap")
        assert gm.register_web_session(1, uid, "tester")
        hub = WebHub(gm)
        sess = hub.registry.create(user_id=uid, display_name="tester", channel_id=1)
        hub.connections[8] = ClientConnection(cid=8, session=sess, joined=True)

        await hub.handle_envelope({"type": "client_connected", "cid": 8})
        await hub.handle_envelope({
            "cid": 8,
            "frame": {"type": "join", "token": sess.token, "channel_id": 1},
        })
        _frames(hub)  # drain join/welcome noise

        # Travel to the cave like production, then die there.
        rt_cave, _msg = await gm.web_travel_portal(1, uid, "hang")
        assert rt_cave is not None and rt_cave.map_data.map_id == CAVE_MAP
        player = rt_cave.state.get_player(uid)
        assert player is not None
        player.hp = 0
        player.visible = False
        import time as _time_mod
        from game.death_reasons import stamp
        stamp(player, "test", kind="mob")
        player.dead_until = _time_mod.time() + 5.0
        gm._schedule_respawn(rt_cave, uid)

        # RELOAD: disconnect + rejoin with the same token (the client's reload
        # path). The 5s respawn task is still pending at this point — exactly
        # the production timing of "chết rồi reload ngay".
        await hub.handle_envelope({"type": "client_disconnected", "cid": 8})
        hub.connections[9] = ClientConnection(cid=9, session=sess, joined=False)
        await hub.handle_envelope({
            "cid": 9,
            "frame": {"type": "join", "token": sess.token, "channel_id": 1},
        })

        # The new welcome must describe the SAME world the body lives in.
        welcome = [f["frame"] for f in _frames(hub)
                   if f.get("cid") == 9 and f.get("frame", {}).get("type") == "welcome"]
        assert welcome, "a reload must be answered with a welcome frame"
        wf = welcome[-1]
        assert wf.get("map", {}).get("id") == CAVE_MAP, (
            f"reload after cave death must welcome the CAVE world, "
            f"got map_id={wf.get('map', {}).get('id')}"
        )

        # The body must be both ALIVE and in the world the welcome announced:
        # a body left dead in a runtime nobody resolves = dead controls forever.
        holder = gm.runtime_of(1, uid)
        assert holder is not None, "the body must live in a resolvable runtime"
        body = holder.state.get_player(uid)
        assert body is not None, "the body must exist after the reload"

        # 5 s respawn countdown (the same UX the user saw): the pending
        # respawn task must fire and heal the body. This validates the
        # "death in a side runtime" respawn path end-to-end.
        for task in list(gm.respawn_tasks.values()):
            if not task.done():
                await task
        body = holder.state.get_player(uid)
        assert body is not None and body.hp > 0, "respawn must heal the body"

        # And the player must actually be CONTROLLABLE: an attack dispatch
        # must not answer "dead"/"no_player".
        from game.actions import AttackAction
        rt_after, res = await gm.dispatch(1, AttackAction(user_id=uid))
        assert rt_after is not None, "the attack must resolve a runtime"
        assert res is not None, "the action must return a result"
        # "dead"/"no_player"/"invisible" = the control path is broken (the
        # world the action dispatched to does not hold a controllable body).
        # "no_target" = FINE: the body is alive and swinging, no mob nearby.
        assert res.reason not in ("dead", "no_player", "invisible"), (
            f"post-reload attack must reach a live body, got reason={res.reason}"
        )
        await hub.stop()
        gm.drop_web_session(1, uid)
        await db.close()
        shutil.rmtree(d, ignore_errors=True)

    asyncio.new_event_loop().run_until_complete(run())
