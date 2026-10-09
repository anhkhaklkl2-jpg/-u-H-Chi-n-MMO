// ---- Web spells bridge ---------------------------------------------------
// The cast closure lives with the scene/net/hud references in main.ts; this
// tiny bridge lets ui.ts (spell card clicks + R key), the Tab radial menu
// and the WAND aim-cast fire the SAME cast code path (one hook, one toast
// language), plus the per-wand BIND storage (which spell a held wand fires).
let castHook: ((spellId: string) => void) | null = null;
let toastFn: ((msg: string) => void) | null = null;

/** Bound spell per wand (v2 scope: one global binding — the wand holds
 *  ONE attuned spell; re-pick via the radial to re-attune). */
let boundSpellId: string | null = null;

export function castSpellAtNearest(
  hook: (spellId: string) => { toast: string } | null,
  toast: (msg: string) => void,
): void {
  castHook = (spellId: string) => {
    const res = hook(spellId);
    if (res?.toast) toast(res.toast);
  };
  toastFn = toast;
}

export function getSpellCastHook(): ((spellId: string) => void) | null {
  return castHook;
}

export function getSpellToast(): ((msg: string) => void) | null {
  return toastFn;
}

/** Radial release while holding the wand: ATTUNE (bind), not cast. */
export function bindWandSpell(spellId: string): void {
  boundSpellId = spellId;
}

export function getBoundSpell(): string | null {
  return boundSpellId;
}
