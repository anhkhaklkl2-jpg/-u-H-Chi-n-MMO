// DialogBox — hộp thoại NPC theo đúng asset Ninja Adventure pack (CC0) +
// font VT323 (OFL) đã chuẩn hoá trong demo. DOM overlay nằm TRÊN canvas
// Phaser, không đụng game loop; phím tắt / click để tới trang sau.
//
// Quy ước hiển thị (đã tinh chỉnh qua demo pixel):
// - Box 600x116 (2x gốc 300x58), neo đáy giữa màn hình.
// - Face 76x76 dán khít ô window tối (rect 6,14,44,52 của gốc ×2).
// - Nameplate "tab" lún 6px vào viền trên box, nền tối viền vàng.
// - VT323 24px cho thoại (3 dòng x 26px) + 24px cho tên.
// - Typewriter: reveal từng ký tự, hoàn tất thì hiện mũi tên Arrow chớp.
// - Paginate: chuỗi dài tự cắt trang; Enter/Space/click → next page/close.

const BOX_W = 600;
const BOX_H = 116;

const WIN_BB = [6, 14, 44, 52]; // ô window tối trong ảnh gốc 300x58
const FACE_KEYS = "ui/dialog/face_gacdac.png";
const EMOTE_BANG = "ui/dialog/emote_bang.png";

export interface DialogPage {
  who: string;
  lines: string[];
  face?: string;   // url faceset 38x38 (nếu khác mặc định)
  choices?: string[]; // nếu có → hiện ChoiceBox + Yes/No (demo chỉ 2 lựa)
  onChoice?: (yes: boolean) => void;
  /** Live NPC mode: buttons rendered from the server's dialogue options.
   *  Khi có options, click gọi onPick(label, next) thay vì next page. */
  options?: { label: string; next: string | null }[];
  onPick?: (label: string, next: string | null) => void;
}

function ensureFont(): void {
  if (document.getElementById("vt323-face")) return;
  const st = document.createElement("style");
  st.id = "vt323-face";
  st.textContent = "@font-face{font-family:'VT323';src:url('ui/dialog/VT323-Regular.ttf') format('truetype');font-display:swap}";
  document.head.appendChild(st);
}

function el(tag: string, css: string, parent: HTMLElement): HTMLElement {
  const e = document.createElement(tag);
  e.style.cssText = css;
  parent.appendChild(e);
  return e;
}

export class DialogBox {
  private root: HTMLElement | null = null;
  private faceImg: HTMLImageElement | null = null;
  private nameEl: HTMLElement | null = null;
  private textEl: HTMLElement | null = null;
  private arrowEl: HTMLElement | null = null;
  private pages: DialogPage[] = [];
  private pageIdx = 0;
  private timer: number | null = null;
  private onDone: (() => void) | null = null;
  private keyHandler = (ev: KeyboardEvent) => this.onKey(ev);
  private resizeHandler = () => this.applyScale();

  /** Phóng box theo be rong man hinh (max 92% viewport, scale nguyen ken pixel). */
  private applyScale(): void {
    if (!this.root) return;
    const vw = window.innerWidth;
    const s = Math.max(1, Math.min((vw - 24) / BOX_W, 2.2));
    this.root.style.transform = `translateX(-50%) scale(${s})`;
  }

  get isOpen(): boolean {
    return this.root !== null;
  }

  open(pages: DialogPage[], onDone?: () => void): void {
    this.close();
    ensureFont();
    this.pages = pages;
    this.pageIdx = 0;
    this.onDone = onDone ?? null;
    this.root = el("div", [
      "position:fixed", "left:50%", "transform:translateX(-50%)",
      "transform-origin:center bottom",
      "bottom:26px", "z-index:2500", "pointer-events:none",
      `width:${BOX_W}px`, `height:${BOX_H}px`,
      "image-rendering:pixelated", "user-select:none",
    ].join(";"), document.body);
    window.addEventListener("resize", this.resizeHandler);
    this.applyScale();

    const box = el("img", [
      "position:absolute", "left:0", "top:0",
      `width:${BOX_W}px`, `height:${BOX_H}px`,
      "image-rendering:pixelated",
    ].join(";"), this.root) as HTMLImageElement;
    box.src = "ui/dialog/DialogBoxFaceset.png";

    // face dán khít ô window (WIN_BB × 2) — box img ở (0,0) nên KHÔNG cộng offset demo.
    // Bọc overflow:hidden để face không bao giờ tràn ra viền/UI kế bên.
    const fx = WIN_BB[0] * 2, fy = WIN_BB[1] * 2;
    const fw = (WIN_BB[2] - WIN_BB[0]) * 2, fh = (WIN_BB[3] - WIN_BB[1]) * 2;
    const faceWrap = el("div", [
      "position:absolute", `left:${fx}px`, `top:${fy}px`,
      `width:${fw}px`, `height:${fh}px`, "overflow:hidden",
      "pointer-events:none",
    ].join(";"), this.root);
    this.faceImg = el("img", [
      "position:absolute", "left:0", "top:0",
      `width:${fw}px`, `height:${fh}px`, "image-rendering:pixelated",
    ].join(";"), faceWrap) as HTMLImageElement;

    // nameplate tab
    this.nameEl = el("div", [
      "position:absolute", "left:22px", "bottom:" + (BOX_H - 12) + "px",
      "transform:translateY(0)", "padding:1px 10px 3px",
      "background:#141b1b", "border:2px solid #f0b050",
      "color:#f0b050", "font:24px/1 'VT323',monospace",
      "letter-spacing:1px", "white-space:nowrap",
      "text-shadow:none", "border-radius:0",
    ].join(";"), this.root);

    this.textEl = el("div", [
      "position:absolute", "left:144px", "top:24px",
      "width:" + (BOX_W - 160) + "px",
      "font:24px/26px 'VT323',monospace", "color:#3f2832",
      "white-space:pre-wrap", "letter-spacing:0.5px",
    ].join(";"), this.root);

    this.arrowEl = el("img", [
      "position:absolute", "right:12px", "bottom:10px", "width:26px",
      "display:none", "image-rendering:pixelated",
      "animation:dlgArrow 0.9s steps(2) infinite",
    ].join(";"), this.root) as HTMLImageElement;
    (this.arrowEl as HTMLImageElement).src = "ui/dialog/Arrow.png";
    if (!document.getElementById("dlg-arrow-kf")) {
      const st = document.createElement("style");
      st.id = "dlg-arrow-kf";
      st.textContent = "@keyframes dlgArrow{0%,49%{opacity:1}50%,100%{opacity:0}}";
      document.head.appendChild(st);
    }

    // lựa chọn Yes/No
    // (demo: 2 nút asset gốc; vị trí như frame 4 trong preview pixel)
    window.addEventListener("keydown", this.keyHandler);
    this.showPage(0);
  }

  close(): void {
    if (this.timer !== null) { clearInterval(this.timer); this.timer = null; }
    window.removeEventListener("keydown", this.keyHandler);
    window.removeEventListener("resize", this.resizeHandler);
    this.root?.remove();
    this.root = null;
    this.pages = [];
  }

  private onKey(ev: KeyboardEvent): void {
    if (ev.key === "Enter" || ev.key === " " || ev.key === "e" || ev.key === "f" || ev.key === "F") {
      ev.preventDefault();
      // Khi đang có options (live NPC) thì phím KHÔNG tự chuyển trang —
      // người chơi phải click chọn. Skip typing vẫn cho phép.
      // "f"/"F": cùng phím F mở hộp thoại cũng phải chuyển trang — trước
      // đây F trong box là phím chết (main.ts return true để đỡ re-open,
      // nhưng dialogBox không hề xử lý F → không avance được trang nào).
      this.next();
    }
  }

  private clearChoiceWrap(): void {
    // xoá CHÍNH XÁC các nút options + ChoiceBox/Yes/No (không đụng ảnh box/face/arrow)
    if (!this.root) return;
    [...this.root.querySelectorAll("button")].forEach((b) => b.remove());
    [...this.root.querySelectorAll("img")].forEach((i) => {
      const s = i.src;
      if (s.includes("ChoiceBox") || s.includes("YesButton") || s.includes("NoButton")) i.remove();
    });
    [...this.root.querySelectorAll('[data-dlg-options]')].forEach((d) => d.remove());
  }

  private showPage(i: number): void {
    this.pageIdx = i;
    const p = this.pages[i];
    if (!p) { this.finish(); return; }
    this.faceImg!.src = p.face ?? FACE_KEYS;
    this.nameEl!.textContent = p.who;
    this.arrowEl!.style.display = "none";
    this.clearChoiceWrap();
    const full = p.lines.join("\n");
    let n = 0;
    if (this.timer !== null) clearInterval(this.timer);
    this.timer = window.setInterval(() => {
      n += 2;
      if (n >= full.length) {
        this.textEl!.textContent = full;
        this.finishTyping(p);
        return;
      }
      this.textEl!.textContent = full.slice(0, n);
    }, 24);
    this.textEl!.textContent = "";
  }

  private finishTyping(p: DialogPage): void {
    if (this.timer !== null) { clearInterval(this.timer); this.timer = null; }
    if (p.options && p.options.length) {
      // LIVE NPC mode: options ABOVE the box (user 30/09: đè lên text khi nằm trong box).
      const host = this.root!;
      this.root!.style.pointerEvents = "auto";
      const wrap = el("div", [
        "position:absolute", "right:0", "bottom:" + (BOX_H + 8) + "px",
        "display:flex", "flex-direction:column", "gap:5px", "align-items:flex-end",
      ].join(";"), host);
      wrap.setAttribute("data-dlg-options", "1");
      for (const opt of p.options) {
        const b = el("button", [
          "pointer-events:auto", "cursor:pointer",
          "background:#141b1b", "border:2px solid #f0b050",
          "color:#f0b050", "font:20px/1.1 'VT323',monospace",
          "padding:3px 10px", "letter-spacing:0.5px",
          "transition:transform .06s", "text-align:right",
          "box-shadow:0 2px 0 rgba(0,0,0,.45)",
        ].join(";"), wrap);
        b.textContent = opt.label + (opt.next ? " ▸" : "");
        b.onmouseenter = () => (b.style.transform = "scale(1.05)");
        b.onmouseleave = () => (b.style.transform = "");
        b.onclick = (ev) => {
          ev.stopPropagation();
          this.clearChoiceWrap();
          p.onPick?.(opt.label, opt.next);
        };
      }
      return;
    }
    if (p.choices && p.choices.length >= 2) {
      // render ChoiceBox + Yes/No gốc ở góc phải box
      const host = this.root!;
      const cb = el("img", [
        "position:absolute", "right:-8px", "bottom:-18px", "width:128px",
        "image-rendering:pixelated", "pointer-events:auto", "cursor:pointer",
      ].join(";"), host) as HTMLImageElement;
      cb.src = "ui/dialog/ChoiceBox.png";
      const mk = (src: string, off: number, val: boolean) => {
        const b = el("img", [
          "position:absolute", `right:${off}px`, "bottom:-13px", "width:52px",
          "image-rendering:pixelated", "pointer-events:auto", "cursor:pointer",
          "transition:transform .06s",
        ].join(";"), host) as HTMLImageElement;
        b.src = src;
        b.onmouseenter = () => (b.style.transform = "scale(1.08)");
        b.onmouseleave = () => (b.style.transform = "");
        b.onclick = (ev) => {
          ev.stopPropagation();
          p.onChoice?.(val);
          this.next();
        };
      };
      mk("ui/dialog/YesButton.png", 62, true);
      mk("ui/dialog/NoButton.png", 6, false);
      cb.style.display = "none"; // chỉ dùng 2 nút nổi cho gọn
    } else {
      this.arrowEl!.style.display = "block";
    }
    this.root!.style.pointerEvents = p.choices ? "auto" : "none";
  }

  private next(): void {
    if (this.timer !== null) {
      // đang gõ dở → skip tới hết
      const p = this.pages[this.pageIdx];
      this.textEl!.textContent = p.lines.join("\n");
      this.finishTyping(p);
      return;
    }
    if (this.pageIdx + 1 < this.pages.length) this.showPage(this.pageIdx + 1);
    else this.finish();
  }

  private finish(): void {
    const cb = this.onDone;
    this.close();
    cb?.();
  }
}

/** Trang demo dùng đúng nội dung demo pixel (Gạc Đặc — trạm trade quái). */
export function demoGacDacPages(): DialogPage[] {
  return [
    {
      who: "Gạc Đặc",
      lines: ["Chào mừng đến Chợ Bà!",
              "Ta là Gạc Đặc, đổi thú",
              "hơn quái... trả bằng xu!"],
    },
    {
      who: "Gạc Đặc",
      lines: ["Quái chết rơi hom hoặc",
              "rương? Đem đến ta!",
              "Càng hiếm, càng nhiều xu"],
    },
    {
      who: "Ninja Đỏ",
      lines: ["Để ta đem thử!",
              "3 con Slime hôm nay,",
              "he he, chờ ta 5 phút!"],
      face: "", // dùng face player thật khi tích hợp; demo để face NPC
    },
    {
      who: "Gạc Đặc",
      lines: ["Bán 3x Sushi = 15 xu?",
              "Chốt đơn không?"],
      choices: ["Có", "Không"],
      onChoice: (yes) => {
        // TODO wire thật: gọi trade API. Demo chỉ log.
        // eslint-disable-next-line no-console
        console.log("[dialog] chốt đơn:", yes ? "CÓ" : "KHÔNG");
      },
    },
  ];
}

export const dialogBox = new DialogBox();
export const EMOTE_BANG_URL = EMOTE_BANG;
