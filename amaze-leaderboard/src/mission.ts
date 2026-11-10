import type { Look } from "./art/characters";
import { calculateError, rank, timestamp, type Player, type Attempt } from "./model";

export interface ScoreInput {
  id: string;
  name: string;
  error: number;
  submittedAt?: string | number;
  look?: Partial<Look>;
}
export interface MissionState {
  version: 1;
  targetDistance: number | null;
  unit: string;
  players: Player[];
  attempts: Attempt[];
}

/** Domain logic independent of the DOM, animation, and persistence. */
export class Mission {
  private state: MissionState = { version: 1, targetDistance: null, unit: "cm", players: [], attempts: [] };
  constructor(private makeLook: () => Look) {}

  snapshot(): MissionState { return structuredClone(this.state); }

  restore(state: MissionState) {
    if (!state || state.version !== 1 || !Array.isArray(state.players) || !Array.isArray(state.attempts)) throw new Error("Invalid mission data.");
    if (state.targetDistance !== null) calculateError(0, state.targetDistance);
    if (typeof state.unit !== "string" || !state.unit.trim() || state.unit.length > 12) throw new Error("Invalid distance unit.");
    const ids = new Set<string>(), attemptIds = new Set<string>();
    for (const player of state.players) {
      this.validatePlayer(player.id, player.name);
      if (ids.has(player.id) || !player.look || [player.look.color, player.look.hat, player.look.outfit].some(v => typeof v !== "string")) throw new Error("Invalid player data.");
      ids.add(player.id);
    }
    for (const attempt of state.attempts) {
      if (!attempt.id || attemptIds.has(attempt.id) || !ids.has(attempt.playerId) || !Number.isFinite(attempt.error) || attempt.error < 0) throw new Error("Invalid attempt data.");
      if (typeof attempt.submittedAt !== "string") throw new Error("Attempt timestamp is required.");
      timestamp(attempt.submittedAt);
      if (attempt.guess !== undefined && (state.targetDistance === null || calculateError(attempt.guess, state.targetDistance) !== attempt.error)) throw new Error("Attempt does not match mission target.");
      attemptIds.add(attempt.id);
    }
    this.state = structuredClone(state);
  }

  configure(targetDistance: number, unit = "cm") {
    calculateError(0, targetDistance);
    if (!unit.trim() || unit.trim().length > 12) throw new Error("Enter a distance unit (up to 12 characters).");
    if (this.state.attempts.length && (targetDistance !== this.state.targetDistance || unit.trim() !== this.state.unit)) {
      throw new Error("The target and unit are locked after the first attempt. Start a new mission to change them.");
    }
    this.state.targetDistance = targetDistance;
    this.state.unit = unit.trim();
  }

  register(name: string, look: Partial<Look> = {}, id: string = crypto.randomUUID()): Player {
    this.validatePlayer(id, name);
    if (Object.values(look).some(value => typeof value !== "string")) throw new Error("Invalid avatar selection.");
    const previous = this.state.players.find(p => p.id === id);
    const player = { id, name: name.trim(), look: { ...(previous?.look ?? this.makeLook()), ...look } };
    this.state.players = previous ? this.state.players.map(p => p.id === id ? player : p) : [...this.state.players, player];
    return structuredClone(player);
  }

  submitGuess(playerId: string, guess: number): Attempt {
    if (this.state.targetDistance === null) throw new Error("Configure the target distance first.");
    if (!this.state.players.some(p => p.id === playerId)) throw new Error("Select a registered player.");
    const attempt = { id: crypto.randomUUID(), playerId, guess, error: calculateError(guess, this.state.targetDistance), submittedAt: timestamp() };
    this.state.attempts.push(attempt);
    return structuredClone(attempt);
  }

  /** Import a precomputed attempt from a dashboard or score service. */
  submit(score: ScoreInput): Attempt {
    this.validatePlayer(score.id, score.name);
    if (!Number.isFinite(score.error) || score.error < 0) throw new Error("Error must be a finite non-negative percentage.");
    const submittedAt = timestamp(score.submittedAt);
    this.register(score.name, score.look, score.id);
    const attempt = { id: crypto.randomUUID(), playerId: score.id, error: score.error, submittedAt };
    this.state.attempts.push(attempt);
    return structuredClone(attempt);
  }

  standings(limit = 20) {
    const best = new Map<string, Attempt>();
    for (const attempt of this.state.attempts) {
      const previous = best.get(attempt.playerId);
      if (!previous || attempt.error < previous.error) best.set(attempt.playerId, attempt);
    }
    return rank(this.state.players.flatMap(player => {
      const attempt = best.get(player.id);
      return attempt ? [{ ...player, error: attempt.error, submittedAt: attempt.submittedAt, guess: attempt.guess }] : [];
    }), limit);
  }

  /** Complete snapshot: omitted players are removed, included players retain their best. */
  setPlayers(scores: ScoreInput[]) {
    if (!Array.isArray(scores)) throw new Error("Expected a players array.");
    const next = new Mission(this.makeLook);
    next.restore(this.snapshot());
    const ids = new Set(scores.map(s => s.id));
    next.state.players = next.state.players.filter(p => ids.has(p.id));
    next.state.attempts = next.state.attempts.filter(a => ids.has(a.playerId));
    for (const score of scores) {
      // Identical polled scores must not create an attempt every few seconds.
      const submittedAt = score.submittedAt === undefined ? undefined : timestamp(score.submittedAt);
      const existing = next.state.attempts.some(a => a.playerId === score.id && a.error === score.error && (submittedAt === undefined || submittedAt === a.submittedAt));
      if (existing) {
        next.register(score.name, score.look, score.id);
      } else next.submit(score);
    }
    this.state = next.state;
  }

  remove(id: string) {
    this.state.players = this.state.players.filter(p => p.id !== id);
    this.state.attempts = this.state.attempts.filter(a => a.playerId !== id);
  }
  clear() { this.state.players = []; this.state.attempts = []; }
  private validatePlayer(id: string, name: string) {
    if (typeof id !== "string" || !id.trim()) throw new Error("A stable player ID is required.");
    if (typeof name !== "string" || !name.trim() || name.trim().length > 40) throw new Error("Enter a player name (1–40 characters).");
  }
}
