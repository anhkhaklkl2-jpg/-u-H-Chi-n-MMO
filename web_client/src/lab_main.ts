// SPELL LAB v2 (user 13/10: "tương tự test ở preview — di chuyển đầy đủ,
// hitbox, frame, animation đầy đủ, có cây gậy phép").
//
// PARITY: mọi thứ vẽ ở đây dùng SHEET + CÔNG THỨC của game production:
//   - Caster: players/base.png (pd-base), rows idle_down=0 walk_down=3
//     atk_down=6, 4 frame/row, speeds 250/120/50, offsets (-8,-32) —
//     GIỐNG players_manifest.json + PaperdollBody.
//   - Weapon layer: weapon/stick.png 48x48 (9 rows, cols 4, offset -8,-24)
//     đè lên body cùng frame index — cách PaperdollBody vẽ weapon.
//   - Zombie: mobs/zombie.png 32px cell — rows idle/walk/atk theo
//     MOB_SHEETS zombie trong game.ts.
//   - Spell engine thật: import src/spell_engine.ts (game dùng CÙNG file).
// dùng PaperdollBody THẬT của game (không tự vẽ lại — user 13/10 "làm kỹ
// lại"): feet-anchor origin (0.5,1), shared-centre weapon, Kaetram frame
// pacing — đầy đủ như production.
import Phaser from "phaser";
import { PaperdollBody, registerPaperdollTextures, registerWeaponSheet } from "./paperdoll";
import type { PlayersManifest } from "./protocol";
import { spellEngine } from "./spell_engine";
import { SPELL_ENGINE_DEFS, type SpellDef } from "./spell_defs";

const TILE = 32;
const MAP_W = 26;
const MAP_H = 14;
const CASTER_SPAWN = { x: 4, y: 7 };

const defIn = SPELL_ENGINE_DEFS.find((d) => d.id === "rocklift");
if (!defIn) throw new Error("rocklift def missing");
const def: SpellDef = { ...defIn };

const logEl = document.getElementById("log") as HTMLElement;
const tlEl = document.getElementById("timeline") as HTMLElement;

// DES TRÁNH TS "assigned never used" noise: các biến startSpawn dùng ở killCaster.
function log(s: string): void { logEl.textContent = s; }

/* (paperdoll constants + row helper đã bỏ — PaperdollBody tự quản frame
 * pacing nội bộ; lab không còn tự đẩy frame tay.) */

/* ===== MOB_SHEETS zombie rows (GIỮ ĐỒNG BỘ với game.ts MOB_SHEETS) ======= */
const Z_ROWS = {
  atk:  { right: [0, 4], up: [3, 5], down: [6, 4] },
  walk: { right: [1, 4], up: [4, 4], down: [7, 4] },
  idle: { right: [2, 2], up: [5, 2], down: [8, 2] },
};

/* ===== LAB SERVER (web_api/core.py shape) =============================== */
let castT0 = 0;
let flightMs = 1445;
let lastServerDmg = 18;
let lastCritical = false;
let resolveDeadline: number | null = null;
let resolvePayload: (() => void) | null = null;

/* ===== CASTER STATE ===================================================== */
let sceneRef: Phaser.Scene | null = null;
let casterDoll: PaperdollBody | null = null;
let casterX = CASTER_SPAWN.x; // tile float (server space)
let casterY = CASTER_SPAWN.y;
let casterFrameDir = "S"; // game direction string (paperdoll DIR_SUFFIX)
let spellSelected = 0;

// MANIFEST THẬT (cùng shape với assets/players/players_manifest.json):
const PlayersManifestLike = {
  base: { file: "base.png", frame_w: 32, frame_h: 32, cols: 4, rows: 12, offset_x: -8, offset_y: -32 },
  weapons: { stick: { file: "weapon/stick.png", frame_w: 48, frame_h: 48, cols: 4, rows: 9, offset_x: -8, offset_y: -24 } },
  rows: { idle_down: 0, idle_right: 1, idle_up: 2, walk_down: 3, walk_right: 4, walk_up: 5, atk_down: 6, atk_right: 7, atk_up: 8 },
  frames_per_row: 4,
  speeds: { idle: 250, walk: 120, atk: 50 },
  scale: 2,
} as unknown as PlayersManifest;

// đăng ký pd-base + weapon sheet BÊN TRONG create qua registerPaperdollTextures
// của game — 1 path duy nhất cho caster + weapon.

/* ===== ZOMBIE =========================================================== */
interface LabZombie {
  container: Phaser.GameObjects.Container;
  body: Phaser.GameObjects.Sprite;
  hp: number; hpMax: number;
  xF: number; yF: number;
  anim: "idle" | "walk" | "atk";
  dir: "N" | "S" | "E" | "W" | "NE" | "NW" | "SE" | "SW"; // game facing field (8 hướng)
  frame: number;
  frameT0: number;
  hpFill: Phaser.GameObjects.Rectangle;
  /* SHAKE chỉ là hiển thị: offset cộng mỗi frame, KHÔNG đổi xF/yF (nguồn
   * sự thật) — vi phạm này trắng trước đây chính là "hitbox lệch model" */
  stunOffset: number;
  baseBodyX: number;
}

let zombie: LabZombie | null = null;

/* ===== TOMB / BIA MỘ (user 13/10: chết → hoá mộ, đồ rơi vào rương mộ,
 * quay lại chỗ chết mở rương lấy lại đồ). Sprite tách từ
 * assets/maps/mộ.json — tile gid=68 của [Base]BaseChip_pipo.png
 * (col=(68-1)%8=3, row=(68-1)//8=8) — đã extract sẵn thành
 * fx/tombstone.png (public dir).
 */
interface LabTomb {
  x: number; y: number;            // tile (nguyên)
  items: string[];                 // đồ rơi vào rương mộ
  sprite: Phaser.GameObjects.Image;
  hint: Phaser.GameObjects.Text;
}
let tomb: LabTomb | null = null;

const DEMO_BAG = ["wood", "stone", "berry", "sword"];

function killCaster(): void {
  const sc = sceneRef; if (!sc) return;
  // ĐỒ RƠI: toàn bộ bag demo → rương mộ.
  const items = tomb ? DEMO_BAG.slice() : DEMO_BAG.slice();
  const tx = Math.floor(casterX), ty = Math.floor(casterY);
  // Mộ KHÔNG chặn player (đi qua được — không thêm collision, đơn giản nhất).
  if (tomb) { tomb.sprite.destroy(); tomb.hint.destroy(); }
  const sprite = sc.add.image((tx + 0.5) * TILE, (ty + 0.9) * TILE, "tombstone")
    // PNG extract ở 64px (upscale 2x cho nét) → scale 0.5 để vẽ đúng xấp xỉ
    // chiều cao player (32px * ~1.5 = bia mộ hơi cao hơn đầu ngực là hợp lý).
    .setDepth(4).setScale(TILE / 64);
  const hint = sc.add.text((tx + 0.5) * TILE, (ty + 0.9) * TILE - 40,
    tomb ? "Bia mộ cũ " : "Mộ (F: lấy đồ)", {
      fontFamily: "monospace", fontSize: "9px", color: "#e8e8e8",
      stroke: "#000", strokeThickness: 2,
    }).setOrigin(0.5).setDepth(6);
  tomb = { x: tx, y: ty, items, sprite, hint };
  log(`☠️ Chết tại (${tx},${ty}) — ${items.length} món rơi vào rương mộ.`);
  // Respawn về điểm xuất phát (game parity: _schedule_respawn).
  casterX = CASTER_SPAWN.x; casterY = CASTER_SPAWN.y;
}

function openTomb(): void {
  if (!tomb || tomb.items.length === 0) return;
  const got = tomb.items.slice();
  tomb.items = [];
  tomb.hint.setText("Mộ (trống)");
  log(`📦 Lấy lại từ mộ: ${got.join(", ")}`);
  const sc = sceneRef;
  if (sc) {
    const t = sc.add.text((tomb.x + 0.5) * TILE, tomb.y * TILE - 8,
      `+${got.length} món`, {
        fontFamily: "monospace", fontSize: "13px", color: "#7dffa0",
        stroke: "#000", strokeThickness: 3,
      }).setOrigin(0.5).setDepth(30);
    sc.tweens.add({ targets: t, y: t.y - 30, alpha: 0, duration: 1200, onComplete: () => t.destroy() });
  }
}

/* PORT NGUYÊN game.ts zombieRowFacing + zombieFlipX (user 13/10 "làm kỹ
 * lại"): Kaetram KHÔNG ship hàng left — W/NW/SW = hàng right + flipX. Đoạn
 * trước đây tự chế dir="right" làm mob quay sai khi đi ngang. */
function zombieRowFacing(facing: LabZombie["dir"]): "right" | "up" | "down" {
  const f = (facing || "S").toUpperCase();
  if (f === "N" || f === "NE" || f === "NW") return "up";
  if (f === "E" || f === "NE" || f === "SE") return "right";
  return "down"; // S, SE, SW
}
function zombieFlipX(facing: LabZombie["dir"]): boolean {
  const f = (facing || "S").toUpperCase();
  return f === "W" || f === "NW" || f === "SW";
}

/* Vector -> 8 hướng facing (game style): N/S/E/W khi 1 trục trội hẵn
 * (>2×), ngược lại là diagonal — mob quay tự nhiên khi đi chéo. */
function facingTo(ux: number, uy: number): LabZombie["dir"] {
  const horiz = Math.abs(ux) > 2 * Math.abs(uy);
  const vert = Math.abs(uy) > 2 * Math.abs(ux);
  const ns = uy > 0 ? "S" : "N";
  const ew = ux > 0 ? "E" : "W";
  if (horiz) return ew;
  if (vert) return ns;
  return (ns === "S" ? "S" : "N") + (ew === "E" ? "E" : "W") as LabZombie["dir"];
}

function animateZombie(z: LabZombie, now: number): void {
  if (!z.body) return;
  const fx = zombieFlipX(z.dir);
  const facing = zombieRowFacing(z.dir);
  const rowPair = Z_ROWS[z.anim][facing] as unknown as [number, number];
  const [row, len] = rowPair;
  const pace = z.anim === "atk" ? 90 : z.anim === "walk" ? 160 : 500;
  if (now - z.frameT0 >= pace) {
    z.frameT0 = now;
    z.frame = z.anim === "atk"
      ? Math.min(len - 1, z.frame + 1)
      : (z.frame + 1) % Math.max(1, len);
  }
  const tex = z.body.texture;
  const perRow = Math.max(4, Math.floor(tex.source[0].width / 32));
  z.body.setFrame(row * perRow + z.frame);  z.body.setFlipX(fx);
}

/* ===== DAMAGE FX (giữ từ v1) ============================================ */
function spawnDamageNumber(xPx: number, yPx: number, amount: number, critical: boolean): void {
  const sc = sceneRef; if (!sc) return;
  const t = sc.add.text(xPx, yPx - 30, `-${amount}`, {
    fontFamily: "monospace", fontSize: critical ? "20px" : "15px",
    color: critical ? "#ffd400" : "#ff4444", stroke: "#000", strokeThickness: 3,
  }).setOrigin(0.5).setDepth(30);
  sc.tweens.add({ targets: t, y: yPx - 62, alpha: 0, duration: critical ? 1100 : 900, onComplete: () => t.destroy() });
}
function spawnStunFx(): void {
  const sc = sceneRef;
  if (!sc || !zombie) return;
  const zz = zombie;
  let count = 0;
  const blink = setInterval(() => {
    if (!zz.body || count >= 6) {
      clearInterval(blink);
      zz.body?.clearTint();
      zz.stunOffset = 0; // reset shake — update loop re-pins position mỗi frame
      if (zz.body) zz.body.x = zz.baseBodyX; // restore body x
      return;
    }
    zz.body.setTint(count % 2 === 0 ? 0xff6655 : 0xffffff); count++;
  }, 70);
  // SHAKE QUA stunOffset (giới hạn 300ms): update loop mỗi frame cộng offset
  // này vào container — KHÔNG đụng xF/yF (nguồn sự thật). Hết = 0.
  zz.stunOffset = 3;
  setTimeout(() => { zz.stunOffset = 0; }, 300);
  // ST text bám float pos: dùng anchor từ xF,yF tại thời điểm hit
  const sx = zz.xF * TILE, sy = zz.yF * TILE;
  const st = sc.add.text(sx, sy - 46, "ST", {
    fontFamily: "monospace", fontSize: "11px", color: "#66ddff", stroke: "#000", strokeThickness: 2,
  }).setOrigin(0.5).setDepth(30);
  sc.tweens.add({ targets: st, y: st.y - 10, alpha: 0, duration: 700, onComplete: () => st.destroy() });
}

/* ===== INPUT ============================================================ */
const keys = new Set<string>();
window.addEventListener("keydown", (e) => {
  keys.add(e.code);
  if (e.code === "Tab") { e.preventDefault(); cycleSpell(); }
  if (e.code === "KeyF") {
    if (tomb && Math.hypot(casterX - (tomb.x + 0.5), casterY - (tomb.y + 0.5)) <= 1.6) openTomb();
  }
  if (e.code === "KeyK") killCaster(); // K = tự chết để test mộ
});
window.addEventListener("keyup", (e) => keys.delete(e.code));

// Panel buttons (lab.html): test mộ bằng nút thay vì nhớ phím.
document.getElementById("btnDie")?.addEventListener("click", () => killCaster());
document.getElementById("btnOpenTomb")?.addEventListener("click", () => {
  if (!tomb) { log("Chưa có mộ nào. Bấm ☠️ Chết trước."); return; }
  if (Math.hypot(casterX - (tomb.x + 0.5), casterY - (tomb.y + 0.5)) > 1.6) {
    log(`Mộ ở (${tomb.x},${tomb.y}) — đi lại gần rồi mở.`); return;
  }
  openTomb();
});

function cycleSpell(): void {
  const sel = document.getElementById("spellSelect") as HTMLSelectElement | null;
  if (!sel) return;
  sel.selectedIndex = (sel.selectedIndex + 1) % sel.options.length;
  spellSelected = sel.selectedIndex;
  log(`Spell: ${sel.options[spellSelected].text}`);
}

/* ===== GAME LOOP (20Hz-like) =========================================== */
const MOVE_MS_PER_TILE = 400; // ~2.5 tiles/s (game walk par)
let lastTick = performance.now();

function isWalkable(tx: number, ty: number): boolean {
  if (tx < 0 || ty < 0 || tx >= MAP_W || ty >= MAP_H) return false;
  return true;
}

/* ===== BOOT ============================================================ */
new Phaser.Game({
  type: Phaser.AUTO,
  parent: "stage",
  width: MAP_W * TILE,
  height: MAP_H * TILE,
  pixelArt: true,
  backgroundColor: "#182a1a",
  scene: {
    preload(this: Phaser.Scene) {
      // SHEET THẬT của game (public dir — cùng bytes với assets/)
      this.load.spritesheet("mob-zombie", "mobs/zombie.png", { frameWidth: 32, frameHeight: 32 });
      this.load.spritesheet("pd-base", "players-base.png", { frameWidth: 32, frameHeight: 32 });
      this.load.spritesheet("pd-stick", "weapon-stick.png", { frameWidth: 48, frameHeight: 48 });
      this.load.image("tombstone", "fx/tombstone.png");
    },
    create(this: Phaser.Scene) {
      const sc = this;
      sceneRef = sc;
      (sc as unknown as { tilePx: number }).tilePx = TILE;
      spellEngine.attach(sc);
      spellEngine.loadTextures(def);

      // Grid thảo nguyên (checkerboard) — thấy di chuyển rõ
      const g = sc.add.graphics();
      for (let y = 0; y < MAP_H; y++)
        for (let x = 0; x < MAP_W; x++) {
          g.fillStyle((x + y) % 2 === 0 ? 0x224422 : 0x1c3a1c, 1);
          g.fillRect(x * TILE, y * TILE, TILE, TILE);
        }

      // CASTER = PaperdollBody THẬT của game: đăng ký sheet CO GIỐNG game
      // (registerPaperdollTextures nhận Uint8Array — lab dùng fetch công khai).
      const toBytes = async (url: string): Promise<Uint8Array> =>
        new Uint8Array(await (await fetch(url)).arrayBuffer());
      void (async () => {
        const baseB = await toBytes("players-base.png");
        const stickB = await toBytes("weapon-stick.png");
        registerPaperdollTextures(sc, PlayersManifestLike, baseB, {});
        registerWeaponSheet(sc, PlayersManifestLike, "stick", stickB);
        casterDoll = new PaperdollBody(sc, PlayersManifestLike);
        casterDoll.spawn((casterX + 0.5) * TILE, (casterY + 0.5) * TILE, 7);
        casterDoll.setWeapon("stick"); // cây gậy (weapon sheet lab)
      })();

      // ZOMBIE — spawn cách caster 4 ô (zombienear parity)
      zombie = createZombie(sc);

      sc.input.on("pointerdown", (p: Phaser.Input.Pointer) => {
        castAt(Math.floor(p.x / TILE), Math.floor(p.y / TILE));
      });

      const sel = document.getElementById("spellSelect") as HTMLSelectElement | null;
      if (sel) spellSelected = sel.selectedIndex;
      log("WASD di chuyển • Tab đổi spell • click cast");
    },
    update() {
      const now = performance.now();
      const dtMs = Math.min(80, now - lastTick);
      lastTick = now;

      // --- MOVE (WASD/arrows như input.ts MOVE_KEYS) ---
      const vx = (keys.has("KeyD") || keys.has("ArrowRight") ? 1 : 0) - (keys.has("KeyA") || keys.has("ArrowLeft") ? 1 : 0);
      const vy = (keys.has("KeyS") || keys.has("ArrowDown") ? 1 : 0) - (keys.has("KeyW") || keys.has("ArrowUp") ? 1 : 0);
      const moving = vx !== 0 || vy !== 0;
      if (moving) {
        const tiles = dtMs / MOVE_MS_PER_TILE;
        const nx = casterX + vx * tiles, ny = casterY + vy * tiles;
        // apply_move parity: per-axis walkable gate
        if (isWalkable(Math.floor(nx), Math.floor(casterY))) casterX = nx;
        if (isWalkable(Math.floor(casterX), Math.floor(ny))) casterY = ny;
        // facing字符串 như game (DIR_SUFFIX): S/N/E/W... chọn giống mob facingTo
        casterFrameDir = facingTo(vx, vy); // dùng ux= vx, uy= vy
      }

      if (casterDoll) {
        // animate(x, y, action, dir, now) — PaperdollBody tự lo khung px
        // feet-anchor (như spawnSelfDoll + update remote dolls của game):
        casterDoll.animate(
          (casterX + 0.5) * TILE,
          (casterY + 0.5) * TILE,
          moving ? "walk" : "idle",
          casterFrameDir,
          now,
        );
      }

      // --- ZOMBIE chase-walk khi caster gần (hunter parity) ---
      if (zombie) {
          const d = Math.hypot(casterX - zombie.xF, casterY - zombie.yF);
        const zz = zombie;
        // facing 8 hướng như game (apply turn/face): chọn dominant axis
        // + diagonal khi cả |ux| và |uy| đáng kể
        if (d <= 1.6) {
          zz.dir = facingTo(casterX - zz.xF, casterY - zz.yF);
          if (zz.anim !== "atk") { zz.frame = 0; zz.anim = "atk"; zz.frameT0 = now; }
        } else if (d < 8) {
          const sp = 2.2 * (dtMs / 1000); // 2.2 ô/s — game hunter speed band
          const ux = (casterX - zz.xF) / d, uy = (casterY - zz.yF) / d;
          zz.xF += ux * sp; zz.yF += uy * sp;
          zz.dir = facingTo(ux, uy);
          if (zz.anim !== "walk") { zz.frame = 0; zz.anim = "walk"; zz.frameT0 = now; }
        } else if (zz.anim !== "idle") {
          zz.frame = 0; zz.anim = "idle"; zz.frameT0 = now;
        }
        // MỖI frame: container = float pos × TILE (+ shake offset nếu stun) —
        // một nguồn sự thật duy nhất (xF/yF); shake KHÔNG được cộng dồn.
        zz.container.setPosition(zz.xF * TILE + zz.stunOffset, zz.yF * TILE);
        // body lúc nào cũng ở offset gốc trong container (mỗi frame re-pin
        // vì stun blink chỉnh x tay thò frag:
        zz.body.x = zz.baseBodyX;
        animateZombie(zz, now);
      }

      // --- resolve_pending_spells moment (lab server paced) ---
      if (resolveDeadline !== null && performance.now() >= resolveDeadline) {
        const cb = resolvePayload;
        resolveDeadline = null; resolvePayload = null;
        cb?.();
      }
    },
  },
});

function createZombie(sc: Phaser.Scene): LabZombie {
  const zt = { x: CASTER_SPAWN.x + 4, y: CASTER_SPAWN.y };
  const container = sc.add.container(zt.x * TILE, zt.y * TILE);
  const body = sc.add.sprite(0, TILE / 2 - 24, "mob-zombie");
  body.setScale(48 / 32);
  container.add(body);
  container.setDepth(5);
  const barBg = sc.add.rectangle(0, TILE / 2 - 34, 30, 4, 0x220a0a).setOrigin(0.5);
  const barFill = sc.add.rectangle(0, TILE / 2 - 34, 28, 2.5, 0xd83030).setOrigin(0.5);
  container.add([barBg, barFill]);
  const z: LabZombie = {
    container, body, hp: 100, hpMax: 100,
    xF: zt.x + 0.5, yF: zt.y + 0.5, anim: "idle", dir: "S",
    frame: 0, frameT0: performance.now(), hpFill: barFill,
    stunOffset: 0, baseBodyX: 0,
  };
  z.baseBodyX = body.x; // vị trí body gốc trong container (re-pin mỗi frame)
  return z;
}

/* ===== CAST ============================================================ */
function castAt(tx: number, ty: number): void {
  const sc = sceneRef;
  if (!sc || !zombie) return;
  const spellNames = ["Vận chiêu đá", "Khúc gỗ bay (chưa engine)", "Đạn bóng tối (chưa engine)"];
  if (spellSelected !== 0) {
    log(`"${spellNames[spellSelected]}" — chưa port qua engine. Tab đổi về Vận chiêu đá.`);
    return;
  }
  castT0 = performance.now();
  flightMs = Number((document.getElementById("flightMs") as HTMLInputElement).value);
  def.liftMs = Number((document.getElementById("liftMs") as HTMLInputElement).value);
  spellEngine.impactVfx = (document.getElementById("chkImpact") as HTMLInputElement)?.checked ?? false;

  // swing: PaperdollBody.swing() plays the atk rows ONCE (one-shot, owned
  // by the class — same as the game's combatSwing path).
  casterDoll?.swing(performance.now());

  spellEngine.cast(def, { x: (casterX + 0.5) * TILE, y: (casterY + 0.5) * TILE }, { x: tx, y: ty });

  /* HIT-TEST TẠI IMPACT (fix "dejavu"): boss đi từ A→B trong khi đá đang bay,
   * ném A mà resolve giờ theo vị trí CAST thì mob đã đi rồi → "đá trúng
   * đường đi quá khứ". ĐỜN GIỐNG game thật: apply_spell cast-time CHỈ
   * schedule; resolve_pending_spells applies dmg khi flight DUE — tức
   * là lúc đá CHẠM,외 vị trí mob HIỆN TẠI. Lab giờ giữ ảnh hưởng hit-test
   * đến khi toolbox: đo khoảng cách (tx,ty)のも mob HIỆN TẠI tại mốc impact. */
  const radius = (def.impactRadiusPx ?? 40) / TILE;
  resolveDeadline = castT0 + flightMs + 60; // +60ms = pending → tick 20Hz push
  tlEl.textContent = "flight " + flightMs + "ms — hit-check at impact…";
  resolvePayload = () => {
      if (!zombie) return;
      // ================= HIT-CHECK TẠI ĐIỂM ĐÁ CHẠM =================
      // Khoảng cách (tx,ty) vs vị trí mob HIỆN TẠI (vừa di chuyển qua
      // flightMs ms) — mob trượt khỏi bán kính thì TRƯỢT thật.
      const nowDx = (tx + 0.5) - zombie.xF;
      const nowDy = (ty + 0.5) - zombie.yF;
      const nowD2 = Math.hypot(nowDx, nowDy);
      if (nowD2 > radius) {
        // MOB ĐI KHỎI trước khi đá tới — đón kết quả "đá rơi đất".
        tlEl.textContent = "TRƯỢT — mob rời điểm ném trước khi đá chạm (" + nowD2.toFixed(2) + "> " + radius.toFixed(2) + ")";
        log("TRƯỢT: mob đi tiếp trong lúc đá bay — KHÔNG dmg.");
        return;
      }
      // CRIT + variance roll LÚC RESOLVE (giống apply_spell cast thật:
      // roll giữ trong pending_spells — lab giả hoạt cùng shape)
      lastCritical = Math.random() < 0.15;
      lastServerDmg = 15 + Math.floor(Math.random() * 9);
      if (lastCritical) lastServerDmg = Math.round(lastServerDmg * 1.5);
      setTimeout(() => {
        spellEngine.notifyServerImpact(tx, ty, flightMs);
      }, 0);
      zombie.hp = Math.max(0, zombie.hp - lastServerDmg);
      zombie.hpFill.width = 28 * zombie.hp / zombie.hpMax;
      // Anchor dmg = FLOAT POS của mob (xF,yF) × TILE tại mốc hit —
      // số bám đúng chỗ mob đang đứng, kể cả khi mob đang di chuyển.
      spawnDamageNumber(zombie.xF * TILE, zombie.yF * TILE, lastServerDmg, lastCritical);
      spawnStunFx();
      tlEl.textContent = `CAST 0ms → SERVER ${flightMs}ms → dmg ${lastServerDmg}${lastCritical ? " (CRIT)" : ""}`;
      if (zombie.hp <= 0) log("Mob CHẾT.");
    };
}
