import type { Look } from "./art/characters";

export interface Entry {
  id: string;
  name: string;
  /** Distance from the correct answer, in percent. Lower ranks higher. */
  error: number;
  /** Seconds taken to answer. Breaks ties. */
  time: number;
  look: Look;
  /** Submission order, the last tiebreaker. */
  at: number;
}

export const MAX_SHOWN = 20;

export function rank(entries: Iterable<Entry>): Entry[] {
  return [...entries].sort((a, b) => a.error - b.error || a.time - b.time || a.at - b.at).slice(0, MAX_SHOWN);
}

export const fmtError = (e: number) => `${e.toFixed(1)}%`;
export const fmtTime = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;

/** Accepts seconds or an "m:ss" string. */
export function parseTime(t: number | string): number {
  if (typeof t === "number") return t;
  const [m, s] = t.split(":").map(Number);
  return s === undefined ? m : m * 60 + s;
}
