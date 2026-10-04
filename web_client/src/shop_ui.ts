// Shop UI — two styles ported from the approved demos:
//   Shop 1 (style "kaetram"): Kaetram store (slices, buy dialog Enter/Esc,
//     sell slot + gold preview + ✓ confirm; click the sell slot to cancel).
//   Shop 2 (style "rbcat"): Rainbow-cat shop_menu (panel + Mua/Bán tabs +
//     list/detail, SpinBox + Max + action button).
// All prices/stock/bag come from the server frame (server-authoritative, same
// rule as Kaetram's purchase()). The client only *previews* sell prices with
// Kaetram's own getTotalCost formula; the server re-sends shop_open after
// every buy/sell so the panel always converges to the truth.

import type { ShopOpenFrame } from "./net";
import { itemIconUrl } from "./pixel_ui";

export interface ShopApi {
  /** Server buy: index into frame.items. */
  buy(index: number, count: number): void;
  /** Server sell: item id + qty. */
  sell(itemId: string, qty: number): void;
  close(): void;
}

/* ---------- shared helpers ---------- */

function iconUrlOf(key: string): string {
  return itemIconUrl(key) ?? "";
}

/** Kaetram's linear decay (stores.ts getTotalCost): the fuller the shop's
 *  stock, the less it pays — 50% down to 20% of the price per unit. */
export function getTotalCost(count: number, price: number, storeCount = 0, limit = 10): number {
  if (storeCount > limit) return Math.floor(0.2 * price * count);
  let total = 0;
  let remaining = count;
  for (let i = 0; i < count; i++) {
    if (i > limit) break;
    total += ((50 - 3 * Math.min(storeCount + i, limit)) / 100) * price;
    remaining--;
  }
  total += 0.2 * price * remaining;
  return Math.floor(total);
}

/** Overlay root shared by both styles (fixed, above every game layer). */
function overlayRoot(): HTMLElement {
  const root = document.getElementById("shop-overlay");
  if (root) return root;
  const el = document.createElement("div");
  el.id = "shop-overlay";
  el.style.display = "none"; // no dim backdrop until a panel opens
  document.body.appendChild(el);
  return el;
}

const SHOP_CSS = `
#shop-overlay { position: fixed; inset: 0; z-index: 900; display: flex;
  align-items: center; justify-content: center; background: rgba(0,0,0,.45); }
#shop-overlay .kt-root { font-size: 18px; color: #eee; font-family: "Segoe UI", Tahoma, sans-serif; }
#shop-overlay .kt-slice-container {
  position: relative; display: flex; flex-direction: row; gap: .5em;
  box-sizing: border-box; width: 44em; height: 19em; padding: 1em;
  border-image: url("/ui/kaetram/interface/slices/container.png") 44% fill / 1em / 0 stretch; }
#shop-overlay .kt-slice-inner {
  overflow: hidden auto; flex: 1; box-sizing: border-box; padding: .75em;
  border-image: url("/ui/kaetram/interface/slices/inner-container.png") 42% fill / 2em / 0 stretch; }
#shop-overlay .kt-close {
  position: absolute; top: -.25em; right: -.25em; width: 22px; height: 22px; cursor: pointer;
  background-image: url("/ui/kaetram/interface/guilds/elements.png"); background-repeat: no-repeat;
  background-size: 640px 512px; background-position: -128px 0; }
#shop-overlay .kt-close:hover { background-position: -152px 0; }
#shop-overlay .kt-close:active { background-position: -176px 0; }
#shop-overlay .kt-store-content { display: flex; flex: 3; flex-direction: row; gap: .5em; height: 100%; width: 100%; }
#shop-overlay .kt-store-content.dimmed { filter: brightness(.6); }
#shop-overlay .kt-store-inventory { display: flex; flex-direction: column; gap: .5em; flex: 1.25; }
#shop-overlay .kt-store-inventory-slots { flex: 1; }
#shop-overlay .kt-store-inventory-slots ul {
  display: grid; grid-template-columns: repeat(5, 1fr); gap: .25em; margin: 0; padding: 0;
  list-style: none; height: 100%; }
#shop-overlay .kt-item-slot {
  box-sizing: border-box; width: 2.6em; height: 2.6em; padding: .5em;
  border-image: url("/ui/kaetram/interface/slices/item-slot.png") 44% fill / .5em / 0 stretch;
  position: relative; }
#shop-overlay .kt-item-slot .fill { width: 100%; height: 100%; background-size: 100% 100%; background-repeat: no-repeat; }
#shop-overlay .kt-item-slot .img-fill, #shop-overlay .kt-item-slot .glyph-fill {
  width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }
#shop-overlay .kt-item-slot .glyph-fill { font-size: 1em; color: #ddd; }
#shop-overlay .kt-inv-slot { cursor: pointer; }
#shop-overlay .kt-inv-slot:hover { filter: brightness(1.3); }
#shop-overlay .kt-inv-slot .item-count {
  position: absolute; right: .15em; bottom: 0; font-size: .62em; color: #fff;
  text-shadow: 1px 1px 0 #000; }
#shop-overlay .kt-store-sell { display: flex; flex-direction: row; align-items: center; justify-content: center; gap: .8em; padding: .2em 0; }
#shop-overlay .kt-sell-info { display: flex; flex-direction: column; gap: .15em; min-width: 5em; }
#shop-overlay .kt-sell-gain { display: flex; align-items: center; gap: .25em; color: #ffd76e; font-weight: bold; font-size: .85em; }
#shop-overlay .kt-coin { width: 14px; height: 14px; image-rendering: pixelated; }
#shop-overlay .kt-sell-slot { cursor: pointer; }
#shop-overlay .kt-sell-slot:hover { filter: brightness(1.35); }
#shop-overlay .kt-store-sell-text { height: 1em; font-size: .72em; color: #e6dcc0; }
#shop-overlay .kt-ok-check {
  width: 42px; height: 28px; cursor: pointer; flex: none;
  background-image: url("/ui/kaetram/interface/characterdialogsheet.png");
  background-repeat: no-repeat; background-size: 1240px 868px;
  background-position: 0 -616px; }
#shop-overlay .kt-ok-check:hover { background-position: -44px -616px; }
#shop-overlay .kt-ok-check:active { background-position: -88px -616px; }
#shop-overlay .kt-store-slots { display: flex; flex: 2; flex-direction: column; gap: .5em; }
#shop-overlay .kt-store-slots-content { flex: 1; }
#shop-overlay .kt-store-slots-content ul {
  display: flex; flex-direction: column; gap: .25em; margin: 0; padding: 0;
  list-style: none; height: 100%; }
#shop-overlay .kt-store-slots-content li {
  display: flex; flex-direction: row; flex-shrink: 0; gap: .6em; align-items: center;
  padding: .3em .5em; cursor: pointer;
  border-image: url("/ui/kaetram/interface/slices/list-item.png") 44% fill / .5em / 0 stretch; }
#shop-overlay .kt-store-slots-content li:hover { border-image-source: url("/ui/kaetram/interface/slices/list-item-hover.png"); }
#shop-overlay .kt-store-item-image { width: 2em; height: 2em; background-size: 100% 100%; background-repeat: no-repeat; flex: none; }
#shop-overlay .kt-store-item-name { flex: 3; font-size: .9em; white-space: nowrap; }
#shop-overlay .kt-store-item-count, #shop-overlay .kt-store-item-price { flex: 1; font-size: .9em; text-align: right; white-space: nowrap; }
#shop-overlay .kt-store-item-price { color: #ffd76e; }
#shop-overlay .kt-dialog {
  position: absolute; inset: 0; margin: auto; width: 13em; height: 7.5em;
  display: none; flex-direction: column; align-items: center; justify-content: center; gap: .3em;
  padding: .6em; color: #e3e3e3;
  border-image: url("/ui/kaetram/interface/slices/dialog.png") 44% fill / 1em / 0 stretch;
  background: rgba(0,0,0,.45); }
#shop-overlay .kt-dialog.show { display: flex; }
#shop-overlay .kt-dialog-title { font-size: .75em; }
#shop-overlay .kt-dialog input {
  width: 7.5em; margin: .25em; font-size: .75em; color: #fff;
  background-color: rgb(0 0 0 / 50%); border: 1px solid #666; padding: .2em; text-align: center; }
#shop-overlay .kt-dialog-buttons { display: flex; flex-direction: row; justify-content: space-evenly; width: 100%; }
#shop-overlay .kt-confirm {
  width: 42px; height: 28px; cursor: pointer;
  background-image: url("/ui/kaetram/interface/characterdialogsheet.png");
  background-repeat: no-repeat; background-size: 1240px 868px;
  background-position: 0 -616px; }
#shop-overlay .kt-confirm:hover { background-position: -44px -616px; }
#shop-overlay .kt-confirm:active { background-position: -88px -616px; }
#shop-overlay .kt-cancel {
  width: 22px; height: 22px; cursor: pointer;
  background-image: url("/ui/kaetram/interface/guilds/elements.png");
  background-repeat: no-repeat; background-size: 640px 512px;
  background-position: -128px 0; background-color: transparent; align-self: center; }
#shop-overlay .kt-cancel:hover { background-position: -152px 0; }
#shop-overlay .kt-cancel:active { background-position: -176px 0; }
#shop-overlay .kt-hint { font-size: .62em; color: #cbbf9e; text-align: center; }
#shop-overlay .shop-toast {
  position: fixed; left: 50%; bottom: 24px; transform: translateX(-50%);
  background: rgba(20,16,10,.94); border: 2px solid #ffbe5a; color: #ffe9b0;
  padding: 8px 16px; border-radius: 4px; font: 13px Tahoma; opacity: 0;
  transition: .2s; pointer-events: none; z-index: 950; }
`;

let cssInjected = false;
function ensureCss(): void {
  if (cssInjected) return;
  cssInjected = true;
  const style = document.createElement("style");
  style.textContent = SHOP_CSS;
  document.head.appendChild(style);
}

const overlay = {
  el: null as HTMLElement | null,
  toastEl: null as HTMLElement | null,
  toastTimer: 0 as unknown as ReturnType<typeof setTimeout>,
  open(frame: ShopOpenFrame, api: ShopApi): void {
    this.close();
    ensureCss();
    const root = overlayRoot();
    // Backdrop only while a panel is inside (an empty overlay would still
    // paint its dim rgba layer over the game).
    root.style.display = "flex";
    const toast = document.createElement("div");
    toast.className = "shop-toast";
    root.appendChild(toast);
    this.el = root;
    this.toastEl = toast;
    if (frame.style === "rbcat") buildRainbow(root, frame, api);
    else buildKaetram(root, frame, api);
  },
  toast(msg: string): void {
    const t = this.toastEl;
    if (!t) return;
    t.textContent = msg;
    t.style.opacity = "1";
    clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => { t.style.opacity = "0"; }, 1600);
  },
  close(): void {
    const root = document.getElementById("shop-overlay");
    if (root) {
      root.innerHTML = "";
      root.style.display = "none";
    }
    this.el = null;
    this.toastEl = null;
  },
};

/** Open the shop panel for a frame. Replaces any existing panel. */
export function openShop(frame: ShopOpenFrame, api: ShopApi): void {
  overlay.open(frame, api);
}

/** True while a shop panel is on screen (F/click gates in main.ts — a
 *  second F used to re-open the NPC dialogue OVER the shop: bug). */
export function isShopOpen(): boolean {
  return overlay.el !== null;
}

/** Close the shop panel (server push, map switch…). */
export function closeShop(): void {
  overlay.close();
}

/* ============================ SHOP 1 — KAETRAM ============================ */

interface KtState {
  frame: ShopOpenFrame;
  api: ShopApi;
  bag: [number, string, number][];   // server bag rows (mirror for sell)
  sellPreview: { key: string; count: number; coins: number; slot: number } | null;
  buyIndex: number;
}

const ktEsc = (s: string): string =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

function ktStoreItemOf(st: KtState, key: string) {
  return st.frame.items.find((s) => s.key === key) ?? null;
}

function ktSellPreviewCoins(st: KtState, key: string, count: number): number {
  const s = ktStoreItemOf(st, key);
  if (!s) return 0; // shop only buys items it stocks (Kaetram base rule)
  return getTotalCost(count, s.price, s.count < 0 ? 0 : s.count);
}

function buildKaetram(root: HTMLElement, frame: ShopOpenFrame, api: ShopApi): void {
  const st: KtState = { frame, api, bag: frame.bag.map((r) => [...r] as [number, string, number]),
    sellPreview: null, buyIndex: -1 };
  root.insertAdjacentHTML("beforeend", `
  <div class="kt-root">
    <div class="kt-slice-container" id="kt-store">
      <div class="kt-close" title="Đóng shop" id="kt-close"></div>
      <div class="kt-store-content" id="kt-content">
        <div class="kt-store-inventory">
          <div class="kt-slice-inner kt-store-inventory-slots"><ul id="kt-inv"></ul></div>
          <div class="kt-store-sell">
            <div class="kt-item-slot kt-sell-slot" id="kt-sell-slot" title="Bấm để hủy chọn bán"><div class="fill" id="kt-sell-fill"></div></div>
            <div class="kt-sell-info">
              <div class="kt-store-sell-text" id="kt-sell-text"></div>
              <div class="kt-sell-gain"><img src="${iconUrlOf("coin")}" class="kt-coin" draggable="false"> <span id="kt-gain"></span></div>
            </div>
            <div class="kt-ok-check" id="kt-sell-confirm" title="Bán (Sell)"></div>
          </div>
        </div>
        <div class="kt-store-slots">
          <div class="kt-slice-inner kt-store-slots-content"><ul id="kt-store-list"></ul></div>
        </div>
      </div>
      <div class="kt-dialog" id="kt-buy-dialog">
        <div class="kt-dialog-title">Input Buy Amount</div>
        <input id="kt-buy-count" type="number" min="1" step="1" value="1" size="6">
        <div class="kt-dialog-buttons">
          <div class="kt-confirm" id="kt-buy-accept" title="Mua (Enter)"></div>
          <div class="kt-cancel" id="kt-buy-cancel" title="Hủy (Esc)"></div>
        </div>
        <div class="kt-hint" id="kt-dialog-hint"></div>
      </div>
    </div>
  </div>`);
  const panel = root.querySelector<HTMLElement>(".kt-root")!;
  const invList = panel.querySelector<HTMLElement>("#kt-inv")!;
  const storeList = panel.querySelector<HTMLElement>("#kt-store-list")!;
  const buyDialog = panel.querySelector<HTMLElement>("#kt-buy-dialog")!;
  const buyCount = panel.querySelector<HTMLInputElement>("#kt-buy-count")!;

  const ITEM_SLOTS = 20;
  const bagAt = (i: number): [string, number] | null => {
    const row = st.bag.find((r) => r[0] === i);
    return row && row[2] > 0 ? [row[1], row[2]] : null;
  };
  const money = frame.currency === "coin" ? "x" : frame.currency[0];

  function renderInventory(): void {
    invList.innerHTML = "";
    for (let i = 0; i < ITEM_SLOTS; i++) {
      const li = document.createElement("li");
      const slot = document.createElement("div");
      slot.className = "kt-item-slot kt-inv-slot";
      const it = bagAt(i);
      if (it) {
        const [key, count] = it;
        const fill = document.createElement("div");
        fill.className = "fill";
        const url = iconUrlOf(key);
        if (url) {
          const img = document.createElement("img");
          img.className = "img-fill";
          img.src = url;
          img.draggable = false;
          fill.appendChild(img);
        } else {
          fill.innerHTML = `<div class="glyph-fill">${ktEsc((key[0] ?? "?").toUpperCase())}</div>`;
        }
        const cnt = document.createElement("div");
        cnt.className = "item-count";
        cnt.textContent = String(count);
        slot.appendChild(cnt);
        slot.title = `${ktEsc(key)} ×${count} — bấm để chọn bán`;
        slot.onclick = () => selectInventory(i);
        slot.prepend(fill);
      }
      li.appendChild(slot);
      invList.appendChild(li);
    }
  }

  function renderStore(): void {
    storeList.innerHTML = "";
    frame.items.forEach((s, i) => {
      const li = document.createElement("li");
      const icon = iconUrlOf(s.key);
      const iconHtml = icon
        ? `<div class="kt-store-item-image" style="background-image:url('${icon}')"></div>`
        : `<div class="kt-store-item-image">${ktEsc((s.key[0] ?? "?").toUpperCase())}</div>`;
      li.innerHTML = `${iconHtml}
        <div class="kt-store-item-name">${ktEsc(s.name || s.key)}</div>
        <div class="kt-store-item-count">${s.count === -1 ? "" : "x" + s.count}</div>
        <div class="kt-store-item-price">${s.price}${money}</div>`;
      li.title = `Mua ${ktEsc(s.name || s.key)} — ${s.price}${money}`;
      li.onclick = () => { st.buyIndex = i; showBuyDialog(); };
      storeList.appendChild(li);
    });
  }

  function renderSellSlots(): void {
    const fill = panel.querySelector<HTMLElement>("#kt-sell-fill")!;
    fill.innerHTML = "";
    if (st.sellPreview) {
      const url = iconUrlOf(st.sellPreview.key);
      if (url) {
        const img = document.createElement("img");
        img.className = "img-fill";
        img.src = url;
        img.draggable = false;
        fill.appendChild(img);
      } else {
        fill.innerHTML = `<div class="glyph-fill">${ktEsc((st.sellPreview.key[0] ?? "?").toUpperCase())}</div>`;
      }
    }
    panel.querySelector<HTMLElement>("#kt-sell-text")!.textContent =
      st.sellPreview ? `${ktEsc(st.sellPreview.key)} ×${st.sellPreview.count}` : "Chọn món trong túi…";
    panel.querySelector<HTMLElement>("#kt-gain")!.textContent =
      st.sellPreview ? `+${st.sellPreview.coins}${money}` : "+0";
  }

  function selectInventory(index: number): void {
    const it = bagAt(index);
    if (!it) return;
    const [key, count] = it;
    if (key === frame.currency) return overlay.toast("Không thể bán tiền tệ!");
    const coins = ktSellPreviewCoins(st, key, count);
    if (coins < 1) return overlay.toast("Shop này không mua món này.");
    st.sellPreview = { key, count, coins, slot: index };
    renderSellSlots();
    renderInventory();
    // Kaetram mirror: the picked item is hidden from the bag panel.
    const cell = invList.children[index]?.querySelector<HTMLElement>(".fill");
    if (cell) cell.innerHTML = "";
    const cnt = invList.children[index]?.querySelector<HTMLElement>(".item-count");
    if (cnt) cnt.textContent = "";
  }

  function clearSellSlot(): void {
    st.sellPreview = null;
    renderSellSlots();
    renderInventory();
  }

  panel.querySelector<HTMLElement>("#kt-sell-slot")!.onclick = () => {
    if (!st.sellPreview) return overlay.toast("Chọn món trong túi để bán");
    clearSellSlot();
    overlay.toast("Đã hủy chọn bán");
  };
  panel.querySelector<HTMLElement>("#kt-sell-confirm")!.onclick = () => {
    if (!st.sellPreview) return overlay.toast("Chọn món trong túi để bán");
    const { key, count } = st.sellPreview;
    api.sell(key, count);
    overlay.toast(`Đang bán ${count}× ${ktEsc(key)}…`);
    clearSellSlot();
  };
  panel.querySelector<HTMLElement>("#kt-close")!.onclick = () => api.close();

  function showBuyDialog(): void {
    buyDialog.classList.add("show");
    panel.querySelector<HTMLElement>("#kt-content")!.classList.add("dimmed");
    buyCount.value = "1";
    buyCount.focus();
    const s = frame.items[st.buyIndex];
    panel.querySelector<HTMLElement>("#kt-dialog-hint")!.textContent =
      s ? `${s.name || s.key} — ${s.price}${money}/cái${s.count === -1 ? " (vô hạn)" : " (còn " + s.count + ")"}` : "";
  }
  function hideBuyDialog(): void {
    buyDialog.classList.remove("show");
    panel.querySelector<HTMLElement>("#kt-content")!.classList.remove("dimmed");
  }
  panel.querySelector<HTMLElement>("#kt-buy-cancel")!.onclick = hideBuyDialog;
  panel.querySelector<HTMLElement>("#kt-buy-accept")!.onclick = () => {
    const s = frame.items[st.buyIndex];
    if (!s) return;
    let n = Math.max(1, parseInt(buyCount.value) || 1);
    if (s.count !== -1) n = Math.min(n, s.count);
    const total = s.price * n;
    if (total > frame.gold) return overlay.toast("Không đủ xu!");
    const free = st.bag.length < ITEM_SLOTS || st.bag.some((r) => r[1] === s.key);
    if (!free) return overlay.toast("Túi đầy!");
    hideBuyDialog();
    api.buy(st.buyIndex, n);
    overlay.toast(`Đang mua ${n}× ${ktEsc(s.name || s.key)} (−${total}${money})…`);
  };
  buyDialog.addEventListener("keydown", (e) => {
    if (e.key === "Enter") panel.querySelector<HTMLElement>("#kt-buy-accept")!.click();
    else if (e.key === "Escape") hideBuyDialog();
  });

  renderInventory();
  renderStore();
  renderSellSlots();
}

/* ========================= SHOP 2 — RAINBOW-CAT ========================= */

const RB_CSS = `
#shop-overlay .rb-root { color: rgba(237,228,209,1); font-size: 15px; }
#shop-overlay .rb-shell {
  border-radius: 8px; border: 1px solid rgba(107,153,199,.3);
  background: rgba(10,12,17,.93); padding: 14px 16px;
  display: flex; flex-direction: column; gap: 12px; width: 660px; }
#shop-overlay .rb-header { display: flex; align-items: center; gap: 10px; }
#shop-overlay .rb-title { font-size: 15px; font-weight: 600; }
#shop-overlay .rb-header-center { margin-left: auto; display: flex; gap: 6px; }
#shop-overlay .rb-tab {
  min-width: 104px; padding: 6px 10px; cursor: pointer; font: inherit; font-size: 13px;
  color: rgba(237,228,209,1); border-radius: 5px;
  border: 1px solid rgba(107,153,199,.6); background: rgba(10,12,17,.6); }
#shop-overlay .rb-tab:hover, #shop-overlay .rb-tab.on { border-color: rgba(148,209,250,.95); background: rgba(27,29,33,.92); }
#shop-overlay .rb-header-right { display: flex; align-items: center; gap: 6px; }
#shop-overlay .rb-gold-icon { width: 20px; height: 20px; image-rendering: pixelated; }
#shop-overlay .rb-golds { color: rgba(255,217,102,1); font-weight: 600; font-size: 13px; }
#shop-overlay .rb-close {
  width: 22px; height: 22px; border-radius: 5px; cursor: pointer; flex: none;
  border: 1px solid rgba(107,153,199,.6); background: rgba(10,12,17,.6);
  color: rgba(237,228,209,1); display: flex; align-items: center; justify-content: center; font-size: 13px; }
#shop-overlay .rb-close:hover { border-color: rgba(148,209,250,.95); }
#shop-overlay .rb-body { display: flex; gap: 14px; align-items: stretch; height: 400px; }
#shop-overlay .rb-list-panel {
  flex: 1.2; min-width: 0; border-radius: 8px; padding: 12px 14px;
  border: 1px solid rgba(107,153,199,.3); background: rgba(10,12,17,.93);
  display: flex; flex-direction: column; gap: 8px; }
#shop-overlay .rb-list-header { display: flex; gap: 8px; font-size: 12px; color: rgba(255,217,128,1); }
#shop-overlay .rb-list-header .h-items { flex: 1; padding-left: 38px; }
#shop-overlay .rb-list-header .h-stock { width: 72px; text-align: center; }
#shop-overlay .rb-list-header .h-price { width: 96px; text-align: right; }
#shop-overlay .rb-scroll { flex: 1; overflow: auto; display: flex; flex-direction: column; gap: 5px; min-height: 0; }
#shop-overlay .rb-scroll::-webkit-scrollbar { width: .5em; }
#shop-overlay .rb-scroll::-webkit-scrollbar-track { background: transparent; }
#shop-overlay .rb-scroll::-webkit-scrollbar-thumb { background-color: #3c4456; }
#shop-overlay .rb-scroll::-webkit-scrollbar-thumb:hover { background-color: #5a688a; }
#shop-overlay .rb-row {
  display: flex; align-items: center; gap: 10px; cursor: pointer; font-size: 13px;
  padding: 7px 10px; border-radius: 5px; min-height: 26px;
  border: 1px solid rgba(107,153,199,.6); background: rgba(10,12,17,.6); }
#shop-overlay .rb-row:hover, #shop-overlay .rb-row.sel { border-color: rgba(148,209,250,.95); background: rgba(27,29,33,.92); }
#shop-overlay .rb-row .r-icon { width: 28px; height: 28px; image-rendering: pixelated; flex: none; }
#shop-overlay .rb-row .r-name { flex: 1; white-space: nowrap; }
#shop-overlay .rb-row .r-stock { width: 72px; text-align: center; color: rgba(190,190,180,1); white-space: nowrap; }
#shop-overlay .rb-row .r-price { width: 96px; text-align: right; color: rgba(255,217,102,1); white-space: nowrap; }
#shop-overlay .rb-row .r-price.sell { color: rgba(160,224,140,1); }
#shop-overlay .rb-detail-panel {
  width: 250px; flex: none; box-sizing: border-box; border-radius: 8px; padding: 16px 14px;
  border: 1px solid rgba(107,153,199,.3); background: rgba(10,12,17,.93);
  display: flex; flex-direction: column; align-items: center; gap: 10px; }
#shop-overlay .rb-detail-icon { width: 72px; height: 72px; image-rendering: pixelated; margin: 4px 0; }
#shop-overlay .rb-detail-name { font-size: 15px; font-weight: 600; }
#shop-overlay .rb-detail-price { color: rgba(255,217,102,1); font-weight: 600; font-size: 13px; }
#shop-overlay .rb-detail-owned { font-size: 12px; color: rgba(190,190,180,1); }
#shop-overlay .rb-detail-desc { font-size: 13px; color: rgba(200,196,186,1); text-align: center; min-height: 36px; }
#shop-overlay .rb-qty-row { display: flex; align-items: center; gap: 10px; width: 100%; justify-content: space-between; box-sizing: border-box; }
#shop-overlay .rb-qty-label { font-size: 13px; color: rgba(210,204,192,1); }
#shop-overlay .rb-spinbox {
  width: 84px; padding: 5px 8px; font: inherit; font-size: 13px; text-align: right;
  color: rgba(237,228,209,1); border-radius: 5px;
  border: 1px solid rgba(107,153,199,.6); background: rgba(10,12,17,.6); }
#shop-overlay .rb-btn {
  padding: 7px 16px; cursor: pointer; font: inherit; font-size: 13px; border-radius: 5px;
  color: rgba(237,228,209,1); border: 1px solid rgba(107,153,199,.6); background: rgba(10,12,17,.6); }
#shop-overlay .rb-btn:hover { border-color: rgba(148,209,250,.95); }
#shop-overlay .rb-action { width: 100%; padding: 10px 0; font-weight: 600; font-size: 14px; box-sizing: border-box; }
#shop-overlay .rb-action:disabled { opacity: .45; cursor: not-allowed; }
`;

interface RbRow {
  key: string; name: string; price: number; stock: string; sell: boolean; have: number;
}

function buildRainbow(root: HTMLElement, frame: ShopOpenFrame, api: ShopApi): void {
  const css = document.createElement("style");
  css.textContent = RB_CSS;
  document.head.appendChild(css);

  root.insertAdjacentHTML("beforeend", `
  <div class="rb-root">
    <div class="rb-shell">
      <div class="rb-header">
        <div class="rb-title">Shop</div>
        <div class="rb-header-center">
          <button class="rb-tab on" id="rb-buy-tab">Mua</button>
          <button class="rb-tab" id="rb-sell-tab">Bán</button>
        </div>
        <div class="rb-header-right">
          <img class="rb-gold-icon" src="${iconUrlOf("coin")}" draggable="false">
          <span class="rb-golds" id="rb-golds">${frame.gold}</span>
          <div class="rb-close" id="rb-close">✕</div>
        </div>
      </div>
      <div class="rb-body">
        <div class="rb-list-panel">
          <div class="rb-list-header">
            <span class="h-items">Items</span><span class="h-stock">Stock</span><span class="h-price">Price</span>
          </div>
          <div class="rb-scroll" id="rb-list"></div>
        </div>
        <div class="rb-detail-panel">
          <img class="rb-detail-icon" id="rb-icon" draggable="false">
          <div class="rb-detail-name" id="rb-name"></div>
          <div class="rb-detail-price" id="rb-price"></div>
          <div class="rb-detail-owned" id="rb-owned"></div>
          <div class="rb-detail-desc" id="rb-desc"></div>
          <div class="rb-qty-row">
            <span class="rb-qty-label">Số lượng</span>
            <input class="rb-spinbox" id="rb-qty" type="number" min="1" value="1">
            <button class="rb-btn" id="rb-max">Max</button>
          </div>
          <button class="rb-btn rb-action" id="rb-action">Mua</button>
        </div>
      </div>
    </div>
  </div>`);
  const panel = root.querySelector<HTMLElement>(".rb-root")!;
  const rbList = panel.querySelector<HTMLElement>("#rb-list")!;
  const rbQty = panel.querySelector<HTMLInputElement>("#rb-qty")!;
  const rbAction = panel.querySelector<HTMLButtonElement>("#rb-action")!;

  let tab: "buy" | "sell" = "buy";
  let sel = 0;

  const nameOf = (key: string): string =>
    frame.items.find((s) => s.key === key)?.name ?? key;

  function rows(): RbRow[] {
    if (tab === "buy") {
      return frame.items.filter((s) => s.count !== 0).map((s) => ({
        key: s.key, name: s.name || s.key, price: s.price,
        stock: s.count === -1 ? "∞" : "x" + s.count, sell: false,
        have: frame.bag.filter((b) => b[1] === s.key).reduce((a, b) => a + b[2], 0),
      }));
    }
    return frame.bag
      .filter((b) => b[2] > 0 && b[1] !== frame.currency && ktStoreItemOfRaw(b[1]))
      .map((b) => ({
        key: b[1], name: nameOf(b[1]),
        price: getTotalCost(b[2], ktStoreItemOfRaw(b[1])!.price,
          ktStoreItemOfRaw(b[1])!.count < 0 ? 0 : ktStoreItemOfRaw(b[1])!.count),
        stock: "×" + b[2], sell: true, have: b[2],
      }));
  }
  function ktStoreItemOfRaw(key: string) {
    return frame.items.find((s) => s.key === key) ?? null;
  }

  function render(): void {
    const list = rows();
    if (sel >= list.length) sel = Math.max(0, list.length - 1);
    rbList.innerHTML = "";
    list.forEach((it, i) => {
      const row = document.createElement("div");
      row.className = "rb-row" + (i === sel ? " sel" : "");
      const url = iconUrlOf(it.key);
      const iconHtml = url
        ? `<img class="r-icon" src="${url}" draggable="false">`
        : `<div class="r-icon">${ktEsc((it.key[0] ?? "?").toUpperCase())}</div>`;
      row.innerHTML = `${iconHtml}
        <span class="r-name">${ktEsc(it.name)}</span>
        <span class="r-stock">${it.stock}</span>
        <span class="r-price${it.sell ? " sell" : ""}">${it.price}</span>`;
      row.onclick = () => { sel = i; rbQty.value = "1"; render(); };
      rbList.appendChild(row);
    });
    panel.querySelector<HTMLElement>("#rb-golds")!.textContent = String(frame.gold);
    const it = list[sel];
    if (!it) return;
    const iconEl = panel.querySelector<HTMLImageElement>("#rb-icon")!;
    const url = iconUrlOf(it.key);
    if (url) { iconEl.src = url; iconEl.style.display = ""; }
    else iconEl.style.display = "none";
    panel.querySelector<HTMLElement>("#rb-name")!.textContent = it.name;
    panel.querySelector<HTMLElement>("#rb-price")!.textContent =
      (it.sell ? "Bán: " : "Giá: ") + it.price + " xu";
    panel.querySelector<HTMLElement>("#rb-owned")!.textContent =
      it.sell ? "Trong túi: " + it.have : "Đang có: " + it.have;
    panel.querySelector<HTMLElement>("#rb-desc")!.textContent = "";
    const total = it.price * Math.max(1, parseInt(rbQty.value) || 1);
    rbAction.textContent = it.sell ? `Bán (+${total} xu)` : `Mua (${total} xu)`;
    rbAction.disabled = !it.sell && total > frame.gold;
  }

  panel.querySelector<HTMLElement>("#rb-buy-tab")!.onclick = () => {
    tab = "buy"; sel = 0;
    panel.querySelector<HTMLElement>("#rb-buy-tab")!.classList.add("on");
    panel.querySelector<HTMLElement>("#rb-sell-tab")!.classList.remove("on");
    rbQty.value = "1"; render();
  };
  panel.querySelector<HTMLElement>("#rb-sell-tab")!.onclick = () => {
    tab = "sell"; sel = 0;
    panel.querySelector<HTMLElement>("#rb-sell-tab")!.classList.add("on");
    panel.querySelector<HTMLElement>("#rb-buy-tab")!.classList.remove("on");
    rbQty.value = "1"; render();
  };
  panel.querySelector<HTMLElement>("#rb-max")!.onclick = () => {
    const it = rows()[sel];
    if (it) rbQty.value = tab === "sell" ? String(it.have) : "99";
    render();
  };
  rbQty.oninput = render;
  rbAction.onclick = () => {
    const it = rows()[sel];
    if (!it) return;
    const n = Math.max(1, parseInt(rbQty.value) || 1);
    if (it.sell) {
      api.sell(it.key, n);
      overlay.toast(`Đang bán ${n}× ${ktEsc(it.name)}…`);
    } else {
      const total = it.price * n;
      if (total > frame.gold) return overlay.toast("Không đủ xu!");
      api.buy(frame.items.findIndex((s) => s.key === it.key), n);
      overlay.toast(`Đang mua ${n}× ${ktEsc(it.name)} (−${total} xu)…`);
    }
  };
  panel.querySelector<HTMLElement>("#rb-close")!.onclick = () => api.close();

  render();
}
