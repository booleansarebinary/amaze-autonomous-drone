import { gsap } from "gsap";
import { calm, EASE } from "../ease";
import { tile } from "../art/svg";
import { layersHtml, W0, H0, type Actor } from "../actor";
import { hatSvg } from "../art/characters";
import type { Place } from "../place";
import type { K, PropDef, Seq } from "./types";

const GUARD = { color: "Periwinkle", outfit: "Overalls", hat: "Cap" };
const DEF = { x: 0, y: 0, r: 0, sx: 1, sy: 1, o: 1 };
const sec = (ms: number) => ms / 1000;
const sound = (cue: string, id: string) => window.dispatchEvent(new CustomEvent("leaderboard:sound", { detail: { cue, id } }));

/** Fill each key with the previous key's values so every tween has all six channels. */
function normalize(keys: K[], base: Required<Omit<K, "t" | "e">>) {
  const sorted = [...keys].sort((a, b) => a.t - b.t);
  let prev = { ...base };
  return sorted.map(k => { prev = { x: k.x ?? prev.x, y: k.y ?? prev.y, r: k.r ?? prev.r, sx: k.sx ?? prev.sx, sy: k.sy ?? prev.sy, o: k.o ?? prev.o }; return { t: k.t, e: k.e, ...prev }; });
}

function track(tl: gsap.core.Timeline, target: Element, keys: K[], base: typeof DEF, ox = 0, oy = 0) {
  const ks = normalize(keys, base);
  const vars = (k: (typeof ks)[number]) => ({ x: k.x - ox, y: k.y - oy, rotation: k.r, scaleX: k.sx, scaleY: k.sy, opacity: k.o });
  tl.set(target, vars(ks[0]), 0);
  for (let i = 1; i < ks.length; i++) tl.to(target, { ...vars(ks[i]), duration: sec(ks[i].t - ks[i - 1].t), ease: ks[i].e ?? "power1.inOut" }, sec(ks[i - 1].t));
}

export interface Cast { place: Place; actor: Actor; other?: Actor; world: HTMLElement; }
export interface Run { clear: Promise<void>; done: Promise<void>; }

/** Play a sequence on a step. Exits end with the actor off stage; entrances end with the actor home on the deck. */
export function runSeq(seq: Seq, cast: Cast): Run {
  const { place, actor, other, world } = cast;
  let clearResolve!: () => void, doneResolve!: () => void;
  const clear = new Promise<void>(r => (clearResolve = r)), done = new Promise<void>(r => (doneResolve = r));
  const entering = seq.kind !== "exit";

  if (calm.on) return calmRun(seq, cast, clearResolve, doneResolve, clear, done);

  const o = place.tileOrigin, created: HTMLElement[] = [];
  const tl = gsap.timeline({ paused: true });
  sound(seq.sound, seq.id);

  track(tl, actor.motion, seq.actor, { ...DEF, x: 290, y: 303 }, 290, 303);
  if (other && seq.other) track(tl, other.motion, seq.other, { ...DEF, x: 290, y: 303 }, 290, 303);
  for (const [t, b] of seq.behind ?? []) tl.call(() => actor.setZ(b ? "behind" : "normal"), [], sec(t));
  for (const [t, v] of seq.deck ?? []) tl.call(() => place.setDeck(v), [], sec(t));
  if (seq.rocket) track(tl, place.el, seq.rocket, { ...DEF });

  for (const p of seq.props ?? []) {
    const who = p.who === "other" && other ? other : actor;
    const el = makeProp(p, who, o, world);
    created.push(el);
    if (p.kind === "hat") {
      const first = [...p.keys].sort((a, b) => a.t - b.t).find(k => (k.o ?? 1) > 0);
      if (first) tl.set(who.hatEl, { opacity: 0 }, sec(first.t));
      track(tl, el, p.keys, { ...DEF, x: 290, y: 303 }, 290, 303);
    } else if (p.kind === "ghost" || p.kind === "guard") {
      track(tl, el, p.keys, { ...DEF, x: 290, y: 303 }, 290, 303);
    } else {
      if (p.origin) gsap.set(el, { transformOrigin: `${p.origin[0]}px ${p.origin[1]}px` });
      track(tl, el, p.keys, { ...DEF });
    }
  }

  tl.call(() => clearResolve(), [], sec(seq.clearAt));
  tl.call(() => {
    created.forEach(el => el.remove());
    gsap.set(place.el, { x: 0, y: 0, opacity: 1 });
    place.setDeck(true);
    actor.setZ("normal");
    if (other) other.setZ("normal");
    gsap.set(actor.hatEl, { opacity: 1 });
    doneResolve();
  }, [], sec(Math.max(seq.dur, seq.clearAt) + 30));
  if (entering && seq.kind === "entrance") gsap.set(actor.motion, { opacity: 0 });
  tl.play();
  return { clear, done };
}

function makeProp(p: PropDef, who: Actor, o: { x: number; y: number }, world: HTMLElement) {
  const el = document.createElement("div");
  const svg = typeof p.svg === "function" ? p.svg(who.look) : p.svg ?? "";
  if (p.kind === "hat" || p.kind === "ghost" || p.kind === "guard") {
    el.className = "fig";
    el.innerHTML = p.kind === "hat" ? hatSvg(who.look.hat) : layersHtml(p.kind === "guard" ? GUARD : who.look);
    Object.assign(el.style, { left: `${o.x + 290 - W0 / 2}px`, top: `${o.y + 303 - H0 / 2}px`, zIndex: p.kind === "guard" ? "21" : "22" });
    world.appendChild(el);
    return el;
  }
  if (p.layer === "attach" || p.layer === "under") {
    el.className = "attach";
    el.innerHTML = `<svg viewBox="0 0 ${W0} ${H0}" width="${W0}" height="${H0}" overflow="visible">${svg}</svg>`;
    if (p.layer === "under") who.size.insertBefore(el, who.idle); else who.size.appendChild(el);
    return el;
  }
  el.className = "prop";
  el.innerHTML = tile(svg);
  Object.assign(el.style, { left: `${o.x}px`, top: `${o.y}px`, zIndex: p.layer === "back" ? "5" : p.layer === "mid" ? "12" : "30" });
  world.appendChild(el);
  return el;
}

/** Calm mode: no travel, squash or spin. Exits fade out, entrances fade in (300 ms). */
function calmRun(seq: Seq, cast: Cast, clearResolve: () => void, doneResolve: () => void, clear: Promise<void>, done: Promise<void>): Run {
  const { actor, other } = cast;
  if (seq.kind === "exit") {
    gsap.to(actor.motion, { opacity: 0, duration: 0.3, ease: EASE.out, onComplete: () => { clearResolve(); doneResolve(); } });
  } else if (seq.kind === "entrance") {
    gsap.fromTo(actor.motion, { opacity: 0 }, { opacity: 1, duration: 0.3, ease: EASE.out, onComplete: () => { clearResolve(); doneResolve(); } });
  } else {
    gsap.to(actor.motion, { opacity: 0, duration: 0.3, ease: EASE.out });
    if (other) gsap.fromTo(other.motion, { opacity: 0, x: 0, y: 0 }, { opacity: 1, duration: 0.3, delay: 0.3, ease: EASE.out, onComplete: () => { clearResolve(); doneResolve(); } });
  }
  return { clear, done };
}
