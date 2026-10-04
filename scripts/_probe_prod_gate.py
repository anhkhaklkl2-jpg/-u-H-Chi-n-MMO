"""Probe production relay như client thật (docs/portal_sub_areas.md §7).

Kết nối wss://web-production-f53c5.up.railway.app/ws, login guest, join
scenario, /khutraodoi in, rồi đẩy vào cửa montertradebase bằng input frames
(client-authoritative: report từng bước nhỏ ~0.05 ô/frame). Kết quả mong đợi:
frame welcome MỚI với map montertradebase.
"""
import asyncio
import json
import random
import sys

import aiohttp

RELAY = "wss://web-production-f53c5.up.railway.app/ws"


async def main() -> int:
    guest_id = str(random.randint(900000000000000000, 999999999999999999))
    async with aiohttp.ClientSession() as http:
        async with http.ws_connect(RELAY, heartbeat=20) as ws:
            await ws.send_json({"type": "guest_login", "guest_id": guest_id})
            login = json.loads((await ws.receive()).data)
            print("[probe] login:", login.get("type"), "ok=", login.get("ok"))
            token = login.get("token")

            await ws.send_json({"type": "list"})
            ch = None
            while True:
                f = json.loads((await asyncio.wait_for(ws.receive(), 10)).data)
                if "channel" in json.dumps(f)[:200].lower() or f.get("type") in (
                    "scenario_list", "list_result",
                ):
                    print("[probe] list frame keys:", list(f.keys()))
                    items = f.get("scenarios") or f.get("channels") or f.get("items") or []
                    if items:
                        ch = items[0].get("channel_id") or items[0].get("id")
                    break
            if ch is None:
                print("[probe] FAIL: không lấy được channel_id từ list")
                return 1
            print("[probe] join channel:", ch)

            await ws.send_json({"type": "join", "token": token, "channel_id": str(ch)})
            welcome = json.loads((await asyncio.wait_for(ws.receive(), 15)).data)
            if welcome.get("type") != "welcome":
                print("[probe] FAIL: frame đầu sau join:", welcome.get("type"))
                return 1
            print("[probe] welcome map:", welcome["map"]["id"],
                  "| has input_seq:", "input_seq" in welcome,
                  "| self:", welcome["self"]["x"], welcome["self"]["y"])

            # vào chợ
            await ws.send_json({"type": "chat_cmd", "text": "/khutraodoi in"})
            welcome2 = None
            for _ in range(20):
                f = json.loads((await asyncio.wait_for(ws.receive(), 10)).data)
                if f.get("type") == "welcome":
                    welcome2 = f
                    break
            if welcome2 is None:
                print("[probe] FAIL: không nhận welcome lobbytrade")
                return 1
            print("[probe] welcome 2 map:", welcome2["map"]["id"],
                  "| self:", welcome2["self"]["x"], welcome2["self"]["y"])

            sx, sy = welcome2["self"]["x"], welcome2["self"]["y"]
            print(f"[probe] spawn lobby at ({sx},{sy}) — đi bộ tới cửa (38,26)...")

            # Walk: report từng bước nhỏ về phía cửa (38.5, 26.3) rồi đẩy lên.
            # Đi theo đường thẳng đơn giản (server tự lo collision khi converge).
            seq = welcome2.get("input_seq", 0)
            x, y = sx, sy

            async def walk_to(tx, ty, steps):
                nonlocal x, y, seq
                for _ in range(steps):
                    dx = tx - x
                    dy = ty - y
                    d = max(abs(dx), abs(dy))
                    if d < 0.02:
                        return True
                    step = 0.05
                    nx = x + max(-step, min(step, dx))
                    ny = y + max(-step, min(step, dy))
                    # Diagonal guard: chỉ trục xa hơn di chuyển (đơn giản hoá)
                    seq += 1
                    await ws.send_json({
                        "type": "input", "seq": seq,
                        "dx": (1 if dx > 0 else -1 if dx < 0 else 0),
                        "dy": (1 if dy > 0 else -1 if dy < 0 else 0),
                        "running": False,
                        "x": round(nx, 3), "y": round(ny, 3),
                    })
                    x, y = nx, ny
                    await asyncio.sleep(0.05)
                return False

            await walk_to(38.5, 26.3, 400)
            print(f"[probe] tới vị trí đẩy cửa: ({x:.2f},{y:.2f}) — giữ phái lên...")

            # Giữ đẩy lên 6s: report y nhỏ dần tới 26.29 rồi đứng
            teleport_seen = False
            for i in range(120):
                seq += 1
                ny = max(26.29, y - 0.01)
                await ws.send_json({
                    "type": "input", "seq": seq, "dx": 0, "dy": -1,
                    "running": False,
                    "x": round(x, 3), "y": round(ny, 3),
                })
                y = ny
                try:
                    while True:
                        f = json.loads((await asyncio.wait_for(ws.receive(), 0.06)).data)
                        if f.get("type") == "welcome":
                            print("[probe] *** WELCOME MỚI:", f["map"]["id"],
                                  "self:", f["self"]["x"], f["self"]["y"])
                            if "monter" in f["map"]["id"]:
                                teleport_seen = True
                                break
                except asyncio.TimeoutError:
                    pass
                if teleport_seen:
                    break
            print("[probe] RESULT:",
                  "PASS — teleport vào montertradebase OK" if teleport_seen
                  else "FAIL — server không tele (hoặc không nhận welcome)")
            return 0 if teleport_seen else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
