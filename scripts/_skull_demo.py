"""DEMO-ONLY preview for NPC "Skull:" (Princess sprite, static trader).

- Does NOT touch game data: the NPC + dialogues + shop are injected into
  the preview runtime's memory only. No .npcs.json / .shops.json is written.
- Every tab auto-lands on montertradebase next to Skull: (game tile 9,6).
- Run: .venv/Scripts/python scripts/_skull_demo.py   (port 8897; override
  with PREVIEW_PORT=xxxx). Open http://127.0.0.1:8897/?preview=1
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aiohttp import web  # noqa: E402

from game.npc import DialogueNode, DialogueOption, NPCDef  # noqa: E402
from game.shops import Shop, ShopItem  # noqa: E402
from scripts._local_game_stack import _fresh_preview_user  # noqa: E402
from scripts._preview_stack import PreviewStack, _resolve_tp_tile  # noqa: E402
from web_api.snapshots import build_welcome  # noqa: E402

PORT = int(os.environ.get("PREVIEW_PORT", "8897"))

SKULL_POS = (9, 6)   # Tiled (9,9) minus map bbox origin (0,3)
PLAYER_POS = (9, 8)  # customer side, directly in front of the counter

# PLACEHOLDER stock — user has not given the real list yet. Marked clearly
# in the demo push message so nobody mistakes it for the final shop.
PLACEHOLDER_STOCK = [
    ("steel_sword", 900, 1),
    ("key_stone", 700, 1),
    ("leatherchest", 380, 1),
    ("steel_ingot", 260, 2),
]


def inject_skull(rt) -> None:
    """Memory-only NPC + dialogue + shop (idempotent)."""
    rt.npc_map.npcs = [n for n in rt.npc_map.npcs if n.id != "skull"]
    npc = NPCDef(
        id="skull",
        name="Skull:",
        emoji="\U0001F451",
        x=SKULL_POS[0],
        y=SKULL_POS[1],
        dialogue="skull_intro",
        sprite={"w": 16, "h": 16, "frames": 4, "scale": 0.5},
        facing="down",
        reach=2,  # talk THROUGH the counter row (no map edit needed)
    )
    npc.init_float()
    rt.npc_map.npcs.append(npc)
    rt.npc_map.dialogues["skull_intro"] = DialogueNode(
        text="Ch\u00e0o ng\u01b0\u1eddi l\u00e3ng kh\u00e1ch \u0111\u1ebfn t\u1eeb ph\u01b0\u01a1ng xa, "
             "ch\u1edb hay mu\u1ed1n h\u1ecfi \u0111\u1ebfn \u0111\u00e2y t\u00ecm g\u00ec?",
        options=[DialogueOption(label="(G\u1eadt \u0111\u1ea7u ch\u00e0o l\u1ea1i)", next="skull_shop_line")],
    )
    rt.npc_map.dialogues["skull_shop_line"] = DialogueNode(
        text="H\u00e0ng trong s\u00e0n \u0111\u1ec1u c\u00f3 gi\u00e1 ni\u00eam y\u1ebft, "
             "kh\u00e1ch l\u1ea1 kh\u00e1ch quen \u0111\u1ec1u nh\u01b0 nhau. M\u1eddi xem.",
        options=[
            DialogueOption(label="Xem h\u00e0ng hi\u1ebfm", next="shop:skull"),
            DialogueOption(label="Ch\u1ec9 gh\u00e9 ngang qua", next=None),
        ],
    )
    rt.shops["skull"] = Shop(
        key="skull",
        currency="coin",
        items=[ShopItem(key=k, price=p, count=c, max_count=c) for k, p, c in PLACEHOLDER_STOCK],
    )


# Test anchors (verify the room_fx pipeline; the real markers now live in
# the map JSON — see _inject_test_fx note below).
_TEST_FIRES = [(9, 3)]
_TEST_WINDOWS = [(4, 5)]


def _inject_test_fx(rt) -> None:
    # Direct anchor set (same shape map_loader harvests from Tiled layers).
    rt.map_data.fx_markers = {
        "fires": [list(c) for c in _TEST_FIRES],
        "windows": [list(c) for c in _TEST_WINDOWS],
    }


class SkullDemoStack(PreviewStack):
    async def _frame(self, cid: int, frame: dict) -> None:
        t = frame.get("type")
        if t in ("join", "map_preview"):
            # Force every tab into the trade house with Skull: injected.
            if cid not in self.sessions:
                uid0 = _fresh_preview_user()
                self.sessions[cid] = {"user_id": uid0, "name": f"Khach-{uid0 % 10000}"}
            uid = self.sessions[cid]["user_id"]
            ch = uid ^ 0x5EED000000000000
            old = self.gm.get_runtime(ch)
            if old is not None:
                self.gm.remove_runtime(ch)
            self.gm.create_runtime(ch, "montertradebase")
            self.gm.register_web_session(ch, uid, self.sessions[cid]["name"])
            self.joined[cid] = ch
            self.ensure_tick()
            rt = self.gm.get_runtime(ch)
            inject_skull(rt)
            # Room FX now come from the REAL map JSON marker layers
            # ("fx lửa" @Tiled(9,6) / "fx cửa sổ" @Tiled(4,8)) — no injection.
            player = rt.state.get_player(uid)
            print(f"[demo] join uid={uid} player={player is not None}", flush=True)
            if player is not None:
                tile = _resolve_tp_tile(rt, player, f"{PLAYER_POS[0]},{PLAYER_POS[1]}")
                print(f"[demo] tp tile={tile} pos=({player.x},{player.y})", flush=True)
                if tile is not None:
                    player.revive_teleport(*tile)
                    print(f"[demo] after=({player.x},{player.y})", flush=True)
                try:
                    if int(getattr(player, "coins", 0) or 0) < 2000:
                        player.coins = 2000
                except Exception:
                    pass
                self.gm._schedule_save(rt, player)
            await self._send(cid, build_welcome(rt, uid))
            await self._send(cid, {
                "type": "push",
                "message": "[demo] Skull: \u0111ang \u0111\u1ee9ng k\u1ebf b\u00ean (ph\u1ea3i). "
                           "B\u1ea5m F \u0111\u1ec3 n\u00f3i chuy\u1ec7n. "
                           "H\u00e0ng trong shop l\u00e0 T\u1ea0M (ch\u01b0a ch\u1ed1t list th\u1eadt).",
            })
            return
        await super()._frame(cid, frame)


    async def _preview_cmd(self, cid: int, frame: dict) -> None:
        if str(frame.get("cmd", "")) == "skull":
            uid = self.sessions[cid]["user_id"]
            ch = self.joined.get(cid)
            rt = self.gm.get_runtime(ch) if ch is not None else None
            if rt is None:
                await self._send(cid, {"type": "push", "message": "[demo] Ch\u01b0a v\u00e0o map."})
                return
            inject_skull(rt)
            await self._send(cid, {"type": "push", "message": "[demo] \u0110\u00e3 n\u1ea1p l\u1ea1i Skull:."})
            return
        await super()._preview_cmd(cid, frame)


async def main() -> None:
    from scripts._local_game_stack import DIST_DIR

    stack = SkullDemoStack()
    app = web.Application()
    app.router.add_get("/ws", stack.handle_browser)
    app.router.add_get("/config.json", stack.serve_config)
    app.router.add_get("/", stack.serve_index)
    app.router.add_get("/index.html", stack.serve_index)
    app.router.add_static("/", str(DIST_DIR))
    stack.snap_task = asyncio.get_event_loop().create_task(stack._snapshot_loop())

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", PORT)
    await site.start()
    print(f"[skull-demo] ready on http://127.0.0.1:{PORT}/?preview=1", flush=True)
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
