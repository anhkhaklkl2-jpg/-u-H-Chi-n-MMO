// ---- Character panel (UI kit v5 "character_panel", user 06/10) -----------
// Replaces the plain CSS #hud-topright HP/mana/stamina bars with the kit's
// REAL panel art, rendered as DOM pixel-art scaled ×3 (same scale the
// inventory/craft panels use) so every art pixel stays crisp.
//
// Panel geometry (psd_layers/character_panel, frame-local, kit px):
//   frame  [0,0] 59x19     (003_frame)
//   face   [-21,-1] 22x22  (004_face) — overflow LEFT of the frame (kit rule:
//                          "negative local coordinates are meaningful")
//   border [-25,-5] 30x30  (007_border) — decorative ring around the face
//   bar track [3,3] 52x12  (005_bar) — THREE bands sliced at export time:
//       hp      rows 0..1  (red)   -> panel-local y=3
//       mana    rows 5..6  (blue)  -> panel-local y=8
//       stamina rows 10..11 (green) -> panel-local y=13
//   bar fill  [3,3] 8x12   (006_bar_element) — same 3 bands, sliced the same
//                          way; width scaled to the value ratio (max 52px).
//
// Render contract (panels/character_panel.json): frame first, z order,
// preserve alpha, pixel_art_scaling=nearest, child_geometry = local_bbox
// verbatim, uniform panel scale only. All honoured: children keep raw kit-px
// geometry inside .cp-scale, which is transform-scaled ×3 as ONE unit.
const KIT = "ui/v6/character";

type BarKey = "hp" | "mana" | "stamina";

export class CharacterPanel {
  /** Root element (positioned by CSS #char-panel). */
  readonly root: HTMLDivElement;
  private faceImg: HTMLImageElement;
  private fills: Record<BarKey, HTMLImageElement> = {} as never;
  private labels: Record<BarKey, HTMLSpanElement> = {} as never;
  /** Face src cache: avoid re-setting the same Discord CDN url every call. */
  private faceSrc: string | null = null;

  constructor() {
    // Outer sizer reserves layout space (59x3 x 19x3 screen px); .cp-scale
    // holds children in RAW kit px and is scaled ×3 with a top-right origin
    // (the panel hugs the screen's top-right corner and its face overflows
    // to the LEFT, exactly like the kit preview).
    const root = document.createElement("div");
    root.id = "char-panel";
    const scale = document.createElement("div");
    scale.className = "cp-scale";
    root.appendChild(scale);
    const el = (cls: string, css: string): HTMLImageElement => {
      const img = document.createElement("img");
      img.className = `cp-img ${cls}`.trim();
      img.alt = "";
      img.draggable = false;
      img.style.cssText = css;
      scale.appendChild(img);
      return img;
    };

    // --- overflow children BEHIND the frame (border ring; the kit preview
    // draws the ring under the face; both overflow left) ---
    el("", `left:-25px;top:-5px;width:30px;height:30px;`).src = `${KIT}/border.png`;

    // --- face (portrait), also overflowing left. SOFT HALO (user 08/10:
    // "hào quang ở chỗ avatar, không phải model") lives HERE as a CSS glow
    // on the circular face — default ON, toggle via setHalo. Starts EMPTY
    // (user 09/10: no static kit placeholder on login) — setFace fills it,
    // clearFace empties it back to a blank dark ring. ---
    this.faceImg = el("cp-face cp-halo", `left:-21px;top:-1px;width:22px;height:22px;`);

    // --- frame on top of the overflow art ---
    el("", `left:0;top:0;width:59px;height:19px;`).src = `${KIT}/frame.png`;

    // --- 3 bars: track + fill, per sliced band geometry. Each band is
    // TRIMMED to its real opaque pixels at export time — the kit's bar
    // element sheet draws mana (43px, x=2) and stamina (38px, x=1) SHORTER
    // than HP (52px, x=0), so every bar keeps its own offset+length (user
    // 06/10: bars rendered at 52px looked over-long).
    const bands: Array<{ key: BarKey; y: number; x: number; w: number; h: number }> = [
      { key: "hp", y: 3, x: 3, w: 52, h: 2 },
      { key: "mana", y: 8, x: 5, w: 43, h: 2 },
      { key: "stamina", y: 13, x: 4, w: 38, h: 2 },
    ];
    for (const b of bands) {
      el("", `left:${b.x}px;top:${b.y}px;width:${b.w}px;height:${b.h}px;`).src = `${KIT}/track_${b.key}.png`;
      this.fills[b.key] = el("cp-fill", `left:${b.x}px;top:${b.y}px;width:${b.w}px;height:${b.h}px;`);
      this.fills[b.key].src = `${KIT}/fill_${b.key}.png`;
      // Remember the geometry so width-only resizing never re-derives it.
      this.fills[b.key].dataset.h = String(b.h);
      this.fills[b.key].dataset.w = String(b.w);
      // Labels ("cur/max") are DISABLED (user 06/10: hub mới không cần số).
      // Elements stay in the DOM but render nothing; the CSS keeps them off.
      const label = document.createElement("span");
      label.className = "cp-label";
      label.style.cssText = `left:${b.x}px;top:${b.y}px;width:${b.w}px;height:${b.h}px;`;
      label.style.display = "none";
      this.labels[b.key] = label;
      scale.appendChild(label);
    }

    this.root = root;
  }

  /** Wire into the HUD: called once from the Hud ctor (mounts into #overlay). */
  mount(parent: HTMLElement): void {
    parent.appendChild(this.root);
  }

  /** Discord/web avatar into the portrait ring. Empty/null = blank ring
   *  (user 09/10: the static kit face must NOT appear — login/lobby shows
   *  an empty avatar slot). */
  setFace(url: string | null): void {
    const src = url || "";
    if (src === this.faceSrc) return;
    this.faceSrc = src;
    if (src) {
      this.faceImg.src = src;
    } else {
      this.faceImg.removeAttribute("src");
    }
  }

  /** Empty the portrait ring (login/lobby — no placeholder art). */
  clearFace(): void {
    this.setFace(null);
  }

  /** Toggle the avatar's soft glow rim (default ON). */
  setHalo(on: boolean): void {
    this.faceImg.classList.toggle("cp-halo", on);
  }

  /** Live values. Ratios are clamped. IMPACT FX (user 07/10 + 08/10 refinement):
   *  - HP only: panel shake + white blink, intensity SCALED by how much was
   *    lost (small dip = wink; big hit = heavy shake). Rise = heal pulse.
   *  - Mana/stamina: their OWN subtler FX (no shake): mana = cool blue-white
   *    wink, stamina = soft green pulse. Everything lives on filter/transform
   *    only — kit geometry untouched. Noise floor 5% of max. */
  setBars(hp: number, maxHp: number, mana: number, maxMana: number,
          stamina = 1, maxStamina = 0): void {
    const set = (key: BarKey, cur: number, max: number, show: boolean): void => {
      const img = this.fills[key];
      const full = Number(img.dataset.w || 52);
      const ratio = max > 0 ? Math.max(0, Math.min(1, cur / max)) : 0;
      // Fill width in KIT px, rounded to WHOLE kit px (user 07/10: fractional
      // widths made pixelated art render with ragged/dotted pixels).
      img.style.width = `${Math.max(0, Math.round(ratio * full))}px`;
      img.style.height = `${img.dataset.h || 2}px`;
      this.labels[key].textContent = show ? `${Math.round(cur)}/${Math.round(max)}` : "";
      // ---- impact FX ----
      const prev = this.prevRatios[key];
      this.prevRatios[key] = ratio;
      if (prev === undefined || max <= 0) return;
      const delta = ratio - prev;
      if (Math.abs(delta) < 0.05) return; // noise floor: no flash for small ticks
      if (delta < 0) {
        if (key === "hp") {
          // HP: blink + shake, both scaled by the size of the hit.
          this.flashDrop(img, Math.min(1, -delta));
          this.shakePanel(-delta);
        } else {
          // Mana/stamina: own wink, no shake (keeps HP as THE danger signal).
          this.flashBar(img, key === "mana" ? "brightness(1.9) saturate(0.4)" : "brightness(1.7)");
        }
      } else {
        this.flashBar(img, key === "hp" ? "brightness(1.6)" : "brightness(1.5)");
      }
    };
    set("hp", hp, maxHp, true);
    set("mana", mana, maxMana, true);
    set("stamina", stamina, maxStamina, maxStamina > 0);
  }

  private prevRatios: Partial<Record<BarKey, number>> = {};
  private shakeTimer: number | null = null;
  private flashTimers: number[] = [];

  /** Blink the fill: hard flash then ease back. Intensity 0..1 scales the
   *  brightness and the total time (bigger hit = longer flash). */
  private flashDrop(img: HTMLImageElement, intensity: number): void {
    for (const t of this.flashTimers) window.clearTimeout(t);
    this.flashTimers = [];
    const bright = 1.6 + intensity * 1.4;      // 1.6 .. 3.0
    const t1 = 90 + intensity * 130;           // 90 .. 220 ms hard flash
    img.style.filter = `brightness(${bright.toFixed(2)}) saturate(0.15)`;
    this.flashTimers.push(window.setTimeout(() => {
      img.style.filter = `brightness(${(1 + intensity * 0.8).toFixed(2)})`;
    }, t1));
    this.flashTimers.push(window.setTimeout(() => { img.style.filter = ""; }, t1 + 160));
  }

  /** Subtle one-shot brightness wink (mana/stamina drops, any rise). */
  private flashBar(img: HTMLImageElement, filter: string): void {
    for (const t of this.flashTimers) window.clearTimeout(t);
    this.flashTimers = [];
    img.style.filter = filter;
    this.flashTimers.push(window.setTimeout(() => { img.style.filter = ""; }, 180));
  }

  /** Whole-panel shake, intensity-scaled (0..1): <0.15 = tiny wink, then
   *  medium / heavy classes. Outer root only (outside .cp-scale so the
   *  ×3 geometry is untouched). Re-triggering resets the animation. */
  private shakePanel(intensity: number): void {
    const el = this.root;
    el.classList.remove("cp-shake", "cp-shake-md", "cp-shake-lg");
    void el.offsetWidth; // reflow restarts the CSS animation
    el.classList.add(intensity >= 0.35 ? "cp-shake-lg" : intensity >= 0.15 ? "cp-shake-md" : "cp-shake");
    if (this.shakeTimer !== null) window.clearTimeout(this.shakeTimer);
    this.shakeTimer = window.setTimeout(
      () => el.classList.remove("cp-shake", "cp-shake-md", "cp-shake-lg"),
      intensity >= 0.35 ? 420 : 320,
    );
  }
}
