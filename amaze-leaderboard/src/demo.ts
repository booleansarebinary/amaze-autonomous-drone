import type { LeaderboardApi } from "./api";
import { randomLook } from "./api";
import type { Look } from "./art/characters";
import { SEQS } from "./director";
import { BIG_ENTRANCES } from "./choreo/entrances";

// Synthetic sample data from the Figma file. Replace with real players.
const SEED: [string, number, Look?][] = [
  ["Mira", 1.2, { color: "Pink", outfit: "Tank top", hat: "Headband" }],
  ["Theo", 2.8, { color: "Mint", outfit: "Overalls", hat: "Cap" }],
  ["Juno", 3.5, { color: "Yellow", outfit: "Tee", hat: "Beanie" }],
  ["Kai", 4.1], ["Priya", 5.0], ["Oskar", 6.3], ["Lena", 7.7], ["Diego", 8.2], ["Ana Sofia", 9.4], ["Ravi", 10.8],
  ["Noor", 11.5], ["Felix", 12.9], ["Hana", 14.2], ["Marcus", 15.6], ["Zoe", 17.0], ["Ibrahim", 18.3], ["Clara", 20.1],
  ["Tomás", 22.4], ["Yuki", 24.0], ["Benedikt", 27.5],
];
const NAMES = ["Nova", "Ziggy", "Ada", "Bruno", "Cleo", "Dev", "Elif", "Finn", "Gaia", "Hugo", "Iris", "Jonas", "Kira", "Luca", "Maya", "Nils", "Olga", "Pablo", "Quinn", "Rosa", "Sami", "Tara", "Uma", "Vik", "Wren", "Xena", "Yara", "Zane"];

export function seed(api: LeaderboardApi) {
  api.setPlayers(SEED.map(([name, error, look], i) => ({ id: `demo-${i}`, name, error, submittedAt: new Date().toISOString(), look: look ?? randomLook() })));
}

let n = 0;
const nextName = () => `${NAMES[n++ % NAMES.length]}${n > NAMES.length ? " " + Math.ceil(n / NAMES.length) : ""}`;

/** A new random player. `place` puts them on that podium step (1–3) by choosing their error. */
export function newPlayer(api: LeaderboardApi, place?: 1 | 2 | 3) {
  const cur = api.players();
  let error: number;
  if (place && cur.length >= 3) {
    const above = place === 1 ? 0 : cur[place - 2].error, below = cur[place - 1].error;
    error = +(above + (below - above) * (0.3 + Math.random() * 0.4)).toFixed(2);
  } else error = +(Math.random() * Math.random() * 30).toFixed(1);
  api.submit({ id: crypto.randomUUID(), name: nextName(), error, look: randomLook() });
}

/** Demo loop: a new score every 9 s, about a third of them landing on the podium. */
export function startDemo(api: LeaderboardApi) {
  return window.setInterval(() => {
    const r = Math.random();
    newPlayer(api, r < 0.12 ? 1 : r < 0.22 ? 2 : r < 0.35 ? 3 : undefined);
  }, 9000);
}

/** Preview loop (?preview=all, ?preview=anvil, ?preview=meteor): plays one sequence after another. */
export function startPreview(api: LeaderboardApi, which: string, show: (s: string) => void) {
  const ids = which === "all" ? Object.keys(SEQS) : which.split(",");
  let i = 0;
  const play = () => {
    const id = ids[i++ % ids.length], s = SEQS[id];
    if (!s) return;
    show(`${s.kind} · ${s.name} (${s.id})`);
    if (s.kind === "entrance") { api.forceNext({ entrance: id }); newPlayer(api, BIG_ENTRANCES.includes(id) ? 1 : 3); }
    else if (s.kind === "exit") { api.forceNext({ exit: id, entrance: "parachute" }); newPlayer(api, 3); }
    else { api.forceNext({ exit: id }); newPlayer(api, 3); }
  };
  play();
  return window.setInterval(play, 6500);
}
