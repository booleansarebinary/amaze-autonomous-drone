// Entrances for a new player arriving on an empty step (Figma 04-1, 04-2 and the 08 entrance library). Times in ms.
import { type Seq, F, home, show, hide, window_ } from "./types";
import * as A from "../art/props";
import { G, L, INK, sp, puff, hl } from "../art/svg";
import { BODY_COLORS } from "../art/characters";

const at = (t: number, k: object = {}) => ({ ...home(t), ...k });

export const ENTRANCES: Seq[] = [
  {
    id: "parachute", name: "Parachute", kind: "entrance", sound: "flutter", clearAt: 1450, dur: 2120,
    actor: [{ t: 0, x: 330, y: -560, sx: 0.9, sy: 1.1 }, { t: 80, y: -500 }, { t: 240, x: 330, y: -470, sx: 1, sy: 1, e: "uiOut" }, { t: 700, x: 290, y: -180, r: -8, e: "sine.inOut" }, { t: 1100, x: 320, y: 120, r: 8, e: "sine.inOut" }, { ...F(1400), e: "uiOut" }, F(1500, { sx: 1.15, sy: 0.85 }), F(1700, { e: "back.out(1.5)" })],
    props: [
      { svg: A.canopy, layer: "attach", origin: [76.7, -90], keys: [{ t: 0, sx: 1.2, sy: 0.6 }, { t: 240, sx: 1, sy: 1, e: "back.out(1.8)" }, { t: 1400 }, { t: 1520, o: 0 }] },
      { svg: A.canopyDown, layer: "mid", keys: [...show(1520), { t: 1820 }, { t: 2120, o: 0 }] },
      { svg: A.sparkles([[170, 250, 17], [394, 210, 13], [418, 360, 10], [150, 390, 9]]), origin: [290, 300], keys: [...show(1450), { t: 1450, sx: 0.6, sy: 0.6 }, { t: 1600, sx: 1, sy: 1 }, { t: 1900, o: 0 }] },
    ],
  },
  {
    id: "dive", name: "Head-first dive", kind: "entrance", sound: "whistle-boom", clearAt: 1000, dur: 1700, big: true,
    actor: [{ t: 0, o: 0 }, { t: 119, o: 0, x: 290, y: -800, r: 180, sx: 0.8, sy: 1.3 }, { t: 120, o: 1, e: "none" }, { t: 450, x: 290, y: 342, e: "power1.in" }, { t: 451, sx: 1.3, sy: 0.68, e: "none" }, { t: 530 }, { t: 830, x: 290, y: 83, r: 360, sx: 1, sy: 1, e: "power1.out" }, { ...F(1000, { sx: 1.25, sy: 0.78 }), r: 360, e: "power1.in" }, { ...F(1400), r: 360, e: "back.out(2)" }],
    rocket: [{ t: 0, y: 0 }, { t: 450 }, { t: 470, y: 14, e: "power2.out" }, { t: 650, y: 0, e: "back.out(2)" }, { t: 1000 }, { t: 1015, y: 8 }, { t: 1200, y: 0, e: "back.out(2)" }],
    props: [
      { svg: A.dropCue, origin: [290, 40], keys: [{ t: 0, sx: 0.4, sy: 0.4 }, { t: 60, sx: 1.2, sy: 1.2 }, { t: 120, sx: 1, sy: 1 }, ...hide(160)] },
      { svg: A.burst(290, 440, 1.3), layer: "mid", origin: [290, 440], keys: [{ t: 0, o: 0 }, { t: 449, o: 0, sx: 0.6, sy: 0.6 }, { t: 450, o: 1, e: "none" }, { t: 610, sx: 1.15, sy: 1.15 }, { t: 700, sx: 1, sy: 1 }, { t: 800, o: 0 }] },
      { svg: puff(120, 426, 34) + puff(170, 404, 22) + puff(460, 426, 34) + puff(410, 404, 22), origin: [290, 420], keys: [{ t: 0, o: 0 }, { t: 449, o: 0, sx: 0.4, sy: 0.4 }, { t: 450, o: 1, e: "none" }, { t: 850, sx: 1, sy: 1, o: 0, e: "uiOut" }] },
      { svg: A.sparkles([[220, 170, 14], [290, 150, 12], [360, 170, 14]]), origin: [290, 160], keys: [...show(650), { t: 950, r: 20 }, { t: 1250, r: 40, o: 0 }] },
      { svg: A.sparkles([[140, 190, 17], [420, 150, 14], [440, 340, 11], [120, 360, 10]]), keys: [...show(1300), { t: 1700, o: 0 }] },
    ],
  },
  {
    id: "elevator", name: "Elevator drop", kind: "entrance", sound: "ding", clearAt: 800, dur: 1300, deck: [[0, false], [900, true]],
    actor: [{ ...F(0, { fy: 420 }), y: F(0, { fy: 420 }).y! - 1100 }, { ...F(200, { fy: 420 }), e: "back.out(1.2)" }, F(600, { fy: 420 }), { ...F(750, { sx: 1.12, sy: 0.9 }), e: "power1.in" }, { ...F(950), e: "back.out(1.5)" }],
    props: [
      { svg: A.cabBack, layer: "mid", keys: [{ t: 0, y: -1100 }, { t: 200, y: 0, e: "back.out(1.2)" }, { t: 900 }, { t: 1300, y: -1300, e: "uiInOut" }] },
      { svg: A.doorL, origin: [208, 286], keys: [{ t: 0, y: -1100 }, { t: 200, y: 0, e: "back.out(1.2)" }, { t: 330 }, { t: 550, sx: 0, e: "uiInOut" }, { t: 560, o: 0 }] },
      { svg: A.doorR, origin: [372, 286], keys: [{ t: 0, y: -1100 }, { t: 200, y: 0, e: "back.out(1.2)" }, { t: 330 }, { t: 550, sx: 0, e: "uiInOut" }, { t: 560, o: 0 }] },
      { svg: A.cabFrame, keys: [{ t: 0, y: -1100 }, { t: 200, y: 0, e: "back.out(1.2)" }, { t: 900 }, { t: 1300, y: -1300, e: "uiInOut" }] },
      { svg: sp(346, 112, 14, G), origin: [346, 112], keys: [...show(200), { t: 260, sx: 1.4, sy: 1.4 }, { t: 340, sx: 1, sy: 1 }, ...hide(450)] },
    ],
  },
  {
    id: "bungee", name: "Bungee jump", kind: "entrance", sound: "boing", clearAt: 1200, dur: 1500,
    actor: [{ t: 0, x: 290, y: -800, r: 180, sx: 0.8, sy: 1.3 }, { t: 400, y: 300, sx: 1.1, sy: 0.9, e: "power1.in" }, { t: 460 }, { t: 750, y: 170, sx: 0.9, sy: 1.15, e: "power1.out" }, { t: 1000, y: 260, sx: 1, sy: 1, e: "sine.inOut" }, { ...F(1200, { sx: 1.2, sy: 0.82 }), r: 360, e: "power1.in" }, { ...F(1500), r: 360, e: "back.out(2)" }],
    props: [
      { svg: A.bungee, layer: "under", keys: [{ t: 0 }, ...hide(1000)] },
      { svg: A.cordUp, keys: [...show(1000), { t: 1400, y: -1600, e: "power1.in" }] },
      { svg: puff(214, 420, 12) + puff(366, 420, 12), keys: [...show(1200), { t: 1500, o: 0 }] },
    ],
  },
  {
    id: "meteor", name: "Meteor landing", kind: "entrance", sound: "boom", clearAt: 1100, dur: 2200, big: true,
    actor: [{ t: 0, o: 0 }, { ...F(599, { sx: 1.15, sy: 0.82 }), o: 0 }, { ...F(600, { sx: 1.15, sy: 0.82 }), o: 1, e: "none" }, { ...F(1100), e: "uiOut" }],
    rocket: [{ t: 0, y: 0 }, { t: 300 }, { t: 320, y: 10 }, { t: 500, y: 0, e: "back.out(2)" }],
    props: [
      { svg: sp(60, 60, 18, G), keys: window_(0, 150) },
      { svg: A.fireball(290, 410), keys: [{ t: 0, o: 0 }, { t: 149, o: 0, x: -500, y: -800 }, { t: 150, o: 1, e: "none" }, { t: 300, x: 0, y: 0, e: "power1.in" }, ...hide(300)] },
      { svg: A.splat, origin: [290, 410], keys: [...show(300), { t: 300, sx: 0.6, sy: 0.6 }, { t: 380, sx: 1.15, sy: 1.15 }, { t: 460, sx: 1, sy: 1 }, ...hide(460)] },
      { svg: A.crater, layer: "mid", keys: [...show(300), { t: 1200 }, { t: 2200, o: 0 }] },
      { svg: puff(206, 360, 40) + puff(376, 350, 44) + puff(300, 400, 30), origin: [290, 380], keys: [...show(320), { t: 320, sx: 0.4, sy: 0.4 }, { t: 700, sx: 1.1, sy: 1.1 }, { t: 1100, o: 0, y: -40 }] },
      { svg: A.wisps, keys: [...show(1100), { t: 1700, o: 0, y: -30 }] },
    ],
  },
  {
    id: "balloons", name: "Balloon bunch", kind: "entrance", sound: "whistle", clearAt: 950, dur: 1800,
    actor: [{ t: 0, x: 320, y: -420, r: 6 }, { t: 300, x: 290, y: -200, r: -6, e: "sine.inOut" }, { t: 600, x: 330, y: 20, r: 6, e: "sine.inOut" }, { ...F(900, { sx: 1.1, sy: 0.9 }), e: "uiOut" }, { ...F(1100), e: "back.out(1.4)" }],
    props: [
      { svg: A.balloons(150, -150, 1.1, [140, 184]), layer: "attach", keys: [{ t: 0 }, ...hide(1100)] },
      { svg: A.balloons(420, 90, 1), keys: [...show(1100), { t: 1100, x: -40, y: 30 }, { t: 1800, x: 160, y: -800, e: "power1.in" }] },
    ],
  },
  {
    id: "toaster", name: "Pop-up toaster", kind: "entrance", sound: "ding-pop", clearAt: 800, dur: 1400, deck: [[0, false], [1000, true]], behind: [[0, true], [300, false]],
    actor: [at(0, { y: 410 }), at(150, { y: 410 }), at(300, { y: 150, sx: 0.8, sy: 1.3, e: "power2.out" }), at(500, { y: 120, r: 180, e: "none" }), at(650, { y: 110, r: 360 }), { ...F(800, { sx: 1.2, sy: 0.82 }), r: 360, e: "power1.in" }, { ...F(1000), r: 360, e: "back.out(1.8)" }],
    props: [
      { svg: A.toaster(false), origin: [290, 426], keys: [{ t: 0, sy: 0.2 }, { t: 150, sy: 1, e: "back.out(1.6)" }, ...hide(300)] },
      { svg: A.heat, keys: window_(0, 300) },
      { svg: A.toaster(true), origin: [290, 426], keys: [...show(300), { t: 800 }, { t: 1000, sy: 0, o: 0 }] },
      { svg: `<path d="M226 304L210 288M354 304L370 288M290 300V284" stroke="${L}" stroke-width="5" stroke-linecap="round"/>`, keys: window_(300, 450) },
      { svg: A.crumbs, keys: [...show(800), { t: 1400, o: 0 }] },
    ],
  },
  {
    id: "whack", name: "Whack-a-mole", kind: "entrance", sound: "pop", clearAt: 1200, dur: 1500,
    actor: [{ t: 0, x: 290, y: 520, o: 0 }, { t: 199, o: 0 }, { t: 200, y: 480, o: 1, e: "none" }, { t: 300, y: 420, sx: 0.9, sy: 1.12, e: "uiOut" }, { t: 400, y: 350, sx: 1, sy: 1 }, { t: 650, r: -8 }, { t: 900, r: 8 }, { t: 1100, x: 290, y: 303, r: 0, e: "back.out(1.4)" }],
    rocket: [{ t: 0, o: 0, y: 140 }, { t: 900 }, { t: 901, o: 1, e: "none" }, { t: 1300, y: 0, e: "back.out(1.4)" }],
    props: [
      { svg: A.moleHole, layer: "mid", origin: [290, 432], keys: [{ t: 0, sx: 0.2, sy: 0.2 }, { t: 200, sx: 1, sy: 1, e: "back.out(2)" }, { t: 900 }, { t: 1100, sx: 0.1, sy: 0.1, o: 0 }] },
      { svg: A.moleLip, keys: [{ t: 0 }, ...hide(900)] },
      { svg: A.lookL, keys: window_(500, 750) },
      { svg: A.lookR, keys: window_(750, 950) },
      { svg: A.sparkles([[150, 470, 18], [432, 520, 14], [140, 600, 10, L], [446, 640, 12, L]]), keys: [...show(1100), { t: 1500, o: 0 }] },
    ],
  },
  {
    id: "geyser", name: "Geyser", kind: "entrance", sound: "splash", clearAt: 900, dur: 1500,
    actor: [{ t: 0, x: 290, y: 330, o: 0 }, { t: 199, o: 0 }, { t: 200, o: 1, sx: 0.9, sy: 1.1, e: "none" }, { t: 500, y: 77, e: "uiOut" }, { t: 800, y: 200, r: -10, e: "sine.inOut" }, { ...F(900, { sx: 1.25, sy: 0.78 }), e: "power1.in" }, { ...F(1200), e: "back.out(2)" }],
    props: [
      { svg: A.drops([[270, 398], [300, 384], [322, 402], [256, 376]]), keys: [...show(0), { t: 100, y: -20 }, ...hide(200)] },
      { svg: A.geyser, origin: [290, 432], keys: [{ t: 0, o: 0, sy: 0 }, { t: 200, o: 1, e: "none" }, { t: 500, sy: 1, e: "uiOut" }, { t: 800, sy: 0.3, e: "uiInOut" }, { t: 900, sy: 0, o: 0 }] },
      { svg: A.drops([[220, 320], [372, 300], [240, 250], [350, 360]]), keys: [...show(600), { t: 900, y: 80 }, ...hide(900)] },
      { svg: A.drops([[184, 380], [204, 352], [396, 380], [376, 352], [168, 410], [412, 410]]), keys: [...show(900), { t: 1300, y: 30, o: 0 }] },
      { svg: A.splashPool, layer: "mid", keys: [...show(900), { t: 1500, o: 0 }] },
    ],
  },
  {
    id: "dig", name: "Digging out", kind: "entrance", sound: "crunch", clearAt: 1200, dur: 1700, deck: [[0, false], [1500, true]], behind: [[0, true], [1150, false]],
    actor: [{ t: 0, o: 0, x: 290, y: 480, r: 6, sx: 0.9 }, { t: 500, o: 0 }, { t: 501, o: 1, e: "none" }, { t: 800, y: 420 }, { t: 1000, y: 373, r: -6 }, { ...F(1200), e: "uiOut" }, { t: 1300, r: -8 }, { t: 1400, r: 8 }, { t: 1500, r: 0 }],
    props: [
      { svg: A.reachArm(300, 300), layer: "mid", keys: [...show(300), { t: 300, y: 80 }, { t: 500, y: 0, e: "uiOut" }, ...hide(800)] },
      { svg: A.mound, origin: [290, 432], keys: [{ t: 0, sy: 0.6 }, { t: 150, sy: 1.05 }, { t: 300, sy: 1 }, { t: 1000 }, { t: 1400, sy: 0.2, o: 0 }] },
      { svg: A.moundCracks, keys: window_(0, 300) },
      { svg: A.chunks([[250, 330, 30], [348, 316, -20], [300, 290, 10]]), keys: [...show(350), { t: 700, y: -60, o: 0 }] },
      { svg: A.chunks([[200, 300, 40], [380, 280, -30]]), keys: [...show(700), { t: 1000, y: -40, o: 0 }] },
      { svg: A.flatMound + puff(206, 340, 12) + puff(380, 330, 10), keys: [...show(1200), { t: 1700, o: 0 }] },
    ],
  },
  {
    id: "skateboard", name: "Skateboard", kind: "entrance", sound: "clack", clearAt: 900, dur: 1700,
    actor: [F(0, { cx: -400, fy: 404 }), { ...F(400, { cx: 110, fy: 404 }), e: "uiOut" }, F(500, { cx: 200, fy: 404, sy: 0.92 }), { t: 700, x: 254, y: 180, r: 8, sx: 1, sy: 1, e: "power1.out" }, { ...F(900, { fy: 410, sx: 1.15, sy: 0.86 }), e: "power1.in" }, F(1050, { fy: 410 }), { ...F(1250, { cx: 270 }), e: "back.out(1.5)" }],
    props: [
      { svg: A.board(76.7, 262), layer: "attach", keys: [{ t: 0 }, ...hide(1050)] },
      { svg: `<g transform="rotate(80 392 330)">${A.board(392, 330)}</g>`, keys: [...show(1050), { t: 1200, y: -10 }, { t: 1300, y: 0 }, { t: 1700, o: 0 }] },
      { svg: hl(-80, 110, 60) + hl(-90, 150, 70) + hl(-70, 190, 50), layer: "attach", keys: window_(0, 400) },
    ],
  },
  {
    id: "stampede", name: "Stampede arrival", kind: "entrance", sound: "skid", clearAt: 600, dur: 1600,
    actor: [{ t: 0, x: -450, y: 300, r: 14, sx: 1.05, sy: 0.95 }, { t: 400, x: 300, y: 306, r: -14, sx: 1.1, sy: 0.92, e: "none" }, { ...F(600), e: "uiOut" }, F(800)],
    props: [
      { svg: hl(-80, 110, 60) + hl(-90, 150, 70) + hl(-70, 190, 50), layer: "attach", keys: window_(0, 400) },
      { svg: A.skid, keys: [...show(400), { t: 800, o: 0 }] },
      { svg: A.dustCloud, keys: [{ t: 0, o: 0 }, { t: 799, o: 0, x: -800 }, { t: 800, o: 1, e: "none" }, { t: 1100, x: 0, e: "uiInOut" }, { t: 1600, o: 0 }] },
    ],
  },
  {
    id: "teleport", name: "Teleport", kind: "entrance", sound: "zap", clearAt: 650, dur: 1000,
    actor: [at(0, { o: 0 }), at(200, { o: 0 }), at(450, { o: 1, e: "steps(6)" }), at(500, { o: 0.6, e: "none" }), at(550, { o: 1, e: "none" }), at(600, { o: 0.7, e: "none" }), at(650, { o: 1, e: "none" }), at(720, { o: 0.8, e: "none" }), at(760, { o: 1, e: "none" })],
    props: [
      { svg: A.beam, layer: "mid", origin: [290, 430], keys: [{ t: 0, sy: 0 }, { t: 200, sy: 1, e: "uiOut" }, { t: 650 }, { t: 800, o: 0 }] },
      { svg: A.pixels, keys: [...show(200), { t: 330, o: 0.5 }, ...hide(450)] },
      { kind: "ghost", keys: [{ t: 0, o: 0, x: 276, y: 303 }, { t: 450, o: 0 }, { t: 451, o: 0.35, e: "none" }, { t: 520, x: 304 }, { t: 600, x: 276 }, { t: 650, o: 0 }] },
      { svg: A.glitchBars, keys: [...show(450), { t: 500, o: 0, e: "none" }, { t: 550, o: 1, e: "none" }, ...hide(650)] },
      { svg: A.sparkles([[226, 220, 10], [360, 300, 8], [240, 380, 7]]), keys: [...show(650), { t: 1000, y: 40, o: 0 }] },
    ],
  },
  {
    id: "portal", name: "Portal", kind: "entrance", sound: "hum", clearAt: 800, dur: 1400,
    actor: [{ t: 0, o: 0, x: 290, y: 310, sx: 0.69, sy: 0.92 }, { t: 400, o: 0 }, { t: 401, o: 1, e: "none" }, { ...F(800), e: "uiInOut" }],
    props: [
      { svg: A.portal, layer: "mid", origin: [290, 300], keys: [{ t: 0, sx: 0.35, sy: 0.35 }, { t: 300, sx: 1, sy: 1, e: "back.out(1.5)" }, { t: 800 }, { t: 1100, sx: 0.05, sy: 0.05, e: "power2.in" }, { t: 1101, o: 0 }] },
      { svg: A.sparkles([[390, 180, 14], [420, 230, 10, "#5D3BC3"], [380, 260, 8]]), keys: [...show(1100), { t: 1400, o: 0 }] },
    ],
  },
  {
    id: "magician", name: "Magician's reveal", kind: "entrance", sound: "ta-da", clearAt: 500, dur: 2000, big: true,
    actor: [{ t: 0, o: 0 }, { ...F(299), o: 0 }, { ...F(300), o: 1, e: "none" }, { ...F(500, { dy: -16, sx: 0.95, sy: 1.06 }), e: "back.out(1.6)" }, { ...F(800), e: "uiOut" }],
    props: [
      { svg: A.drape, origin: [290, 430], keys: [{ t: 0, sy: 0.2 }, { t: 200, sy: 1, e: "back.out(1.6)" }, { t: 230, x: -3 }, { t: 260, x: 3 }, { t: 290, x: 0 }, ...hide(300)] },
      { svg: A.whisked, keys: [...show(300), { t: 300, x: -60, y: 60 }, { t: 450, x: 400, y: -500, r: 30, e: "uiOut" }] },
      { svg: A.confetti(22, 80, 400), keys: [...show(450), { t: 450, y: -100 }, { t: 1100, y: 120, o: 0 }] },
      { svg: A.confetti(10, 412, 428), keys: [...show(1000), { t: 2000, o: 0 }] },
    ],
  },
  {
    id: "hatch", name: "Hatching", kind: "entrance", sound: "crack", clearAt: 1000, dur: 1600, deck: [[0, false], [1400, true]],
    actor: [at(0, { o: 0 }), at(499, { o: 0 }), at(500, { o: 1, e: "none" }), at(900, { r: 6 }), at(1100, { r: -4 }), at(1300, { r: 3 }), at(1400, { r: 0 })],
    props: [
      { svg: A.egg, origin: [290, 430], keys: [{ t: 0, sy: 0.3 }, { t: 150, sy: 1, e: "back.out(1.6)" }, { t: 250, r: -6 }, { t: 350, r: 6 }, { t: 450, r: -6 }, { t: 500, r: 0 }, ...hide(500)] },
      { svg: A.eggBottom, origin: [290, 380], keys: [...show(500), { t: 700 }, { t: 1000, x: 150, y: 140, r: 30, o: 0, e: "power1.in" }] },
      { svg: A.eggTop, origin: [290, 250], keys: [...show(500), { t: 650, y: -150, r: -18, e: "uiOut" }, { t: 1000, x: -170, y: 150, r: -60, o: 0, e: "power1.in" }] },
      { svg: A.shellBits, keys: [...show(900), { t: 1600, o: 0 }] },
    ],
  },
  {
    id: "gift", name: "Gift unwrapping", kind: "entrance", sound: "party-horn", clearAt: 700, dur: 1400, deck: [[0, false], [1200, true]],
    actor: [{ t: 0, o: 0 }, { t: 299, o: 0, x: 290, y: 330 }, { t: 300, o: 1, sx: 0.9, sy: 1.15, e: "none" }, { t: 500, y: 150, e: "uiOut" }, { ...F(700, { sx: 1.1, sy: 0.9 }), e: "power1.in" }, { ...F(1000), e: "back.out(1.6)" }],
    props: [
      { svg: A.giftBox, origin: [290, 426], keys: [{ t: 0, sy: 0.2 }, { t: 200, sy: 1, e: "back.out(1.6)" }, { t: 230, sx: 1.06 }, { t: 260, sx: 1 }, { t: 280, sx: 1.06 }, { t: 300, sx: 1 }, ...hide(400)] },
      { svg: A.giftLid, origin: [290, 244], keys: [{ t: 0, sy: 0.2 }, { t: 200, sy: 1, e: "back.out(1.6)" }, { t: 300 }, { t: 700, x: 150, y: -500, r: 30, e: "power1.out" }, { t: 701, o: 0 }] },
      { svg: A.bulge, keys: window_(200, 300) },
      { svg: A.giftFlat, keys: [...show(400), { t: 1100 }, { t: 1400, o: 0 }] },
      { svg: A.confetti(14, 80, 260), keys: [...show(300), { t: 900, y: 200, o: 0 }] },
      { svg: A.ribbon, keys: [...show(1000), { t: 1400, o: 0 }] },
    ],
  },
  {
    id: "pole", name: "Sliding down a pole", kind: "entrance", sound: "zip", clearAt: 550, dur: 1100,
    actor: [{ t: 0, o: 0 }, { t: 149, o: 0, x: 318, y: -400, sx: 0.95, sy: 1.05 }, { t: 150, o: 1, e: "none" }, { t: 450, x: 318, y: 292, sx: 1.08, sy: 0.92, e: "power1.in" }, { ...F(550, { cx: 312 }), e: "uiOut" }, { ...F(650, { cx: 312 }), r: 6 }, { ...F(750, { cx: 312 }), r: -4 }, { ...F(900, { cx: 312 }), r: 0 }, { ...F(1100), e: "uiInOut" }],
    props: [
      { svg: A.pole, layer: "back", keys: [{ t: 0, y: -1400 }, { t: 150, y: 0, e: "power2.in" }, { t: 800 }, { t: 1000, y: -1600, e: "power1.in" }] },
      { svg: A.sparkles([[364, 330, 12], [352, 360, 8]]), keys: window_(450, 560) },
      { svg: `<path d="M226 426Q216 410 226 396M410 426Q420 410 410 396" stroke="${L}" stroke-width="5" stroke-linecap="round"/>`, keys: window_(550, 900) },
    ],
  },
  {
    id: "poledance", name: "Pole dance (burlesque)", kind: "entrance", sound: "sax", clearAt: 1700, dur: 2100,
    actor: [{ t: 0, o: 0 }, { t: 149, o: 0, x: 312, y: -300, r: 10 }, { t: 150, o: 1, e: "none" }, { t: 700, x: 312, y: 160, r: 10, e: "uiInOut" }, { t: 900, x: 268, y: 260, r: -25, sx: 0.95, sy: 1.06, e: "uiInOut" }, { t: 1100, x: 300, y: 300, r: 0, sx: 1, sy: 1 }, { t: 1150, x: 288, y: 310, r: 8, sx: 1.05, sy: 0.96, e: "back.out(1.6)" }, { ...F(1400), e: "uiInOut" }, F(1800)],
    props: [
      { svg: A.spotlight, layer: "back", keys: [{ t: 0, o: 0 }, { t: 150, o: 1 }, { t: 1800 }, { t: 2100, o: 0 }] },
      { svg: A.pole, layer: "back", keys: [{ t: 0, o: 0 }, { t: 150, o: 1 }, { t: 1800 }, { t: 2100, y: -1600, e: "power1.in" }] },
      { svg: A.capeBack, layer: "under", keys: [{ t: 0 }, ...hide(1100)] },
      { svg: A.capeFlung, keys: [...show(1100), { t: 1100, x: -160, y: 150, r: -40 }, { t: 1500, x: 200, y: -700, e: "uiOut" }] },
      { svg: A.boaNeck, layer: "attach", keys: [{ t: 0 }, ...hide(1400)] },
      { svg: A.boaPole, keys: [...show(1400), { t: 1400, y: -60 }, { t: 1600, y: 0, e: "back.out(1.5)" }] },
      { svg: look => A.winkLid(BODY_COLORS[look.color] ?? BODY_COLORS.Pink), layer: "attach", keys: window_(1450, 1800) },
      { svg: A.sparkles([[196, 220, 18], [420, 300, 12], [210, 330, 10, "#E8B6C7"]]), keys: [...show(1400), { t: 1900, o: 0 }] },
    ],
  },
  {
    id: "waterslide", name: "Water slide", kind: "entrance", sound: "whee-splash", clearAt: 1100, dur: 1700,
    actor: [{ t: 0, x: -200, y: -120, sx: 0.72, sy: 0.72, r: 20 }, { t: 200, x: -60, y: -90 }, { t: 500, x: 108, y: 150, sx: 0.78, sy: 0.86, r: -40, e: "power1.in" }, { t: 750, x: 120, y: 280, r: -10, sx: 0.8, sy: 0.8 }, { t: 900, x: 262, y: 300, sx: 0.81, sy: 0.99, r: 15, e: "power1.out" }, { ...F(1100, { sx: 1.2, sy: 0.82 }), e: "power1.in" }, { ...F(1400), e: "back.out(1.6)" }],
    props: [
      { svg: A.waterSlide, layer: "back", keys: [{ t: 0, o: 0 }, { t: 200, o: 1 }, { t: 1500 }, { t: 1700, o: 0 }] },
      { svg: A.drops([[160, 250], [176, 230]]), keys: window_(500, 800) },
      { svg: A.drops([[196, 384], [212, 356], [384, 384], [368, 356]]), keys: [...show(1100), { t: 1400, y: 20, o: 0 }] },
    ],
  },
  {
    id: "stealth", name: "Stealth entrance", kind: "entrance", sound: "tiptoe", clearAt: 1600, dur: 1700,
    actor: [{ t: 0, x: -200, y: 286, r: 8, sx: 0.95, sy: 1.06 }, { t: 200, x: -60, y: 270, e: "sine.inOut" }, { t: 350, x: 40, y: 286 }, { t: 500, x: 120, y: 270 }, { t: 650 }, { t: 800, x: 290, y: 300, r: -8, sx: 1, sy: 1, e: "sine.inOut" }, { t: 950 }, { t: 1100, r: 8 }, { t: 1200 }, { t: 1250, r: 0 }, { ...F(1350, { dy: -10, sx: 1.05, sy: 0.96 }), e: "back.out(1.6)" }, F(1600)],
    props: [
      { svg: A.tiptoe, keys: [...show(0), { t: 350, x: 40 }, ...hide(700)] },
      { svg: A.lookL, keys: window_(700, 950) },
      { svg: A.lookR, keys: window_(950, 1200) },
      { svg: A.sparkles([[190, 220, 18], [392, 200, 14], [400, 320, 10]]), keys: [...show(1300), { t: 1700, o: 0 }] },
    ],
  },
  {
    id: "drawn", name: "Drawn on", kind: "entrance", sound: "pencil", clearAt: 1000, dur: 1500,
    actor: [at(0, { o: 0 }), at(600, { o: 0 }), at(1000, { o: 1 }), at(1100, { sx: 1.05, sy: 1.05 }), { ...F(1200), e: "back.out(2)" }],
    props: [
      { svg: A.sketchHalf, keys: [{ t: 0, o: 0 }, { t: 100, o: 1 }, ...hide(400)] },
      { svg: A.sketchFull, keys: [...show(400), { t: 1000 }, { t: 1150, o: 0 }] },
      { svg: A.hatching, keys: window_(600, 1000) },
      { svg: A.pencil(290, 421, 30), origin: [290, 421], keys: [{ t: 0, y: -200 }, { t: 100, y: 0 }, { t: 150, y: -12 }, { t: 200, y: 0 }, { t: 400, x: 54, y: -210 }, { t: 600, x: 50, y: -90 }, { t: 1000, x: 30, y: -60 }, { t: 1200, x: 250, y: -400, r: 30, o: 0, e: "uiInOut" }] },
      { svg: A.sparkles([[196, 230, 14], [392, 300, 10]]), keys: [...show(1150), { t: 1500, o: 0 }] },
    ],
  },
];

export const BIG_ENTRANCES = ENTRANCES.filter(e => e.big).map(e => e.id);
export { INK };
