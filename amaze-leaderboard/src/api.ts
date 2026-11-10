import { BODY_COLORS, HATS, OUTFITS, type Look } from "./art/characters";
import { rank, parseTime, type Entry } from "./model";
import type { Director } from "./director";
import { SEQS } from "./director";
import { calm } from "./ease";

export interface ScoreInput {
  /** Stable player id. Defaults to the name. Submitting the same id again updates that player. */
  id?: string;
  name: string;
  /** Error in percent (2.5 means 2.5%). */
  error: number;
  /** Seconds, or "m:ss". */
  time: number | string;
  look?: Partial<Look>;
}

const pickOne = <T,>(xs: T[]) => xs[Math.floor(Math.random() * xs.length)];
export const randomLook = (): Look => ({
  color: pickOne(Object.keys(BODY_COLORS)),
  outfit: pickOne(Object.keys(OUTFITS).filter(o => o !== "None")),
  hat: pickOne(Object.keys(HATS).filter(h => h !== "None" && !/^Hat\d+$/.test(h))),
});

/** The public API, also exposed as window.Leaderboard. */
export class LeaderboardApi {
  private entries = new Map<string, Entry>();
  private seq = 0;
  private pollTimer = 0;

  constructor(private director: Director) {}

  submit(s: ScoreInput) {
    const id = s.id ?? s.name;
    const prev = this.entries.get(id);
    const look = { ...(prev?.look ?? randomLook()), ...(s.look ?? {}) } as Look;
    this.entries.set(id, { id, name: s.name, error: Number(s.error), time: parseTime(s.time), look, at: prev?.at ?? this.seq++ });
    this.render();
  }

  /** Replace every player at once (for example from your game server). */
  setPlayers(list: ScoreInput[]) {
    const next = new Map<string, Entry>();
    for (const s of list) {
      const id = s.id ?? s.name, prev = this.entries.get(id);
      next.set(id, { id, name: s.name, error: Number(s.error), time: parseTime(s.time), look: { ...(prev?.look ?? randomLook()), ...(s.look ?? {}) } as Look, at: prev?.at ?? this.seq++ });
    }
    this.entries = next;
    this.render();
  }

  remove(id: string) { this.entries.delete(id); this.render(); }
  clear() { this.entries.clear(); this.render(); }
  players() { return rank(this.entries.values()); }

  /** Load players once from a JSON URL: an array of ScoreInput, or { players: ScoreInput[] }. */
  async load(url: string) {
    const res = await fetch(url, { cache: "no-store" });
    const data = await res.json();
    this.setPlayers(Array.isArray(data) ? data : data.players);
  }
  /** Re-load the URL every `ms` milliseconds; differences animate. */
  poll(url: string, ms = 3000) {
    clearInterval(this.pollTimer);
    void this.load(url).catch(console.error);
    this.pollTimer = window.setInterval(() => void this.load(url).catch(console.error), ms);
  }
  stopPolling() { clearInterval(this.pollTimer); }

  calm(on: boolean) { calm.on = on; }
  /** Force the next exit and/or entrance by id, e.g. forceNext({ exit: "anvil", entrance: "meteor" }). */
  forceNext(f: { exit?: string; entrance?: string }) { this.director.force = { ...this.director.force, ...f }; }
  sequences() { return Object.values(SEQS).map(s => ({ id: s.id, name: s.name, kind: s.kind, sound: s.sound })); }
  /** Listen for sound cues, e.g. onSound(({ cue }) => audio[cue]?.play()). */
  onSound(cb: (d: { cue: string; id: string }) => void) {
    const h = (e: Event) => cb((e as CustomEvent).detail);
    window.addEventListener("leaderboard:sound", h);
    return () => window.removeEventListener("leaderboard:sound", h);
  }

  private render() { this.director.show(rank(this.entries.values())); }
}
