"""Local repro stack for the web-client movement stutter (no Discord, no cloud).

Starts:
  1. an in-process game loop (GameManager + 20 Hz web tick + snapshot pump),
     speaking the EXACT WebHub frame protocol (net.ts speaks the same),
  2. an in-process relay: serves web_client/relay/dist statically AND accepts
     the browser WebSocket at /ws, faking the bot side in-process,

so the REAL web client can be loaded in a browser (Freebuff preview) and the
movement pipeline can be measured end-to-end on THIS machine.

Run:  .venv/Scripts/python scripts/_local_game_stack.py   (Ctrl+C to stop)
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aiohttp import web, WSMsgType  # noqa: E402

from game.manager import GameManager, _loop_time  # noqa: E402
from web_api.snapshots import build_welcome, build_snapshot  # noqa: E402

RELAY_PORT = int(os.environ.get("RELAY_PORT", "8899"))
# Simulated one-way latency (ms) for browser<->game frames — set
# LATENCY_MS=150 to reproduce prod relay conditions locally.
LATENCY_MS = float(os.environ.get("LATENCY_MS", "0"))
DIST_DIR = ROOT / "web_client" / "relay" / "dist"

PREVIEW_USER = 910000000000000042
PREVIEW_CHANNEL = PREVIEW_USER ^ 0x5EED000000000000
# MULTI-SESSION (user 28/09): 2-4 preview tabs run side by side; each tab gets
# its OWN user_id + channel so it lives in a separate world instance. The ids
# come from a random 40-bit space hashed into the safe int64 band (> 2^53),
# far from real Discord snowflakes; collisions across tabs are vanishingly
# rare and only cost a shared world (same as the old single-session mode).
def _fresh_preview_user() -> int:
    import secrets as _s

    return 910000000000000000 + (_s.randbits(40) << 8)


def now_ms() -> float:
    return time.time() * 1000


class LocalStack:
    def __init__(self) -> None:
        self.gm = GameManager(ROOT / "assets" / "maps")
        self.browsers: dict[int, web.WebSocketResponse] = {}
        self.next_cid = 1
        self.sessions: dict[int, dict] = {}
        self.joined: dict[int, int] = {}  # cid -> channel_id
        self.seq = 0
        self.tick_task: asyncio.Task | None = None
        self.snap_task: asyncio.Task | None = None
        self.selected_slot: dict[int, int] = {}  # cid -> held hotbar slot
        # PARITY with web_api/core.WebHub: the manager must push travel_begin
        # frames so the web client's iris veil closes BEFORE the teleport —
        # without this the preview tests a different flow than production.
        self.gm.web_travel_begin_hook = self._send_travel_begin

    async def _send_travel_begin(self, map_name: str, user_id: int) -> None:
        for cid, sess in self.sessions.items():
            if sess.get("user_id") == user_id and self.joined.get(cid):
                await self._send(cid, {
                    "type": "travel_begin", "map_name": map_name,
                })

    # ---------------- game plumbing ----------------

    def ensure_tick(self) -> None:
        if self.tick_task is None or self.tick_task.done():
            self.tick_task = asyncio.get_event_loop().create_task(self._tick_loop())

    async def _tick_loop(self) -> None:
        interval = 1 / 20
        next_t = time.perf_counter()
        while True:
            next_t += interval
            await asyncio.sleep(max(0.0, next_t - time.perf_counter()))
            now = _loop_time()
            for rt in list(self.gm.runtimes.values()) + list(self.gm.side_runtimes.values()):
                sessions = getattr(rt, "web_sessions", None)
                if not sessions:
                    continue
                try:
                    await self.gm._web_tick_runtime(rt, sessions, now)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    import traceback
                    traceback.print_exc()

    def _map_payload(self, rt) -> dict:
        from web_api import snapshots as S

        fn = getattr(S, "_web_map_payload", None)
        if fn is None:
            fn = getattr(S, "build_welcome", None)
        return fn(rt) if fn else {}

    async def handle_browser(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(max_msg_size=16 * 1024 * 1024)
        await ws.prepare(request)
        cid = self.next_cid
        self.next_cid += 1
        self.browsers[cid] = ws
        print(f"[stack] browser connected cid={cid}", flush=True)
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                await self._frame(cid, json.loads(msg.data))
        finally:
            self.browsers.pop(cid, None)
            ch = self.joined.pop(cid, None)
            sess = self.sessions.pop(cid, None)
            if ch and sess:
                self.gm.drop_web_session(ch, sess["user_id"])
            print(f"[stack] browser disconnected cid={cid}", flush=True)
        return ws

    async def _frame(self, cid: int, frame: dict) -> None:
        t = frame.get("type")
        if t == "ping":
            await self._send(cid, {"type": "pong"})
            return
        if cid not in self.sessions and t not in ("guest_login", "resume_login"):
            # Frame before login (stale reconnect): auto-guest so old clients
            # never KeyError the handler. ISOLATED (user 28/09): a fresh user
            # per connection — two preview tabs never share a world.
            uid0 = _fresh_preview_user()
            self.sessions[cid] = {"user_id": uid0, "name": f"Khach-{uid0 % 10000}"}
        if t == "guest_login" or t == "resume_login":
            # ISOLATED (user 28/09): ignore any client-sent guest_id and mint a
            # unique user per TAB. resume_login from a dropped tab gets a new
            # user too — the old world despawns with the socket, so resuming
            # into it would spawn a ghost on a dead channel.
            user_id = _fresh_preview_user()
            self.sessions[cid] = {"user_id": user_id, "name": f"Khach-{user_id % 10000}"}
            await self._send(cid, {
                "type": "login_result", "ok": True,
                "token": "local", "user_id": user_id,
                "display_name": self.sessions[cid]["name"],
            })
            return
        if t == "map_preview" or t == "join":
            uid = self.sessions[cid]["user_id"]
            map_id = str(frame.get("map_id") or "ekonia/forest")
            if map_id not in ("ekonia/forest", "ekonia/cave_area1", "ekonia/overworld", "bigmap"):
                map_id = "ekonia/forest"
            ch = uid ^ 0x5EED000000000000
            old = self.gm.get_runtime(ch)
            if old is not None:
                self.gm.remove_runtime(ch)
            self.gm.create_runtime(ch, map_id)
            self.gm.register_web_session(ch, uid, self.sessions[cid]["name"])
            self.joined[cid] = ch
            self.ensure_tick()
            rt = self.gm.get_runtime(ch)
            await self._send(cid, build_welcome(rt, uid))
            return
        if t == "input":
            uid = self.sessions[cid]["user_id"]
            ch = self.joined.get(cid)
            if ch is None:
                return
            self.gm.web_input(
                ch, uid,
                float(frame.get("dx", 0.0)),
                float(frame.get("dy", 0.0)),
                running=bool(frame.get("running", frame.get("sprint", False))),
                input_seq=frame.get("seq"),
                report_x=frame.get("x", frame.get("report_x")),
                report_y=frame.get("y", frame.get("report_y")),
            )
            return
        if t == "select_slot":
            slot = frame.get("slot")
            if isinstance(slot, int) and 0 <= slot < 8:
                self.selected_slot[cid] = slot
                # PRODUCTION PARITY (web_api/core.py): mirror the held slot
                # onto the runtime's held_slots map — without this the
                # preview player ALWAYS swung bare-handed (chop answered
                # needed=65 even with a pickaxe selected).
                ch = self.joined.get(cid)
                uid = (self.sessions.get(cid) or {}).get("user_id")
                rt0 = self.gm.get_runtime(ch) if ch else None
                if rt0 is not None and uid is not None:
                    rt0.held_slots[uid] = slot
            return
        if t == "action":
            # Preview parity with web_api._handle_action: build the SAME
            # action objects and route through manager.dispatch like prod.
            print(f"[stack] action {frame.get('name')} tx={frame.get('tx')} ty={frame.get('ty')} block={frame.get('block_id')}", flush=True)
            uid = self.sessions[cid]["user_id"]
            ch = self.joined.get(cid)
            if not ch:
                return
            from game.actions import (
                AttackAction, ChopAction, BreakBlockAction, TurnAction,
                PlaceBlockAction, ShovelAction,
            )
            name = str(frame.get("name", ""))
            rt_a = self.gm.get_runtime(ch)
            player_a = rt_a.state.get_player(uid) if rt_a else None
            abs_dx = abs_dy = None
            raw_tx, raw_ty = frame.get("tx"), frame.get("ty")
            if (player_a is not None and isinstance(raw_tx, (int, float))
                    and isinstance(raw_ty, (int, float))):
                abs_dx = int(raw_tx) - player_a.x
                abs_dy = int(raw_ty) - player_a.y
                lim = 3 + 2
                if max(abs(abs_dx), abs(abs_dy)) > lim:
                    abs_dx = max(-3, min(3, abs_dx)) if abs(abs_dx) > 3 else abs_dx
                    abs_dy = max(-3, min(3, abs_dy)) if abs(abs_dy) > 3 else abs_dy
            action = None
            if name == "attack":
                action = AttackAction(user_id=uid)
            elif name == "spell":
                # WEB SPELLS (user 08/10): parity with web_api/core.py —
                # resolve via rules.apply_spell and echo action_result so
                # the preview client sees damage/drops like production.
                rt_s = self.gm.get_runtime(ch)
                from game import rules as _rules
                from game.rules import ActionResult
                spell_result = (
                    _rules.apply_spell(
                        rt_s.state, uid, str(frame.get("spell_id", "")),
                        abs_dx, abs_dy,
                    ) if rt_s is not None and rt_s.state.get_player(uid) is not None
                    else ActionResult(False, "no_scenario")
                )
                await self._send(cid, {
                    "type": "action_result",
                    "name": "spell",
                    "ok": bool(spell_result.state_changed),
                    "reason": spell_result.reason or "",
                    "tx": spell_result.pos[0] if spell_result.pos else None,
                    "ty": spell_result.pos[1] if spell_result.pos else None,
                    "kind": "zombie" if getattr(spell_result, "target_id", None) else "",
                    "target_id": getattr(spell_result, "target_id", None),
                    "target_defeated": bool(getattr(spell_result, "target_defeated", False)),
                    "needed": None,
                    "drops": [[i, q] for i, q in (spell_result.drops or [])],
                    "damage": int(getattr(spell_result, "damage", 0) or 0),
                    "critical": bool(getattr(spell_result, "critical", False)),
                    "missed": bool(getattr(spell_result, "missed", False)),
                    "spell_id": frame.get("spell_id", ""),
                })
                return
            elif name == "chop":
                action = ChopAction(user_id=uid, dx=abs_dx, dy=abs_dy)
            elif name == "break":
                action = BreakBlockAction(user_id=uid, dx=abs_dx, dy=abs_dy)
            elif name == "shovel":
                action = ShovelAction(user_id=uid)
            elif name == "turn":
                # Parity with web_api/core.py: mouse-facing sync sends a
                # throttled "turn" — without this branch EVERY facing change
                # answered error bad_action (toast "Lỗi: bad_action" popped
                # whenever the mouse moved ⇒ phím F "lúc được lúc không").
                from game.state import Direction
                try:
                    direction = Direction[str(frame.get("dir", "SOUTH")).upper()]
                    action = TurnAction(user_id=uid, direction=direction)
                except KeyError:
                    action = None
            elif name == "place":
                dx, dy = (abs_dx, abs_dy) if abs_dx is not None else (
                    frame.get("dx"), frame.get("dy"))
                block_id = str(frame.get("block_id", ""))
                if not block_id and player_a is not None:
                    inv = self.gm.get_inventory(ch, uid)
                    from game.blocks import get_block
                    held = inv.hotbar().get(self.selected_slot.get(cid, 0) or 0)
                    if held and get_block(held) is not None:
                        block_id = held
                action = PlaceBlockAction(
                    user_id=uid, block_id=block_id,
                    dx=int(dx) if dx is not None else None,
                    dy=int(dy) if dy is not None else None,
                )
            if action is None:
                await self._send(cid, {"type": "error", "code": "bad_action"})
                return
            try:
                _, result = await self.gm.dispatch(ch, action)
            except Exception as exc:
                await self._send(cid, {"type": "push", "message": f"[preview] action error: {exc!r}"})
                return
            # PRODUCTION PARITY: echo the action outcome so the client can
            # show progress/failures (web_api/core.py sends the same frame;
            # without it the preview client never sees ok/reason/needed/
            # drops — chop progress bars stayed invisible and failed swings
            # looked like dead clicks).
            if result is not None:
                await self._send(cid, {
                    "type": "action_result",
                    "name": name,
                    "ok": bool(result.state_changed),
                    "reason": result.reason or "",
                    "tx": result.pos[0] if result.pos else None,
                    "ty": result.pos[1] if result.pos else None,
                    "kind": (
                        "zombie" if getattr(result, "target_id", None)
                        else (result.block_id or "")
                    ),
                    "target_id": getattr(result, "target_id", None),
                    "target_defeated": bool(getattr(result, "target_defeated", False)),
                    "needed": result.needed,
                    "drops": [[i, q] for i, q in (result.drops or [])],
                    "damage": int(getattr(result, "damage", 0) or 0),
                    "critical": bool(getattr(result, "critical", False)),
                    "missed": bool(getattr(result, "missed", False)),
                })
            return
        if t == "inventory_op":
            op = frame.get("op")
            uid = self.sessions[cid]["user_id"]
            ch = self.joined.get(cid)
            inv = self.gm.get_inventory(ch, uid) if ch else None
            if op == "reorder" and inv is not None:
                # Preview parity with web_api/core reorder → manager.reorder_bag:
                # bag-grid drag & drop persists the client's slot layout
                # (missing this made every drag echo back the OLD server
                # layout — items "tự sắp xếp" after each drag in preview).
                await self.gm.reorder_bag(
                    ch, uid, [(e.get("id"), e.get("qty", 0))
                              for e in frame.get("order", [])])
                return
            if op == "move_to" and inv is not None:
                await self.gm.set_hotbar_slot(ch, uid, int(frame.get("slot", 0)),
                                              frame.get("item_id"))
                return
            if op == "split" and inv is not None:
                inv.split_slot(int(frame.get("slot", -1)))
                return
            if op == "use":
                await self.gm.use_item(ch, uid, frame.get("item_id", ""))
                return
            if op != "armor_equip":
                return  # unknown inventory op: stay silent in preview
        if t == "inventory_op" and frame.get("op") == "armor_equip":
            # Preview parity with web_api/core._handle_inventory_op armor_equip:
            # server validates the slot match and swaps the old piece back.
            from game.items import armor_slot_of
            uid = self.sessions[cid]["user_id"]
            ch = self.joined.get(cid)
            rt = self.gm.get_runtime(ch) if ch else None
            player = rt.state.get_player(uid) if rt is not None else None
            if player is None:
                return
            action = str(frame.get("action", ""))
            slot = str(frame.get("slot", ""))
            equipped = getattr(player, "equipped_armor", None)
            if equipped is None:
                equipped = player.equipped_armor = {}
            inv = self.gm.get_inventory(ch, uid)
            if action == "equip":
                item_id = str(frame.get("item_id", ""))
                want = armor_slot_of(item_id)
                if want is None or slot != want or inv.count(item_id) <= 0:
                    await self._send(cid, {"type": "error", "code": "bad_slot"})
                    return
                prev = equipped.get(slot)
                # Position-precise parity with web_api/core equip: the old
                # piece swaps into the cell the new one was dragged FROM.
                slot_idx = frame.get("slot_index")
                slot_idx = int(slot_idx) if isinstance(slot_idx, int) else None
                if slot_idx is not None and 0 <= slot_idx < len(inv.slots):
                    src_cell = inv.slots[slot_idx]
                    if src_cell and src_cell[0] == item_id:
                        if src_cell[1] > 1:
                            inv.set_slot(slot_idx, item_id, src_cell[1] - 1)
                        else:
                            inv.set_slot(slot_idx, None, 0)
                    else:
                        slot_idx = None
                if slot_idx is None:
                    inv.remove(item_id, 1)
                equipped[slot] = item_id
                if prev:
                    if slot_idx is not None and inv.slots[slot_idx] is None:
                        inv.set_slot(slot_idx, prev, 1)
                    else:
                        inv.add(prev, 1)
            elif action == "unequip":
                prev = equipped.pop(slot, None)
                if prev:
                    # Position-precise parity with web_api/core: drop-to-slot
                    # lands EXACTLY where dropped (no auto-tidy).
                    slot_idx = frame.get("slot_index")
                    slot_idx = int(slot_idx) if isinstance(slot_idx, int) else None
                    if slot_idx is not None and 0 <= slot_idx < len(inv.slots):
                        if inv.slots[slot_idx] is None:
                            inv.set_slot(slot_idx, prev, 1)
                        elif armor_slot_of(inv.slots[slot_idx][0]) == slot:
                            equipped[slot] = inv.slots[slot_idx][0]
                            inv.set_slot(slot_idx, prev, 1)
                        else:
                            equipped[slot] = prev  # roll back
                    elif inv.first_free_slot() >= 0:
                        inv.add(prev, 1)
                    else:
                        equipped[slot] = prev  # bag full: roll back
            await self._send(cid, build_welcome(rt, uid))
            return
        if t == "asset_request":
            await self._serve_asset(cid, str(frame.get("name", "")))
            return
        if t == "list":
            items = [
                {"channel_id": str(rt.channel_id), "map_id": rt.map_data.map_id,
                 "map_name": rt.map_data.display_name or rt.map_data.map_id,
                 "players": len(rt.state.get_visible_players())}
                for rt in self.gm.runtimes.values()
            ]
            await self._send(cid, {"type": "scenario_list", "items": items})
            return
        if t == "command":
            await self._send(cid, {"type": "command_result", "ok": False, "code": "local_stack"})
            return
        if t == "chat_cmd":
            # Preview parity with web_api/core._handle_chat_cmd: route slash
            # commands through the SAME manager calls production uses, so
            # /cuahang, /give, ... behave identically in the preview tab.
            text = (frame.get("text") or "").strip()
            uid = self.sessions[cid]["user_id"]
            ch = self.joined.get(cid)
            if not ch:
                return
            if not text.startswith("/"):
                await self._send(cid, {"type": "chat", "uid": uid,
                                       "name": self.sessions[cid]["name"],
                                       "color": "", "text": text[:200]})
                return
            parts = text[1:].split()
            cmd, args = parts[0].lower(), parts[1:]
            if cmd == "cuahang":
                dest = " ".join(args) if args else "hang"
                rt, message = await self.gm.web_travel_portal(ch, uid, dest)
                await self._send(cid, {"type": "push", "message": message})
                if rt is not None:
                    await self._send(cid, build_welcome(rt, uid))
                return
            if cmd == "khutraodoi":
                action = (args[0].lower() if args else "in")
                rt, message = await self.gm.web_travel_trade(ch, uid, action)
                await self._send(cid, {"type": "push", "message": message})
                if rt is not None:
                    await self._send(cid, build_welcome(rt, uid))
                return
            if cmd == "give":
                from game.items import ITEM_REGISTRY
                from game.blocks import BLOCK_REGISTRY
                if not args:
                    ids = " ".join(sorted(ITEM_REGISTRY.keys()))
                    await self._send(cid, {"type": "push", "message": f"Dùng: /give <item> [số lượng]. Có: {ids}"})
                    return
                item_id = args[0].lower()
                try:
                    qty = max(1, min(999, int(args[1]))) if len(args) > 1 else 1
                except ValueError:
                    qty = 1
                rt = self.gm.get_runtime(ch)
                if rt is not None and (item_id in ITEM_REGISTRY or item_id in BLOCK_REGISTRY):
                    await self.gm.add_item(ch, uid, item_id, qty)
                    await self._send(cid, {"type": "push", "message": f"Đã nhận {qty} {item_id}."})
                else:
                    await self._send(cid, {"type": "push", "message": f"Không biết vật phẩm: {item_id}"})
                return
            if cmd == "mac":
                # Preview parity with web_api/core._cmd_mac: demo-equip the
                # Kaetram leather armor set on the paperdoll.
                from web_api.snapshots import _players_manifest_payload
                rt = self.gm.get_runtime(ch)
                player = rt.state.get_player(uid) if rt is not None else None
                if rt is None or player is None:
                    return
                armor_catalog = _players_manifest_payload().get("armor", {})
                sub = (args[0].lower() if args else "leather")
                if sub == "off":
                    player.equipped_armor = {}
                    await self._send(cid, {"type": "push", "message": "Đã THÁO hết giáp."})
                elif sub == "leather":
                    player.equipped_armor = {
                        "helmet": "leatherhelmet",
                        "chest": "leatherchest",
                        "legs": "leatherleggings",
                    }
                    await self._send(cid, {"type": "push", "message": "Đã mặc BỘ GIÁP DA."})
                else:
                    await self._send(cid, {"type": "push", "message":
                        "Dùng: /mac leather | /mac off | /mac <helmet|chest|legs> <stem>. "
                        f"Sheet có: {', '.join(sorted(armor_catalog.keys()))}"})
                return
            if cmd == "npc":
                # Parity with web_api/core.py "npc" (per-NPC reach incl.
                # shopkeeper through-counter range).
                from game.npc import npc_in_reach
                npc_id = (args[0].lower() if args else "")
                rt = self.gm.get_runtime(ch)
                player = rt.state.get_player(uid) if rt is not None else None
                npc = None
                if rt is not None and player is not None:
                    px, py = float(player.x), float(player.y)
                    for n in rt.npc_map.npcs:
                        if n.id.lower() != npc_id:
                            continue
                        if npc_in_reach(n, px, py):
                            npc = n
                            break
                if npc is None or npc.dialogue is None:
                    await self._send(cid, {"type": "push",
                                           "message": "Không có NPC nào ở cạnh đó."})
                    return
                node = rt.npc_map.dialogues.get(npc.dialogue)
                await self._send(cid, {
                    "type": "npc_dialogue",
                    "npc": npc.id,
                    "name": npc.name,
                    "emoji": npc.emoji,
                    "text": node.text if node else "…",
                    "options": [
                        {"label": o.label, "next": o.next}
                        for o in (node.options if node else [])
                    ],
                })
                return
            if cmd == "npc_next":
                # Dialogue tree navigation (parity with web_api/core.py).
                node_id = (args[0].lower() if args else "")
                # SHOP BRANCH (parity with core.py): next == "shop:<key>[:<style>]"
                if node_id.startswith("shop:"):
                    parts = node_id.split(":")
                    shop_key = parts[1] if len(parts) > 1 else ""
                    style = parts[2] if len(parts) > 2 else "kaetram"
                    rt = self.gm.get_runtime(ch)
                    shop = rt.shops.get(shop_key)
                    if rt is None or shop is None:
                        await self._send(cid, {"type": "push",
                                               "message": "Shop không tồn tại."})
                        return
                    await self._preview_shop_payload(cid, ch, uid, rt, shop, style)
                    return
                rt = self.gm.get_runtime(ch)
                node = rt.npc_map.dialogues.get(node_id) if rt else None
                if node is None:
                    await self._send(cid, {"type": "push",
                                           "message": "Hội thoại không tồn tại."})
                    return
                # Speaker identity (parity with web_api/core.py): prefer the
                # npc id the client sends as 2nd arg over the node id.
                talk_id = (args[1].lower() if len(args) > 1 else "")
                talk_npc = None
                if rt is not None and talk_id:
                    for n in rt.npc_map.npcs:
                        if n.id.lower() == talk_id:
                            talk_npc = n
                            break
                who = talk_npc.name if talk_npc \
                    else ("Gạc Đặc" if node_id.startswith("gac_dac") else node_id)
                await self._send(cid, {
                    "type": "npc_dialogue",
                    "npc": talk_npc.id if talk_npc else node_id.split("_")[0],
                    "name": who,
                    "emoji": talk_npc.emoji if talk_npc else "🦝",
                    "text": node.text,
                    "options": [
                        {"label": o.label, "next": o.next} for o in node.options
                    ],
                })
                return
            if cmd in ("shop", "shop_buy", "shop_sell"):
                await self._preview_shop_cmd(cid, ch, uid, cmd, args)
                return
            await self._send(cid, {"type": "push", "message": f"[preview] Lệnh không hỗ trợ local: {cmd}"})
            return
        await self._send(cid, {"type": "error", "code": "unknown_type", "got": t})

    async def _preview_shop_payload(self, cid, ch, uid, rt, shop, style="kaetram") -> None:
        """Frame shop_open (parity with web_api/core.py _send_shop_payload)."""
        from game.shops import payload as shop_payload
        from game.items import get_item

        inv = self.gm.get_inventory(ch, uid)
        coins = inv.count(shop.currency)

        def name_of(iid: str) -> str:
            it = get_item(iid)
            return it.name if it is not None else iid

        frame = shop_payload(shop, inv, coins, name_of=name_of)
        frame["style"] = style
        await self._send(cid, frame)

    async def _preview_shop_cmd(self, cid, ch, uid, cmd: str, args: list) -> None:
        """shop / shop_buy / shop_sell (parity with web_api/core.py)."""
        from game import shops as shop_mod

        if not args:
            await self._send(cid, {"type": "push", "message": "Thiếu tham số shop."})
            return
        rt = self.gm.get_runtime(ch)
        shop_key = str(args[0]).lower()
        shop = rt.shops.get(shop_key) if rt is not None else None
        if shop is None:
            await self._send(cid, {"type": "push", "message": "Shop không tồn tại."})
            return
        inv = self.gm.get_inventory(ch, uid)
        if cmd == "shop":
            style = str(args[1]).lower() if len(args) > 1 else "kaetram"
            await self._preview_shop_payload(cid, ch, uid, rt, shop, style=style)
            return
        if cmd == "shop_buy":
            if len(args) < 3:
                await self._send(cid, {"type": "push",
                                       "message": "Dùng: /shop_buy <key> <index> <count>"})
                return
            index, count = int(args[1]), max(1, min(999, int(args[2])))
            coins = inv.count(shop.currency)
            ok, msg, new_coins, _spent = shop_mod.buy(shop, index, count, inv, coins)
            if not ok:
                await self._send(cid, {"type": "push", "message": msg})
                return
            item = shop.items[index]
            if not item.infinite:
                item.count -= count
            inv.remove(shop.currency, coins - new_coins)
            inv.add(item.key, count)
            await self._send(cid, {"type": "push", "message": msg})
            style = str(args[3]).lower() if len(args) > 3 else "kaetram"
            await self._preview_shop_payload(cid, ch, uid, rt, shop, style=style)
            return
        # shop_sell
        if len(args) < 3:
            await self._send(cid, {"type": "push",
                                   "message": "Dùng: /shop_sell <key> <item_id> <qty>"})
            return
        item_id = str(args[1]).lower()
        qty = max(1, min(999, int(args[2])))
        store_item = next((i for i in shop.items if i.key == item_id), None)
        base_price = store_item.price if store_item else 1
        ok, msg, gained = shop_mod.sell(shop, inv, item_id, qty, base_price)
        if not ok:
            await self._send(cid, {"type": "push", "message": msg})
            return
        inv.remove(item_id, qty)
        inv.add(shop.currency, gained)
        await self._send(cid, {"type": "push", "message": msg})
        style = str(args[3]).lower() if len(args) > 3 else "kaetram"
        await self._preview_shop_payload(cid, ch, uid, rt, shop, style=style)

    async def _serve_asset(self, cid: int, name: str) -> None:
        """Mirror WebHub._handle_asset_request (basename-confined PNG serve)."""
        import base64
        from config import ASSETS_DIR

        safe = Path(name).name
        if name.startswith("players/weapon/") or name.startswith("players/armor/"):
            safe = Path(name).parts[-2] + "/" + Path(name).parts[-1]
        if not safe.lower().endswith(".png"):
            await self._send(cid, {"type": "asset_data", "name": name, "b64": None})
            return
        if name.startswith("npcs/"):
            # NPC real sprites (parity with web_api/core.py asset serve).
            base_dir = ASSETS_DIR.parent / "npcs"
        elif name.startswith("blocks/"):
            base_dir = ASSETS_DIR.parent / "blocks"
        elif name.startswith("tilesets/"):
            base_dir = ASSETS_DIR.parent / "tilesets"
        elif name.startswith("icons/"):
            base_dir = ASSETS_DIR.parent / "gui" / "icons"
        elif name.startswith("mobs/"):
            base_dir = ASSETS_DIR.parent / "mobs"
        elif name.startswith("node/"):
            # Bundled node sprites (meteor-ore crater rock).
            base_dir = ASSETS_DIR.parent / "node"
        elif name.startswith("players/"):
            base_dir = ASSETS_DIR.parent / "players"
        elif name.startswith("fx/"):
            # Room-FX strips (parity with web_api/core.py).
            base_dir = ASSETS_DIR.parent / "fx"
        else:
            base_dir = ASSETS_DIR
        path = base_dir / safe
        try:
            path.resolve().relative_to(base_dir.resolve())
        except ValueError:
            path = None
        if path is not None and not Path(path).exists() and name.startswith("tilesets/"):
            for cand in ASSETS_DIR.rglob(safe):
                path = cand
                break
        b64 = None
        if path is not None and Path(path).exists():
            try:
                b64 = base64.b64encode(Path(path).read_bytes()).decode("ascii")
            except OSError:
                b64 = None
        await self._send(cid, {"type": "asset_data", "name": name, "b64": b64})

    async def _send(self, cid: int, frame: dict) -> None:
        ws = self.browsers.get(cid)
        if ws is None or ws.closed:
            return
        try:
            if LATENCY_MS > 0:
                await asyncio.sleep(LATENCY_MS / 1000)
            await ws.send_str(json.dumps(frame))
        except ConnectionResetError:
            pass

    async def _snapshot_loop(self) -> None:
        while True:
            await asyncio.sleep(0.05)
            for cid, ch in list(self.joined.items()):
                uid = self.sessions[cid]["user_id"]
                # PARITY with web_api/core: pump the runtime the player is
                # ACTUALLY on (side runtime after /cuahang or a portal step),
                # not the channel's main world — otherwise snapshots keep
                # carrying the OLD map_id and the client's map-change gate
                # (travel veil readiness) never fires in preview.
                rt = self.gm.runtime_of(ch, uid) or self.gm.get_runtime(ch)
                if rt is None:
                    continue
                self.seq += 1
                snap = build_snapshot(rt, uid, self.seq)
                if snap is not None:
                    await self._send(cid, snap)

    # ---------------- static relay ----------------

    async def serve_index(self, request: web.Request) -> web.FileResponse:
        return web.FileResponse(DIST_DIR / "index.html")

    async def serve_config(self, request: web.Request) -> web.Response:
        return web.json_response({"client_id": "0", "redirect_uri": None})


async def main() -> None:
    stack = LocalStack()
    app = web.Application()
    app.router.add_get("/ws", stack.handle_browser)
    app.router.add_static("/", str(DIST_DIR))
    app.router.add_get("/config.json", stack.serve_config)
    app.router.add_get("/", stack.serve_index)
    app.router.add_get("/index.html", stack.serve_index)
    stack.snap_task = asyncio.get_event_loop().create_task(stack._snapshot_loop())

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", RELAY_PORT)
    await site.start()
    print(f"[stack] ready on http://127.0.0.1:{RELAY_PORT}  (dist={DIST_DIR})", flush=True)
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
