import { BODY_COLORS, HATS, OUTFITS, type Look } from "./art/characters";
import { Mission, type ScoreInput } from "./mission";
export type { ScoreInput } from "./mission";
import type { Director } from "./director";
import { SEQS } from "./director";
import { calm } from "./ease";

const STORAGE_KEY = "amaze-distance-mission-v1";

const pickOne = <T,>(xs: T[]) => xs[Math.floor(Math.random() * xs.length)];
export const randomLook = (): Look => ({
  color: pickOne(Object.keys(BODY_COLORS)),
  outfit: pickOne(Object.keys(OUTFITS).filter(o => o !== "None")),
  hat: pickOne(Object.keys(HATS).filter(h => h !== "None" && !/^Hat\d+$/.test(h))),
});

/** The public API, also exposed as window.Leaderboard. */
export class LeaderboardApi {
  private mission = new Mission(randomLook);
  private listeners = new Set<() => void>();
  private pollTimer = 0;
  private loadVersion = 0;
  storageError = "";

  constructor(private director: Director | null, private persistent = true) {
    if (persistent) {
      try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) this.mission.restore(JSON.parse(saved));
      } catch (error) { this.storageError = `Could not restore mission: ${String(error)}`; }
      window.addEventListener("storage", event => {
        if (event.key !== STORAGE_KEY || !event.newValue) return;
        try { this.mission.restore(JSON.parse(event.newValue)); this.render(false); }
        catch (error) { console.error("Invalid mission update", error); }
      });
    }
    this.render(false);
  }

  state() { return this.mission.snapshot(); }
  configure(targetDistance: number, unit = "cm") { this.mission.configure(targetDistance, unit); this.render(); }
  registerPlayer(name: string, look: Partial<Look> = {}, id?: string) {
    const player = this.mission.register(name, look, id);
    this.render();
    return player;
  }
  submitGuess(playerId: string, guess: number) {
    const attempt = this.mission.submitGuess(playerId, guess);
    this.render();
    return attempt;
  }
  onChange(listener: () => void) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  submit(s: ScoreInput) {
    const attempt = this.mission.submit(s);
    this.render();
    return attempt;
  }

  /** Replace every player at once (for example from your game server). */
  setPlayers(list: ScoreInput[]) {
    this.mission.setPlayers(list);
    this.render();
  }

  remove(id: string) { this.mission.remove(id); this.render(); }
  clear() { this.mission.clear(); this.render(); }
  players() { return this.mission.standings(); }

  /** Load players once from a JSON URL: an array of ScoreInput, or { players: ScoreInput[] }. */
  async load(url: string) {
    const version = ++this.loadVersion;
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`Leaderboard request failed (${res.status}).`);
    const data = await res.json();
    if (version !== this.loadVersion) return;
    this.setPlayers(Array.isArray(data) ? data : data.players);
  }
  /** Re-load the URL every `ms` milliseconds; differences animate. */
  poll(url: string, ms = 3000) {
    if (!Number.isFinite(ms) || ms < 250) throw new Error("Polling interval must be at least 250 milliseconds.");
    clearInterval(this.pollTimer);
    void this.load(url).catch(console.error);
    this.pollTimer = window.setInterval(() => void this.load(url).catch(console.error), ms);
  }
  stopPolling() { clearInterval(this.pollTimer); this.loadVersion++; }

  calm(on: boolean) { calm.on = on; }
  /** Force the next exit and/or entrance by id, e.g. forceNext({ exit: "anvil", entrance: "meteor" }). */
  forceNext(f: { exit?: string; entrance?: string }) { if (this.director) this.director.force = { ...this.director.force, ...f }; }
  sequences() { return Object.values(SEQS).map(s => ({ id: s.id, name: s.name, kind: s.kind, sound: s.sound })); }
  /** Listen for sound cues, e.g. onSound(({ cue }) => audio[cue]?.play()). */
  onSound(cb: (d: { cue: string; id: string }) => void) {
    const h = (e: Event) => cb((e as CustomEvent).detail);
    window.addEventListener("leaderboard:sound", h);
    return () => window.removeEventListener("leaderboard:sound", h);
  }

  private render(save = true) {
    if (save && this.persistent) {
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(this.mission.snapshot())); this.storageError = ""; }
      catch { this.storageError = "Browser storage is unavailable or full. Changes will not survive a reload."; }
    }
    this.director?.show(this.mission.standings());
    this.listeners.forEach(listener => listener());
    window.dispatchEvent(new CustomEvent("leaderboard:change", { detail: this.state() }));
  }
}
