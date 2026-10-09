"""E2E gate test through the preview stack (raw WS client, no browser).

Run with the preview stack up (port 8898):
    .venv/Scripts/python scripts/_test_gate_ws.py
"""
import asyncio
import json
import sys

import aiohttp

BASE = "http://127.0.0.1:8898"
WS = "ws://127.0.0.1:8898/ws"


async def main() -> int:
    async with aiohttp.ClientSession() as http:
        async with http.ws_connect(WS, max_msg_size=32 * 1024 * 1024) as ws:
            await ws.send_str(json.dumps({"type": "guest_login", "guest_id": 424242}))
            await ws.send_str(json.dumps({"type": "join", "map_id": "bigmap"}))

            welcome_map = None
            got_lobby_welcome = False
            pos = None

            async def pump(reader_done: list):
                nonlocal welcome_map, got_lobby_welcome, pos
                async for msg in ws:
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        continue
                    f = json.loads(msg.data)
                    t = f.get("type")
                    if t == "welcome":
                        mid = f.get("map", {}).get("id", "?")
                        welcome_map = mid
                        if "lobbytrade" in str(mid):
                            got_lobby_welcome = True
                        print("[ws] welcome map:", mid)
                    elif t == "snapshot":
                        pos = f.get("self")
                        if f.get("map_id") and "monter" in str(f.get("map_id")):
                            print("[ws] SNAPSHOT MAP:", f.get("map_id"))
                            return True

            reader_flag: list = []
            pump_task = asyncio.create_task(pump(reader_flag))
            await asyncio.sleep(2.0)
            print("[test] welcome_map after join:", welcome_map)

            await ws.send_str(json.dumps({"type": "chat_cmd", "text": "/khutraodoi in"}))
            await asyncio.sleep(2.5)
            print("[test] got lobby welcome:", got_lobby_welcome, "welcome_map:", welcome_map)

            # Push UP into the door: dy=-1 with predicted report pinned at
            # the flush rest position (38.5, 26.3) — what the browser does.
            seq = 0
            for i in range(140):
                seq += 1
                await ws.send_str(json.dumps({
                    "type": "input", "dx": 0.0, "dy": -1.0,
                    "x": 38.5, "y": 26.3, "seq": seq,
                }))
                await asyncio.sleep(0.05)
                if pump_task.done():
                    break

            await pump_task
            print("[test] final self snapshot:", pos)
            ok = pump_task.done() and (not pump_task.exception())
            print("[test] RESULT:", "PASS — teleported into montertradebase" if ok else "FAIL — never left lobbytrade")
            return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
