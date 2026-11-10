// Exits for a player leaving the podium (Figma 02A, 03B and the 07 exit library). Times in ms.
import { type Seq, F, home, show, hide, window_, H0 } from "./types";
import * as A from "../art/props";
import { G, INK, L, sp, star, puff, vl, hl } from "../art/svg";

const lift = (sx: number, sy: number, dy: number) => F(0, { sx, sy, dy }).y!;

export const EXITS: Seq[] = [
  {
    id: "punch", name: "Punch box", kind: "exit", sound: "punch", clearAt: 700, dur: 1500,
    actor: [home(0), home(480), F(540, { sx: 0.8, sy: 1.12, cx: 304 }), { t: 1000, x: 1700, y: -700, r: 540, sx: 0.85, sy: 1.2, e: "power1.out" }],
    props: [
      { svg: A.punchClosed, keys: [{ t: 0, y: -700 }, { t: 320, y: 0, e: "back.out(1.6)" }, ...hide(320)] },
      { svg: A.punchWindup, origin: [130, 213], keys: [...show(320), { t: 420, r: -8 }, ...hide(480)] },
      { svg: A.punchStrike, keys: window_(480, 700) },
      { svg: A.punchClosed, keys: [...show(700), { t: 1100, y: 0 }, { t: 1500, y: -800, e: "uiInOut" }] },
      { svg: A.burst(282, 222), origin: [282, 222], keys: [{ t: 0, o: 0 }, { t: 479, o: 0, sx: 0.6, sy: 0.6 }, { t: 480, o: 1, e: "none" }, { t: 560, sx: 1.15, sy: 1.15 }, { t: 640, sx: 1, sy: 1 }, { t: 800, o: 0 }] },
    ],
  },
  {
    id: "spring", name: "Spring launch", kind: "exit", sound: "boing", clearAt: 900, dur: 1250, deck: [[0, false], [1200, true]],
    actor: [home(0), F(160, { fy: A.springTop(36) + 8 }), F(460, { sx: 1.22, sy: 0.78, fy: A.springTop(10) + 8, e: "uiInOut" }), { t: 900, x: 290, y: -900, sx: 0.78, sy: 1.32, r: 180, e: "power2.out" }],
    props: [
      { svg: A.springPad(36), layer: "mid", origin: [290, 448], keys: [{ t: 0, sy: 0.2 }, { t: 160, sy: 1, e: "back.out(2)" }, ...hide(160)] },
      { svg: A.springPad(10), layer: "mid", keys: window_(160, 460) },
      { svg: A.springPad(150), layer: "mid", origin: [290, 448], keys: [...show(460), { t: 560, sy: 1 }, { t: 680, sy: 0.4 }, { t: 800, sy: 0.85 }, { t: 920, sy: 0.5 }, { t: 1040, sy: 0.65 }, { t: 1200, sy: 0.3, o: 0 }] },
      { svg: A.sparkles([[270, 470, 12], [330, 440, 9], [290, 520, 8]]), layer: "front", keys: [...show(580), { t: 1000, y: 60, o: 0 }] },
    ],
  },
  {
    id: "trapdoor", name: "Trapdoor", kind: "exit", sound: "whoosh", clearAt: 760, dur: 1100, deck: [[80, false], [900, true]], behind: [[170, true]],
    actor: [home(0), F(60, { sx: 0.95, sy: 1.05, dy: -12, e: "uiOut" }), F(160), { t: 180, x: 290, y: 330, sx: 0.85, sy: 1.2 }, { t: 420, y: 620, e: "power1.in" }, { t: 421, o: 0 }],
    props: [
      { svg: A.crack, keys: window_(0, 80) },
      { svg: A.hole, keys: window_(80, 900) },
      { svg: vl(262, 230, 70) + vl(290, 200, 100) + vl(318, 240, 60), keys: [...show(160), { t: 420, y: -60, o: 0 }] },
      { svg: A.waveArm + A.waveMarks(334, 368), origin: [300, 430], keys: [...show(420), { t: 540, r: 20 }, { t: 660, r: -20 }, { t: 760, r: 0 }, ...hide(760)] },
      { svg: puff(232, 420, 16) + puff(348, 420, 16) + sp(290, 392, 12, G), keys: [...show(900), { t: 1100, o: 0 }] },
    ],
  },
  {
    id: "anvil", name: "Anvil drop", kind: "exit", sound: "clang", clearAt: 1300, dur: 1600,
    actor: [home(0), F(300, { sx: 0.97, sy: 1.03 }), F(380, { sx: 1.7, sy: 0.15, e: "none" }), F(700, { sx: 1.78, sy: 0.15 }), F(800, { sx: 1.64, sy: 0.15 }), F(900, { sx: 1.74, sy: 0.15 }), { t: 1300, x: 410, y: 446, sx: 1.6, sy: 0.14, r: 28 }, { t: 1600, x: 560, y: 900, r: 60, e: "power1.in" }],
    props: [
      { svg: `<ellipse cx="290" cy="424" rx="60" ry="10" fill="${INK}" fill-opacity="0.25"/>`, layer: "mid", origin: [290, 424], keys: [{ t: 0, sx: 0.2, sy: 0.2 }, { t: 300, sx: 1, sy: 1 }, { t: 380, o: 0 }] },
      { svg: A.anvil(290, 354), origin: [290, 387], keys: [{ t: 0, y: -1000 }, { t: 300, y: -1000 }, { t: 380, y: 0, e: "power1.in" }, { t: 430, sy: 0.94 }, { t: 500, sy: 1 }, { t: 600, x: 0 }, { t: 900, x: 180, y: -160, r: 28, e: "power1.out" }, { t: 1300, x: 420, y: 800, r: 120, e: "power1.in" }] },
      { svg: star(166, 396, 28, 14, 8, G) + star(414, 396, 28, 14, 8, G), origin: [290, 396], keys: [{ t: 0, o: 0 }, { t: 379, o: 0, sx: 0.6, sy: 0.6 }, { t: 380, o: 1, e: "none" }, { t: 520, sx: 1, sy: 1 }, { t: 700, o: 0 }] },
      { svg: hl(236, 414, 70) + hl(226, 436, 90), keys: window_(1000, 1400) },
    ],
  },
  {
    id: "sinkhole", name: "Sinkhole", kind: "exit", sound: "gurgle", clearAt: 1100, dur: 1500, deck: [[0, false], [1500, true]], behind: [[480, true]],
    actor: [home(0), { t: 300, r: 6 }, { t: 400, r: -6 }, { t: 500, r: 0 }, { t: 1100, x: 290, y: 560, r: 900, sx: 0.7, e: "power1.in" }, { t: 1101, o: 0 }],
    props: [
      { svg: A.swirl(82), origin: [290, 436], keys: [{ t: 0, sx: 0.45, sy: 0.45 }, { t: 300, sx: 1, sy: 1, e: "back.out(1.6)" }, { t: 1300 }, { t: 1500, sx: 0.1, sy: 0.1, o: 0 }] },
      { svg: `<ellipse cx="290" cy="436" rx="72" ry="15" stroke="${L}" stroke-width="4"/>`, origin: [290, 436], keys: [{ t: 0, sx: 0.6, sy: 0.6 }, { t: 400, sx: 1.4, sy: 1.4, o: 0 }] },
      { svg: A.bubble(290, 392, 14), keys: window_(1100, 1300) },
    ],
  },
  {
    id: "claw", name: "Claw machine", kind: "exit", sound: "arcade", clearAt: 1000, dur: 2200,
    actor: [home(0), F(500, { sx: 0.97, sy: 0.97 }), F(650, { sx: 0.9, sy: 1.15 }), { t: 950, x: 290, y: lift(0.9, 1.15, 0) - 70 }, { t: 1200, x: 395, y: 265, r: 8 }, { t: 1350, x: 420, y: 262, r: -6 }, { t: 1500, x: 470, y: 262, r: -4 }, { t: 2000, x: 640, y: 1000, r: 40, e: "power1.in" }],
    props: [
      { svg: A.claw(290, 90, true), keys: [{ t: 0, y: -700 }, { t: 500, y: 0, e: "uiOut" }, ...hide(500)] },
      { svg: A.claw(290, 60, false), origin: [290, 0], keys: [...show(500), { t: 500, y: 70 }, { t: 650, y: 70 }, { t: 950, y: 0, e: "uiInOut" }, { t: 1200, x: 140, r: 6 }, { t: 1350, x: 160, r: -5 }, { t: 1500, x: 190, y: 10, r: 0 }, ...hide(1500)] },
      { svg: A.claw(480, 70, true), keys: [...show(1500), { t: 1650, y: -8 }, { t: 1800, y: 0 }, { t: 2200, y: -900, e: "power1.in" }] },
    ],
  },
  {
    id: "vacuum", name: "Vacuum", kind: "exit", sound: "vacuum", clearAt: 800, dur: 1700,
    actor: [home(0), { t: 200, x: 280, y: 303, r: -10 }, { t: 400, x: 280, r: -10 }, { t: 600, x: 326, y: 292, sx: 0.6, sy: 1.4, r: 40 }, { t: 800, x: 380, y: 236, sx: 0.25, sy: 0.6, r: 40, o: 0, e: "power1.in" }],
    props: [
      { svg: A.nozzle(430, 190, 20, "M1000 -500C700 -100 470 70 440 156"), keys: [{ t: 0, x: 500, y: -500 }, { t: 400, x: 0, y: 0, e: "uiOut" }, ...hide(400)] },
      { svg: A.nozzle(380, 236, -30, "M1000 -500C640 0 430 120 396 200"), keys: window_(400, 900) },
      { svg: `<path d="M286 330Q318 292 336 270M266 300Q306 268 326 246" stroke="${L}" stroke-width="5" stroke-linecap="round"/>`, keys: window_(450, 800) },
      { svg: A.nozzle(470, 160, 10, "M1000 -500C700 -60 500 70 476 124"), keys: [...show(900), { t: 1300, x: 700, y: -700, e: "uiInOut" }] },
      { svg: `<ellipse cx="556" cy="30" rx="36" ry="30" fill="#5D3BC3"/>`, keys: [...show(900), { t: 900, x: -60, y: 90 }, { t: 1300, x: 400, y: -400 }] },
      { svg: A.plug, origin: [520, 190], keys: [...show(1300), { t: 1380, r: -12 }, { t: 1460, r: 12 }, { t: 1540, r: -12 }, { t: 1620, r: 0 }, { t: 1700, o: 0 }] },
    ],
  },
  {
    id: "cannon", name: "Cannon", kind: "exit", sound: "boom", clearAt: 700, dur: 1800, deck: [[0, false], [1800, true]],
    actor: [home(0), F(400, { sx: 0.95, sy: 0.95 }), { t: 550, x: 340, y: 170, r: -100, sx: 0.95, sy: 1 }, { t: 700, x: 396, y: 262, r: -145, sx: 0.9, sy: 1.1, e: "power1.in" }, { t: 1000, x: 396, y: 262 }, { t: 1500, x: 1500, y: -800, r: 775, sx: 0.75, sy: 1.35, e: "power2.out" }],
    props: [
      { svg: A.cannon(250, 396, -35, 170), keys: [{ t: 0, x: -500 }, { t: 400, x: 0, e: "uiOut" }, { t: 1000 }, { t: 1060, x: -24 }, { t: 1200, x: -14 }, { t: 1500 }, { t: 1800, x: -700, e: "uiInOut" }] },
      { svg: sp(212, 414, 14, G), origin: [212, 414], keys: [...show(700), { t: 780, sx: 1.4, sy: 1.4 }, { t: 860, sx: 1, sy: 1 }, { t: 940, sx: 1.4, sy: 1.4 }, ...hide(1000)] },
      { svg: puff(372, 314, 30) + puff(402, 286, 24) + puff(346, 284, 18), origin: [380, 300], keys: [...show(1000), { t: 1000, sx: 0.5, sy: 0.5 }, { t: 1300, sx: 1.3, sy: 1.3, y: -40 }, { t: 1500, o: 0, y: -60 }] },
    ],
  },
  {
    id: "backrocket", name: "Rocket on the back", kind: "exit", sound: "sputter", clearAt: 1250, dur: 2000,
    actor: [home(0), home(200), { t: 350, y: 273, e: "power1.out" }, { t: 450, y: 303, e: "power1.in" }, { t: 600, y: 270, e: "power1.out" }, { t: 700, y: 303, e: "power1.in" }, { t: 850, y: 243, e: "power1.out" }, { t: 1100, y: 243 }, { t: 1500, y: -900, sx: 0.8, sy: 1.3, e: "power2.in" }],
    props: [
      { svg: A.backRocket(0), layer: "under", keys: [{ t: 0, o: 0, y: -20 }, { t: 200, o: 1, y: 0, e: "back.out(2)" }, ...hide(1100)] },
      { svg: A.backRocket(120), layer: "under", keys: window_(1100, 1600) },
      { svg: A.strap, layer: "attach", keys: [{ t: 0, o: 0 }, { t: 200, o: 1 }] },
      { svg: puff(354, 350, 10), keys: [...show(350), { t: 600, y: 10, o: 0 }] },
      { svg: puff(340, 340, 8), keys: [...show(600), { t: 850, y: 10, o: 0 }] },
      { svg: puff(300, 400, 30) + puff(320, 330, 24) + puff(340, 262, 20) + puff(350, 200, 16), keys: [...show(1150), { t: 1500, y: -30 }, { t: 2000, o: 0, y: -60 }] },
    ],
  },
  {
    id: "catapult", name: "Catapult", kind: "exit", sound: "thwack", clearAt: 700, dur: 1600, deck: [[0, false], [1600, true]],
    actor: [home(0), { t: 300, x: 440, y: 352, sx: 0.96, sy: 0.64 }, { t: 600, x: 440, y: 352 }, { t: 680, x: 170, y: 150, r: -35, sx: 0.66, sy: 1.1, e: "power2.out" }, { t: 1100, x: -500, y: -800, r: -220, sx: 0.5, sy: 0.5, e: "power1.out" }],
    props: [
      { svg: A.catapult(440, 404, false), origin: [290, 426], keys: [{ t: 0, sy: 0 }, { t: 300, sy: 1, e: "back.out(1.4)" }, ...hide(600)] },
      { svg: A.catapult(196, 268, false), origin: [290, 426], keys: [...show(600), { t: 1300, sy: 1 }, { t: 1600, sy: 0, o: 0 }] },
      { svg: A.catapult(196, 268, true), keys: window_(680, 1100) },
      { svg: `<path d="M216 296L196 284M226 286L214 268M252 296L264 280" stroke="${INK}" stroke-width="5" stroke-linecap="round"/>`, keys: window_(680, 900) },
    ],
  },
  {
    id: "toilet", name: "Toilet flush", kind: "exit", sound: "flush", clearAt: 1100, dur: 1500, deck: [[0, false], [1500, true]], behind: [[700, true]],
    actor: [home(0), F(250, { fy: 432 }), { t: 500, x: 290, y: 350, r: -120, sx: 0.8, sy: 1 }, { t: 900, y: 470, r: -300, sx: 0.6, sy: 1.2 }, { t: 1100, y: 580, r: -500, sx: 0.4, sy: 1, o: 0, e: "power1.in" }],
    props: [
      { svg: A.toiletLid, layer: "mid", origin: [290, 430], keys: [{ t: 0, sy: 0 }, { t: 250, sy: 1, e: "back.out(1.6)" }, ...hide(1300)] },
      { svg: A.bowl(false), origin: [290, 440], keys: [{ t: 0, sx: 0.3, sy: 0.3 }, { t: 250, sx: 1, sy: 1, e: "back.out(1.6)" }, ...hide(300)] },
      { svg: A.bowl(true), keys: window_(300, 1300) },
      { svg: A.bowl(false) + A.lidShut, origin: [290, 440], keys: [...show(1300), { t: 1500, sx: 0.2, sy: 0.2, o: 0 }] },
      { svg: A.bubble(300, 366), keys: window_(1300, 1500) },
    ],
  },
  {
    id: "pinball", name: "Pinball bumper", kind: "exit", sound: "ding", clearAt: 500, dur: 2000, deck: [[0, false], [1500, true]],
    actor: [home(0), { t: 200, x: 300, y: 318, r: -20, sx: 0.9, sy: 0.9 }, { t: 500, x: 184, y: 246, r: -50, sx: 1.04, sy: 0.6, e: "none" }, { t: 560, x: 200, y: 240, r: -90, sx: 0.72, sy: 0.72 }, { t: 850, x: 404, y: 196, r: -160, e: "none" }, { t: 910, x: 400, y: 190, r: -200 }, { t: 1150, x: 310, y: 124, r: -320, e: "none" }, { t: 1400, x: 150, y: 420, r: -400, e: "none" }, { t: 1700, x: 82, y: 640, r: -450, sx: 0.5, sy: 0.5, o: 0, e: "power1.in" }],
    props: [
      { svg: A.BUMPERS.map(([x, y]) => A.bumper(x, y)).join(""), layer: "back", origin: [290, 160], keys: [{ t: 0, sx: 0, sy: 0 }, { t: 200, sx: 1, sy: 1, e: "back.out(2)" }, { t: 1700 }, { t: 2000, sx: 0, sy: 0 }] },
      { svg: A.bumperLit(130, 230), layer: "back", keys: window_(500, 640) },
      { svg: A.bumperLit(450, 170), layer: "back", keys: window_(850, 990) },
      { svg: A.bumperLit(290, 80), layer: "back", keys: window_(1150, 1290) },
      { svg: A.tiltDeck, keys: window_(0, 500) },
      { svg: A.gutter, keys: [{ t: 0, o: 0 }, { t: 1300, o: 1 }, { t: 2000, o: 0 }] },
    ],
  },
  {
    id: "deflate", name: "Deflating", kind: "exit", sound: "pfft", clearAt: 700, dur: 2500,
    actor: [home(0), F(200, { sx: 1.1, sy: 1.08, e: "uiOut" }), { t: 700, x: 392, y: 216, r: 30, sx: 0.7, sy: 0.7, e: "power1.out" }, { t: 1000, x: 470, y: 110, r: 120, sx: 0.6, sy: 0.6, e: "none" }, { t: 1300, x: 330, y: 60, r: 260, sx: 0.5, sy: 0.5, e: "none" }, { t: 1550, x: 250, y: 150, r: 380, sx: 0.45, sy: 0.45, e: "none" }, { t: 1800, x: 120, y: 120, r: 480, sx: 0.4, sy: 0.4, e: "none" }, { ...F(2100, { cx: 320, sx: 0.55, sy: 0.12 }), r: 720, e: "uiOut" }, { t: 2500, o: 0 }],
    props: [
      { svg: puff(378, 318, 10), keys: window_(0, 300) },
      { svg: puff(330, 282, 14) + puff(302, 312, 10) + puff(278, 336, 7), keys: [...show(500), { t: 900, o: 0, x: -20, y: 20 }] },
      { svg: puff(350, 392, 8), keys: [...show(2200), { t: 2500, o: 0, y: -10 }] },
    ],
  },
  {
    id: "melt", name: "Melting", kind: "exit", sound: "drip", clearAt: 1500, dur: 2000,
    actor: [home(0), F(500, { sx: 1.03, sy: 0.94, e: "uiInOut" }), F(1200, { sx: 1.3, sy: 0.5, e: "uiInOut" }), F(1500, { sx: 2.2, sy: 0.12, o: 0 })],
    props: [
      { svg: A.drip(222, 404) + A.drip(356, 406), keys: [{ t: 0, o: 0 }, { t: 200, o: 1 }, { t: 800, y: 20 }, ...hide(800)] },
      { svg: A.puddle, layer: "mid", origin: [290, 420], keys: [{ t: 0, o: 0, sx: 0.3 }, { t: 800, o: 1, sx: 0.3 }, { t: 1500, sx: 1, e: "uiInOut" }, ...hide(1500)] },
      { svg: A.drip(184, 444) + A.drip(398, 452), keys: [...show(800), { t: 1500, y: 40, o: 0 }] },
      { svg: A.puddleEyes(272, 410, 308, 410), origin: [290, 410], keys: [...show(1300), { t: 1400, sy: 0.1 }, { t: 1450, sy: 1 }, ...hide(1500)] },
      { svg: A.puddleSlide + A.puddleEyes(364, 430, 388, 440), keys: [...show(1500), { t: 1700, x: 20, y: 40 }, { t: 2000, x: 40, y: 500, e: "power1.in" }] },
    ],
  },
  {
    id: "conveyor", name: "Conveyor belt", kind: "exit", sound: "hum", clearAt: 1700, dur: 2200, deck: [[0, false], [2200, true]],
    actor: [home(0), { t: 300, x: 282, y: 300, r: -6 }, { t: 500, x: 290, r: 0 }, { ...F(1600, { cx: 410 }), e: "none" }, { t: 1900, x: 448, y: 330, r: 35, sx: 0.9, sy: 1.1, e: "power1.in" }, { t: 2200, x: 480, y: 800, r: 70, e: "power1.in" }],
    props: [
      { svg: A.belt(), keys: [{ t: 0, o: 0 }, { t: 300, o: 1 }, { t: 2100 }, { t: 2200, o: 0 }] },
      { svg: A.waveMarks(-14, 70), layer: "attach", keys: window_(800, 1500) },
      { svg: A.waveMarks(470, 360), keys: window_(1950, 2200) },
    ],
  },
  {
    id: "escort", name: "Escorted out", kind: "exit", sound: "whistle", clearAt: 900, dur: 2400,
    actor: [home(0), home(500), F(650, { sx: 0.92, sy: 1.1, dy: -40, e: "uiOut" }), F(850, { sx: 0.92, sy: 1.1, dy: -40 }), { t: 2000, x: 990, y: 263, r: -8, sx: 0.92, sy: 1.1, e: "uiInOut" }],
    props: [
      { kind: "guard", keys: [{ t: 0, x: -300, y: 371, sx: 0.55, sy: 0.55 }, { t: 500, x: 214, y: 367, e: "none" }, { t: 850, x: 214 }, { t: 2000, x: 914, e: "uiInOut" }] },
      { kind: "guard", keys: [{ t: 0, x: 900, y: 371, sx: 0.55, sy: 0.55 }, { t: 500, x: 366, y: 367, e: "none" }, { t: 850, x: 366 }, { t: 2000, x: 1066, e: "uiInOut" }] },
      { svg: A.kicks(76.7, 250), layer: "attach", origin: [76, 250], keys: [...show(650), { t: 800, r: 10 }, { t: 950, r: -10 }, { t: 1100, r: 10 }, { t: 1250, r: -10 }, { t: 1400, r: 10 }, { t: 1550, r: -10 }, ...hide(2000)] },
    ],
  },
  {
    id: "asleep", name: "Falling asleep", kind: "exit", sound: "snore", clearAt: 1300, dur: 2400,
    actor: [home(0), F(600, { sy: 1.08, e: "uiInOut" }), { t: 1100, x: 304, y: 318, r: 20, sx: 1.05, sy: 0.92, e: "uiOut" }, { t: 1500, x: 442, y: 486, r: 80, e: "power1.in" }, { t: 2000, x: 480, y: 1000, r: 90, e: "power1.in" }],
    props: [
      { svg: A.yawn, origin: [290, 286], keys: [{ t: 0, sy: 0.3, o: 0 }, { t: 150, o: 1 }, { t: 400, sy: 1 }, { t: 600, sy: 0.3, o: 0 }] },
      { svg: A.zzz(372, 180, 48), keys: [...show(700), { t: 2000, y: -120, o: 0 }] },
      { svg: A.zzz(420, 140, 36), keys: [...show(900), { t: 2200, y: -120, o: 0 }] },
      { svg: A.zzz(452, 330, 44), keys: [...show(1400), { t: 2400, y: -140, o: 0 }] },
      { kind: "hat", keys: [{ t: 0, o: 0 }, { t: 1300, o: 0, x: 304, y: 318, r: 20 }, { t: 1301, o: 1, e: "none" }, { t: 1600, x: 300, y: 485, r: -8, e: "power1.in" }, { t: 2400 }] },
    ],
  },
  {
    id: "monster", name: "Monster swallow", kind: "exit", sound: "gulp", clearAt: 700, dur: 2400,
    actor: [home(0), { t: 120, r: 4 }, { t: 250, r: -4 }, { t: 400, r: 0 }, home(550), { t: 560, o: 0, e: "none" }],
    props: [
      { svg: A.monster(660) + A.eyesUp(650), keys: [{ t: 0, y: 80 }, { t: 250, y: 0 }, ...hide(250)] },
      { svg: A.shake, keys: window_(0, 250) },
      { svg: A.monster(150) + A.mouthOpen(150) + A.eyesUp(110), layer: "mid", keys: [...show(250), { t: 250, y: 560 }, { t: 550, y: 0, e: "uiOut" }, ...hide(700)] },
      { svg: A.teeth(150), keys: [...show(250), { t: 250, y: 560 }, { t: 550, y: 0, e: "uiOut" }, ...hide(700)] },
      { svg: A.monster(150) + A.mouthShut + A.eyesUp(110), origin: [290, 300], keys: [...show(700), { t: 800, sx: 1.04 }, { t: 900, sx: 1 }, { t: 1000, sx: 1.04 }, { t: 1100, sx: 1, y: 0 }, { t: 1800, y: 620, e: "uiInOut" }] },
      { svg: puff(390, 440, 30) + puff(420, 408, 20), keys: [...show(1300), { t: 1800, y: -80, o: 0 }] },
      { kind: "hat", keys: [{ t: 0, o: 0 }, { t: 1000, o: 0, x: 300, y: -200 }, { t: 1001, o: 1, e: "none" }, { t: 1800, x: 300, y: 485, r: 18, e: "power1.out" }, { t: 2400 }] },
    ],
  },
  {
    id: "ufo", name: "UFO abduction", kind: "exit", sound: "theremin", clearAt: 1200, dur: 2300,
    actor: [home(0), home(700), { t: 1000, y: 260, r: -15, sx: 0.92, sy: 1.1 }, { t: 1200, y: 220, r: 15 }, { t: 1400, y: 190, r: -15, sx: 0.8, sy: 0.88 }, { t: 1600, y: 150, r: 15, sx: 0.6, sy: 0.66 }, { t: 1700, y: 110, r: 0, sx: 0.35, sy: 0.35, o: 0 }],
    props: [
      { svg: A.tractor(290, 90), layer: "mid", keys: [{ t: 0, o: 0 }, { t: 500, o: 0 }, { t: 540, o: 1, e: "none" }, { t: 580, o: 0.2, e: "none" }, { t: 620, o: 1, e: "none" }, { t: 1700 }, { t: 1750, o: 0 }] },
      { svg: A.ufo(290, 90), origin: [290, 90], keys: [{ t: 0, x: 300, y: -500, r: 12 }, { t: 500, x: 0, y: 0, r: 0, e: "uiOut" }, { t: 700, r: 5 }, { t: 800, r: -5 }, { t: 900, r: 0 }, { t: 1700 }, { t: 2200, x: 900, y: -700, sx: 0.55, sy: 0.55, e: "power1.in" }] },
      { svg: A.flail(76.7, 140), layer: "attach", keys: window_(700, 1500) },
      { svg: A.sparkles([[440, 92, 14], [384, 122, 11], [330, 146, 8]]), keys: [...show(1800), { t: 2300, o: 0 }] },
    ],
  },
];

export const COMBOS: Seq[] = [
  {
    id: "trading", name: "Trading places", kind: "combo", sound: "fanfare", clearAt: 900, dur: 1800,
    actor: [home(0), home(500), { t: 560, x: 352, y: 300, r: -14, sx: 0.8, sy: 1.1 }, { t: 900, x: 1400, y: -500, r: 300, sx: 0.85, sy: 1.2, e: "power1.out" }],
    other: [{ t: 0, x: -500, y: 300, r: 12, sx: 1.05, sy: 0.95 }, { t: 380, x: 200, e: "none" }, { t: 500, x: 222, r: 14, sx: 0.9, sy: 1 }, { t: 700, x: 250, y: 303, r: 0, sx: 1, sy: 1 }, F(900), F(1100, { dy: -30, e: "power1.out" }), F(1250, { e: "power1.in" }), F(1450, { dy: -30, e: "power1.out" }), F(1600, { e: "power1.in" }), F(1800, { e: "back.out(2)" })],
    props: [
      { svg: hl(-80, 110, 60) + hl(-90, 150, 70) + hl(-70, 190, 50), layer: "attach", who: "other", keys: window_(0, 500) },
      { svg: star(292, 286, 36, 18, 8, G), origin: [292, 286], keys: [...show(500), { t: 500, sx: 0.5, sy: 0.5 }, { t: 600, sx: 1.1, sy: 1.1 }, ...hide(700)] },
      { svg: A.sparkles([[196, 200, 20], [392, 176, 16], [412, 300, 12]]), keys: [...show(1100), { t: 1800, o: 0 }] },
    ],
  },
  {
    id: "banana", name: "Banana peel", kind: "combo", sound: "squeak", clearAt: 1700, dur: 2200,
    actor: [home(0), home(900), { t: 960, x: 330, y: 300, sx: 0.85, sy: 1.1 }, { t: 1300, x: 1400, y: -600, r: 320, sx: 0.85, sy: 1.2, e: "power1.out" }],
    other: [{ t: 0, x: -500, y: 300, r: 10 }, { t: 450, x: 150, e: "none" }, { t: 600, x: 200, y: 230, r: -110, sx: 0.9, sy: 0.9, e: "uiOut" }, { t: 900, x: 300, y: 256, r: -160, e: "power1.in" }, { t: 1300, x: 300, y: 260, r: -300 }, { ...F(1500, { sx: 1.2, sy: 0.82 }), r: -360, e: "power1.in" }, { ...F(1700, { sx: 1.2, sy: 0.82 }), r: -360 }, { ...F(2200), r: -360, e: "back.out(2)" }],
    props: [
      { svg: A.peel(226, 420), origin: [226, 410], keys: [{ t: 0 }, { t: 450 }, { t: 700, x: -140, y: -80, r: -180, e: "power1.out" }, { t: 1000, x: -400, y: 200, r: -400, e: "power1.in" }] },
      { svg: `<path d="M196 380Q170 360 160 330M240 392Q230 368 236 340" stroke="${L}" stroke-width="5" stroke-linecap="round"/>`, keys: window_(450, 700) },
      { svg: star(330, 250, 36, 18, 8, G), keys: window_(900, 1100) },
      { svg: A.sparkles([[244, 196, 14], [290, 172, 12], [336, 196, 14]]), origin: [290, 186], keys: [...show(1500), { t: 1850, r: 20 }, { t: 2200, r: 0, o: 0 }] },
    ],
  },
];

export const ALL_EXITS = [...EXITS, ...COMBOS];
export { H0 };
