// ---- SPELL ENGINE — DATA DEFS (user 11/10: "cần 1 engine riêng cho hệ spell")
//
// MỖI SPELL = 1 DATA RECORD mô tả các lifecycle stage:
//   cast   : nạp chưởng tại player (100ms) — VFX mở, KHÔNG damage
//   launch : bắn ra khỏi player (emerge/slide) — KHOÁ hướng + duration tối đa
//   travel : bay tới đích theo SPEED đặt trước — hit-test theo quãng đường THỰC
//   impact : nơi石头 chạm/tự nổ — server resolve damage + client vẽ vỡ TẠI ĐÓ
//   (cleanup tự động sau impact frames)
//
// Nguyên tắc (GAS-style): damage là GAMEPLAY EVENT tại impact — không dính
// tới animation. Server là thẩm quyến, client chỉ VFX theo event.
//
// Timeout mặc định của launch: nếu không trúng trước `travelMs` thì impact
// tại điểm cuối của đường bay (expiring at the target tile).

export type SpellStage =
  | { type: "emerge"; ms: number; px: number }        // trượt khỏi player
  | { type: "flight"; speedTiles: number; maxMs: number } // bay theo speed/ô
  | { type: "impact"; radiusPx: number; frames: number; fps: number };

export interface SpellDef {
  id: string;
  name: string;
  dir: string; // texture dir under ui/fx/spells
  mana: number;
  cooldownS: number;
  // Damage (server-authoritative)
  dmg: number;
  variance: number;
  // Hit-test: bán kính va chạm trong lúc bay + bán kính nổ đất khi impact
  collideRadiusPx: number;
  impactRadiusPx: number;
  // Stage list theo thứ tự chạy
  stages: SpellStage[];
  // VFX nâng cao
  liftMs?: number;   // rocklift: nổi lên trước khi bay
  liftPx?: number;
  scale?: number;
}

export const SPELL_ENGINE_DEFS: SpellDef[] = [
  {
    id: "rocklift",
    name: "Vận chiêu đá",
    dir: "rocklift",
    mana: 12,
    cooldownS: 1.2,
    dmg: 18,
    variance: 5,
    collideRadiusPx: 16,   // mob chạm đá trong lúc bay → nổ tại chỗ
    impactRadiusPx: 40,    // bán kính nổ tại điểm chạm-đất
    stages: [
      { type: "emerge", ms: 0, px: 0 },
      { type: "flight", speedTiles: 12, maxMs: 500 }, // 12 ô/s = bay 0.5s cho 6 ô
      { type: "impact", radiusPx: 40, frames: 7, fps: 10 },
    ],
    liftMs: 600,  // nổi lên 26px trước
    liftPx: 26,
    scale: 1.0,
  },
];
