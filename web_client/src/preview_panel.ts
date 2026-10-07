// Preview panel (DEV/PREVIEW builds only): a floating remote control for the
// server's REAL mechanics. Talks to the local preview stack
// (scripts/_preview_stack.py) via preview_cmd frames; the stack answers with
// push toasts (the log feed) and preview_state dumps (the status line).
//
// MULTI-SESSION (user 28/09): every browser tab is its own server-side user
// (see scripts/_local_game_stack.py) — 2-4 tabs play in separate worlds at
// once. The panel therefore shows THIS tab's identity in the header and the
// status line so instances never get confused with each other.
//
// OVERHAUL (user 28/09): collapsed sections keep the panel compact —
// "Thế giới" (clock/meteors/weather), "Quái & Động vật", "Nhân vật"
// (heal/kill/respawn/status/teleport), "Map" — plus a boxed log. Sections
// are <details> so the reviewer opens only what they need.
//
// Gated by `?preview=1` (or #preview) so production clients never build it.

type Cmd =
  | "clock" | "meteor" | "weather" | "zombies" | "animals" | "map"
  | "state" | "bite" | "heal" | "kill" | "respawn" | "status" | "tp"
  | "hurt"
  | "give"
  | "kit"
  | "block"; // 🧱 block: đặt/gỡ bàn chế tạo cạnh player (test near_station)

interface PanelHooks {
  send: (frame: Record<string, unknown>) => void;
}

const MAPS: Array<[string, string]> = [
  ["ekonia/overworld", "Bigmap"],
  ["ekonia/forest", "Rừng"],
  ["ekonia/cave_area1", "Hang"],
];

const WEATHERS: Array<[string, string]> = [
  ["normal", "Tự động"],
  ["rain", "Mưa"],
  ["heavy_rain", "Mưa to"],
  ["storm", "Bão"],
  ["snow", "Tuyết"],
  ["cold", "Rét"],
  ["wind", "Gió"],
  ["sun_clouds", "Nắng"],
  ["cloud_shadow", "Mây đen"],
];

/** Real server-side debuffs (game.status_effects.EFFECTS). */
const STATUSES: Array<[string, string]> = [
  ["infection", "Thối Rửa"],
  ["poison", "Độc"],
];

const LS_POS_KEY = "preview-panel-pos";
const LS_OPEN_KEY = "preview-panel-open";

export class PreviewPanel {
  private root: HTMLDivElement | null = null;
  private log: HTMLDivElement | null = null;
  private status: HTMLDivElement | null = null;
  private hooks: PanelHooks | null = null;
  private demoTimer: number | null = null;

  attach(hooks: PanelHooks): void {
    if (this.root || !enabledByQuery()) return;
    this.hooks = hooks;
    this.build();
  }

  private send(cmd: Cmd, value?: string | number): void {
    this.hooks?.send({ type: "preview_cmd", cmd, value });
  }

  private build(): void {
    const root = document.createElement("div");
    root.id = "preview-panel";
    root.style.cssText = [
      "position:fixed", "top:52px", "right:8px", "z-index:3000",
      // Translucent so the map/status rail underneath stays readable.
      "background:rgba(10,12,20,0.72)", "backdrop-filter:blur(2px)",
      "color:#dfe6ff",
      "border:1px solid #3b4a7a", "border-radius:10px",
      "font:12px/1.5 monospace", "padding:8px 10px", "width:248px",
      "max-height:calc(100vh - 70px)", "overflow-y:auto",
      "box-shadow:0 4px 18px rgba(0,0,0,0.5)", "user-select:none",
    ].join(";");

    const head = document.createElement("div");
    head.style.cssText = "display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;cursor:move";
    head.innerHTML = `<b style="color:#ffd75e">🧪 PREVIEW <span id="preview-tab-id" style="color:#8fa3d9;font-weight:400"></span></b>`;
    const mini = document.createElement("button");
    mini.textContent = "–";
    mini.style.cssText = btnStyle("#2a3352", "22px");
    mini.onclick = () => this.setMinimized(!this.minimized);

    // DRAGGABLE + position memory: drag by the header; the position is
    // remembered in localStorage so EVERY future session starts where the
    // user last parked the panel (and it stops covering the status rail).
    this.restorePosition(root);
    this.makeDraggable(root, head);
    head.appendChild(mini);
    root.appendChild(head);

    const body = document.createElement("div");
    body.id = "preview-body";
    root.appendChild(body);
    this.root = root;

    // ---- helpers ----
    const details = (label: string, open = false): HTMLDivElement => {
      const det = document.createElement("details");
      det.style.cssText = "margin:2px 0;border-top:1px solid #3b4a7a;padding-top:3px";
      det.open = open;
      const summary = document.createElement("summary");
      summary.textContent = label;
      summary.style.cssText = "cursor:pointer;color:#8fa3d9;list-style:none;user-select:none";
      det.appendChild(summary);
      const inner = document.createElement("div");
      inner.style.cssText = "margin-top:4px";
      det.appendChild(inner);
      body.appendChild(det);
      // Remember open/closed across sessions.
      det.addEventListener("toggle", () => {
        try {
          const openKeys = JSON.parse(localStorage.getItem(LS_OPEN_KEY) || "{}") as Record<string, boolean>;
          openKeys[label] = det.open;
          localStorage.setItem(LS_OPEN_KEY, JSON.stringify(openKeys));
        } catch { /* storage unavailable — fine this session */ }
      });
      try {
        const openKeys = JSON.parse(localStorage.getItem(LS_OPEN_KEY) || "{}") as Record<string, boolean>;
        det.open = !!openKeys[label];
      } catch { /* keep default */ }
      return inner;
    };
    const row = (parent: HTMLElement): HTMLDivElement => {
      const d = document.createElement("div");
      d.style.cssText = "display:flex;flex-wrap:wrap;gap:4px;margin-bottom:5px";
      parent.appendChild(d);
      return d;
    };
    const btn = (parent: HTMLElement, label: string, fn: () => void, color = "#2a3352"): HTMLButtonElement => {
      const b = document.createElement("button");
      b.textContent = label;
      b.style.cssText = btnStyle(color);
      b.onclick = fn;
      parent.appendChild(b);
      return b;
    };

    // ---- 🌍 Thế giới: giờ / thiên thạch / thời tiết ----
    const world = details("🌍 Thế giới", true);
    row(world);
    btn(world, "☀️ Ngày", () => this.send("clock", "day"), "#3a3312");
    btn(world, "🌆 Hoàng hôn", () => this.send("clock", "dusk"));
    btn(world, "🌙 Đêm", () => this.send("clock", "night"), "#1a2a52");
    btn(world, "Tự nhiên", () => this.send("clock", "normal"));
    const timeRow = row(world);
    const timeInput = document.createElement("input");
    timeInput.placeholder = "HH:MM (vd 02:30)";
    timeInput.style.cssText =
      "flex:1;min-width:90px;background:#0e1424;color:#dfe6ff;border:1px solid #4a5a8a;border-radius:6px;padding:3px 6px;font:11px monospace";
    timeRow.appendChild(timeInput);
    const timeBtn = document.createElement("button");
    timeBtn.textContent = "Đặt giờ";
    timeBtn.style.cssText = btnStyle("#3a3312");
    timeBtn.onclick = () => {
      const v = timeInput.value.trim();
      if (v) this.send("clock", v);
    };
    timeRow.appendChild(timeBtn);
    row(world);
    btn(world, "☄️ Tại chỗ", () => this.send("meteor", "here"), "#5a1a1a");
    btn(world, "☄️ Gần", () => this.send("meteor", "rand"), "#5a1a1a");
    btn(world, "☄️ Auto ON", () => this.send("meteor", "auto"), "#1a3a1a");
    btn(world, "☄️ Auto OFF", () => this.send("meteor", "off"));
    row(world);
    for (const [key, label] of WEATHERS) {
      btn(world, label, () => this.send("weather", key));
    }

    // ---- 👾 Quái & động vật ----
    const mobs = details("👾 Quái & động vật", true);
    row(mobs);
    btn(mobs, "Spawn 10 quái", () => this.send("zombies", "pack"), "#1a3a1a");
    btn(mobs, "Cắn -10", () => this.send("bite"), "#5a3a1a");
    btn(mobs, "Cắn -50", () => this.send("bite", 50), "#5a3a1a");
    btn(mobs, "Dọn quái", () => this.send("zombies", "none"), "#5a1a1a");
    row(mobs);
    btn(mobs, "+1 động vật", () => this.send("animals", "rand"), "#1a3a1a");
    btn(mobs, "Thỏ", () => this.send("animals", "bunny"), "#1a2a1a");
    btn(mobs, "Nai", () => this.send("animals", "deer"), "#1a2a1a");
    btn(mobs, "Heo", () => this.send("animals", "boar"), "#1a2a1a");
    btn(mobs, "Gấu", () => this.send("animals", "bear"), "#1a2a1a");
    btn(mobs, "Sói", () => this.send("animals", "wolf"), "#1a2a1a");
    btn(mobs, "Dọn vật", () => this.send("animals", "none"), "#5a1a1a");

    // ---- 🧍 Nhân vật: heal / kill / respawn / status / teleport ----
    const me = details("🧍 Nhân vật", true);
    row(me);
    btn(me, "Rail demo", () => this.startStatusDemo(), "#2a2a3a");
    btn(me, "❤️ Hồi full", () => this.send("heal"), "#1a3a1a");
    // 🩸 Nặng Má: HP = 15% — ngưỡng bật bloody screen (xem main.ts lowHpFx).
    btn(me, "🩸 Nặng Má", () => this.send("hurt", "0.15"), "#3a1418");
    btn(me, "☠️ Chết", () => this.send("kill"), "#5a1a1a");
    btn(me, "✨ Hồi sinh", () => this.send("respawn"), "#1a2a52");
    // 🎁 give: bộ demo item (potion/sword/block/giáp) để thử rich tooltip.
    btn(me, "🎁 Bộ demo", () => this.send("give", "demo"), "#2a2a1a");
    // 🎒 Kit test (user 08/10): full giáp + vũ khí + potion + block, auto-mặc.
    btn(me, "🎒 Kit test", () => this.send("kit", ""), "#2a1a0f");
    // 🎁 give <item_id>: item bất kỳ theo id (đặt block như crafting_table
    // để test near_station/craft grid; server _cmd_give nhận ITEM/BLOCK id).
    const giveRow = row(me);
    const giveInput = document.createElement("input");
    giveInput.placeholder = "item_id (vd crafting_table)";
    giveInput.style.cssText =
      "flex:1;min-width:110px;background:#0e1424;color:#dfe6ff;border:1px solid #4a5a8a;border-radius:6px;padding:3px 6px;font:11px monospace";
    giveRow.appendChild(giveInput);
    const giveBtn = document.createElement("button");
    giveBtn.textContent = "🎁 Tặng";
    giveBtn.style.cssText = btnStyle("#2a2a1a");
    giveBtn.onclick = () => {
      const v = giveInput.value.trim();
      if (v) this.send("give", v);
    };
    giveRow.appendChild(giveBtn);
    // 🧱 block: server-side đặt/gỡ bàn chế tạo cạnh player — test thật đường
    // near_station (icon craft-mode + lưới 3x3/2x2) không cần UI hotbar.
    let blockPlaced = false;
    const blockBtn = document.createElement("button");
    blockBtn.textContent = "🧱 Bàn CT: ĐẶT";
    blockBtn.title = "Đặt/gỡ bàn chế tạo cạnh player (test near_station)";
    blockBtn.style.cssText = btnStyle("#1a2a3a");
    blockBtn.onclick = () => {
      blockPlaced = !blockPlaced;
      this.send("block", blockPlaced ? "crafting_table" : "remove");
      blockBtn.textContent = blockPlaced ? "🧱 Bàn CT: GỠ" : "🧱 Bàn CT: ĐẶT";
    };
    giveRow.appendChild(blockBtn);
    // 📊 Bars TESTER (user 08/10: "tool test trực quan bằng cách nhấn chi tiết"):
    // stateful bar mirrors + one button per impact size — press each button and
    // judge exactly THAT impact (HP tiers sm/md/lg, heal, mana, stamina).
    const barsState = { hp: 100, mhp: 100, mana: 50, mmana: 50, stam: 120, mstam: 120 };
    const hud2 = () => (window as unknown as {
      hud?: {
        setBars(...args: number[]): void;
        setBarsTest?(...args: number[]): void;
        holdBars?(hold: boolean): void;
      };
    }).hud;
    // Write through setBarsTest: bypasses the hold (the hold blocks the
    // 20 Hz snapshot, NOT the tester that owns the bars while held).
    // HOLD POLICY (08/10 fix #2): hold is PER-PRESS — every press holds for
    // 4s, then the server regains control automatically. A hold armed at
    // page load froze the REAL bars (snapshots blocked → "luôn full").
    const push = () => {
      const h2 = hud2();
      (h2?.setBarsTest ?? h2?.setBars)?.call(h2,
        barsState.hp, barsState.mhp, barsState.mana, barsState.mmana,
        barsState.stam, barsState.mstam);
    };
    let pressHoldTimer: number | null = null;
    const pressHold = () => {
      hud2()?.holdBars?.(true);
      if (pressHoldTimer !== null) window.clearTimeout(pressHoldTimer);
      pressHoldTimer = window.setTimeout(() => {
        pressHoldTimer = null;
        hud2()?.holdBars?.(false);
      }, 4000);
    };
    // Every tester press refreshes the 4s hold; presses call pressHold().
    const barRow = (parent: HTMLElement): HTMLDivElement => row(parent);
    const barBtn = (parent: HTMLElement, label: string, fn: () => void, color: string) =>
      btn(parent, label, fn, color);
    const barBox = details("📊 Bars tester", true);
    const line1 = barRow(barBox);
    // HP tiered drops: each press REMOVES that % of max from the mirror.
    barBtn(line1, "🩸 -5%", () => { barsState.hp = Math.max(0, barsState.hp - barsState.mhp * 0.05); pressHold(); push(); }, "#3a1418");
    barBtn(line1, "🩸 -15%", () => { barsState.hp = Math.max(0, barsState.hp - barsState.mhp * 0.15); pressHold(); push(); }, "#4a1418");
    barBtn(line1, "💢 -35%", () => { barsState.hp = Math.max(0, barsState.hp - barsState.mhp * 0.35); pressHold(); push(); }, "#5a1418");
    barBtn(line1, "💀 -60%", () => { barsState.hp = Math.max(0, barsState.hp - barsState.mhp * 0.6); pressHold(); push(); }, "#6a0f0f");
    const line2 = barRow(barBox);
    barBtn(line2, "❤️ +40%", () => { barsState.hp = Math.min(barsState.mhp, barsState.hp + barsState.mhp * 0.4); pressHold(); push(); }, "#1a3a1a");
    barBtn(line2, "✨ Full", () => { barsState.hp = barsState.mhp; barsState.mana = barsState.mmana; barsState.stam = barsState.mstam; pressHold(); push(); }, "#1a3a1a");
    const line3 = barRow(barBox);
    // ↺ Reset: clear the tester state AND hand the bars back to the server NOW.
    barBtn(line3, "↺ Reset", () => {
      barsState.hp = 100; barsState.mana = 50; barsState.stam = 120;
      if (pressHoldTimer !== null) window.clearTimeout(pressHoldTimer);
      pressHoldTimer = null;
      hud2()?.holdBars?.(false); push();
    }, "#2a3352");
    barBtn(line2, "🔵 mana -50%", () => { barsState.mana = Math.max(0, barsState.mana - barsState.mmana * 0.5); pressHold(); push(); }, "#12233f");
    barBtn(line2, "🟢 stam -40%", () => { barsState.stam = Math.max(0, barsState.stam - barsState.mstam * 0.4); pressHold(); push(); }, "#12301a");
    // 🎬 Auto choreography: same tiers back-to-back for a side-by-side feel.
    barBtn(line3, "🎬 Auto", () => {
      hud2()?.holdBars?.(true); // the choreography owns the bars for its run
      const seq: Array<() => void> = [
        () => { barsState.hp -= barsState.mhp * 0.06; },
        () => { barsState.hp -= barsState.mhp * 0.22; },
        () => { barsState.hp -= barsState.mhp * 0.45; },
        () => { barsState.hp = Math.min(barsState.mhp, barsState.hp + barsState.mhp * 0.6); },
        () => { barsState.mana -= barsState.mmana * 0.5; },
        () => { barsState.stam -= barsState.mstam * 0.4; },
        () => { barsState.hp = 100; barsState.mana = 50; barsState.stam = 120; },
      ];
      let i = 0;
      const t = window.setInterval(() => {
        if (i >= seq.length) {
          window.clearInterval(t);
          hud2()?.holdBars?.(false); // hand the bars back to the server
          return;
        }
        seq[i++]();
        push();
      }, 900);
    }, "#2a1a2a");
    push(); // paint the tester's initial state immediately
    // ✨ Hào quang toggle (user 08/10: rim sáng nhẹ quanh AVATAR, không phải
    // model world). Routes into the character panel's face CSS glow.
    let haloOn = true;
    const haloBtn = btn(me, "✨ Hào quang: BẬT", () => {
      haloOn = !haloOn;
      (window as unknown as {
        hud?: { setHalo?(on: boolean): void };
      }).hud?.setHalo?.(haloOn);
      haloBtn.textContent = `✨ Hào quang: ${haloOn ? "BẬT" : "TẮT"}`;
    }, "#1a2a3a");
    // 🖼️ Avatar căn: REMOVED (user 08/10 calibration {"side":0.56,"ox":0,
    // "oy":8} baked into portrait_crop.ts defaults — tool no longer needed).
    // 💬 Hộp thoại NPC: mở overlay DialogBox (asset pack + VT323) ngay trên map.
    // 💬 Hộp thoại NPC: mở overlay DialogBox (asset pack + VT323) ngay trên map.
    btn(me, "💬 Hộp thoại demo", () => {
      import("./dialog_box").then((m) => {
        if (m.dialogBox.isOpen) m.dialogBox.close();
        else m.dialogBox.open(m.demoGacDacPages());
      });
    }, "#1a2a3a");
    row(me);
    for (const [key, label] of STATUSES) {
      btn(me, `☣️ ${label}`, () => this.send("status", key), "#1a2a1a");
    }
    btn(me, "Xoá hiệu ứng", () => this.send("status", "off"), "#5a1a1a");
    const tpRow = row(me);
    const tpInput = document.createElement("input");
    tpInput.placeholder = "x,y (trống = ngẫu nhiên)";
    tpInput.style.cssText =
      "flex:1;min-width:90px;background:#0e1424;color:#dfe6ff;border:1px solid #4a5a8a;border-radius:6px;padding:3px 6px;font:11px monospace";
    tpRow.appendChild(tpInput);
    const tpBtn = document.createElement("button");
    tpBtn.textContent = "🌀 Tới";
    tpBtn.style.cssText = btnStyle("#33321a");
    tpBtn.onclick = () => {
      const v = tpInput.value.trim();
      this.send("tp", v || "rand");
    };
    tpRow.appendChild(tpBtn);
    row(me);
    btn(me, "Về spawn", () => this.send("tp", "spawn"), "#33321a");
    btn(me, "Đi chỗ khác", () => this.send("tp", "rand"), "#33321a");

    // ---- 🗺️ Map ----
    const mapSec = details("🗺️ Đổi map");
    row(mapSec);
    for (const [id, label] of MAPS) {
      btn(mapSec, label, () => this.send("map", id), "#33321a");
    }
    // 🟧 Box chặn: local collision overlay (game.ts setCollisionDebug) —
    // đỏ = ô chặn vuông, cam = phần mask thực sự chặn. Toggle qua window
    // event — cùng đường với phím F3, không cần frame server.
    btn(mapSec, "🟧 Box chặn", () => {
      const scene = (window as unknown as {
        gameScene?: { getCollisionDebug(): boolean };
      }).gameScene;
      const on = !(scene?.getCollisionDebug() ?? false);
      window.dispatchEvent(new CustomEvent("toggle-collision", { detail: on }));
    }, "#3a2a12");
    // 🎯 Căn FX: kéo chấm sáng lửa / dải cửa sổ bằng tay trên canvas;
    // thả ra là client gửi toạ độ ô về server (fx_align) — server ghi
    // thẳng vào marker layers của map JSON (preview-only tool).
    let fxAlignOn = false;
    const fxBtn = btn(mapSec, "🎯 Kéo căn FX: TẮT", () => {
      const scene = (window as unknown as {
        gameScene?: { setFxAlign(on: boolean): void };
      }).gameScene;
      if (!scene) return;
      fxAlignOn = !fxAlignOn;
      scene.setFxAlign(fxAlignOn);
      fxBtn.textContent = `🎯 Kéo căn FX: ${fxAlignOn ? "BẬT — kéo chấm sáng, thả để lưu" : "TẮT"}`;
    }, "#3a2a12");
    // 🎚️ FX look tuning: size + speed per kind (fire/window), live-applied
    // and auto-saved (debounced) through the same fx_align channel.
    const fxScene = () => (window as unknown as {
      gameScene?: {
        setFxParams(p: Record<string, number>): void;
        commitFxAlign(): void;
        welcome?: { map?: { room_fx?: Record<string, number> | null } };
      };
    }).gameScene;
    let fxSaveTimer: number | null = null;
    const fxSave = () => {
      if (fxSaveTimer !== null) window.clearTimeout(fxSaveTimer);
      fxSaveTimer = window.setTimeout(() => fxScene()?.commitFxAlign(), 700);
    };
    const fxSliders: Array<{ key: string; inp: HTMLInputElement; val: HTMLSpanElement }> = [];
    const fxSlider = (label: string, key: string, min: number, max: number): void => {
      const cur = fxScene()?.welcome?.map?.room_fx?.[key] ?? 1;
      const line = document.createElement("div");
      line.style.cssText = "display:flex;align-items:center;gap:5px;margin:2px 0";
      const cap = document.createElement("span");
      cap.textContent = label;
      cap.style.cssText = "font:10px monospace;color:#9fb0d8;min-width:64px";
      const inp = document.createElement("input");
      inp.type = "range";
      inp.min = String(min); inp.max = String(max); inp.step = "0.05";
      inp.value = String(cur);
      inp.style.cssText = "flex:1";
      const val = document.createElement("span");
      val.textContent = Number(cur).toFixed(2);
      val.style.cssText = "font:10px monospace;color:#dfe6ff;min-width:32px;text-align:right";
      inp.oninput = () => {
        const v = parseFloat(inp.value);
        val.textContent = v.toFixed(2);
        fxScene()?.setFxParams({ [key]: v });
        fxSave();
      };
      line.append(cap, inp, val);
      mapSec.appendChild(line);
      fxSliders.push({ key, inp, val });
    };
    // Sync slider positions from the welcome's saved tuning (the panel
    // builds BEFORE the welcome arrives, so the initial 1.00 default is
    // often wrong — user 05/10 "lấy fx mik fix làm gốc"). Skips the slider
    // the user is currently dragging.
    const syncFxSliders = (): void => {
      const rf = fxScene()?.welcome?.map?.room_fx;
      if (!rf) return;
      for (const s of fxSliders) {
        const v = rf[s.key];
        if (typeof v !== "number") continue;
        if (document.activeElement === s.inp) continue;
        s.inp.value = String(v);
        s.val.textContent = v.toFixed(2);
      }
    };
    window.setInterval(syncFxSliders, 5000);
    window.setTimeout(syncFxSliders, 3000);
    fxSlider("🔥 cỡ", "fire_scale", 0.5, 2.5);
    fxSlider("🔥 tốc độ", "fire_speed", 0.25, 3);
    fxSlider("🪟 cỡ", "window_scale", 0.5, 2.5);
    fxSlider("🪟 tốc độ", "window_speed", 0.25, 3);

    // ---- 📡 status + log ----
    const st = details("📡 Trạng thái & log", true);
    this.status = document.createElement("div");
    this.status.style.cssText = "color:#7fff9f;white-space:pre-wrap;margin-bottom:4px";
    this.status.textContent = "…";
    st.appendChild(this.status);
    const refresh = document.createElement("button");
    refresh.textContent = "↻ Refresh";
    refresh.style.cssText = btnStyle("#2a3352");
    refresh.onclick = () => this.send("state");
    st.appendChild(refresh);
    this.log = document.createElement("div");
    this.log.style.cssText =
      "margin-top:5px;max-height:120px;overflow-y:auto;color:#a9b7e8;white-space:pre-wrap;border-top:1px solid #3b4a7a;padding-top:4px";
    st.appendChild(this.log);

    document.body.appendChild(root);
    // Auto-refresh the status line every 5s so the reviewer never pokes
    // Refresh manually to see mob counts / HP after an action.
    window.setInterval(() => {
      if (!this.minimized) this.send("state");
    }, 5000);
    this.send("state");
  }

  private minimized = false;

  private setMinimized(min: boolean): void {
    this.minimized = min;
    const body = document.getElementById("preview-body");
    const mini = this.root?.querySelector("button");
    if (body) body.style.display = min ? "none" : "block";
    if (mini) mini.textContent = min ? "+" : "–";
  }

  /** Restore the last-dragged position (every session, same browser). */
  private restorePosition(root: HTMLDivElement): void {
    try {
      const raw = localStorage.getItem(LS_POS_KEY);
      if (!raw) return;
      const { x, y } = JSON.parse(raw) as { x: number; y: number };
      if (typeof x !== "number" || typeof y !== "number") return;
      root.style.right = "auto";
      root.style.left = `${x}px`;
      root.style.top = `${y}px`;
    } catch { /* corrupted storage — keep the default corner */ }
  }

  /** Header-drag (mouse + touch), clamped to the viewport, saved on release. */
  private makeDraggable(root: HTMLDivElement, handle: HTMLElement): void {
    let sx = 0, sy = 0, ox = 0, oy = 0, dragging = false;
    const save = (): void => {
      const r = root.getBoundingClientRect();
      try {
        localStorage.setItem(
          LS_POS_KEY,
          JSON.stringify({ x: Math.round(r.left), y: Math.round(r.top) }),
        );
      } catch { /* storage unavailable — drag still works this session */ }
    };
    const clamp = (): void => {
      const r = root.getBoundingClientRect();
      const maxX = window.innerWidth - r.width;
      const maxY = window.innerHeight - r.height;
      const x = Math.min(Math.max(0, r.left), Math.max(0, maxX));
      const y = Math.min(Math.max(0, r.top), Math.max(0, maxY));
      root.style.right = "auto";
      root.style.left = `${x}px`;
      root.style.top = `${y}px`;
    };
    const down = (cx: number, cy: number): void => {
      const r = root.getBoundingClientRect();
      // Anchor on the panel's current top-left so right-positioned panels
      // don't jump when the drag starts.
      root.style.right = "auto";
      root.style.left = `${r.left}px`;
      root.style.top = `${r.top}px`;
      sx = cx; sy = cy; ox = r.left; oy = r.top; dragging = true;
    };
    const move = (cx: number, cy: number): void => {
      if (!dragging) return;
      root.style.left = `${ox + cx - sx}px`;
      root.style.top = `${oy + cy - sy}px`;
      clamp();
    };
    const up = (): void => {
      if (!dragging) return;
      dragging = false;
      save();
    };
    handle.addEventListener("mousedown", (e) => {
      if ((e.target as HTMLElement).tagName === "BUTTON") return;
      down(e.clientX, e.clientY);
      e.preventDefault();
    });
    window.addEventListener("mousemove", (e) => move(e.clientX, e.clientY));
    window.addEventListener("mouseup", up);
    handle.addEventListener("touchstart", (e) => {
      const t = e.touches[0];
      down(t.clientX, t.clientY);
    }, { passive: true });
    window.addEventListener("touchmove", (e) => {
      if (!dragging) return;
      const t = e.touches[0];
      move(t.clientX, t.clientY);
      e.preventDefault();
    }, { passive: false });
    window.addEventListener("touchend", up);
    window.addEventListener("resize", clamp);
  }

  /** push toasts land here too (the preview stack tags them "[preview]"). */
  feed(message: string): void {
    if (!this.log) return;
    const line = document.createElement("div");
    line.textContent = message;
    this.log.prepend(line);
    while (this.log.childElementCount > 40) this.log.lastElementChild!.remove();
  }

  onState(s: Record<string, unknown>): void {
    if (!this.status) return;
    const self = (s.self ?? {}) as {
      name?: string; hp?: number; max_hp?: number;
      x?: number; y?: number; dead?: boolean;
      effects?: Array<[string, number, number]>;
    };
    const kinds = Array.isArray(s.mob_kinds) ? (s.mob_kinds as string[]).join(",") : "";
    const effTxt = (self.effects ?? []).length
      ? JSON.stringify(self.effects)
      : "KHÔNG";
    // Tab identity: the server mints a unique name per connection — two side-
    // by-side preview tabs can never be confused.
    const tabId = document.getElementById("preview-tab-id");
    if (tabId && self.name) tabId.textContent = `· ${self.name}`;
    this.status.textContent =
      `map: ${s.map}\n` +
      `giờ: ${s.clock} (${s.night ? "ĐÊM" : "day"})\n` +
      `thời tiết: ${s.weather}\n` +
      `quái: ${s.zombies} [${kinds}] | ☄️: ${s.meteors}\n` +
      `tôi: ${self.name ?? "?"} ${self.hp ?? "?"}/${self.max_hp ?? "?"} HP` +
      `${self.dead ? " (CHẾT)" : ""} @ (${self.x ?? "?"},${self.y ?? "?"})\n` +
      `hiệu ứng: ${effTxt}\n` +
      `đã rơi đêm nay: ${s.felled_tonight} | auto: ${s.auto_meteor ? "ON" : "OFF"}`;
  }

  /** DEMO rail (kept for UI tests): fake 3 effects with LIVE countdowns.
   *  Prefer the REAL server-side status via the "Nhân vật" section. */
  private startStatusDemo(): void {
    this.stopStatusDemo();
    const hud = (window as unknown as {
      hud?: {
        setDemoStatusEffects(e: Array<[string, number, number?]> | null): void;
      };
    }).hud;
    if (!hud) return;
    let effects: Array<[string, number, number?]> = [
      ["infection", 30, 2], ["poison", 20, 3], ["poison2", 10, 4],
    ];
    const tick = (): void => {
      hud.setDemoStatusEffects(effects);
      effects = effects
        .map(([id, s, l]) => [id, s - 1, l] as [string, number, number?])
        .filter(([, s]) => s > 0);
      if (!effects.length) {
        hud.setDemoStatusEffects(null);
        this.demoTimer = null;
        return;
      }
      this.demoTimer = window.setTimeout(tick, 1000);
    };
    tick();
  }

  private stopStatusDemo(): void {
    if (this.demoTimer !== null) {
      clearTimeout(this.demoTimer);
      this.demoTimer = null;
    }
    (window as unknown as {
      hud?: {
        setDemoStatusEffects(e: Array<[string, number, number?]> | null): void;
      };
    }).hud?.setDemoStatusEffects(null);
  }
}

function btnStyle(bg: string, w = "auto"): string {
  return [
    `background:${bg}`, "color:#dfe6ff", "border:1px solid #4a5a8a",
    "border-radius:6px", "padding:3px 7px", "cursor:pointer",
    "font:11px monospace", w === "auto" ? "" : `width:${w}`,
  ].filter(Boolean).join(";");
}

function enabledByQuery(): boolean {
  return (
    new URLSearchParams(location.search).has("preview") ||
    location.hash.includes("preview")
  );
}

export const previewPanel = new PreviewPanel();
