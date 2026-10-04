// Room FX for indoor maps: fireplace fire + window light shafts.
//
// Anchors ride the welcome frame (welcome.map.room_fx, game-coord cells
// from the map's "fx lua" / "fx cua so" marker layers — absent on unmarked
// maps, then this module stays idle). Rendering reuses the cave-ambience
// recipe (procedural radial canvases + ADD blend), plus the Ninja FX fire
// particle strip (fx/fire_12.png, 8 frames of 12px) for real flames:
//
//   fire:    2 stacked flame sprites (ping-pong strip frames, additive)
//            + 6 rising ember dots + warm halo with dual-sine flicker
//            (halo strengthens at night via dayNightPhaser.ambientFactor).
//   window:  cool gradient shaft falling ~3.5 tiles + 4 drifting dust motes
//            (day: bright cool white, night: dim moon blue).
//
// Cheap by design: a handful of sprites, no per-frame canvas repaints
// (only numeric alpha/frame/position updates). Gated by perf.room (?fx=0
// or ?fx=room to isolate).

import Phaser from "phaser";
import { dayNightPhaser } from "./daynight_phaser";
import { perf } from "./perf";

export interface RoomFxAnchors {
  fires?: [number, number][];
  windows?: [number, number][];
}

export const FIRE_SHEET = "fx/fire_12.png";
export const FIRE_KEY = "fx-fire_12";

interface Ember {
  spr: Phaser.GameObjects.Image;
  seed: number;
}

interface Flame {
  cx: number;
  cy: number;
  phase: number;
  spr: Phaser.GameObjects.Image | null;
  spr2: Phaser.GameObjects.Image | null;
  halo: Phaser.GameObjects.Image;
  embers: Ember[];
}

interface Mote {
  spr: Phaser.GameObjects.Image;
  seed: number;
}

interface Shaft {
  cx: number;
  top: number;
  img: Phaser.GameObjects.Image;
  motes: Mote[];
}

function radialCanvas(r: number, stops: [number, string][]): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = r * 2;
  c.height = r * 2;
  const g = c.getContext("2d")!;
  const grad = g.createRadialGradient(r, r, 0, r, r, r);
  for (const [at, col] of stops) grad.addColorStop(at, col);
  g.fillStyle = grad;
  g.fillRect(0, 0, r * 2, r * 2);
  return c;
}

export class RoomFx {
  private scene: Phaser.Scene;
  private flames: Flame[] = [];
  private shafts: Shaft[] = [];
  private tw = 32;
  private fireAsked = false;

  // ---- DRAG-ALIGN (preview-only tool, user request 05/10) ----
  // When enabled, the user grabs a fire's warm HALO ("ánh sáng") or a
  // window shaft on the canvas and drags it; every drop snaps to a tile
  // and commits the FULL anchor list (game coords) via onAlignCommit
  // (game.ts -> preview_cmd "fx_align" -> demo server writes the map's
  // fx marker layers). Code never changes — only the Tiled JSON data.
  onAlignCommit: ((anchors: RoomFxAnchors) => void) | null = null;
  private alignOn = false;
  private alignLabel: Phaser.GameObjects.Text | null = null;

  constructor(scene: Phaser.Scene) {
    this.scene = scene;
  }

  /** Toggle the drag-align mode (preview panel "🎯 Căn FX"). */
  setAlignMode(on: boolean): void {
    this.alignOn = on;
    const sc = this.scene;
    if (on && !this.alignLabel) {
      this.alignLabel = sc.add
        .text(8, 8, "", {
          fontFamily: "Verdana, sans-serif", fontSize: "12px",
          color: "#7fff9f", stroke: "#0a0d12", strokeThickness: 3,
        })
        .setDepth(4000)
        .setScrollFactor(0);
    }
    if (this.alignLabel) {
      this.alignLabel.setVisible(on);
      this.alignLabel.setText(on ? "🎯 Kéo chấm sáng lửa / dải cửa sổ…" : "");
    }
    for (const f of this.flames) this.wireDrag(f.halo, on);
    for (const sh of this.shafts) this.wireDrag(sh.img, on);
  }

  /** (Un)register drag on one fx grab-target. Handlers guard on alignOn. */
  private wireDrag(g: Phaser.GameObjects.Image, on: boolean): void {
    if (on) {
      g.setInteractive({ useHandCursor: true });
      this.scene.input.setDraggable(g);
      g.off("drag").on(
        "drag",
        (_p: Phaser.Input.Pointer, dx: number, dy: number) => this.onDrag(g, dx, dy),
      );
      g.off("dragend").on("dragend", () => this.commitAlign());
    } else {
      g.disableInteractive();
      (this.scene.input as unknown as { setDraggable: (o: Phaser.GameObjects.Image, v: boolean) => void }).setDraggable(g, false);
    }
  }

  private onDrag(g: Phaser.GameObjects.Image, wx: number, wy: number): void {
    if (!this.alignOn) return;
    const tx = Math.floor(wx / this.tw);
    const ty = Math.floor(wy / this.tw);
    const fl = this.flames.find((f) => f.halo === g);
    if (fl) {
      fl.cx = (tx + 0.5) * this.tw;
      fl.cy = (ty + 0.5) * this.tw;
      fl.halo.setPosition(fl.cx, fl.cy - this.tw * 0.35);
      fl.spr?.setPosition(fl.cx, fl.cy - 9);
      fl.spr2?.setPosition(fl.cx + 4, fl.cy - 8);
      // embers/halo flicker re-read cx/cy every update() — no extra work.
      this.alignLabel?.setText(`🔥 lửa → ô (${tx},${ty})`);
      return;
    }
    const sh = this.shafts.find((s) => s.img === g);
    if (!sh) return;
    sh.cx = (tx + 0.5) * this.tw;
    sh.top = ty * this.tw;
    sh.img.setPosition(sh.cx, sh.top);
    this.alignLabel?.setText(`🪟 cửa sổ → ô (${tx},${ty})`);
  }

  /** Drop -> snap already applied; report the whole anchor set. */
  private commitAlign(): void {
    if (!this.alignOn || !this.onAlignCommit) return;
    this.onAlignCommit({
      fires: this.flames.map(
        (f) => [Math.round(f.cx / this.tw - 0.5), Math.round(f.cy / this.tw - 0.5)] as [number, number],
      ),
      windows: this.shafts.map(
        (s) => [Math.round(s.cx / this.tw - 0.5), Math.round(s.top / this.tw)] as [number, number],
      ),
    });
  }

  /** (Re)build from welcome anchors. Null/empty tears everything down. */
  setup(anchors: RoomFxAnchors | null | undefined, tilePx: number, fetchAsset: (name: string) => void): void {
    this.destroy();
    if (!perf.room) return;
    if (!anchors || ((anchors.fires ?? []).length === 0 && (anchors.windows ?? []).length === 0)) return;
    this.tw = tilePx || 32;
    this.ensureSharedTextures();
    for (const [fx, fy] of anchors.fires ?? []) this.addFire((fx + 0.5) * this.tw, (fy + 0.5) * this.tw);
    for (const [wx, wy] of anchors.windows ?? []) this.addShaft((wx + 0.5) * this.tw, wy * this.tw);
    // Flame art flies through the confined asset pipe (bytes stay on bot).
    if (this.flames.length > 0 && !this.scene.textures.exists(FIRE_KEY) && !this.fireAsked) {
      this.fireAsked = true;
      fetchAsset(FIRE_SHEET);
    }
    if (this.flames.length > 0 && this.scene.textures.exists(FIRE_KEY)) this.attachFlames();
  }

  /** The fire strip arrived (main.ts fx/ lane) — attach flame sprites. */
  onFireTexture(): void {
    if (this.flames.length > 0) this.attachFlames();
  }

  update(nowMs: number): void {
    if (this.flames.length === 0 && this.shafts.length === 0) return;
    const dayF = dayNightPhaser.ambientFactor ?? 1; // 1 = full day
    const nightBoost = 0.75 + 0.55 * (1 - dayF);
    for (const f of this.flames) {
      // Flame strip frames (0..7 loop) + gentle scale breathing.
      // Scaled DOWN + slower burn so the fire stays INSIDE the hearth
      // (user: "lửa cháy ra cả ngoài lò").
      if (f.spr) {
        f.spr.setFrame(Math.floor(nowMs / 175 + f.phase) % 8);
        const s = 1.8 + 0.12 * Math.sin(nowMs / 340 + f.phase);
        f.spr.setScale(s);
      }
      if (f.spr2) {
        f.spr2.setFrame(Math.floor(nowMs / 150 + f.phase * 1.7 + 3) % 8);
        const s2 = 1.1 + 0.1 * Math.sin(nowMs / 290 + f.phase * 2.1);
        f.spr2.setScale(s2);
      }
      // Halo flicker: two detuned sines read as candle chaos, never periodic.
      const flick =
        0.30 +
        0.05 * Math.sin(nowMs / 310 + f.phase) +
        0.03 * Math.sin(nowMs / 113 + f.phase * 1.7);
      f.halo.setAlpha(Math.max(0.12, flick * nightBoost));
      // Embers rise ~1.5 tiles, wobble, fade.
      for (const e of f.embers) {
        const t = (nowMs / 1500 + e.seed) % 1;
        e.spr.setPosition(
          f.cx + Math.sin(nowMs / 480 + e.seed * 9) * 7 * t,
          f.cy - 12 - t * this.tw * 1.5,
        );
        e.spr.setAlpha((1 - t) * 0.75);
        const es = 0.5 + t * 0.9;
        e.spr.setScale(es);
      }
    }
    for (const sh of this.shafts) {
      // Day: bright cool shaft; night: dim moon-blue wash.
      const a = 0.05 + 0.09 * dayF;
      sh.img.setAlpha(a);
      sh.img.setTint(dayF > 0.45 ? 0xcfe0ff : 0x8fa8ff);
      for (const m of sh.motes) {
        m.spr.setPosition(
          sh.cx + Math.sin(nowMs / 1700 + m.seed * 7) * this.tw * 0.45,
          sh.top + ((nowMs / 5200 + m.seed) % 1) * this.tw * 3.2,
        );
        m.spr.setAlpha(0.10 + 0.14 * (0.5 + 0.5 * Math.sin(nowMs / 900 + m.seed * 5)));
      }
    }
  }

  destroy(): void {
    for (const f of this.flames) {
      f.spr?.destroy();
      f.spr2?.destroy();
      f.halo.destroy();
      for (const e of f.embers) e.spr.destroy();
    }
    for (const sh of this.shafts) {
      sh.img.destroy();
      for (const m of sh.motes) m.spr.destroy();
    }
    this.flames = [];
    this.shafts = [];
  }

  private ensureSharedTextures(): void {
    const tex = this.scene.textures;
    if (!tex.exists("roomfx-halo")) {
      tex.addCanvas(
        "roomfx-halo",
        radialCanvas(64, [
          [0, "rgba(255,190,110,0.55)"],
          [0.45, "rgba(255,150,70,0.22)"],
          [1, "rgba(255,120,50,0)"],
        ]),
      );
    }
    if (!tex.exists("roomfx-dot")) {
      tex.addCanvas(
        "roomfx-dot",
        radialCanvas(8, [
          [0, "rgba(255,220,160,1)"],
          [0.5, "rgba(255,170,90,0.5)"],
          [1, "rgba(255,150,70,0)"],
        ]),
      );
    }
    if (!tex.exists("roomfx-shaft")) {
      // Soft vertical shaft: bright head fading down, feathered sides.
      const c = document.createElement("canvas");
      c.width = 64;
      c.height = 128;
      const g = c.getContext("2d")!;
      const grad = g.createLinearGradient(0, 0, 0, 128);
      grad.addColorStop(0, "rgba(255,255,255,0.85)");
      grad.addColorStop(0.7, "rgba(255,255,255,0.28)");
      grad.addColorStop(1, "rgba(255,255,255,0)");
      g.fillStyle = grad;
      g.fillRect(0, 0, 64, 128);
      // Feather left/right edges (destination-in gradient).
      g.globalCompositeOperation = "destination-in";
      const side = g.createLinearGradient(0, 0, 64, 0);
      side.addColorStop(0, "rgba(0,0,0,0)");
      side.addColorStop(0.25, "rgba(0,0,0,1)");
      side.addColorStop(0.75, "rgba(0,0,0,1)");
      side.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = side;
      g.fillRect(0, 0, 64, 128);
      tex.addCanvas("roomfx-shaft", c);
    }
  }

  private addFire(cx: number, cy: number): void {
    const sc = this.scene;
    const halo = sc.add
      .image(cx, cy - this.tw * 0.35, "roomfx-halo")
      .setOrigin(0.5, 0.5)
      .setDepth(18)
      .setBlendMode(Phaser.BlendModes.ADD);
    halo.setScale((this.tw * 1.7 * 2) / 128);
    const embers: Ember[] = [];
    for (let i = 0; i < 6; i++) {
      // Depth 32 = above the OVER canvas (30): tall fireplace chimneys
      // bake y-sorted over actors and would swallow flames/embers at 26.
      const spr = sc.add
        .image(cx, cy, "roomfx-dot")
        .setDepth(32)
        .setBlendMode(Phaser.BlendModes.ADD);
      spr.setTint(0xffb060);
      embers.push({ spr, seed: (i + 1) / 7 });
    }
    const phase = (cx * 0.37 + cy * 0.73) % 6.28;
    this.flames.push({ cx, cy, phase, spr: null, spr2: null, halo, embers });
  }

  private attachFlames(): void {
    if (!this.scene.textures.exists(FIRE_KEY)) return;
    for (const f of this.flames) {
      if (!f.spr) {
        f.spr = this.scene.add
          .image(f.cx, f.cy - 9, FIRE_KEY, 0)
          .setOrigin(0.5, 0.85)
          .setDepth(32)
          .setBlendMode(Phaser.BlendModes.ADD);
      }
      if (!f.spr2) {
        f.spr2 = this.scene.add
          .image(f.cx + 4, f.cy - 8, FIRE_KEY, 3)
          .setOrigin(0.5, 0.85)
          .setDepth(32)
          .setBlendMode(Phaser.BlendModes.ADD);
      }
    }
  }

  private addShaft(cx: number, top: number): void {
    const img = this.scene.add
      .image(cx, top, "roomfx-shaft")
      .setOrigin(0.5, 0)
      .setDepth(18)
      .setBlendMode(Phaser.BlendModes.ADD);
    img.setScale((this.tw * 1.25) / 64, (this.tw * 3.5) / 128);
    const motes: Mote[] = [];
    for (let i = 0; i < 4; i++) {
      const spr = this.scene.add
        .image(cx, top, "roomfx-dot")
        .setDepth(19)
        .setBlendMode(Phaser.BlendModes.ADD);
      spr.setTint(0xd8e4ff);
      spr.setScale(0.45);
      motes.push({ spr, seed: (i + 1) / 5 });
    }
    this.shafts.push({ cx, top, img, motes });
  }
}
