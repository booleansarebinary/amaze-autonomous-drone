import type { Look } from "./art/characters";

export interface Player { id: string; name: string; look: Look; }
export interface Attempt {
  id: string;
  playerId: string;
  guess?: number;
  error: number;
  /** ISO instant, displayed in fixed Central Standard Time (UTC−6). */
  submittedAt: string;
}
export interface Entry extends Player {
  error: number;
  submittedAt: string;
  guess?: number;
  rank: number;
}

export const MAX_SHOWN = 20;

/** Equal errors share a competition rank. IDs only stabilize their display order. */
export function rank(entries: Iterable<Omit<Entry, "rank">>, limit = MAX_SHOWN): Entry[] {
  const sorted = [...entries].sort((a, b) => a.error - b.error || a.id.localeCompare(b.id));
  let position = 0;
  return sorted.map((entry, i) => {
    if (i === 0 || entry.error !== sorted[i - 1].error) position = i + 1;
    return { ...entry, rank: position };
  }).slice(0, limit);
}

export const fmtError = (e: number) => `${e.toFixed(1)}%`;
export function calculateError(guess: number, target: number): number {
  if (!Number.isFinite(target) || target <= 0) throw new Error("Target distance must be greater than zero.");
  if (!Number.isFinite(guess) || guess < 0) throw new Error("Guess must be a non-negative distance.");
  const error = Math.abs(guess - target) / target * 100;
  if (!Number.isFinite(error)) throw new Error("Distance is too large.");
  return error;
}

export function timestamp(value: string | number = Date.now()): string {
  if (typeof value !== "string" && typeof value !== "number") throw new Error("Invalid submission timestamp.");
  if (typeof value === "string" && !/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/i.test(value)) {
    throw new Error("Timestamp must be an ISO date with a timezone, or epoch milliseconds.");
  }
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) throw new Error("Invalid submission timestamp.");
  return date.toISOString();
}

const clock = new Intl.DateTimeFormat("en-US", {
  timeZone: "Etc/GMT+6", hour: "numeric", minute: "2-digit", hour12: true,
});
export const fmtTimestamp = (value: string) => clock.format(new Date(value));
