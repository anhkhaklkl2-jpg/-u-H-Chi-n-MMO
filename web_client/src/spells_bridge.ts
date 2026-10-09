// ---- Web spells bridge ---------------------------------------------------
// The cast closure lives with the scene/net/hud references in main.ts; this
// tiny bridge lets ui.ts (spell card clicks + R key) and the Tab radial menu
// fire the SAME cast code path (one hook, one toast language).
let castHook: ((spellId: string) => void) | null = null;
let toastFn: ((msg: string) => void) | null = null;

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
