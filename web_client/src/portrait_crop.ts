// ---- Portrait crop config (user 08/10: tool tự kéo zoom + vị trí) --------
// The character-panel portrait generator (game.ts characterPortraitSrc)
// reads these values. The preview panel's 🖼️ Avatar tuning tool mutates +
// persists them (localStorage), so hand-tuned framing survives reloads.
//   side — crop square as a fraction of the base frame width (zoom:
//          smaller = closer on the face, bigger = wider framing; values
//          > 1 show the background around the doll).
//   ox   — horizontal offset of the crop centre in KIT px (drag).
//   oy   — vertical offset in KIT px (drag; negative = up).
export const portraitCrop = { side: 0.56, ox: 0, oy: 8 };

// BAKED DEFAULTS (user 08/10 calibration: {"side":0.56,"ox":0,"oy":8} —
// hand-tuned via the temporary 🖼️ Avatar căn tool, then removed).
// One-time cleanup of the tuning tool's localStorage key so the baked
// defaults are the single source of truth.
try { localStorage.removeItem("portrait-crop"); } catch { /* ignore */ }

const LS_KEY = "portrait-crop";

let loaded = false;

/** Restore the hand-tuned crop ONCE (user 08/10 bug: loading on every read
 *  clobbered the in-memory crop with the stale localStorage value mid-drag,
 *  before the pointerup save could land — every drag reset itself). */
export function loadPortraitCrop(): void {
  if (loaded) return;
  loaded = true;
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return;
    const saved = JSON.parse(raw) as Partial<typeof portraitCrop>;
    if (typeof saved.side === "number") portraitCrop.side = saved.side;
    if (typeof saved.ox === "number") portraitCrop.ox = saved.ox;
    if (typeof saved.oy === "number") portraitCrop.oy = saved.oy;
  } catch { /* corrupted storage — keep defaults */ }
}

/** Persist the current crop after every tool change. */
export function savePortraitCrop(): void {
  try { localStorage.setItem(LS_KEY, JSON.stringify(portraitCrop)); } catch { /* ignore */ }
}
