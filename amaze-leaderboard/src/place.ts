import { gsap } from "gsap";
import { EASE, calm } from "./ease";
import { darken, INK, P, C, G, WH, PERI } from "./art/svg";
import { fmtError, fmtTimestamp, type Entry } from "./model";
import type { Actor } from "./actor";

// Podium/Rocket geometry from the Figma component (body bottoms share y 920).
export const SPECS = [
  { x: 384, y: 436, w: 280, h: 470, color: G, d: 132, rank: 84, name: 52, err: 52, time: 36, band: 80, bandY: 308, dataY: 402, fh: 120, bean: 260, amp: 8, phase: 0 },
  { x: 88, y: 516, w: 248, h: 390, color: PERI, d: 112, rank: 68, name: 44, err: 44, time: 32, band: 68, bandY: 234, dataY: 316, fh: 96, bean: 230, amp: -6, phase: 0.8 },
  { x: 712, y: 576, w: 248, h: 330, color: C, d: 104, rank: 68, name: 44, err: 44, time: 32, band: 68, bandY: 174, dataY: 256, fh: 88, bean: 230, amp: 6, phase: 1.6 },
];

const flameSvg = (h: number) => `<svg width="100" height="${h}" viewBox="0 0 100 ${h}"><path d="M50 ${h}C22 ${h * 0.62} 2 ${h * 0.34} 6 0H94C98 ${h * 0.34} 78 ${h * 0.62} 50 ${h}Z" fill="${C}"/><path d="M50 ${h * 0.78}C32 ${h * 0.5} 18 ${h * 0.28} 22 0H78C82 ${h * 0.28} 68 ${h * 0.5} 50 ${h * 0.78}Z" fill="${G}"/><path d="M50 ${h * 0.48}C42 ${h * 0.32} 36 ${h * 0.16} 38 0H62C64 ${h * 0.16} 58 ${h * 0.32} 50 ${h * 0.48}Z" fill="${WH}"/></svg>`;
const nozzleSvg = `<svg width="140" height="36" viewBox="0 0 140 36"><path d="M22 0H118L140 30C140 33 138 36 134 36H6C2 36 0 33 0 30Z" fill="${INK}"/></svg>`;
const finSvg = (right: boolean) => `<svg width="40" height="150" viewBox="0 0 40 150"><path d="${right ? "M0 0C22 34 40 74 40 118C40 142 26 152 0 138Z" : "M40 0C18 34 0 74 0 118C0 142 14 152 40 138Z"}" fill="${P}"/></svg>`;

export type BandState = { kind: "entry"; entry: Entry } | { kind: "incoming" } | { kind: "empty" };

export class Place {
  readonly el: HTMLElement;
  readonly spec: (typeof SPECS)[number];
  readonly W: number;
  occupant: Actor | null = null;
  private deckEl: HTMLElement;
  private slots: HTMLElement[];
  private bobTween: gsap.core.Tween | null = null;
  private bandKey = "";

  constructor(readonly index: number, world: HTMLElement) {
    const s = (this.spec = SPECS[index]);
    const W = (this.W = s.w + 48), bodyBottom = 14 + s.h, cx = 24 + s.w / 2, dw = Math.round(s.w * 0.5), ringY = s.bandY - 22 - s.d;
    const el = (this.el = document.createElement("div"));
    el.className = "rocket";
    Object.assign(el.style, { left: `${s.x}px`, top: `${s.y}px`, width: `${W}px`, height: `${bodyBottom + 32 + s.fh}px` });
    el.innerHTML = `
      <div class="flame abs" style="left:${cx - 50}px;top:${bodyBottom + 30}px;animation-delay:-${index * 80}ms">${flameSvg(s.fh)}</div>
      <div class="abs" style="left:${cx - 70}px;top:${bodyBottom - 4}px">${nozzleSvg}</div>
      <div class="abs" style="left:0;top:${bodyBottom - 128}px">${finSvg(false)}</div>
      <div class="abs" style="left:${W - 40}px;top:${bodyBottom - 128}px">${finSvg(true)}</div>
      <div class="body" style="width:${s.w}px;height:${s.h}px;background:${s.color};border-radius:${s.w / 2}px ${s.w / 2}px 28px 28px">
        <div class="shade"></div><div class="hl" style="top:${s.w * 0.45}px;height:${s.h - s.w * 0.45 - 70}px"></div>
      </div>
      <div class="deck" style="left:${24 + (s.w - dw) / 2}px;width:${dw}px;background:${darken(s.color, 0.82)}"></div>
      <div class="ring" style="left:${cx - s.d / 2}px;top:${ringY}px;width:${s.d}px;height:${s.d}px"><div class="glass"></div><div class="rank" style="font-size:${s.rank}px;line-height:${s.rank}px">${index + 1}</div></div>
      <div class="band" style="top:${s.bandY}px;width:${s.w + 32}px;height:${s.band}px"><div class="slot" style="font-size:${s.name}px;line-height:${s.name + 4}px;width:${s.w - 8}px;text-align:center"><span></span></div></div>
      <div class="data" style="left:0;width:${W}px;top:${s.dataY}px"><div class="slot err" style="font-size:${s.err}px;line-height:${s.err + 4}px"><span></span></div><div class="slot" style="font-size:${s.time}px;line-height:${s.time + 8}px"><span></span></div></div>`;
    world.appendChild(el);
    this.deckEl = el.querySelector(".deck")!;
    this.slots = [...el.querySelectorAll<HTMLElement>(".slot")];
    this.setBand({ kind: "empty" }, false);
  }

  get deckCx() { return this.spec.x + this.W / 2; }
  get deckTop() { return this.spec.y + 4; }
  /** Stage position of the storyboard tile's (0, 0) for this step. */
  get tileOrigin() { return { x: this.deckCx - 290, y: this.deckTop - 420 }; }
  get home() { return { x: this.deckCx, y: this.deckTop - 117 }; }
  get charScale() { return this.spec.bean / 230; }

  setDeck(visible: boolean) { this.deckEl.style.visibility = visible ? "visible" : "hidden"; }

  /** Name band roll: old text slides down and out, new text drops in (240 ms, 40 ms stagger name → error → time). */
  setBand(state: BandState, animate = true) {
    this.el.querySelector(".rank")!.textContent = state.kind === "entry" ? String(state.entry.rank) : String(this.index + 1);
    const texts = state.kind === "entry" ? [state.entry.name, fmtError(state.entry.error), `${fmtTimestamp(state.entry.submittedAt)} CST`] : state.kind === "incoming" ? ["Incoming", "-.-%", "--:-- CST"] : ["", "", ""];
    const key = texts.join("|");
    if (key === this.bandKey) return;
    this.bandKey = key;
    this.slots.forEach((slot, i) => {
      const old = slot.querySelector<HTMLElement>("span:not(.out)");
      const next = document.createElement("span");
      next.textContent = texts[i] || " ";
      if (!animate || calm.on || !old) { slot.replaceChildren(next); return; }
      old.classList.add("out");
      slot.appendChild(next);
      const delay = i * 0.04;
      gsap.fromTo(old, { yPercent: 0 }, { yPercent: 110, duration: 0.24, ease: EASE.out, delay, onComplete: () => old.remove() });
      gsap.fromTo(next, { yPercent: -110 }, { yPercent: 0, duration: 0.24, ease: EASE.out, delay });
    });
  }

  /** Ambient bob: ±6–8 px on a 2.4 s loop, phases offset per rocket; the occupant rides along. */
  startBob() {
    this.stopBob(true);
    if (calm.on) return;
    const targets = [this.el, this.occupant?.ride].filter(Boolean) as HTMLElement[];
    gsap.set(targets, { y: 0 });
    this.bobTween = gsap.to(targets, { y: this.spec.amp, duration: 1.2, ease: EASE.sine, yoyo: true, repeat: -1, delay: this.spec.phase });
  }
  stopBob(instant = false) {
    this.bobTween?.kill();
    this.bobTween = null;
    const targets = [this.el, this.occupant?.ride].filter(Boolean) as HTMLElement[];
    if (instant) gsap.set(targets, { y: 0 });
    else gsap.to(targets, { y: 0, duration: 0.3, ease: EASE.out });
  }
}
