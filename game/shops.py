"""Data-driven NPC shops (web client).

Format mirrors Kaetram's ``stores.json`` (assets/maps/<map>.shops.json):

    {
      "gac_dac": {
        "currency": "coin",
        "items": [
          {"key": "apple", "price": 12, "count": -1},
          {"key": "knife", "price": 500, "count": 1}
        ]
      }
    }

``count == -1`` means INFINITE stock (no number shown on the row). A positive
``count`` is the current stock: buying decrements it, selling adds it back.

Prices are server-authoritative: the client only ever *displays* them, so a
tampered client cannot buy cheaper (same rule as Kaetram's ``purchase``).
"""
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class ShopItem:
    key: str
    price: int
    count: int = -1          # -1 = infinite stock
    max_count: int = -1      # restock ceiling for finite items

    @property
    def infinite(self) -> bool:
        return self.count < 0


@dataclass
class Shop:
    key: str
    currency: str = "coin"
    items: List[ShopItem] = field(default_factory=list)

    def index_of(self, item_id: str) -> int:
        for i, it in enumerate(self.items):
            if it.key == item_id:
                return i
        return -1


def load_shops(map_id: str, assets_dir: Path) -> Dict[str, Shop]:
    """Every shop declared for this map (empty dict when the map has none)."""
    path = assets_dir / f"{map_id}.shops.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    out: Dict[str, Shop] = {}
    for key, raw in data.items():
        items: List[ShopItem] = []
        for row in raw.get("items", []):
            iid = row.get("key")
            if not iid:
                continue
            count = int(row.get("count", -1))
            items.append(ShopItem(
                key=iid,
                price=int(row.get("price", 1)),
                count=count,
                max_count=count if count > 0 else -1,
            ))
        out[key] = Shop(key=key, currency=raw.get("currency", "coin"),
                        items=items)
    return out


def shop_of(shops: Dict[str, Shop], key: str) -> Optional[Shop]:
    return shops.get(key) if key else None


def roll_session_stock(shop: Shop, cfg: dict, rng: random.Random) -> None:
    """Terraria-style per-session stock roll for a SESSION MERCHANT.

    Replaces the shop's item list with a random draw of ``min_items``-
    ``max_items`` entries from the FULL declared list (prices from the json;
    finite stock becomes 1-3 units like Stardew's rare 1-or-5 carts).
    Called at session start (game/manager tick) keyed by session_id so ALL
    players in the world share one market per session."""
    import random as _random

    full = getattr(shop, "_full_items", None)
    if full is None:
        full = list(shop.items)
        shop._full_items = full  # keep the declared pool for future rolls
    if not full:
        return
    lo = int(cfg.get("min_items", 4))
    hi = max(lo, int(cfg.get("max_items", 6)))
    n = _random.randint(lo, hi)
    picked = _random.sample(full, min(n, len(full)))
    out: List[ShopItem] = []
    for src in picked:
        it = ShopItem(key=src.key, price=src.price, count=src.count,
                      max_count=src.max_count)
        if not it.infinite:
            it.count = _random.randint(1, 3)
            it.max_count = it.count
        out.append(it)
    shop.items = out


def buy(shop: Shop, index: int, count: int, inventory, coins: int,
        item_name=None) -> Tuple[bool, str, int, int]:
    """Purchase ``count`` of ``shop.items[index]``.

    Returns ``(ok, message, new_coins, spent)``. The caller applies the
    inventory add + persistence — this function only validates and prices.
    """
    if index < 0 or index >= len(shop.items):
        return False, "Món không tồn tại.", coins, 0
    item = shop.items[index]
    count = max(1, int(count))
    if not item.infinite:
        if item.count < 1:
            return False, "Món đã hết hàng.", coins, 0
        count = min(count, item.count)
    total = item.price * count
    if total > coins:
        return False, "Không đủ xu.", coins, 0
    # Bag space: a stack of the same item can absorb it, else a free cell.
    can_merge = any(s and s[0] == item.key for s in inventory.slots)
    if not can_merge and inventory.first_free_slot() < 0:
        return False, "Túi đã đầy.", coins, 0
    return True, f"Mua {count}x {item_name or item.key} (-{total} xu)", coins - total, total


def sell_price(shop: Shop, item_id: str, count: int, base_price: int) -> int:
    """Kaetram's linear decay: the more the shop already holds, the less it
    pays (50% down to 20% of the price). ``base_price`` is the shop price when
    the item is stocked, else the item's own value."""
    store_item = next((i for i in shop.items if i.key == item_id), None)
    price = store_item.price if store_item else base_price
    store_count = 0 if (store_item is None or store_item.infinite) else store_item.count
    limit = 10
    if store_count > limit:
        return max(1, int(0.2 * price * count))
    total = 0.0
    remaining = count
    for i in range(count):
        if i > limit:
            break
        total += ((50 - 3 * min(store_count + i, limit)) / 100) * price
        remaining -= 1
    total += 0.2 * price * remaining
    return max(1, int(total))


def sell(shop: Shop, inventory, item_id: str, qty: int,
         base_price: int) -> Tuple[bool, str, int]:
    """Sell ``qty`` of ``item_id``. Returns ``(ok, message, gained_coins)``."""
    if item_id == shop.currency:
        return False, "Không thể bán tiền tệ.", 0
    qty = max(1, int(qty))
    have = inventory.count(item_id)
    if have < 1:
        return False, "Bạn không có món này.", 0
    qty = min(qty, have)
    gained = sell_price(shop, item_id, qty, base_price)
    # The shop takes the goods into stock (finite shops only).
    store_item = next((i for i in shop.items if i.key == item_id), None)
    if store_item is not None and not store_item.infinite:
        store_item.count = min(
            store_item.max_count if store_item.max_count > 0 else store_item.count + qty,
            store_item.count + qty,
        )
    return True, f"Bán {qty}x {item_id} (+{gained} xu)", gained


def payload(shop: Shop, inventory, coins: int, name_of=None) -> dict:
    """The ``shop_open`` frame: stock + the player's bag (sell tab)."""
    return {
        "type": "shop_open",
        "key": shop.key,
        "currency": shop.currency,
        "gold": int(coins),
        "items": [
            {
                "key": it.key,
                "name": name_of(it.key) if name_of else it.key,
                "count": it.count,
                "price": it.price,
            }
            for it in shop.items
        ],
        # Bag rows for the sell tab: [slot, item_id, qty]
        "bag": [[slot, iid, qty] for slot, iid, qty in inventory.stacks()],
    }
