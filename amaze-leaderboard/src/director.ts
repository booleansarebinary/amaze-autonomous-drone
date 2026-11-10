import { gsap } from "gsap";
import { EASE, calm } from "./ease";
import { Actor } from "./actor";
import { Place } from "./place";
import { RankList } from "./list";
import type { Entry } from "./model";
import { runSeq } from "./choreo/run";
import { EXITS, COMBOS } from "./choreo/exits";
import { ENTRANCES, BIG_ENTRANCES } from "./choreo/entrances";
import type { Seq } from "./choreo/types";
import type { Stage } from "./stage";

const ALL = [...EXITS, ...COMBOS, ...ENTRANCES];
export const SEQS = Object.fromEntries(ALL.map(s => [s.id, s])) as Record<string, Seq>;

type Deferred = { promise: Promise<void>; resolve: () => void };
const deferred = (): Deferred => { let resolve!: () => void; const promise = new Promise<void>(r => (resolve = r)); return { promise, resolve }; };
const wait = (ms: number) => new Promise(r => setTimeout(r, ms));

/** Turns ranking changes into choreography: exits, bottom-up jump-downs, entrances and the list update. */
export class Director {
  readonly places: Place[];
  readonly list: RankList;
  private actors = new Map<string, Actor>();
  private shown: Entry[] = [];
  private pending: Entry[] | null = null;
  private busy = false;
  private recent: string[] = [];
  /** Force the next exit or entrance (preview mode and the API). */
  force: { exit?: string; entrance?: string } = {};
  onSeq: (name: string) => void = () => {};

  constructor(private stage: Stage) {
    this.places = [0, 1, 2].map(i => new Place(i, stage.world));
    this.list = new RankList(stage.root);
  }

  show(ranking: Entry[]) {
    this.pending = ranking;
    if (!this.busy) void this.flush();
  }

  private async flush() {
    this.busy = true;
    while (this.pending) {
      const next = this.pending;
      this.pending = null;
      try { await this.transition(this.shown, next); } catch (err) { console.error(err); this.hardSet(next); }
      this.shown = next;
    }
    this.busy = false;
  }

  /** Put everyone in place with no animation (first paint, or recovery). */
  private hardSet(next: Entry[]) {
    for (const a of this.actors.values()) a.remove();
    this.actors.clear();
    this.places.forEach((p, i) => {
      p.stopBob(true);
      const e = next[i];
      p.occupant = null;
      if (e) { const a = this.spawn(e); a.setHome(p); p.occupant = a; a.setRank(i + 1); a.startIdle(i * 0.6); }
      p.setBand(e ? { kind: "entry", entry: e } : { kind: "empty" }, false);
      p.startBob();
    });
    this.list.update(next.slice(3), false);
  }

  private spawn(e: Entry) { const a = new Actor(e.id, e.look, this.stage.world); this.actors.set(e.id, a); return a; }

  private pick(pool: Seq[], forced?: string): Seq {
    if (forced && SEQS[forced]) return SEQS[forced];
    const fresh = pool.filter(s => !this.recent.includes(s.id));
    const s = (fresh.length ? fresh : pool)[Math.floor(Math.random() * (fresh.length ? fresh.length : pool.length))];
    this.recent = [s.id, ...this.recent].slice(0, 5);
    return s;
  }

  private async transition(old: Entry[], next: Entry[]) {
    if (!this.actors.size && !old.length) { this.hardSet(next); return; }
    const oldTop = [0, 1, 2].map(i => old[i]?.id ?? null), newTop = [0, 1, 2].map(i => next[i]?.id ?? null);
    const byId = new Map(next.map(e => [e.id, e]));
    const exits = oldTop.map((id, i) => ({ id, from: i })).filter(x => x.id && !newTop.includes(x.id)) as { id: string; from: number }[];
    const moves = newTop.map((id, to) => ({ id, to, from: id ? oldTop.indexOf(id) : -1 })).filter(m => m.id && m.from >= 0 && m.from !== m.to) as { id: string; to: number; from: number }[];
    const enters = newTop.map((id, to) => ({ id, to })).filter(x => x.id && !oldTop.includes(x.id)) as { id: string; to: number }[];

    // Nothing changes on the podium: refresh bands and the list only.
    if (!exits.length && !moves.length && !enters.length) {
      this.places.forEach((p, i) => { const e = next[i]; if (e) p.setBand({ kind: "entry", entry: e }); });
      this.list.update(next.slice(3));
      return;
    }

    const involved = new Set<number>([...exits.map(x => x.from), ...moves.flatMap(m => [m.from, m.to]), ...enters.map(x => x.to)]);
    involved.forEach(i => this.places[i].stopBob());
    for (const a of this.actors.values()) a.onRankEvent(exits.length > 0);
    for (const x of enters) if (old.some(e => e.id === x.id)) this.list.liftOut(x.id);

    const freed = this.places.map(() => deferred());
    this.places.forEach((p, i) => { if (!involved.has(i) || !p.occupant) freed[i].resolve(); });
    const tasks: Promise<unknown>[] = [];

    // Trading places and Banana peel: the exit brings the new 3rd-place player in itself.
    const eligible = exits.length === 1 && enters.length === 1 && !moves.length && exits[0].from === enters[0].to && exits[0].from === 2;
    const forcedCombo = COMBOS.find(c => c.id === this.force.exit);
    const combo = !eligible ? null : forcedCombo ?? (!this.force.exit && !this.force.entrance && Math.random() < 2 / 21 ? COMBOS[Math.floor(Math.random() * COMBOS.length)] : null);
    if (combo) this.force = {};

    if (combo) {
      const place = this.places[2], leaving = place.occupant!, e = byId.get(enters[0].id)!;
      leaving.stopIdle();
      const newcomer = this.spawn(e); newcomer.setHome(place); newcomer.stopIdle(true);
      this.onSeq(combo.name);
      const run = runSeq(combo, { place, actor: leaving, other: newcomer, world: this.stage.world });
      tasks.push(run.clear.then(() => { place.occupant = newcomer; place.setBand({ kind: "entry", entry: e }); newcomer.onLand(); }));
      tasks.push(run.done.then(() => { leaving.remove(); this.actors.delete(leaving.id); }));
      setTimeout(() => this.list.update(next.slice(3)), 1000);
    } else {
      for (const x of exits) {
        const place = this.places[x.from], actor = place.occupant!;
        actor.stopIdle();
        const seq = this.pick(EXITS, this.force.exit);
        this.force.exit = undefined;
        this.onSeq(seq.name);
        const run = runSeq(seq, { place, actor, world: this.stage.world });
        tasks.push(run.clear.then(() => { if (place.occupant === actor) place.occupant = null; freed[x.from].resolve(); }));
        tasks.push(run.done.then(() => { actor.remove(); this.actors.delete(actor.id); }));
      }
      const listAt = wait(1000).then(() => this.list.update(next.slice(3)));
      tasks.push(listAt);

      // Bottom-up: each step empties before anyone lands on it.
      for (const to of [2, 1, 0]) {
        const mv = moves.find(m => m.to === to), en = enters.find(x => x.to === to);
        if (mv) {
          const actor = this.actors.get(mv.id)!, from = this.places[mv.from], dest = this.places[to];
          tasks.push(freed[to].promise.then(async () => {
            if (!enters.some(x => x.to === mv.from) && !moves.some(m => m.to === mv.from)) from.setBand({ kind: "empty" });
            const j = this.jump(actor, from, dest);
            await j.takeoff;
            if (from.occupant === actor) from.occupant = null;
            freed[mv.from].resolve();
            await j.done;
            dest.occupant = actor;
            dest.setBand({ kind: "entry", entry: byId.get(mv.id)! });
            actor.onLand();
            actor.onRankUp();
          }));
        } else if (en) {
          const dest = this.places[to], e = byId.get(en.id)!;
          tasks.push(freed[to].promise.then(async () => {
            dest.setBand({ kind: "incoming" });
            await wait(to === 2 ? 100 : 250);
            const seq = this.pick(ENTRANCES.filter(s => (to === 0 ? s.big : !BIG_ENTRANCES.includes(s.id))), this.force.entrance);
            this.force.entrance = undefined;
            this.onSeq(seq.name);
            const actor = this.spawn(e);
            actor.setHome(dest);
            actor.stopIdle(true);
            const run = runSeq(seq, { place: dest, actor, world: this.stage.world });
            await run.clear;
            dest.occupant = actor;
            dest.setBand({ kind: "entry", entry: e });
            actor.onLand();
            await run.done;
          }));
        } else if (exits.some(x => x.from === to)) {
          tasks.push(freed[to].promise.then(() => this.places[to].setBand({ kind: "empty" })));
        }
      }
    }

    await Promise.all(tasks);
    await wait(300);
    this.places.forEach((p, i) => {
      const e = next[i];
      if (e) p.setBand({ kind: "entry", entry: e });
      if (p.occupant) { p.occupant.setHome(p); p.occupant.setRank(i + 1); p.occupant.startIdle(0.4); }
      p.startBob();
    });
  }

  /** Jump-down between steps (Figma 02A): crouch, arc behind the leader, squash on landing, spring back. */
  private jump(actor: Actor, from: Place, to: Place) {
    const takeoff = deferred(), done = deferred();
    actor.stopIdle();
    const dx = to.home.x - from.home.x, dy = to.home.y - from.home.y;
    if (calm.on) {
      gsap.to(actor.motion, { opacity: 0, duration: 0.3, onComplete: () => { takeoff.resolve(); actor.setHome(to); gsap.fromTo(actor.motion, { opacity: 0 }, { opacity: 1, duration: 0.3, onComplete: done.resolve }); } });
      return { takeoff: takeoff.promise, done: done.promise };
    }
    const crosses = (from.index === 1 && to.index === 2) || (from.index === 2 && to.index === 1);
    const apex = Math.min(0, dy) - (crosses ? 260 : 150);
    const tl = gsap.timeline();
    tl.to(actor.squash, { scaleX: 1.15, scaleY: 0.85, duration: 0.16, ease: EASE.inOut })
      .to(from.el, { y: 6, duration: 0.16, ease: EASE.inOut }, 0)
      .to(actor.squash, { scaleX: 0.88, scaleY: 1.18, duration: 0.1, ease: EASE.out })
      .to(from.el, { y: 0, duration: 0.4, ease: EASE.bouncy }, 0.16)
      .call(() => { actor.setZ(crosses ? "low" : "normal"); }, [], 0.2)
      .to(actor.motion, { x: dx, duration: 0.74, ease: EASE.inOut }, 0.26)
      .to(actor.motion, { y: apex, duration: 0.37, ease: EASE.gravityUp }, 0.26)
      .to(actor.motion, { y: dy, duration: 0.37, ease: EASE.gravityDown }, 0.63)
      .to(actor.squash, { scaleX: 1, scaleY: 1, duration: 0.3, ease: "sine.inOut" }, 0.36)
      .to(actor.size, { scale: to.charScale, duration: 0.74, ease: EASE.inOut }, 0.26)
      .call(() => takeoff.resolve(), [], 0.45)
      .to(actor.squash, { scaleX: 1.3, scaleY: 0.72, duration: 0.08, ease: "power2.out" }, 1.0)
      .to(to.el, { y: 10, duration: 0.08 }, 1.0)
      .to(actor.squash, { scaleX: 1, scaleY: 1, duration: 0.5, ease: EASE.bouncy }, 1.08)
      .to(to.el, { y: 0, duration: 0.5, ease: EASE.bouncy }, 1.08)
      .call(() => { actor.setZ("normal"); actor.setHome(to); done.resolve(); }, [], 1.1);
    return { takeoff: takeoff.promise, done: done.promise };
  }
}
