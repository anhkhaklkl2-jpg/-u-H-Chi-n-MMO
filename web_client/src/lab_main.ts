// SPELL LAB — không gian làm việc spell (user 12/10).
// IMPORT ENGINE THẬT của game: fix ở đây = fix src/spell_engine.ts luôn,
// build lại 1 phát là game thật ăn ngay (không có bước "đem qua").
//
// Mô phỏng server GIỐNG GAME REAL:
//  - snapshot 20Hz push zombie (x, y, hp) — mob đứng im hoặc lerp nhẹ
//    (cùng cơ chế buf[] mà game.ts dùng để nội suy việc đi).
//  - action_result spell trả về sau RTT 30ms với impact_delay_ms
//    (giống web_api/_local_game_stack echo).
//  - hp giảm đúng mốc impact_delay_ms sau cast (resolve_pending_spells) —
//    tick snapshot 20Hz mới nhận hp mới, không sớm hơn.
//
// MOB: sprite thật (mobs/zombie.png, sheet 9 hàng như Kaetram), cut cell
// giống applyMobCell của game.ts — texture registry "mob-zombie".
import Phaser from "phaser";
import { spellEngine } from "./spell_engine";
import { SPELL_ENGINE_DEFS, type SpellDef } from "./spell_defs";

const TILE = 16;

const defIn = SPELL_ENGINE_DEFS.find((d) => d.id === "rocklift");
if (!defIn) throw new Error("rocklift def missing");
const def: SpellDef = { ...defIn };

const logEl = document.getElementById("log") as HTMLElement;
const tlEl = document.getElementById("timeline") as HTMLElement;

let tickOn = true;
let castT0 = 0;
let flightMs = 1800;
let hitDone = false;
let zombieHp = 100;
let zombieHpShown = 100;

interface LabZombie {
  container: Phaser.GameObjects.Container;
  body: Phaser.GameObjects.Image;
  barFill: Phaser.GameObjects.Rectangle;
  barBg: Phaser.GameObjects.Rectangle;
  hp: number;
  hpMax: number;
  x: number; // tile
  y: number; // tile
}

let sceneRef: Phaser.Scene | null = null;

/** Floating damage/splat number over the mob: GameObjects.Text trôi lên
 *  rồi mờ dần — như hitsplat của game (web client dùng DOM splat nhưng lab
 *  vẽ trong canvas cho dễ xem). CHỈ HIỆN KHI resolve_pending_spells CHẠM
 *  (đúng lúc hp giảm) — nhìn là biết NGAY khi nào đã gây dmg.
 *  critical=true → chữ TO hơn, màu vàng đậm như splat crit của game. */
function spawnDamageNumber(xPx: number, yPx: number,
                           amount: number, critical: boolean): void {
  const sc = sceneRef;
  if (!sc) return;
  const crit = !!critical && amount > 0;
  const t = sc.add.text(xPx, yPx - 30,
    (amount > 0 ? `-${amount}` : "ST"),
    {
      fontFamily: "monospace",
      fontSize: crit ? "20px" : "15px",
      color: crit ? "#ffd400" : "#ff4444",
      stroke: "#000000",
      strokeThickness: 3,
    }).setOrigin(0.5).setDepth(20);
  sc.tweens.add({
    targets: t,
    y: yPx - 62,
    alpha: 0,
    duration: crit ? 1100 : 900,
    ease: "Cubic.easeOut",
    onComplete: () => t.destroy(),
  });
}

/** STUN EFFECT trên mob (user 12/10): nhấp nháy đỏ lắc nhẹ + chữ "ST" bay lên
 *  — nhìn là biết MOB vừa bị stun/đe dmg. SERVER THẬT của game KHÔNG stun
 *  (mode projectile chỉ damage) — đây CHỈ HIỆU ỨNG HIỂN THỊ trên quái,
 *  không đụng logic game. */
function spawnStunFx(): void {
  const sc = sceneRef;
  if (!z || !sc) return;
  const zz = z;
  // chữ "ST" trên đầu mob (user 12/10: hiện ST lên để bik lúc nào bị hit)
  const st = sc.add.text(zz.container.x, zz.container.y - 46, "ST", {
    fontFamily: "monospace", fontSize: "11px", color: "#66ddff",
    stroke: "#000000", strokeThickness: 2,
  }).setOrigin(0.5).setDepth(20);
  sc.tweens.add({
    targets: st,
    y: st.y - 10,
    alpha: 0,
    duration: 700,
    onComplete: () => st.destroy(),
  });
  // nhấp nháy đỏ: tint body 3 lần nhanh (fluxHitFX game-style)
  let count = 0;
  const blink = setInterval(() => {
    if (!zz.body || count >= 6) {
      clearInterval(blink);
      zz.body.clearTint();
      return;
    }
    zz.body.setTint(count % 2 === 0 ? 0xff6655 : 0xffffff);
    count++;
  }, 70);
  // lắc ngang nhẹ (shake container)
  sc.tweens.add({
    targets: zz.container,
    x: zz.container.x + 3,
    duration: 55,
    yoyo: true,
    repeat: 3,
    ease: "Sine.easeInOut",
  });
}

function healMob(): void {
  if (!z) return;
  zombieHp = z.hpMax;
  z.barFill.width = 28;
  const sc = sceneRef;
  if (sc) {
    const t = sc.add.text(
      z.container.x, z.container.y - 30, "+100", {
        fontFamily: "monospace", fontSize: "15px", color: "#44ff88",
        stroke: "#000000", strokeThickness: 3,
      }).setOrigin(0.5).setDepth(20);
    sc.tweens.add({
      targets: t,
      y: t.y - 30,
      alpha: 0,
      duration: 900,
      onComplete: () => t.destroy(),
    });
  }
  log(`Hồi máu mob: hp → ${zombieHp}`);
}

let z: LabZombie | null = null;

function log(s: string): void {
  logEl.textContent = s;
}

function pushTimeline(): void {
  if (castT0 === 0) {
    tlEl.textContent = "timeline: —";
    return;
  }
  const castEl = 0;
  const hpMs = hitDone && zombieHpShownMs !== null ? (zombieHpShownMs - castT0) : -1;
  tlEl.textContent =
    `CAST ${castEl}ms → CHẠM ${flightMs}ms → HP ${hpMs >= 0 ? hpMs.toFixed(0) + "ms" : "…"} ` +
    `(trê HP−CHẠM: ${hpMs >= 0 ? ((zombieHpShownMs! - castT0 - flightMs).toFixed(0) + "ms ✅") : "—"}`;
}

let zombieHpShownMs: number | null = null;
let lastDmgAmount = 18; // mirror của dmg server vừa resolve (variance lab = flat 18)
let lastDmgCritical = false; // critical flag để màu số đậm (đồng bộ action_result.critical)
let lastCastHit = false; // kết quả hit-test của cast đang bay

new Phaser.Game({
  type: Phaser.AUTO,
  parent: "stage",
  width: 480,
  height: 270,
  pixelArt: true,
  backgroundColor: "#1c2430",
  scene: {
    preload(this: Phaser.Scene) {
      // Texture THẬT của game (mobs/zombie.png, public dir) — cùng đường
      // chính main.ts fetchAsset("mobs/zombie.png") sản xuất sẽ nạp.
      this.load.spritesheet("mob-zombie", "mobs/zombie.png", {
        frameWidth: 32,
        frameHeight: 32,
      });
    },
    create(this: Phaser.Scene) {
      const sc = this;
      sceneRef = sc;
      (sc as unknown as { tilePx: number }).tilePx = TILE;
      spellEngine.attach(sc);
      spellEngine.loadTextures(def);

      // Caster: ô xanh đứng yên (thay player doll)
      const g = sc.add.graphics();
      g.fillStyle(0x44ffaa, 1);
      g.fillRect(60, 120, 12, 16);

      // ZOMBIE REAL: container + image cut cell (idle.down row 8, frame 0)
      // — cùng cách game.ts syncZombies dựng mob từ sheet.
      const cx = 9 * TILE; // mob ở tile (9, 4)
      const cy = 4 * TILE;
      const container = sc.add.container(cx, cy);
      const body = sc.add.image(0, TILE / 2 - 48 / 2, "mob-zombie");
      body.setOrigin(0.5);
      // applyMobCell MMO: frame = row * perRow + col; scale = size / cellH
      const tex = sc.textures.get("mob-zombie");
      const perRow = Math.max(1, Math.floor(tex.source[0].width / 32));
      body.setFrame(8 * perRow + 0); // idle.down[0] của sheet zombie
      body.setScale(48 / 32);
      container.add(body);
      container.setDepth(5);

      // HP bar đơn giản (không anti-hero pack — lab minh hoạ đủ)
      const barY = TILE / 2 - 24 - 10;
      const barBg = sc.add.rectangle(0, barY, 30, 4, 0x220a0a).setOrigin(0.5);
      const barFill = sc.add.rectangle(0, barY, 28, 2.5, 0xd83030).setOrigin(0.5);
      container.add([barBg, barFill]);
      z = { container, body, barFill, barBg, hp: 100, hpMax: 100, x: 9, y: 4 };

      sc.input.on("pointerdown", (p: Phaser.Input.Pointer) => {
        castAt(Math.floor(p.x / TILE), Math.floor(p.y / TILE));
      });
      document.getElementById("btnCast")?.addEventListener("click", () => castAt(9, 4));
      document.getElementById("btnHeal")?.addEventListener("click", () => healMob());

      log("Sẵn sàng: click vùng chơi = cast rocklift về mob.");
    },
  },
});

// ---- SERVER GIỐNG GAME REAL ------------------------------------------------
// action_result spell sau RTT 30ms (giống web_api), hp giảm về snapshot
// đúng mốc impact_delay (resolve_pending_spells timeout rồi 20Hz tick push).
function labServerResolve(tx: number, ty: number): void {
  // 1) action_result echo (30ms)
  setTimeout(() => {
    spellEngine.notifyServerImpact(tx, ty, flightMs);
    log(`action_result (impact_delay_ms=${flightMs}) @ ${(performance.now() - castT0).toFixed(0)}ms`);
    // 2) hp mới CHỈ về với snapshot 20Hz SAU khi flight xong (giống server
    //    thật: resolve_pending_spells tick pushed hp vào snapshot sau cùng).
    const resolveAt = castT0 + flightMs; // server deadline = 1800ms
    setTimeout(() => {
      if (!z) return;
      const dmg = lastDmgAmount;
      zombieHp = Math.max(0, z.hp - dmg);
      log(`resolve_pending_spells: hp → ${zombieHp} @ ${(performance.now() - castT0).toFixed(0)}`);
      lastDmgCritical = Math.random() < 0.15; // roll crit giống ATTACK_CRIT_CHANCE
      let showDmg = dmg;
      if (lastDmgCritical) {
        showDmg = Math.round(dmg * 1.5); // crit của phong cách apply_spell
        zombieHp = Math.max(0, Math.max(0, z.hp) - showDmg);
        log(`resolve_pending_spells: CRIT hp → ${zombieHp}`);
      }
      spawnDamageNumber(z.container.x, z.container.y, showDmg, lastDmgCritical);
      spawnStunFx(); // ST FX nhìn thấy ngay mỗi lần trúng
      pushTimeline();
    }, Math.max(0, resolveAt - performance.now()) + 60); // +60ms như server tick đẩy snapshot
  }, 30);
}

function castAt(tx: number, ty: number): void {
  if (!z) return;
  castT0 = performance.now();
  hitDone = false;
  zombieHpShownMs = null;
  flightMs = Number((document.getElementById("flightMs") as HTMLInputElement).value);
  def.liftMs = Number((document.getElementById("liftMs") as HTMLInputElement).value);
  // impact VFX toggle (user 12/10: "tạm bỏ hiệu ứng impact") — truyền thẳng
  // vào engine, mặc định OFF trong lab.
  spellEngine.impactVfx = (document.getElementById("chkImpact") as HTMLInputElement)?.checked ?? false;

  // HIT-TEST GIỐNG GAME THẬT (apply_spell): quái chỉ ăn dmg khi nằm trong
  // bán kính nổ của điểm ném (impactRadiusPx 40px / TILE = 2.5 ô). Ném trượt
  // = đá rơi ù, KHÔNG dmg — fix trước đây mọi cast đều trừ hp.
  const dist = Math.hypot(tx - z.x, ty - z.y);
  const radiusTiles = (def.impactRadiusPx ?? 40) / TILE;
  lastCastHit = dist <= radiusTiles;

  spellEngine.cast(def, { x: 66, y: 128 }, { x: tx, y: ty });
  if (lastCastHit) {
    labServerResolve(tx, ty);
  } else {
    log(`TRƯỢT — ném tại (${tx},${ty}), quái ở (${z.x},${z.y}) — ngoài tầm nổ ${radiusTiles.toFixed(1)} ô. KHÔNG dmg.`);
    pushTimeline();
  }
}

// Mô phỏng snapshot 20Hz — mob đứng im, hp mới chỉ chạy khi resolve xong.
setInterval(() => {
  if (!tickOn || !z) return;
  if (zombieHp !== zombieHpShown) {
    z.hp = zombieHp;
    z.barFill.width = (28 * zombieHp) / (z.hpMax || 100);
    zombieHpShownMs = performance.now();
    hitDone = true;
    zombieHpShown = zombieHp;
    pushTimeline();
  }
}, 50); // 20Hz
