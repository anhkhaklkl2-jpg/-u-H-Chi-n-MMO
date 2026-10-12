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
import Phaser from "phaser";
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

function log(s: string): void { logEl.textContent = s; }

/* ===== PAPERDOLL MANIFEST CONSTANTS (giữ đồng bộ players_manifest.json) === */
const PD_FRAMES_PER_ROW = 4;
const PD_SPEEDS = { idle: 250, walk: 120, atk: 50 };
const PD_BODY_OFFSET = { x: -8, y: -32 };
const STICK_OFFSET = { x: -8, y: -24 };
// manifest rows: idle_down 0 idle_right 1 idle_up 2 walk_down 3 walk_right 4
// walk_up 5 atk_down 6 atk_right 7 atk_up 8
function pdRow(anim: "idle" | "walk" | "atk", dir: "down" | "up" | "side"): number {
  const map = { idle: [0, 1, 2], walk: [3, 4, 5], atk: [6, 7, 8] } as const;
  const order: ("down" | "side" | "up")[] = ["down", "side", "up"];
  return map[anim][order.indexOf(dir)];
}

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
let casterBody: Phaser.GameObjects.Sprite | null = null;
let casterStick: Phaser.GameObjects.Sprite | null = null;
let casterX = CASTER_SPAWN.x; // tile float (server space)
let casterY = CASTER_SPAWN.y;
let casterAnim: "idle" | "walk" | "atk" = "idle";
let casterDir: "down" | "up" | "left" | "right" = "down";
let casterFrameT0 = performance.now();
let casterAtkEndsAt = 0;
let spellSelected = 0;

function pushCasterFrame(now: number): void {
  if (!casterBody || !casterStick) return;
  const dirKey: "down" | "up" | "side" =
    casterDir === "up" ? "up" : casterDir === "down" ? "down" : "side";
  const row = pdRow(casterAnim, dirKey);
  const speed = PD_SPEEDS[casterAnim] ?? 250;
  const frame = Math.floor((now - casterFrameT0) / speed) % PD_FRAMES_PER_ROW;
  casterBody.setFrame(row * PD_FRAMES_PER_ROW + frame);
  casterBody.setFlipX(casterDir === "left");
  // weapon layer: cùng frame index → rocklift swing khớp tay (Kaetram parity)
  casterStick.setFrame(row * PD_FRAMES_PER_ROW + frame);
  casterStick.setFlipX(casterDir === "left");
}

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
});
window.addEventListener("keyup", (e) => keys.delete(e.code));

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

      // CASTER body + weapon layer (PaperdollBody shape)
      casterBody = sc.add.sprite(0, 0, "pd-base").setDepth(6);
      casterStick = sc.add.sprite(0, 0, "pd-stick").setDepth(7);
      pushCasterFrame(performance.now());

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
      if (moving && casterAnim !== "atk") {
        const tiles = dtMs / MOVE_MS_PER_TILE;
        const nx = casterX + vx * tiles, ny = casterY + vy * tiles;
        // apply_move parity: per-axis walkable gate
        if (isWalkable(Math.floor(nx), Math.floor(casterY))) casterX = nx;
        if (isWalkable(Math.floor(casterX), Math.floor(ny))) casterY = ny;
        casterDir = vx < 0 ? "left" : vx > 0 ? "right" : (vy > 0 ? "down" : "up");
        if (casterAnim !== "walk") { casterAnim = "walk"; casterFrameT0 = now; }
      } else if (!moving && casterAnim === "walk") {
        casterAnim = "idle"; casterFrameT0 = now;
      }
      if (casterAtkEndsAt && now > casterAtkEndsAt) {
        casterAtkEndsAt = 0; casterAnim = "idle"; casterFrameT0 = now;
      }

      if (casterBody && casterStick) {
        // getSelfPos production: (tile + 0.5) * tilePx. Paperdoll sprite
        // origin TRÊN-TRÁI với offset (-8,-32) — nghĩa là sprite vẽ 32×32
        // frame nên tâm BASE = px+8, py+16 (32px frame gốc).
        const px = (casterX + 0.5) * TILE, py = (casterY + 0.5) * TILE;
        casterBody.setPosition(px + PD_BODY_OFFSET.x, py + PD_BODY_OFFSET.y);
        casterStick.setPosition(px + STICK_OFFSET.x, py + STICK_OFFSET.y);
        pushCasterFrame(now);
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
  const spellNames = ["Vận chiêu đá", "Khúc gỗ bay (engine?", "Đạn bóng tối (engine?)"];
  if (spellSelected !== 0) {
    log(`"${spellNames[spellSelected]}" — chưa port qua engine. Tab đổi về Vận chiêu đá.`);
    return;
  }
  castT0 = performance.now();
  flightMs = Number((document.getElementById("flightMs") as HTMLInputElement).value);
  def.liftMs = Number((document.getElementById("liftMs") as HTMLInputElement).value);
  spellEngine.impactVfx = (document.getElementById("chkImpact") as HTMLInputElement)?.checked ?? false;

  // swing anim (atk — 50ms x 4 frame như manifest)
  casterAnim = "atk"; casterFrameT0 = performance.now();
  casterAtkEndsAt = performance.now() + PD_SPEEDS.atk * PD_FRAMES_PER_ROW;

  // HIT-TEST như apply_spell: mob nằm trong impact radius của điểm click
  const mobCx = zombie.xF, mobCy = zombie.yF;
  const dTiles = Math.hypot(tx + 0.5 - mobCx, ty + 0.5 - mobCy);
  const hit = dTiles <= (def.impactRadiusPx ?? 40) / TILE;

  spellEngine.cast(def, { x: (casterX + 0.5) * TILE, y: (casterY + 0.5) * TILE }, { x: tx, y: ty });

  if (hit) {
    // lab server: action_result echo 30ms → resolve deadline = impact_delay
    lastCritical = Math.random() < 0.15;
    lastServerDmg = 15 + Math.floor(Math.random() * 9);
    if (lastCritical) lastServerDmg = Math.round(lastServerDmg * 1.5);
    setTimeout(() => {
      spellEngine.notifyServerImpact(tx, ty, flightMs);
      log(`action_result: impact_delay_ms=${flightMs}, dmg=${lastServerDmg}${lastCritical ? " CRIT" : ""}`);
    }, 30);
    resolveDeadline = castT0 + flightMs + 60; // +60ms = pending → tick 20Hz push
    tlEl.textContent = `CAST 0ms → SERVER ${flightMs}ms → dmg ${lastServerDmg}${lastCritical ? " (CRIT)" : ""}`;
    resolvePayload = () => {
      if (!zombie) return;
      zombie.hp = Math.max(0, zombie.hp - lastServerDmg);
      zombie.hpFill.width = 28 * zombie.hp / zombie.hpMax;
      // Anchor dmg = FLOAT POS của mob (xF,yF) × TILE — KHÔNG phải container.x
      // (nó có thể đang shake lệch) — số damage luôn bám đúng chỗ mob đứng
      // tại thời điểm hit, kể cả khi mob đang di chuyển.
      spawnDamageNumber(zombie.xF * TILE, zombie.yF * TILE, lastServerDmg, lastCritical);
      spawnStunFx();
      if (zombie.hp <= 0) log("Mob CHẾT.");
    };
  } else {
    log(`TRƯỢT: ném tại (${tx},${ty}) — mob ở (${mobCx - 0.5},${mobCy - 0.5}) ngoài tầm nổ.`);
    tlEl.textContent = "TRƯỢT — KHÔNG dmg";
  }
}
