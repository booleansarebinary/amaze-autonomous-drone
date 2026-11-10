import { gsap } from "gsap";
import { EASE, calm } from "./ease";
import { bodySvg, hatSvg, outfitSvg, type Look } from "./art/characters";
import type { Place } from "./place";

export const W0 = 153.33, H0 = 260.67;

export const layersHtml = (look: Look) =>
  `<div class="layer body">${bodySvg(look.color)}</div><div class="layer outfit">${outfitSvg(look.outfit)}</div><div class="layer hat">${hatSvg(look.hat)}</div>`;

const BELTS = ["#1E1442", "#8C5A3C", "#5D3BC3", "#4A6FA5", "#6FB59B"];
const EMBLEMS = ["#D2483E", "#F4C95D", "#E8B6C7"];

/**
 * A character on stage. Transform stack, outside in:
 * ride (rocket bob) → motion (choreography, about the box centre) → squash (feet) → size (step scale, feet) → idle (sway/breathing, feet) → layers.
 */
export class Actor {
  readonly root: HTMLElement;
  readonly ride: HTMLElement;
  readonly motion: HTMLElement;
  readonly squash: HTMLElement;
  readonly size: HTMLElement;
  readonly idle: HTMLElement;
  readonly layers: HTMLElement;
  place: Place | null = null;
  private idleTweens: gsap.core.Animation[] = [];
  private behaviorTweens: gsap.core.Animation[] = [];
  private swayDir = 1;

  constructor(public id: string, public look: Look, world: HTMLElement) {
    const root = (this.root = document.createElement("div"));
    root.className = "actor";
    root.innerHTML = `<div class="ride"><div class="motion"><div class="squash"><div class="size"><div class="idle"><div class="layers">${layersHtml(look)}</div></div></div></div></div></div>`;
    world.appendChild(root);
    this.ride = root.querySelector(".ride")!;
    this.motion = root.querySelector(".motion")!;
    this.squash = root.querySelector(".squash")!;
    this.size = root.querySelector(".size")!;
    this.idle = root.querySelector(".idle")!;
    this.layers = root.querySelector(".layers")!;
    gsap.set(this.motion, { transformOrigin: "50% 50%" });
  }

  get hatEl() { return this.layers.querySelector<HTMLElement>(".layer.hat")!; }
  get outfitEl() { return this.layers.querySelector<HTMLElement>(".layer.outfit")!; }

  /** Stand on a step: the box centre sits at the step's home point and the size matches the step. */
  setHome(place: Place) {
    this.place = place;
    const h = place.home;
    Object.assign(this.root.style, { left: `${h.x - W0 / 2}px`, top: `${h.y - H0 / 2}px` });
    gsap.set(this.motion, { x: 0, y: 0, rotation: 0, scaleX: 1, scaleY: 1, opacity: 1 });
    gsap.set(this.squash, { scaleX: 1, scaleY: 1 });
    gsap.set(this.size, { scale: place.charScale });
    this.swayDir = place.index === 1 ? -1 : 1;
  }

  setZ(z: "normal" | "behind" | "low") { this.root.style.zIndex = z === "behind" ? "8" : z === "low" ? "19" : "20"; }

  /** Standing still: ±3° sway from the feet on a 4.8 s loop (neighbours in opposite phase), with 1.0 ↔ 1.02 breathing on top. */
  startIdle(delay = 0) {
    this.stopIdle(true);
    if (calm.on) return;
    const d = this.swayDir * 3;
    gsap.set(this.idle, { rotation: -d });
    this.idleTweens = [
      gsap.to(this.idle, { rotation: d, duration: 2.4, ease: EASE.sine, yoyo: true, repeat: -1, delay }),
      gsap.to(this.idle, { scaleY: 1.02, duration: 1.5, ease: EASE.sine, yoyo: true, repeat: -1, delay }),
    ];
    this.startBehaviors();
  }
  stopIdle(instant = false) {
    this.idleTweens.forEach(t => t.kill());
    this.idleTweens = [];
    this.behaviorTweens.forEach(t => t.kill());
    this.behaviorTweens = [];
    if (instant) gsap.set(this.idle, { rotation: 0, scaleY: 1 });
    else gsap.to(this.idle, { rotation: 0, scaleY: 1, duration: 0.2 });
  }

  /** Item idle behaviours (Figma sheet 05, "Hat behaviors" and "Outfit behaviors"). */
  private startBehaviors() {
    const hat = this.hatEl, outfit = this.outfitEl, q = (sel: string) => [...this.layers.querySelectorAll(sel)];
    const add = (a: gsap.core.Animation) => this.behaviorTweens.push(a);
    const loop = (targets: Element | Element[], vars: gsap.TweenVars) => add(gsap.to(targets, { yoyo: true, repeat: -1, ease: EASE.sine, ...vars }));
    gsap.set(hat, { transformOrigin: "50% 30%" });
    switch (this.look.hat) {
      case "Wizard hat": case "Witch hat": case "Jester hat": loop(hat, { rotation: 4 * this.swayDir, duration: 2.4, delay: 0.1 }); break;
      case "Lampshade": loop(hat, { rotation: 6, duration: 1.6 }); break;
      case "Rubber duck": loop(hat, { y: -4, duration: 0.9 }); break;
      case "Shark fin": loop(hat, { x: 20, duration: 3 }); break;
      case "Headphones": loop(hat, { scale: 1.06, duration: 0.3, ease: "power1.out" }); break;
      case "Halo": loop(hat, { y: -4, duration: 2.4 }); loop(q(".hat .glow"), { opacity: 0.45, duration: 2.4 }); break;
      case "Pumpkin": add(gsap.to(q(".hat .glow"), { opacity: 0.7, duration: 0.12, repeat: -1, yoyo: true, repeatDelay: 0.3, ease: "steps(2)" })); break;
      case "Frog": add(gsap.to(q(".hat .eyes"), { scaleY: 0.1, svgOrigin: "100 0", duration: 0.06, yoyo: true, repeat: -1, repeatDelay: 4 + Math.random() * 3 })); break;
      case "Fishbowl": loop(q(".hat .fish"), { x: -40, duration: 2.5 }); break;
      case "Graduation cap": loop(q(".hat .tassel"), { rotation: 8, svgOrigin: "164 18", duration: 1.2 }); break;
      case "Robot head": add(gsap.to(q(".hat .blink"), { opacity: 0.2, duration: 0.3, stagger: { each: 0.3, repeat: -1, yoyo: true } })); break;
      case "Bird's nest": add(gsap.fromTo(q(".hat .peek"), { y: 10 }, { y: 0, duration: 0.3, yoyo: true, repeat: -1, repeatDelay: 8 + Math.random() * 4, ease: EASE.out })); break;
    }
    switch (this.look.outfit) {
      case "Dinosaur onesie": case "Cow pajamas": case "Unicorn pajamas": loop(q(".outfit .tail"), { rotation: 10, svgOrigin: "170 236", duration: 0.6 }); break;
      case "Inflatable T-Rex": add(gsap.to(outfit, { scale: 1.01, duration: 0.033, yoyo: true, repeat: -1, transformOrigin: "50% 80%" })); break;
      case "Smoking jacket": add(gsap.fromTo(q(".outfit .bubbles"), { y: 0, opacity: 1 }, { y: -30, opacity: 0, duration: 3, repeat: -1, ease: "none" })); break;
      case "Bathrobe": add(gsap.fromTo(q(".outfit .steam"), { y: 0, opacity: 1 }, { y: -16, opacity: 0, duration: 2, repeat: -1, ease: "none" })); break;
      case "Wetsuit": loop(q(".outfit .shine"), { opacity: 0.1, duration: 2 }); break;
      case "Wizard robe": case "Mermaid tail": loop(q(".outfit .twinkle"), { opacity: 0.4, duration: 0.8 }); break;
      case "Space suit · neon": loop(q(".outfit .neon"), { opacity: 0.55, duration: 0.3 }); break;
      case "Cyberpunk jacket": loop(q(".outfit .neon"), { opacity: 0.55, duration: 0.3 }); add(gsap.to(q(".outfit .neon"), { opacity: 0, duration: 0.033, repeat: -1, yoyo: true, repeatDelay: 5 })); break;
      case "Mech suit": loop(this.layers, { y: -4, duration: 1.2 }); add(gsap.to(q(".outfit .blink"), { opacity: 0.3, duration: 0.5, repeat: -1, yoyo: true })); break;
      case "Ghost sheet": loop(this.layers, { y: -6, duration: 1 }); break;
      case "Ninja outfit": add(gsap.to(this.layers, { opacity: 0.85, duration: 0.6, delay: 1 })); break;
      case "Ugly Christmas sweater": add(gsap.to(q(".outfit .blink circle"), { opacity: 0.25, duration: 0.25, stagger: { each: 0.25, repeat: -1, yoyo: true } })); break;
      case "Valentine's outfit": add(gsap.fromTo(q(".outfit .hearts"), { y: 0, opacity: 1 }, { y: -60, opacity: 0, duration: 2, repeat: -1, repeatDelay: 6 + Math.random() * 4, ease: "power1.out" })); break;
      case "Mummy wrap": loop(q(".outfit .strip"), { rotation: 8, svgOrigin: "8 196", duration: 0.8 }); break;
      case "Winter coat + scarf": loop(q(".outfit .scarf-tail"), { rotation: 4, svgOrigin: "140 152", duration: 1.4 }); break;
    }
  }

  /** Landing reactions: cowboy hat tips, sumo padding wobbles, knight armor clanks, strap and parrot swing. */
  onLand() {
    if (calm.on) return;
    const q = (sel: string) => [...this.layers.querySelectorAll(sel)];
    if (this.look.hat === "Cowboy hat") gsap.fromTo(this.hatEl, { rotation: 0 }, { rotation: 12, duration: 0.15, yoyo: true, repeat: 1, ease: EASE.spring, transformOrigin: "50% 40%" });
    if (this.look.hat === "Pirate hat · parrot") gsap.fromTo(q(".hat .parrot"), { rotation: 0 }, { rotation: -20, svgOrigin: "160 40", duration: 0.12, yoyo: true, repeat: 3 });
    if (this.look.hat === "Racing helmet") gsap.to(q(".hat .visor"), { y: -46, opacity: 0.25, duration: 0.18, ease: EASE.out });
    if (this.look.outfit === "Sumo suit") gsap.fromTo(this.outfitEl, { scaleX: 1.04 }, { scaleX: 1, duration: 0.9, ease: EASE.bouncy, transformOrigin: "50% 80%" });
    if (this.look.outfit === "Knight armor") gsap.fromTo(this.layers, { x: -2 }, { x: 0, duration: 0.066, repeat: 1, yoyo: true });
    if (this.look.outfit === "Overalls · one strap") gsap.fromTo(q(".outfit .strap"), { rotation: 0 }, { rotation: 12, svgOrigin: "128 166", duration: 0.2, yoyo: true, repeat: 3 });
    if (this.look.outfit === "Ninja outfit") gsap.to(this.layers, { opacity: 1, duration: 0.15 });
  }

  /** Rank-driven details: varsity letter, karate belt, superhero emblem, bow tie spin on taking 1st. */
  setRank(rank: number) {
    const patch = this.layers.querySelector(".outfit .patch");
    if (patch) patch.textContent = String.fromCharCode(64 + Math.min(rank, 26));
    this.layers.querySelectorAll(".outfit .belt rect, .outfit .belt path").forEach(el => {
      const c = BELTS[Math.min(rank - 1, BELTS.length - 1)] ?? "#FFFFFF";
      el.setAttribute(el.tagName === "path" ? "stroke" : "fill", rank > 5 ? "#FFFFFF" : c);
    });
    this.layers.querySelectorAll(".outfit .emblem path").forEach(el => el.setAttribute("fill", EMBLEMS[rank - 1] ?? "#5D3BC3"));
    if (rank === 1 && !calm.on) gsap.fromTo(this.layers.querySelectorAll(".outfit .bowtie"), { rotation: 0 }, { rotation: 360, svgOrigin: "100 144", duration: 0.4, ease: EASE.out });
  }

  /** Any rank change on screen: cat and bunny ears twitch, the referee blows the whistle on a knock-off. */
  onRankEvent(knockOff: boolean) {
    if (calm.on) return;
    if (this.look.hat === "Cat ears" || this.look.hat === "Bunny ears") gsap.fromTo(this.hatEl, { rotation: 0 }, { rotation: 6, duration: 0.08, yoyo: true, repeat: 3, transformOrigin: "50% 60%" });
    if (knockOff && this.look.outfit === "Referee shirt") gsap.fromTo(this.layers.querySelectorAll(".outfit .whistle"), { scale: 1 }, { scale: 1.4, svgOrigin: "102 190", duration: 0.12, yoyo: true, repeat: 1 });
  }

  onRankUp() {
    if (calm.on || this.look.outfit !== "Sports fan gear") return;
    gsap.fromTo(this.layers.querySelectorAll(".outfit .finger"), { rotation: 0 }, { rotation: -14, svgOrigin: "183 214", duration: 0.15, yoyo: true, repeat: 3 });
  }

  remove() { this.stopIdle(true); gsap.killTweensOf([this.motion, this.squash, this.size, this.ride]); this.root.remove(); }
}
