import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

// Exercise the real transition orchestration with lightweight rendering doubles.
// No browser/GSAP clock is needed for the immediate swap-recovery path.
const doubles = `
const gsap = {}, EASE = {}, calm = { on: false };
const EXITS = [], COMBOS = [], ENTRANCES = [], BIG_ENTRANCES = [];
const runSeq = () => { throw new Error("Unexpected choreography in a cyclic swap"); };
class Actor {
  constructor(id, look) { this.id = id; this.look = look; }
  setHome(place) { this.place = place; }
  setRank(rank) { this.rank = rank; }
  startIdle() {} remove() { this.removed = true; }
}
class Place {
  constructor(index) { this.index = index; this.occupant = null; }
  stopBob() {} startBob() {}
  setBand(state) { this.band = state; }
}
class RankList { update(entries) { this.entries = entries; } }
`;
const source = await readFile(new URL("../src/director.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const executable = doubles + compiled.replace(/^import .*;\r?$/gm, "");
const { Director } = await import(`data:text/javascript;base64,${Buffer.from(executable).toString("base64")}`);
const entry = (id, error, rank) => ({ id, name: id, error, rank, submittedAt: "2026-11-09T18:00:00Z", look: { color: "Pink", outfit: "None", hat: "None" } });

test("a retry swapping first and second place completes without waiting on occupied steps", { timeout: 1000 }, async () => {
  const director = new Director({ root: {}, world: {} });
  const old = [entry("a", 2, 1), entry("b", 3, 2), entry("c", 4, 3)];
  director.hardSet(old);
  await director.transition(old, [entry("b", 1, 1), entry("a", 2, 2), entry("c", 4, 3)]);
  assert.deepEqual(director.places.map(p => p.occupant.id), ["b", "a", "c"]);
});

test("three-way podium cycles recover and subsequent updates still complete", { timeout: 1000 }, async () => {
  const director = new Director({ root: {}, world: {} });
  const old = [entry("a", 2, 1), entry("b", 3, 2), entry("c", 4, 3)];
  const next = [entry("c", 1, 1), entry("a", 2, 2), entry("b", 3, 3)];
  director.hardSet(old);
  await director.transition(old, next);
  const tied = next.map(e => ({ ...e, error: 1, rank: 1 }));
  await director.transition(next, tied);
  assert.deepEqual(director.places.map(p => [p.occupant.id, p.occupant.rank]), [["c", 1], ["a", 1], ["b", 1]]);
});

test("updating an existing podium avatar rebuilds its artwork", async () => {
  const director = new Director({ root: {}, world: {} });
  const old = [entry("a", 2, 1)];
  director.hardSet(old);
  const previousActor = director.places[0].occupant;
  await director.transition(old, [{ ...old[0], look: { ...old[0].look, hat: "Cap" } }]);
  assert.equal(previousActor.removed, true);
  assert.equal(director.places[0].occupant.look.hat, "Cap");
});
