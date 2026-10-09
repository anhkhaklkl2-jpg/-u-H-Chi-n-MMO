// ---- Web spells (user 08/10): 4 projectile spells from the VFX packs ----
// Client plays the projectile/impact VFX; the server (game/rules.apply_spell)
// resolves damage/loot/defeat and the action_result splat shows on arrival.
//
// FRAME SOURCES = the packs under "vfx done" VERBATIM (user 10/10: "spell xấu
// — không giống bản trong vfx done"). Every pack README documents its own
// frame split + tuned timings; SPELLS below mirrors those numbers 1:1:
//   wood   Repeatable1-8 fly / Hit1-7 hit, 32x32, FLY_FPS 6, IMPACT_FPS 6
//   earth  frame_01-06 fly / frame_07-10 hit, 48x32 (rotating — draw 6fps)
//   dark   frame_01-10 fly / frame_11-16 hit, 40x32, tail flip on left fly
//   rocklift  rock frame_01-11 (lift+flight) / impact frame_01-07, 48x48
//
// Hit-test gotcha honored: NO getBounds() anywhere — everything is timed
// tweens to a known tile, so the impact always lands where the server
// resolved the hit (server-side radius ~1.25-1.4 tiles around that tile).

import Phaser from "phaser";

export interface SpellDef {
  id: string;
  name: string;
  /** texture dir under /ui/fx/spells/ */
  dir: string;
  /** 100ms load-up held at the player before flight (all packs: CAST_MS). */
  castMs: number;
  flyCount: number;
  hitCount: number;
  /** flight duration ms (README: FLY_MS) */
  flyMs: number;
  fps: number;
  /** sprite draw scale (frames are 32-48px art at 16px world tiles) */
  scale: number;
  mana: number;
  desc: string;
  kind: "projectile" | "dark" | "rocklift";
  /** rock lift timings */
  liftMs?: number;
}

export const SPELLS: SpellDef[] = [
  {
    id: "wood01", name: "Khúc gỗ bay", dir: "wood",
    castMs: 100, flyCount: 8, hitCount: 7, flyMs: 500, fps: 6, scale: 1.0,
    mana: 6, kind: "projectile",
    desc: "Phóng một khúc gỗ thẳng tới mục tiêu. Mana 6.",
  },
  {
    id: "earth01", name: "Đá bay", dir: "earth",
    castMs: 100, flyCount: 6, hitCount: 4, flyMs: 500, fps: 6, scale: 1.0,
    mana: 8, kind: "projectile",
    desc: "Bắn viên đá xoay tròn về phía trước. Mana 8.",
  },
  {
    id: "dark01", name: "Đạn bóng tối", dir: "dark",
    castMs: 100, flyCount: 10, hitCount: 6, flyMs: 500, fps: 6, scale: 1.0,
    mana: 10, kind: "dark",
    desc: "Cầu bóng tối đuôi lửa — nổ khi trúng địch. Mana 10.",
  },
  {
    id: "rocklift", name: "Vận chiêu đá", dir: "rocklift",
    castMs: 100, flyCount: 0, hitCount: 7, flyMs: 450, fps: 10, scale: 1.0,
    mana: 12, kind: "rocklift", liftMs: 600,
    desc: "Nâng tảng đá từ đất rồi ném — sát thương lớn. Mana 12.",
  },
];

export function spellById(id: string): SpellDef | null {
  return SPELLS.find((s) => s.id === id) ?? null;
}

interface ActiveSpell {
  spell: SpellDef;
  img: Phaser.GameObjects.Image | null;
  overlay: Phaser.GameObjects.Image | null;
  phase: "cast" | "fly" | "impact";
  phaseT0: number;
  fromX: number; fromY: number;
  toX: number; toY: number;
  angle: number;
  /** per-frame sprite stepping state */
  done: boolean;
  /** rock lift phase */
  lift?: boolean;
  liftT0?: number;
}

const SPELL_DEPTH = 90;

export class SpellFx {
  private scene: Phaser.Scene | null = null;
  private active: ActiveSpell[] = [];
  private loadedDirs = new Set<string>();
  private updateBound = this.update.bind(this);

  attach(scene: Phaser.Scene): void {
    if (this.scene === scene) return;
    this.scene = scene;
    scene.events.on(Phaser.Scenes.Events.UPDATE, this.updateBound);
    scene.events.once(Phaser.Scenes.Events.SHUTDOWN, () => {
      this.scene = null;
      this.active = [];
    });
  }

  /** Load the pack's textures once (idempotent per scene + dir). */
  loadTextures(spell: SpellDef): void {
    const scene = this.scene;
    if (!scene || this.loadedDirs.has(spell.dir)) return;
    this.loadedDirs.add(spell.dir);
    const max = spell.kind === "rocklift" ? 11 : Math.max(spell.flyCount, spell.hitCount);
    for (let i = 0; i < max; i++) {
      for (const kind of ["fly", "hit", "rock"]) {
        const key = `sp_${spell.dir}_${kind}${i}`;
        if (scene.textures.exists(key)) continue;
        if (kind === "rock" && spell.kind !== "rocklift") continue;
        if (kind === "fly" && (i >= spell.flyCount || spell.kind === "rocklift")) continue;
        if (kind === "hit" && i >= spell.hitCount) continue;
        if (kind === "rock" && i >= 11) continue;
        scene.load.image(key, `ui/fx/spells/${spell.dir}/${kind}_${String(i).padStart(2, "0")}.png`);
      }
    }
    scene.load.start();
  }

  /** Fire the visual: from (player px) to (target tile px). */
  cast(spell: SpellDef, fromPx: { x: number; y: number }, targetTile: { x: number; y: number }): void {
    const scene = this.scene;
    if (!scene) return;
    this.loadTextures(spell);
    const toX = (targetTile.x + 0.5) * (scene as Phaser.Scene & { tilePx: number }).tilePx;
    const toY = (targetTile.y + 0.5) * (scene as Phaser.Scene & { tilePx: number }).tilePx;
    const angle = Math.atan2(toY - fromPx.y, toX - fromPx.x);

    const act: ActiveSpell = {
      spell, img: null, overlay: null, phase: "cast", phaseT0: performance.now(),
      fromX: fromPx.x, fromY: fromPx.y, toX, toY, angle, done: false,
    };
    if (spell.kind === "rocklift") {
      act.lift = true;
      act.liftT0 = performance.now();
      act.img = scene.add.image(fromPx.x, fromPx.y, `sp_${spell.dir}_rock0`)
        .setDepth(SPELL_DEPTH - 1).setScale(spell.scale);
    } else {
      const key = `sp_${spell.dir}_fly0`;
      act.img = scene.add.image(fromPx.x, fromPx.y, key)
        .setDepth(SPELL_DEPTH).setScale(spell.scale).setAlpha(0);
      // dark pack draws its tail flat — flip vertically when flying left so
      // the head leads (README: flip quanh trục bay, chỉ áp cho frame BAY).
      if (spell.kind === "dark") act.img.setFlipY(Math.abs(angle) > Math.PI / 2);
      else act.img.setRotation(angle);
    }
    this.active.push(act);
  }

  private frameIndex(act: ActiveSpell, now: number, count: number): number {
    const elapsed = now - act.phaseT0;
    return Math.min(count - 1, Math.floor((elapsed / 1000) * act.spell.fps));
  }

  private update(): void {
    const scene = this.scene;
    if (!scene) return;
    const now = performance.now();
    for (const act of this.active) {
      const s = act.spell;
      // CAST phase: 100ms fade-in at the muzzle (README CAST_MS, dark also
      // slides out 18px over 150ms after it — folded into the fade here).
      if (act.phase === "cast" && s.kind !== "rocklift") {
        const t = Math.min(1, (now - act.phaseT0) / s.castMs);
        act.img?.setAlpha(t);
        const fi = Math.floor((now - act.phaseT0) / 1000 * s.fps) % s.flyCount;
        act.img?.setTexture(`sp_${s.dir}_fly${fi}`);
        if (t >= 1) {
          act.phase = "fly";
          act.phaseT0 = now;
          act.img?.setAlpha(1);
        }
        continue;
      }
      if (act.lift) {
        // LIFT: rock rises from the player's feet over liftMs, stepping the
        // rock frames (README rock lift loop).
        const t = Math.min(1, (now - (act.liftT0 ?? now)) / (s.liftMs ?? 600));
        act.img?.setPosition(act.fromX, act.fromY - t * 26);
        const ri = Math.floor((now - (act.liftT0 ?? now)) / 1000 * 8) % 8;
        act.img?.setTexture(`sp_rocklift_rock${ri}`);
        if (t >= 1) {
          act.lift = false;
          act.phase = "fly";
          act.phaseT0 = now;
        }
        continue;
      }
      if (act.phase === "fly") {
        const t = Math.min(1, (now - act.phaseT0) / s.flyMs);
        const x = act.fromX + (act.toX - act.fromX) * t;
        // rock lift arcs DOWN from the lifted height; others fly straight.
        const liftH = s.kind === "rocklift" ? 26 : 0;
        const y = act.fromY - liftH * (1 - t) + (act.toY - act.fromY) * t;
        act.img?.setPosition(x, y);
        if (s.kind === "rocklift") {
          const ri = Math.floor((now - act.phaseT0) / 1000 * 8) % 8;
          act.img?.setTexture(`sp_rocklift_rock${ri}`);
        } else if (s.kind !== "dark") {
          // wood/earth: their frames carry the spin — just step them at the
          // pack's FPS without extra rotation (README: cả hai loop 6fps và
          // khung nhìn xoay sẵn; để nguyên giữ pixel art sắc nét).
          const fi = Math.floor((now - act.phaseT0) / 1000 * s.fps) % s.flyCount;
          act.img?.setTexture(`sp_${s.dir}_fly${fi}`);
          act.img?.setRotation(act.angle);
        } else {
          // dark: loop fly frames; keep flipY for the direction
          const fi = Math.floor((now - act.phaseT0) / 1000 * s.fps) % s.flyCount;
          act.img?.setTexture(`sp_dark_fly${fi}`);
          act.img?.setFlipY(Math.abs(act.angle) > Math.PI / 2);
        }
        if (t >= 1) {
          act.phase = "impact";
          act.phaseT0 = now;
          // IMPACT frames never rotate (README rule).
          act.img?.setRotation(0);
          const key = s.kind === "rocklift"
            ? `sp_rocklift_rock6`
            : `sp_${s.dir}_hit0`;
          act.img?.setTexture(key);
          if (s.kind === "rocklift") {
            act.overlay = scene.add.image(act.toX, act.toY + 14, `sp_rocklift_hit0`)
              .setDepth(SPELL_DEPTH - 2).setScale(s.scale);
          }
          // light shake on impact (matching the pack feel)
          scene.cameras.main.shake(120, 0.004);
        }
        continue;
      }
      // impact phase: step hit frames, destroy when done
      const hi = this.frameIndex(act, now, s.hitCount);
      if (s.kind === "rocklift") {
        act.img?.setTexture(`sp_rocklift_rock${Math.min(10, 6 + hi)}`);
        act.overlay?.setTexture(`sp_rocklift_hit${Math.min(s.hitCount - 1, hi)}`);
      } else {
        act.img?.setTexture(`sp_${s.dir}_hit${hi}`);
      }
      const frames = s.kind === "rocklift" ? 7 : s.hitCount;
      if (hi >= frames - 1 && now - act.phaseT0 > (frames / s.fps) * 1000) {
        act.done = true;
      }
    }
    // reap finished
    for (let i = this.active.length - 1; i >= 0; i--) {
      const act = this.active[i];
      if (!act.done) continue;
      act.img?.destroy();
      act.overlay?.destroy();
      this.active.splice(i, 1);
    }
  }
}

export const spellFx = new SpellFx();
