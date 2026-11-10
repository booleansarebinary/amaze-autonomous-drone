// Choreography DSL. Coordinates are storyboard-tile units (Figma frames 07/08): the deck being acted on has
// its centre-top at (290, 420) and a standing character's box centre sits at (290, 303).

/** A keyframe. Actor and figure keys give the box centre (x, y); prop keys give an offset from where the prop is drawn. */
export interface K { t: number; x?: number; y?: number; r?: number; sx?: number; sy?: number; o?: number; e?: string; }

/** back < rockets < mid < actors < front. attach/under ride inside the actor (character-box coordinates, 153×261). */
export type Layer = "back" | "mid" | "front" | "attach" | "under";

import type { Look } from "../art/characters";

export interface PropDef {
  svg?: string | ((look: Look) => string);
  /** svg: plain artwork. hat: the actor's own hat. guard: a tiny security guard character. */
  kind?: "svg" | "hat" | "ghost" | "guard";
  layer?: Layer;
  /** Transform origin in the prop's own coordinates. */
  origin?: [number, number];
  /** "other" attaches to the second actor in a combo. */
  who?: "actor" | "other";
  keys: K[];
}

export interface Seq {
  id: string;
  name: string;
  kind: "exit" | "entrance" | "combo";
  sound: string;
  /** exit/combo: when the deck is clear. entrance: when they land (the band rolls). */
  clearAt: number;
  dur: number;
  actor: K[];
  other?: K[];
  props?: PropDef[];
  behind?: [number, boolean][];
  otherBehind?: [number, boolean][];
  deck?: [number, boolean][];
  rocket?: K[];
  /** Entrances reserved for a new leader. */
  big?: boolean;
}

export const W0 = 153.33, H0 = 260.67;
export const HOME = { x: 290, y: 303 };

/** Keyframe anchored at the feet: squash and stretch keep the feet on the deck (or on y = fy). */
export function F(t: number, o: { sx?: number; sy?: number; dy?: number; cx?: number; fy?: number; r?: number; o?: number; e?: string } = {}): K {
  const sx = o.sx ?? 1, sy = o.sy ?? 1, h = H0 * sy, fy = (o.fy ?? 428) + (o.dy ?? 0);
  return { t, x: o.cx ?? 290, y: fy - 0.9794 * h + h / 2, sx, sy, r: o.r ?? 0, o: o.o, e: o.e };
}
export const home = (t: number, e?: string): K => ({ t, x: 290, y: 303, sx: 1, sy: 1, r: 0, e });
/** Swap visibility at t (for props whose drawing changes state). */
export const show = (t: number) => [{ t: Math.max(0, t - 1), o: 0, e: "none" }, { t, o: 1, e: "none" }];
export const hide = (t: number) => [{ t, o: 1, e: "none" }, { t: t + 1, o: 0, e: "none" }];
export const window_ = (a: number, b: number, extra: K[] = []): K[] => [...show(a), ...extra, ...hide(b)];
