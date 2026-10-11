"""Ghost-player regression (user 07/10: "player đứng im, không tương tác được,
reload vẫn còn").

Three holes minted permanent standing bodies:
1. register_web_session looked up the body ONLY on the main runtime — a body
   living in a side world (cave/forest after a portal step) returned None and
   a FRESH body was minted at the main spawn on every reload (the duplicate
   the real body was later overwritten by / stood next to).
2. The inactivity watchdog's "no Discord screen -> drop ledger" branch left a
   web-only player's body visible=True forever (standing ghost).
3. Re-register after such a hiding must make the body visible again.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from game.manager import GameManager
from game.travel import TRADE_LOBBY_MAP

ASSETS = pathlib.Path(__file__).resolve().parent.parent / "assets" / "maps"


def _gm():
    gm = GameManager(ASSETS)
    gm.create_runtime(1, "test-map")
    gm.db = None
    gm._schedule_save = lambda rt, player: None
    return gm


def test_rejoin_with_body_in_side_world_mints_no_main_ghost():
    """Reload while the body stands in a side world: the main runtime must
    NOT gain a duplicate body (the old ghost-at-spawn bug)."""
    gm = _gm()
    main = gm.runtimes[1]
    # Live body already in a side world (e.g. walked into the cave).
    side = gm.get_or_create_side_runtime(main, TRADE_LOBBY_MAP)
    side.state.add_player(42, "tester", 5, 5)
    side.state.players[42].world_map = TRADE_LOBBY_MAP

    assert gm.register_web_session(1, 42, "tester")

    # The body is untouched where it stands; no duplicate on main.
    assert 42 in side.state.players
    assert 42 not in main.state.players
    # Session attached on the runtime holding the body.
    assert 42 in side.web_sessions
    assert 42 not in main.web_sessions


def test_register_makes_hidden_body_visible_again():
    gm = _gm()
    rt = gm.runtimes[1]
    p = rt.state.add_player(42, "tester", 2, 2)
    p.visible = False  # hidden by a previous watchdog/drop path
    gm.register_web_session(1, 42, "tester")
    assert p.visible is True


def test_ghost_sweep_hides_nameless_orphan_body():
    """The screenshot ghost: a body standing in the grassland with NO name
    label. ensure_player_world's fresh-join branch minted it with
    display_name="" and no session ever attached — the sweep must hide it."""
    gm = _gm()
    rt = gm.runtimes[1]
    rt.state.add_player(42, "", 3, 3)  # nameless, no web session, not tracked
    rt.state.players[42].is_web = True
    hidden = gm._ghost_sweep()
    assert hidden >= 1
    assert rt.state.get_player(42).visible is False


def test_ghost_sweep_hides_chat_body_without_session():
    """Round 3 (boot restore): the DB has no display_name column, so the bot
    used to re-mint a VISIBLE nameless CHAT body at boot that the is_web-only
    sweep never hid. The sweep must hide chat bodies too (no session, no
    live Discord screen)."""
    gm = _gm()
    rt = gm.runtimes[1]
    p = rt.state.add_player(42, "", 3, 3)  # boot-restored: nameless, visible
    assert p.visible is True  # pre-fix restore left it visible
    hidden = gm._ghost_sweep()
    assert hidden >= 1
    assert rt.state.get_player(42).visible is False


def test_ghost_sweep_spares_chat_body_with_live_screen():
    """A Discord player keeps a live screen message — never hide them even
    if their ledger entry is momentarily absent."""
    gm = _gm()
    rt = gm.runtimes[1]
    p = rt.state.add_player(42, "discorder", 3, 3)
    from game.manager import PlayerScreen

    rt.screens[42] = PlayerScreen(user_id=42, message_id=999)
    gm._ghost_sweep()
    assert p.visible is True


def test_ghost_sweep_spares_live_sessions():
    gm = _gm()
    rt = gm.runtimes[1]
    gm.register_web_session(1, 42, "tester")
    gm._ghost_sweep()
    assert rt.state.get_player(42).visible is True


def test_ensure_player_world_fresh_join_keeps_name():
    """The nameless-ghost SOURCE: a fresh join whose saved body lives in a
    side world must carry the session's display_name, not an empty label."""

    async def run():
        gm = _gm()
        main = gm.runtimes[1]
        gm.db = _FakeDb(TRADE_LOBBY_MAP, 7, 7)
        await gm.ensure_player_world(1, 42, display_name="Tester")
        side = gm.side_runtimes[(1, TRADE_LOBBY_MAP)]
        p = side.state.get_player(42)
        assert p is not None and p.display_name == "Tester"
        assert main.state.get_player(42) is None

    asyncio.run(run())


class _FakeDb:
    """Minimal async db stub returning one saved-world row."""

    def __init__(self, world_map, x, y):
        self._row = (world_map, x, y)

    async def fetchall(self, sql, params=()):
        return [self._row]


async def _unused():  # keep asyncio import used in all paths
    return None


def test_watchdog_hides_web_only_body_without_discord_screen():
    """Web-only player (no Discord screen ever opened) idle past the timeout:
    the body must be hidden, not left standing as a ghost."""

    async def run():
        gm = _gm()
        rt = gm.runtimes[1]
        gm.configure_sessions(timeout_minutes=30, check_interval=1)
        gm.register_web_session(1, 42, "tester")
        assert rt.state.get_player(42).visible is True
        # Kill the web session so the watchdog may hide the body.
        gm.drop_web_session(1, 42)
        # Age the ledger entry past the timeout.
        gm.sessions._sessions[(1, 42)].last_activity -= 31 * 60
        task = asyncio.create_task(gm._session_loop())
        await asyncio.sleep(1.4)  # check_interval=1 + handler time
        task.cancel()
        p = rt.state.get_player(42)
        assert p.visible is False, "web-only ghost body must be hidden"
        assert p.is_web is False and p.mode == "chat"

    asyncio.run(run())
