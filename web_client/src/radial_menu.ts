// ---- Radial quick-menu (Kando-style), kit v5 "Circle_menu" assets ---------
// Hold TAB (desktop) / long-press hotbar (mobile): the menu BLOOMS at the
// CENTER of the screen — hub stroke zooms out from nothing, the ring slots
// fly outward along their radial angle with a stagger, and a faint thin
// "selection ring" (the kit's 1px white stroke) snaps onto the wedge the
// pointer is in. Release → the highlighted slot fires; no drag → menu
// retracts (reverse bloom).
//
// Asset rules honoured (panels/Circle_menu.json):
//  - slots are INDEPENDENT atoms cropped from the 003_frames state strip
//    (normal / hover / active / disabled), never the composite atlas;
//  - the 1px white hub stroke (004) is the hover/selection ring, drawn at
//    the highlighted slot, NON-interactive;
//  - uniform ×3 kit scale (PIXEL_SCALE), nearest-neighbor (crisp), panel-
//    local geometry only.
//
// 8 wedges fixed like the kit's 16-slot ring layout uses the upper 10 ring
// positions; we expose 8 directions (N, NE, E, SE, S, SW, W, NW).

import { itemIconUrl } from "./pixel_ui";

const KIT = "ui/v6/radial";
const SCALE = 3;                 // kit uniform scale (25x26 -> 75x78 on screen)
const RING_RADIUS = 100;         // kit px from center to slot center
const N_WEDGES = 8;
const OPEN_MS = 190;             // bloom duration
const STAGGER_MS = 18;           // per-slot delay
const DEAD_ZONE = 14;            // screen px before a wedge locks

export interface RadialAction {
  id: string;            // action/item id
  label: string;
  iconUrl?: string | null;
  onFire: () => void;
}

interface Wedge {
  el: HTMLDivElement;
  slotImg: HTMLImageElement;
  ringImg: HTMLImageElement;
  iconImg: HTMLImageElement;
  angle: number;         // radians, -PI..PI (0 = East, like atan2 screen coords)
  cx: number; cy: number;// slot center offset from menu center (screen px)
  action: RadialAction | null;
  highlighted: boolean;
}

let root: HTMLDivElement | null = null;
let hubEl: HTMLDivElement | null = null;
let wedges: Wedge[] = [];
let openState: "closed" | "opening" | "open" = "closed";
let curIdx = -1;
let fireCallback: ((a: RadialAction | null) => void) | null = null;

function ensureRoot(): void {
  if (root) return;
  root = document.createElement("div");
  root.id = "radial-menu";
  root.classList.add("hidden");
  document.getElementById("overlay")?.appendChild(root);
}

function angleOfIndex(i: number): number {
  // Wedge 0 = North (up), then clockwise: NE, E, SE, S, SW, W, NW.
  return -Math.PI / 2 + (i * 2 * Math.PI) / N_WEDGES;
}

function idxFromPointer(dx: number, dy: number): number {
  if (Math.hypot(dx, dy) < DEAD_ZONE) return -1;
  // screen coords: y down; convert to math angle then to wedge
  const ang = Math.atan2(dy, dx); // -PI..PI, 0 = East, PI/2 = South(screen)
  // map: North = -PI/2. wedge step = PI/4.
  let deg = (ang * 180) / Math.PI;           // -180..180
  deg += 90;                                  // North = 0
  if (deg < 0) deg += 360;
  return Math.round(deg / (360 / N_WEDGES)) % N_WEDGES;
}

export function isRadialOpen(): boolean {
  return openState !== "closed";
}

/** Begin the hold: bloom the menu at screen center. */
export function radialOpen(actions: RadialAction[], onRelease: (a: RadialAction | null) => void): void {
  if (openState !== "closed") return;
  if (!actions.length) return;
  ensureRoot();
  fireCallback = onRelease;
  const vw = window.innerWidth, vh = window.innerHeight;
  const cx = Math.round(vw / 2), cy = Math.round(vh / 2);

  root!.innerHTML = "";
  root!.classList.remove("hidden");

  // Center hub: the thin stroke ring, zooming out from tiny.
  hubEl = document.createElement("div");
  hubEl.className = "rm-hub";
  const hubImg = document.createElement("img");
  hubImg.src = `${KIT}/hub_stroke.png`;
  hubImg.draggable = false;
  hubEl.appendChild(hubImg);
  root!.appendChild(hubEl);

  wedges = [];
  for (let i = 0; i < N_WEDGES; i++) {
    const a = actions[i % actions.length];
    const ang = angleOfIndex(i);
    const sx = Math.cos(ang) * (RING_RADIUS * SCALE);
    const sy = Math.sin(ang) * (RING_RADIUS * SCALE);
    const el = document.createElement("div");
    el.className = "rm-slot";
    el.style.setProperty("--rm-dx", `${sx}px`);
    el.style.setProperty("--rm-dy", `${sy}px`);
    el.style.setProperty("--rm-delay", `${i * STAGGER_MS}ms`);

    const slotImg = document.createElement("img");
    slotImg.className = "rm-slot-bg";
    slotImg.src = `${KIT}/slot_normal.png`;
    slotImg.draggable = false;

    const iconImg = document.createElement("img");
    iconImg.className = "rm-icon";
    iconImg.draggable = false;
    const url = a.iconUrl ?? itemIconUrl(a.id);
    if (url) iconImg.src = url;

    const ringImg = document.createElement("img");
    ringImg.className = "rm-ring";
    ringImg.src = `${KIT}/hub_stroke.png`;
    ringImg.draggable = false;
    ringImg.style.display = "none";

    el.appendChild(slotImg);
    el.appendChild(iconImg);
    el.appendChild(ringImg);
    root!.appendChild(el);
    wedges.push({ el, slotImg, ringImg, iconImg, angle: ang, cx: sx, cy: sy, action: a, highlighted: false });
  }

  // Position the whole root at screen center.
  root!.style.setProperty("--rm-cx", `${cx}px`);
  root!.style.setProperty("--rm-cy", `${cy}px`);
  curIdx = -1;
  openState = "opening";
  requestAnimationFrame(() => {
    root?.classList.add("rm-open");
    setTimeout(() => { if (openState === "opening") openState = "open"; }, OPEN_MS + N_WEDGES * STAGGER_MS);
  });
}

/** Pointer moved while holding — highlight the wedge under the drag. */
export function radialDrag(dx: number, dy: number): void {
  if (openState !== "open" && openState !== "opening") return;
  const idx = idxFromPointer(dx, dy);
  if (idx === curIdx) return;
  curIdx = idx;
  wedges.forEach((w, i) => {
    const hot = i === idx;
    if (hot === w.highlighted) return;
    w.highlighted = hot;
    w.slotImg.src = `${KIT}/${hot ? "slot_hover" : "slot_normal"}.png`;
    w.el.classList.toggle("rm-hot", hot);
    w.ringImg.style.display = hot ? "block" : "none";
  });
}

/** Release → fire the highlighted action and retract. */
export function radialRelease(): void {
  if (openState === "closed") return;
  const fired = curIdx >= 0 ? wedges[curIdx]?.action ?? null : null;
  const cb = fireCallback;
  closeRadial();
  cb?.(fired);
}

export function closeRadial(): void {
  if (!root || openState === "closed") return;
  openState = "closed";
  root.classList.remove("rm-open");
  const r = root;
  setTimeout(() => { r.classList.add("hidden"); r.innerHTML = ""; }, 140);
  wedges = [];
  curIdx = -1;
  fireCallback = null;
}
