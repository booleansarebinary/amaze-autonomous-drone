import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import ts from "typescript";

// Load the actual TypeScript domain modules without adding a test framework.
const moduleUrl = source => `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`;
const compile = source => ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const modelUrl = moduleUrl(compile(await readFile(new URL("../src/model.ts", import.meta.url), "utf8")));
const { calculateError, fmtTimestamp, timestamp } = await import(modelUrl);
const missionSource = compile(await readFile(new URL("../src/mission.ts", import.meta.url), "utf8")).replace('"./model"', JSON.stringify(modelUrl));
const { Mission } = await import(moduleUrl(missionSource));
const look = () => ({ color: "Pink", outfit: "None", hat: "None" });
const makeMission = () => { const mission = new Mission(look); mission.configure(200); return mission; };

test("distance error is symmetric and retains full precision", () => {
  assert.equal(calculateError(180, 200), 10);
  assert.equal(calculateError(220, 200), 10);
  assert.equal(calculateError(200, 200), 0);
  assert.equal(calculateError(0, 200), 100);
  assert.equal(calculateError(1, 3), 2 / 3 * 100);
});

test("invalid distances cannot enter the mission", () => {
  for (const target of [0, -1, NaN, Infinity]) assert.throws(() => calculateError(1, target));
  for (const guess of [-1, NaN, Infinity]) assert.throws(() => calculateError(guess, 200));
  const mission = new Mission(look);
  const player = mission.register("Ada");
  assert.throws(() => mission.submitGuess(player.id, 100));
  assert.throws(() => mission.configure(200, ""));
});

test("duplicate names have separate UUIDs, and renaming retains identity", () => {
  const mission = makeMission();
  const first = mission.register("Ada"), second = mission.register("Ada");
  assert.notEqual(first.id, second.id);
  mission.submitGuess(first.id, 180);
  mission.submitGuess(second.id, 150);
  mission.register("Ada Lovelace", {}, first.id);
  assert.equal(mission.standings()[0].name, "Ada Lovelace");
  assert.equal(mission.snapshot().players.length, 2);
});

test("worse and equal retries retain the best attempt and its timestamp", () => {
  const mission = makeMission(), player = mission.register("Ada");
  const first = mission.submit({ id: player.id, name: player.name, error: 5, submittedAt: "2026-11-09T18:00:00Z" });
  mission.submit({ id: player.id, name: player.name, error: 8, submittedAt: "2026-11-09T19:00:00Z" });
  mission.submit({ id: player.id, name: player.name, error: 5, submittedAt: "2026-11-09T20:00:00Z" });
  assert.equal(mission.standings()[0].error, 5);
  assert.equal(mission.standings()[0].submittedAt, first.submittedAt);
  assert.equal(mission.snapshot().attempts.length, 3);
});

test("improved guess replaces the personal best and can move an existing leader", () => {
  const mission = makeMission();
  const a = mission.register("Ada"), b = mission.register("Bea");
  mission.submitGuess(a.id, 180); mission.submitGuess(b.id, 160);
  const improved = mission.submitGuess(b.id, 199);
  assert.equal(mission.standings()[0].id, b.id);
  assert.equal(mission.standings()[0].submittedAt, improved.submittedAt);
  assert.equal(mission.standings()[0].guess, 199);
});

test("equal errors share rank regardless of submission time", () => {
  const mission = makeMission();
  for (const score of [
    { id: "z", name: "First", error: 5, submittedAt: "2026-11-09T18:00:00Z" },
    { id: "a", name: "Later", error: 5, submittedAt: "2026-11-09T20:00:00Z" },
    { id: "b", name: "Third", error: 6 },
  ]) mission.submit(score);
  assert.deepEqual(mission.standings().map(p => [p.id, p.rank]), [["a", 1], ["z", 1], ["b", 3]]);
});

test("timestamps are fixed CST in winter and summer, including midnight", () => {
  assert.equal(fmtTimestamp("2026-11-09T18:30:00Z"), "12:30 PM");
  assert.equal(fmtTimestamp("2026-07-09T18:30:00Z"), "12:30 PM");
  assert.equal(fmtTimestamp("2026-11-09T06:00:00Z"), "12:00 AM");
  assert.equal(timestamp("2026-11-09T12:30:00-06:00"), "2026-11-09T18:30:00.000Z");
  assert.equal(timestamp(0), "1970-01-01T00:00:00.000Z");
  assert.throws(() => timestamp("0:35"));
  assert.throws(() => timestamp("2026-11-09T12:30:00"));
  assert.throws(() => timestamp(null));
});

test("mission configuration is locked after the first attempt", () => {
  const mission = makeMission(), player = mission.register("Ada");
  mission.submitGuess(player.id, 180);
  assert.throws(() => mission.configure(300));
  assert.throws(() => mission.configure(200, "m"));
  mission.configure(200, "cm");
  assert.equal(mission.snapshot().targetDistance, 200);
});

test("saved mission round-trips IDs, avatars, attempts, and best results", () => {
  const mission = makeMission(), player = mission.register("Ada", { hat: "Cap" });
  mission.submitGuess(player.id, 180); mission.submitGuess(player.id, 170);
  const restored = new Mission(look);
  restored.restore(JSON.parse(JSON.stringify(mission.snapshot())));
  assert.deepEqual(restored.standings(), mission.standings());
  assert.deepEqual(restored.snapshot(), mission.snapshot());
  const external = restored.snapshot(); external.players[0].name = "Changed";
  assert.equal(restored.snapshot().players[0].name, "Ada");
});

test("invalid restores and bulk imports do not partially mutate mission state", () => {
  const mission = makeMission(); mission.submit({ id: "a", name: "Ada", error: 5 });
  const original = mission.snapshot();
  assert.throws(() => mission.setPlayers([{ id: "b", name: "Bea", error: 1 }, { id: "c", name: "C", error: NaN }]));
  assert.deepEqual(mission.snapshot(), original);
  const invalid = mission.snapshot(); invalid.attempts[0].playerId = "missing";
  assert.throws(() => mission.restore(invalid));
  assert.deepEqual(mission.snapshot(), original);
  assert.throws(() => mission.submit({ name: "No ID", error: 2 }));
});

test("snapshot imports retain best results and do not duplicate unchanged polls", () => {
  const mission = makeMission();
  const score = { id: "a", name: "Ada", error: 2, submittedAt: "2026-11-09T18:00:00Z" };
  mission.setPlayers([score]); mission.setPlayers([score]);
  assert.equal(mission.snapshot().attempts.length, 1);
  mission.setPlayers([{ ...score, error: 5 }]);
  assert.equal(mission.standings()[0].error, 2);
  mission.setPlayers([{ ...score, error: 5 }]);
  assert.equal(mission.snapshot().attempts.length, 2);
  mission.setPlayers([]);
  assert.equal(mission.snapshot().players.length, 0);
  assert.equal(mission.snapshot().attempts.length, 0);
});

test("top-20 display does not discard other players or attempts", () => {
  const mission = makeMission();
  for (let i = 0; i < 25; i++) mission.submit({ id: `p${i}`, name: `Player ${i}`, error: i });
  assert.equal(mission.standings().length, 20);
  assert.equal(mission.snapshot().players.length, 25);
  mission.submit({ id: "p24", name: "Player 24", error: 0 });
  assert.equal(mission.standings().find(p => p.id === "p24").rank, 1);
});
