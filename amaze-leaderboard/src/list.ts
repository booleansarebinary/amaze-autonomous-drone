import { gsap } from "gsap";
import { EASE, calm } from "./ease";
import { fmtError, fmtTimestamp, type Entry } from "./model";
import { layersHtml } from "./actor";
import { G, L } from "./art/svg";

const STEP = 108, PAGE = 6, VISIBLE = 7, HOLD = 5;
const planet = `<svg viewBox="0 0 64 64"><ellipse cx="32" cy="34" rx="29" ry="8" stroke="${G}" stroke-width="5" fill="none"/><circle cx="32" cy="32" r="17" fill="${L}"/><circle cx="26" cy="25" r="5" fill="#F1F0F5" fill-opacity="0.7"/><path d="M3 34A29 8 0 0 0 61 34" stroke="${G}" stroke-width="5" stroke-linecap="round" fill="none"/></svg>`;
const chevron = (up: boolean) => `<svg viewBox="0 0 24 24"><path d="${up ? "M5 15L12 8L19 15" : "M5 9L12 16L19 9"}" stroke="${up ? "#9BD6C0" : "#E96A5B"}" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>`;

/** Ranks 4–20: auto-scrolling, looping list (one page of 6 rows every 5 s, 700 ms ease-in-out). */
export class RankList {
  private strip: HTMLElement;
  private rows = new Map<string, HTMLElement>();
  private order: Entry[] = [];
  private offset = 0;
  private timer = 0;
  private scrollTween: gsap.core.Tween | null = null;
  private copies: HTMLElement[] = [];
  private marker: HTMLElement;

  constructor(stageRoot: HTMLElement) {
    const panel = document.createElement("div");
    panel.className = "panel";
    panel.innerHTML = `<div class="cols"><span class="c-rank">Rank</span><span class="c-name">Player</span><span class="c-time">Submitted<br>(CST)</span><span class="c-err">Error</span></div><div class="viewport"><div class="strip"></div></div><div class="fade-top"></div><div class="fade-bottom"></div>`;
    stageRoot.appendChild(panel);
    this.strip = panel.querySelector(".strip")!;
    this.marker = document.createElement("div");
    this.marker.className = "marker";
    this.marker.innerHTML = `${planet}<span>Back to the list</span>`;
  }

  private rowHtml(e: Entry) {
    return `<div class="r-rank"><span>${e.rank}</span></div><div class="avatar"><div class="mini">${layersHtml(e.look)}</div></div><div class="r-name">${escapeHtml(e.name)}</div><div class="r-time">${fmtTimestamp(e.submittedAt)}</div><div class="r-err">${fmtError(e.error)}</div><div class="ring"></div>`;
  }
  private makeRow(e: Entry) { const r = document.createElement("div"); r.className = "row"; r.innerHTML = this.rowHtml(e); return r; }

  /** Set the list (ranks 4+). New rows slide in with a gold ring; moved rows shift with a 40 ms stagger; rank changes get a chevron for 3 s. */
  update(entries: Entry[], animate = true) {
    if (JSON.stringify(entries) === JSON.stringify(this.order)) return;
    const prev = new Map(this.order.map((e, i) => [e.id, i]));
    const prevTop = new Map([...this.rows].map(([id, el]) => [id, gsap.getProperty(el, "y") as number]));
    this.order = entries;
    const keep = new Set(entries.map(e => e.id));
    for (const [id, el] of this.rows) if (!keep.has(id)) {
      this.rows.delete(id);
      if (animate && !calm.on) gsap.to(el, { opacity: 0, duration: 0.3, ease: EASE.out, onComplete: () => el.remove() }); else el.remove();
    }
    entries.forEach((e, i) => {
      const y = i * STEP;
      let el = this.rows.get(e.id);
      const isNew = !el;
      if (!el) { el = this.makeRow(e); this.strip.appendChild(el); this.rows.set(e.id, el); }
      else { el.innerHTML = this.rowHtml(e); }
      const was = prev.get(e.id);
      if (!animate || calm.on) { gsap.set(el, { y, x: 0, opacity: 1 }); return; }
      if (isNew) {
        gsap.fromTo(el, { y, x: -80, opacity: 0 }, { x: 0, opacity: 1, duration: 0.5, ease: EASE.out });
        gsap.fromTo(el.querySelector(".ring"), { opacity: 1 }, { opacity: 0, duration: 1.2, delay: 0.5, ease: "power1.in" });
      } else {
        gsap.fromTo(el, { y: prevTop.get(e.id) ?? y }, { y, duration: 0.45, ease: EASE.out, delay: Math.max(0, i) * 0.04 });
        if (was !== undefined && was !== i) {
          const r = el.querySelector(".r-rank")!;
          r.insertAdjacentHTML("beforeend", chevron(i < was));
          gsap.to(r.querySelector("svg"), { opacity: 0, duration: 0.3, delay: 3, onComplete() { (this.targets()[0] as Element)?.remove(); } });
        }
      }
    });
    this.layoutLoop();
    if (animate) { this.resetScroll(); this.schedule(3 + HOLD); } else this.schedule(HOLD);
  }

  /** Remove a row ahead of time, e.g. when its player is about to enter the podium. */
  liftOut(id: string) {
    const el = this.rows.get(id);
    if (!el || calm.on) return;
    gsap.to(el, { scale: 1.04, duration: 0.2, ease: EASE.out });
    gsap.to(el.querySelector(".ring"), { opacity: 1, duration: 0.2 });
    gsap.to(el, { opacity: 0, duration: 0.3, delay: 0.3 });
  }

  private layoutLoop() {
    this.copies.forEach(c => c.remove());
    this.copies = [];
    this.marker.remove();
    const n = this.order.length;
    if (n <= VISIBLE) return;
    gsap.set(this.marker, { y: n * STEP });
    this.strip.appendChild(this.marker);
    this.order.slice(0, VISIBLE).forEach((e, i) => {
      const c = this.makeRow(e);
      gsap.set(c, { y: (n + 1 + i) * STEP });
      this.strip.appendChild(c);
      this.copies.push(c);
    });
  }

  private get loopLen() { return (this.order.length + 1) * STEP; }

  private resetScroll() {
    this.scrollTween?.kill();
    this.offset = 0;
    if (calm.on) gsap.set(this.strip, { y: 0 });
    else gsap.to(this.strip, { y: 0, duration: 0.7, ease: EASE.inOut });
  }

  private schedule(seconds: number) {
    clearTimeout(this.timer);
    this.timer = window.setTimeout(() => this.step(), seconds * 1000);
  }

  private step() {
    if (this.order.length > VISIBLE) {
      this.offset = Math.min(this.offset + PAGE * STEP, this.loopLen);
      const target = this.offset;
      const done = () => { if (this.offset >= this.loopLen) { this.offset -= this.loopLen; gsap.set(this.strip, { y: -this.offset }); } };
      if (calm.on) {
        gsap.to(this.strip, { opacity: 0, duration: 0.1, onComplete: () => { gsap.set(this.strip, { y: -target }); done(); gsap.to(this.strip, { opacity: 1, duration: 0.1 }); } });
      } else {
        this.scrollTween = gsap.to(this.strip, { y: -target, duration: 0.7, ease: EASE.inOut, onComplete: done });
      }
    }
    this.schedule(HOLD);
  }
}

export const escapeHtml = (s: string) => s.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
