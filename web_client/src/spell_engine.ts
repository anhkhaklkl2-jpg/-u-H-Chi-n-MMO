// ---- SPELL ENGINE RUNTIME (user 11/10) ------------------------------------
// Chạy lifecycle của 1 spell theo DATA (spell_defs.ts):
//   cast(ε=0 với rocklift) → emerge → flight (theo SPEED, hit-test thật theo
//   quãng đường) → impact event (vẽ vỡ +Mobshake + số damage CÙNG MOMENT).
//
// KHÁC BIỆT với spellFX cũ: FLIGHT kết thúc theo QUÃNG ĐƯỜNG (distance) chứ
// không theo flyMs cứng — đá luôn CHẠM mob/đích rồi MỚI vỡ, đồng bộ với
// impact event từ server (server resolve damage tại impact).

import Phaser from "phaser";
import type { SpellDef } from "./spell_defs";

const SPELL_DEPTH = 90;


type Phase = "lift" | "emerge" | "flight" | "impact";

interface Run {
  def: SpellDef;
  img: Phaser.GameObjects.Image;
  overlay: Phaser.GameObjects.Image | null;
  phase: Phase;
  phaseT0: number;
  from: { x: number; y: number };
  to: { x: number; y: number };
  /** Öång投诉ast distance the projectile has covered in px (flight measured by it). */
  travelledPx: number;
  totalPx: number;
  done: boolean;
  /** server-approved impact: when the frame comes, finish flight instantly */
  serverImpactAt: { x: number; y: number } | null;
}

export class SpellEngine {
  private scene: Phaser.Scene | null = null;
  private runs: Run[] = [];
  private loadedDirs = new Set<string>();
  private updateBound = this.update.bind(this);

  attach(scene: Phaser.Scene): void {
    if (this.scene === scene) return;
    this.scene = scene;
    scene.events.on(Phaser.Scenes.Events.UPDATE, this.updateBound);
    scene.events.once(Phaser.Scenes.Events.SHUTDOWN, () => {
      scene.events.off(Phaser.Scenes.Events.UPDATE, this.updateBound);
      this.scene = null;
      this.runs = [];
    });
  }

  /** Load the pack's texture frames once per dir. */
  loadTextures(def: SpellDef): void {
    const sc = this.scene;
    if (!sc || this.loadedDirs.has(def.dir)) return;
    this.loadedDirs.add(def.dir);
    const pad = (i: number) => String(i).padStart(2, "0");
    // rocklift: rock_00..10 (lift 0-5, flight 5 fixed, impact 6-10) + hit_00..06
    for (let i = 0; i < 11; i++) {
      const key = `sp_${def.dir}_rock${i}`;
      if (!sc.textures.exists(key)) sc.load.image(key, `ui/fx/spells/${def.dir}/rock_${pad(i)}.png`);
    }
    for (let i = 0; i < 7; i++) {
      const key = `sp_${def.dir}_hit${i}`;
      if (!sc.textures.exists(key)) sc.load.image(key, `ui/fx/spells/${def.dir}/hit_${pad(i)}.png`);
    }
    sc.load.start();
  }

  /** Cast: stage lifecaycle bắt đầu. Server đã nhận cast (castSpell route). */
  cast(def: SpellDef, fromPx: { x: number; y: number }, targetTile: { x: number; y: number }): void {
    const sc = this.scene;
    if (!sc) return;
    this.loadTextures(def);
    const t = (sc as unknown as { tilePx: number }).tilePx;
    const to = { x: (targetTile.x + 0.5) * t, y: (targetTile.y + 0.5) * t };
    const img = sc.add.image(fromPx.x, fromPx.y, `sp_${def.dir}_rock0`)
      .setDepth(SPELL_DEPTH - 1).setScale(def.scale ?? 1);
    this.runs.push({
      def, img, overlay: null,
      phase: def.liftMs ? "lift" : "emerge",
      phaseT0: performance.now(),
      from: { x: fromPx.x, y: fromPx.y }, to,
      travelledPx: 0,
      totalPx: Math.max(1, Math.hypot(to.x - fromPx.x, to.y - fromPx.y)),
      done: false, serverImpactAt: null,
    });
  }

  /** SERVER IMPACT EVENT (from action_result echo): đúng mô-men server resolve
   *  damage — kiểm tra impact sẽ bật đúng lúc này thay vì client tự đo. */
  notifyServerImpact(tx: number, ty: number): void {
    const sc = this.scene;
    if (!sc) return;
    const t = (sc as unknown as { tilePx: number }).tilePx;
    const px = { x: (tx + 0.5) * t, y: (ty + 0.5) * t };
    // find a flight run heading near this tile — snap it to impact NOW so
    // VFX vỡ CÙNG lúc mob dính sát thương (chép server position).
    for (const r of this.runs) {
      if (r.phase !== "flight" && r.phase !== "lift" && r.phase !== "emerge") continue;
      if (Math.hypot(r.to.x - px.x, r.to.y - px.y) <= (r.def.impactRadiusPx ?? 40)) {
        r.phase = "impact";
        r.phaseT0 = performance.now();
        r.to = px; // snap to server pos
        r.img?.setPosition(px.x, px.y);
        r.img?.setRotation(0);
        r.img?.setTexture(`sp_${r.def.dir}_rock6`);
        r.overlay = sc.add.image(px.x, px.y + 14, `sp_${r.def.dir}_hit0`)
          .setDepth(SPELL_DEPTH - 2).setScale(r.def.scale ?? 1);
        return;
      }
    }
  }

  private update(): void {
    const sc = this.scene;
    if (!sc) return;
    const now = performance.now();
    const t = (sc as unknown as { tilePx: number }).tilePx;
    for (const r of this.runs) {
      if (r.done) continue;
      const d = r.def;
      if (r.phase === "lift") {
        const raw = Math.min(1, (now - r.phaseT0) / (d.liftMs ?? 600));
        r.img?.setPosition(r.from.x, r.from.y - raw * (d.liftPx ?? 26));
        const ri = Math.min(5, Math.floor((now - r.phaseT0) / 1000 * 6) % 6);
        r.img?.setTexture(`sp_${d.dir}_rock${ri}`);
        if (raw >= 1) { r.phase = "flight"; r.phaseT0 = now; }
        continue;
      }
      if (r.phase === "flight") {
        const stage = d.stages.find(s => s.type === "flight") as
          | { type: "flight"; speedTiles: number; maxMs: number } | undefined;
        const speed = (stage?.speedTiles ?? 10) * t; // px/s
        const dt = Math.min(0.05, (now - r.phaseT0) / 1000);
        r.travelledPx += speed * dt;
        const prog = Math.min(1, r.travelledPx / r.totalPx);
        const ease = prog * prog; // óng the rocklift ease-in
        const x = r.from.x + (r.to.x - r.from.x) * ease;
        const y = r.from.y - (d.liftPx ?? 26) * (1 - prog) + (r.to.y - r.from.y) * prog;
        const arc = -Math.sin(prog * Math.PI) * 11;
        r.img?.setPosition(x, y + arc);
        // frame CỨNG frame_06 (rock5) trong lúc bay — README final
        r.img?.setTexture(`sp_${d.dir}_rock5`);
        if (prog >= 1) {
          // Client-side expiry (no server event yet): impact at target
          r.phase = "impact";
          r.phaseT0 = now;
          r.img?.setRotation(0);
          r.img?.setPosition(r.to.x, r.to.y);
          r.img?.setTexture(`sp_${d.dir}_rock6`);
          r.overlay = sc.add.image(r.to.x, r.to.y + 14, `sp_${d.dir}_hit0`)
            .setDepth(SPELL_DEPTH - 2).setScale(d.scale ?? 1);
        }
        continue;
      }
      if (r.phase === "impact") {
        const fi = Math.min(6, Math.floor((now - r.phaseT0) / 1000 * 10));
        r.img?.setTexture(`sp_${d.dir}_rock${Math.min(10, 6 + fi)}`);
        r.overlay?.setTexture(`sp_${d.dir}_hit${Math.min(6, fi)}`);
        if (fi >= 6 && now - r.phaseT0 > 700) r.done = true;
        continue;
      }
    }
    // reap done runs
    for (let i = this.runs.length - 1; i >= 0; i--) {
      if (!this.runs[i].done) continue;
      this.runs[i].img?.destroy();
      this.runs[i].overlay?.destroy();
      this.runs.splice(i, 1);
    }
  }
}

/** Shared singleton wired by main.ts (same pattern as spellFx bridge). */
export const spellEngine = new SpellEngine();
