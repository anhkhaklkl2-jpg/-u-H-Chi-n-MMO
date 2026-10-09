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
  kind: "projectile" | "dark" | "rocklift" | "debuff" | "bump" | "wall" | "cone";
  /** rock lift timings */
  liftMs?: number;
  /** bump emerge offset from the player (px, README: user tuned 10→40) */
  emergePx?: number;
  /** wall timings */
  finalHoldMs?: number;
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
  // ---- 4 packs mới (user 10/10, vfx done) ----
  {
    id: "dark02", name: "Debuff bóng tối", dir: "dark02",
    castMs: 0, flyCount: 0, hitCount: 15, flyMs: 0, fps: 6, scale: 1.0,
    mana: 4, kind: "debuff",
    desc: "Vùng tối dâng lên phủ địch tại chỗ — hiển thị thuần. Mana 4.",
  },
  {
    id: "bump01", name: "Cục đá dâng", dir: "bump",
    castMs: 0, flyCount: 0, hitCount: 13, flyMs: 0, fps: 12, scale: 1.0,
    mana: 8, kind: "bump", emergePx: 40,
    desc: "Cục đá nổi lên trước mặt, ĐẨY địch xung quanh ra xa. Mana 8.",
  },
  {
    id: "wall01", name: "Tường đất", dir: "wall",
    castMs: 0, flyCount: 0, hitCount: 6, flyMs: 0, fps: 12, scale: 1.0,
    mana: 10, kind: "wall", finalHoldMs: 2500,
    desc: "Tường đất mọc lên chắn đường 2.5s rồi lún xuống. Mana 10.",
  },
  {
    id: "fire01", name: "Thổi lửa", dir: "breath",
    castMs: 100, flyCount: 4, hitCount: 4, flyMs: 100, fps: 6, scale: 1.0,
    mana: 3, kind: "cone",
    desc: "Giữ chuột để THỔI LỬA theo hướng — cone 4 ô, dmg mỗi tick. Mana 3/tick.",
  },
];

export function spellById(id: string): SpellDef | null {
  return SPELLS.find((s) => s.id === id) ?? null;
}

interface ActiveSpell {
  spell: SpellDef;
  img: Phaser.GameObjects.Image | null;
  overlay: Phaser.GameObjects.Image | null;
  phase: "cast" | "fly" | "impact" | "channel";
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
    // URL FILE NAMES follow the PACK's own convention: `fly_00.png` (.File
    // stem + underscore + TWO digits), while the Phaser KEY suffix is the
    // short unpadded form (`fly0`) that cast()/update() reference. Mismatch
    // here = every spell renders as a green missing-texture box (bug 10/10:
    // `fx0.png` 404 while the pack only has `fx_00.png`).
    const dir = spell.dir;
    const pad = (i: number) => String(i).padStart(2, "0");
    const pairs: Array<{ key: string; file: string }> = [];
    if (spell.kind === "rocklift") {
      for (let i = 0; i < 11; i++) pairs.push({ key: `rock${i}`, file: `rock_${pad(i)}` });
      for (let i = 0; i < spell.hitCount; i++) pairs.push({ key: `hit${i}`, file: `hit_${pad(i)}` });
    } else if (spell.kind === "debuff") {
      // Dark02: ONE 15-frame sequence — fx_00..14.
      for (let i = 0; i < 15; i++) pairs.push({ key: `fx${i}`, file: `fx_${pad(i)}` });
    } else if (spell.kind === "bump") {
      // Bump: one 13-frame sequence — fx_00..12.
      for (let i = 0; i < 13; i++) pairs.push({ key: `fx${i}`, file: `fx_${pad(i)}` });
    } else if (spell.kind === "wall") {
      // Wall: grow_00..05 + final + end_00..05.
      for (let i = 0; i < 6; i++) pairs.push({ key: `grow${i}`, file: `grow_${pad(i)}` });
      pairs.push({ key: "final", file: "final" });
      for (let i = 0; i < 6; i++) pairs.push({ key: `end${i}`, file: `end_${pad(i)}` });
    } else if (spell.kind === "cone") {
      // Fire breath: row01_00..02, row02_00..03, row03_00..06, hit_00..03.
      for (let i = 0; i < 3; i++) pairs.push({ key: `row01_${i}`, file: `row01_${pad(i)}` });
      for (let i = 0; i < 4; i++) pairs.push({ key: `row02_${i}`, file: `row02_${pad(i)}` });
      for (let i = 0; i < 7; i++) pairs.push({ key: `row03_${i}`, file: `row03_${pad(i)}` });
      for (let i = 0; i < 4; i++) pairs.push({ key: `hit_${i}`, file: `hit_${pad(i)}` });
    } else {
      for (let i = 0; i < spell.flyCount; i++) pairs.push({ key: `fly${i}`, file: `fly_${pad(i)}` });
      for (let i = 0; i < spell.hitCount; i++) pairs.push({ key: `hit${i}`, file: `hit_${pad(i)}` });
    }
    for (const p of pairs) {
      const key = `sp_${dir}_${p.key}`;
      if (scene.textures.exists(key)) continue;
      scene.load.image(key, `ui/fx/spells/${dir}/${p.file}.png`);
    }
    scene.load.start();
  }

  /** Fire the visual: from (player px) to (target tile px). */
  cast(spell: SpellDef, fromPx: { x: number; y: number }, targetTile: { x: number; y: number }): void {
    const scene = this.scene;
    if (!scene) return;
    this.loadTextures(spell);
    const t = (scene as Phaser.Scene & { tilePx: number }).tilePx;
    const toX = (targetTile.x + 0.5) * t;
    const toY = (targetTile.y + 0.5) * t;
    const angle = Math.atan2(toY - fromPx.y, toX - fromPx.x);

    // ---- ONE-SHOT AT-TARGET KINDS (no flight) ----
    if (spell.kind === "debuff") {
      // Dark02: 15-frame sequence AT THE TARGET, feet-anchored,
      // no rotation, 1 loop then done.
      // STACKING (README Dark02, preview STACK_GAP_MS=200): re-trigger trên
      // cùng tile trong 200ms → instance cũ bị thay (xóa), không chồng.
      const nowMs = performance.now();
      for (let i = this.active.length - 1; i >= 0; i--) {
        const old = this.active[i];
        if (old.spell.kind !== "debuff") continue;
        const fresh = nowMs - old.phaseT0 < 200;
        const sameSpot = Math.hypot(old.toX - toX, old.toY - toY) < 1;
        if (fresh && sameSpot) {
          old.img?.destroy();
          this.active.splice(i, 1);
        }
      }
      const img = scene.add.image(toX, toY, `sp_dark02_fx0`)
        .setDepth(SPELL_DEPTH).setScale(spell.scale);
      // 48x64 frame: anchor the BOTTOM to tile centre (mob feet zone).
      img.setOrigin(0.5, 1);
      this.active.push({
        spell, img, overlay: null, phase: "impact", phaseT0: performance.now(),
        fromX: toX, fromY: toY, toX, toY, angle, done: false,
      });
      return;
    }
    if (spell.kind === "bump") {
      // Earth Bump: bump rises emergePx FROM THE PLAYER toward the aim,
      // flips left/right (NO rotation), 13 frames at 12fps then gone.
      const emerge = spell.emergePx ?? 40;
      const bumpX = fromPx.x + Math.cos(angle) * emerge;
      const bumpY = fromPx.y + Math.sin(angle) * emerge;
      const img = scene.add.image(bumpX, bumpY, `sp_bump_fx0`)
        .setDepth(SPELL_DEPTH).setScale(spell.scale)
        // preview: feet anchored ~b.y + h*0.35 (center origin ~0.85 height)
        .setOrigin(0.5, 0.85);
      img.setFlipX(Math.cos(angle) < 0); // flip horizontal ONLY (README)
      this.active.push({
        spell, img, overlay: null, phase: "impact", phaseT0: performance.now(),
        fromX: bumpX, fromY: bumpY, toX: bumpX, toY: bumpY, angle, done: false,
      });
      // light shake when the bump erupts
      scene.cameras.main.shake(140, 0.005);
      return;
    }
    if (spell.kind === "wall") {
      // Earth Wall: grow 6f (12fps) → HOLD final 2.5s → end 6f → done.
      const img = scene.add.image(toX, toY, `sp_wall_grow0`)
        .setDepth(SPELL_DEPTH).setScale(spell.scale).setOrigin(0.5, 1);
      this.active.push({
        spell, img, overlay: null, phase: "impact", phaseT0: performance.now(),
        fromX: toX, fromY: toY, toX, toY, angle, done: false,
      });
      return;
    }

    // ---- FLIGHT / CHANNEL KINDS (existing behaviour + fire cone) ----
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
      const key = spell.kind === "cone"
        ? `sp_${spell.dir}_row01_0`
        : `sp_${spell.dir}_fly0`;
      act.img = scene.add.image(fromPx.x, fromPx.y, key)
        .setDepth(SPELL_DEPTH).setScale(spell.scale).setAlpha(0);
      // dark pack draws its tail flat — flip vertically when flying left so
      // the head leads (README: flip quanh trục bay, chỉ áp cho frame BAY).
      if (spell.kind === "dark") act.img.setFlipY(Math.abs(angle) > Math.PI / 2);
      else act.img.setRotation(angle);
      // FIRE: art tỏa về phía ĐÔNG — trái thì lật NGANG (preview: Lật nguồn
      // sprite), KHÔNG xoay 180° (lửa bị lộn ngược).
      if (spell.kind === "cone") {
        act.img.setRotation(0);
        if (Math.abs(angle) > Math.PI / 2) act.img.setFlipX(true);
      }
    }
    this.active.push(act);
  }

  /** Fire breath channel: bắt đầu thổi theo hướng aim (angle khoá). */
  channelStart(s: SpellDef, fromPx: { x: number; y: number }, aimTile: { x: number; y: number }): void {
    const scene = this.scene;
    if (!scene) return;
    const t = (scene as Phaser.Scene & { tilePx: number }).tilePx;
    const toX = (aimTile.x + 0.5) * t;
    const toY = (aimTile.y + 0.5) * t;
    const angle = Math.atan2(toY - fromPx.y, toX - fromPx.x);
    const img = scene.add.image(fromPx.x, fromPx.y, `sp_${s.dir}_row01_0`)
      .setDepth(SPELL_DEPTH).setScale(s.scale).setRotation(angle);
    // README: lật khi bắn sang trái (|angle|>90°) — sprite gốc hướng PHẢI
    img.setFlipY(Math.abs(angle) > Math.PI / 2);
    this.channelAct = {
      spell: s, img, overlay: null, phase: "channel", phaseT0: performance.now(),
      fromX: fromPx.x, fromY: fromPx.y, toX, toY, angle, done: false,
    };
    this.active.push(this.channelAct);
  }

  /** Thả tay: chuyển sang row03 (7f, play 1 lần) rồi tự tắt. */
  channelEnd(): void {
    if (this.channelAct) {
      this.channelAct.phase = "impact";
      this.channelAct.phaseT0 = performance.now();
      this.channelAct = null;
    }
  }

  private channelAct: ActiveSpell | null = null;

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
      // ---- DEBUFF (dark02): 15 fx frames at the mob, one loop, then done.
      // STACKING (README Dark02): re-cast lên CÙNG mob trong 200ms → instance
      // cũ bị xóa (STACK_GAP_MS preview), chỉ giữ 1 instance/mob.
      if (s.kind === "debuff") {
        const fi = this.frameIndex(act, now, 15);
        act.img?.setTexture(`sp_dark02_fx${fi}`);
        if (fi >= 14 && now - act.phaseT0 > (15 / s.fps) * 1000) act.done = true;
        continue;
      }
      // ---- BUMP: 13 fx frames at the bump spot (flipX already set).
      // KNOCK CENTER = bump spot (preview): server pos = best mob nhưng
      // client VFX center = bump px point (fromX/fromY set at cast).
      if (s.kind === "bump") {
        const fi = this.frameIndex(act, now, 13);
        act.img?.setTexture(`sp_bump_fx${fi}`);
        if (fi >= 12 && now - act.phaseT0 > (13 / s.fps) * 1000) act.done = true;
        continue;
      }
      // ---- WALL: grow 6 → final hold → end 6 → done. Fires camera shake ONCE
      // at the grow->final transition.
      if (s.kind === "wall") {
        const el = now - act.phaseT0;
        const growMs = (6 / s.fps) * 1000;
        if (el < growMs) {
          const gi = Math.floor(el / 1000 * s.fps);
          act.img?.setTexture(`sp_wall_grow${Math.min(5, gi)}`);
        } else if (el < growMs + (s.finalHoldMs ?? 2500)) {
          if ((act as unknown as { _shaken?: boolean })._shaken !== true) {
            (act as unknown as { _shaken?: boolean })._shaken = true;
            scene.cameras.main.shake(150, 0.005);
          }
          act.img?.setTexture(`sp_wall_final`);
        } else {
          const ei = Math.min(5, Math.floor((el - growMs - (s.finalHoldMs ?? 2500)) / 1000 * s.fps));
          act.img?.setTexture(`sp_wall_end${ei}`);
          if (ei >= 5 && el > growMs + (s.finalHoldMs ?? 2500) + (6 / s.fps) * 1000) act.done = true;
        }
        continue;
      }
      // ---- CONE (fire breath) — TRUE CHANNEL per README: giữ chuột = thổi.
      // phase "channel": row01 mở 3f (12fps) → row02 LOOP liên tục, v geile
      // tại caster. phase "impact" (từ channelEnd): row03 7f play 1 lần.
      if (s.kind === "cone") {
        const el = now - act.phaseT0;
        const f = s.fps;
        if (act.phase === "channel") {
          const openMs = (3 / f) * 1000;
          if (el < openMs) {
            act.img?.setTexture(`sp_${s.dir}_row01_${Math.min(2, Math.floor(el / 1000 * f))}`);
          } else {
            const li = Math.floor((el - openMs) / 1000 * f) % 4;
            act.img?.setTexture(`sp_${s.dir}_row02_${li}`);
          }
          act.img?.setPosition(act.fromX, act.fromY);
          act.img?.setAlpha(Math.min(1, el / 60));
        } else {
          // end burst: row03 7f @fps, giữ vị trí + angle đã khoá
          const ei = Math.min(6, Math.floor(el / 1000 * f));
          act.img?.setTexture(`sp_${s.dir}_row03_${ei}`);
          if (ei >= 6 && el > (7 / f) * 1000) act.done = true;
        }
        continue;
      }
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
        // lift loop 6fps, rock 0..5 (bản preview final: ROCK_FPS=6,
        // ROCT.length=6). Lift kết thúc ĐÚNG tại frame 5 (frame_06) và
        // pha bay GIỮ NGUYÊN frame 5 (cứng) → chuyển lift→fly không lóe
        // (fix "nháy 1 frame" user 10/10).
        const ri = Math.min(5, Math.floor((now - (act.liftT0 ?? now)) / 1000 * 6) % 6);
        act.img?.setTexture(`sp_rocklift_rock${ri}`);
        if (t >= 1) {
          act.lift = false;
          act.phase = "fly";
          act.phaseT0 = now;
        }
        continue;
      }
      if (act.phase === "fly") {
        const raw = Math.min(1, (now - act.phaseT0) / s.flyMs);
        // rock lift: ease-in (bị QUĂNG đi) + arc giảm 20% (11px) đúng bản
        // preview final; điểm bắt đầu bay trùng khít điểm lift kết thúc —
        // không nhảy gây lóe.
        const liftH = s.kind === "rocklift" ? 26 : 0;
        const prog = s.kind === "rocklift" ? raw * raw : raw;
        const x = act.fromX + (act.toX - act.fromX) * prog;
        const y0 = act.fromY - liftH * (1 - raw) + (act.toY - act.fromY) * raw;
        const y = y0 - (s.kind === "rocklift" ? Math.sin(raw * Math.PI) * 11 : 0);
        act.img?.setPosition(x, y);
        if (s.kind === "rocklift") {
          // Frame bay CỨNG duy nhất rock_05 (frame_06) — không anim, đúng
          // bản preview final (fix loop ngược frame đầu).
          act.img?.setTexture(`sp_rocklift_rock5`);
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
        if (raw >= 1) {
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

// ---- FIRE BREATH CHANNEL (README Fire Breath: giữ để thổi) -----------------
// `channelStart`: bắt đầu thổi theo hướng aim — row01 mở (3f, 12fps) rồi
// row02 LOOP kh liên tục. `channelEnd`: chuyển row03 (7f) play 1 lần rồi mất.
// Xoay MỌI hướng theo README, angle KHOÁ tại lúc bắt đầu (không tự theo chuột).
// Trả cái SpellFx cùng object; dmg tick do server lo, client chỉ vẽ.
export function fireChannelStart(
  fromPx: { x: number; y: number }, aimTile: { x: number; y: number },
): void {
  const s = SPELLS.find((sp) => sp.id === "fire01");
  if (!s) return;
  spellFx.loadTextures(s);
  spellFx.channelStart(s, fromPx, aimTile);
}
export function fireChannelEnd(): void {
  spellFx.channelEnd();
}
