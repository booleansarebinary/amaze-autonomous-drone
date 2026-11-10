# Amaze Distance Mission

A self-contained distance-guessing mission with player registration, avatar customization, attempt history, and an animated leaderboard. No drone connection is required.

## Run

```powershell
cd amaze-leaderboard
npm install
npm run dev
```

Open the URL Vite prints (normally http://localhost:5173).

1. Open `?view=setup` and enter the correct distance and unit (for example, 200 cm).
2. Open `?view=input`, create a player, choose an avatar, and submit a distance guess.
3. Open `/` in another tab for the animated leaderboard. Tabs must use the same browser profile and origin.
4. After a guess, the form resets for the next player. Use **New player** to start a fresh character at any time without leaving the page. For repeat attempts, select the existing player. Creating another player always creates a new UUID, even if the name is identical.

The target is not shown on the participant page. Setup is an operator convenience, not an authenticated admin area; this local demo does not conceal the answer from someone inspecting browser data.

## Mission rules

- Error = `abs(guess - target) / target * 100`. Target must be positive; guesses may be zero.
- Every attempt is saved. Only the lowest error per player enters the leaderboard.
- Worse or equal attempts retain the existing best score and the timestamp of that best attempt.
- Submission speed and timestamps have no effect on ranking. Equal errors share a competition rank (1, 1, 3). IDs only stabilize display order within ties.
- Rankings use unrounded error; the screen displays one decimal place.
- Timestamps are ISO instants internally and display as wall-clock time in **fixed CST (UTC-6)**, including summer. This intentionally does not switch to CDT.
- Target and unit lock after the first submission. Clear the mission before changing them.
- Players have stable UUIDs; names and avatar settings can change without losing attempts.
- Top 20 players appear on screen. Other players and their attempts remain saved.

The three rocket positions show the first three entries; equal scores share the rank label even across podium and list positions. Cyclic podium swaps caused by improvements refresh directly instead of waiting on occupied steps.

## Storage and dashboard integration

Mission configuration, players, avatars, and attempts are saved under `amaze-distance-mission-v1` in localStorage. Reloads restore the mission and storage events update other tabs. Browser storage failures are displayed. Demo, preview, and external-polling screens use isolated in-memory data.

This is a local demo, not a multi-device backend. Use one participant-entry tab as the writer. Concurrent writers can overwrite each other's browser snapshots. Separate devices or concurrent submissions need a shared service that owns player IDs, validates guesses, calculates errors, stores attempts, and broadcasts standings. Scoring is isolated in `src/mission.ts` for that integration.

`window.Leaderboard` is available on leaderboard, setup, and input pages:

```js
Leaderboard.configure(200, "cm");
const player = Leaderboard.registerPlayer("Ada", {
  color: "Mint", outfit: "Tuxedo", hat: "Top hat"
});
Leaderboard.submitGuess(player.id, 180); // 10% error
Leaderboard.submitGuess(player.id, 198); // 1% error: new best
Leaderboard.submitGuess(player.id, 150); // attempt recorded, 1% stays

Leaderboard.registerPlayer("Ada Lovelace", { hat: "Cap" }, player.id);
Leaderboard.players(); // best standings, limited to 20
Leaderboard.state();   // full configuration, players, and attempt history
const unsubscribe = Leaderboard.onChange(() => console.log(Leaderboard.players()));
unsubscribe();

// Import a precomputed attempt from an external score service. ID is required.
Leaderboard.submit({
  id: "player-42", name: "Ada", error: 1.9,
  submittedAt: "2026-11-09T18:30:00Z"
});
// Omitted submittedAt defaults to now; numbers mean epoch milliseconds.

Leaderboard.setPlayers([...]); // complete snapshot; removes omitted players
// Included players retain their best. Unchanged snapshots do not add attempts.
Leaderboard.remove(player.id); // removes this player and their attempts
Leaderboard.clear();           // removes all players and attempts; keeps config
Leaderboard.configure(300, "cm"); // can change config again after clearing

Leaderboard.load("/players.json");
Leaderboard.poll("/players.json", 3000);
Leaderboard.stopPolling();
```

JSON endpoints accept an array or `{ "players": [...] }`, using the input format shown in `public/sample-players.json`. The old elapsed-time `time` field is no longer supported. Imported scores require an explicit stable `id` and a numeric non-negative `error`. External endpoints need appropriate same-origin routing or CORS.

A `leaderboard:change` browser event carries the complete mission snapshot. Dashboard code can also call `onChange` and `state()` to consume results. No dashboard wiring or Crazyflie integration is included.

## Views and development tools

| URL option | Effect |
| --- | --- |
| `?view=setup` | Configure the correct distance and unit |
| `?view=input` | Player identity, avatar, guesses, and personal attempt history |
| `/` | Saved mission leaderboard, initially empty |
| `?demo=1` | Isolated sample scores with a random score every 9 seconds |
| `?data=/sample-players.json&every=3000` | Poll JSON snapshots |
| `?preview=all` | Preview animation sequences |
| `?preview=anvil,meteor` | Preview selected sequences |
| `?calm=1` | Reduced-motion transitions |
| `?hud=1` | Animation diagnostics |
| `?view=gallery` | Character parts gallery |

C toggles calm mode; H toggles diagnostics. N and 1/2/3 inject scores only in explicit demo/preview modes. No fake players are inserted during normal mission use.

No audio files ship with the app. `Leaderboard.onSound(({ cue }) => sounds[cue]?.play())` connects custom audio. `Leaderboard.sequences()` and `forceNext({ exit: "anvil", entrance: "meteor" })` support animation previews.

## Code map

| Path | Purpose |
| --- | --- |
| `src/model.ts` | Player/attempt/entry types, error formula, ranking, CST formatting |
| `src/mission.ts` | Domain logic, best-attempt selection, registration, configuration, snapshots |
| `src/api.ts` | Public interface, browser persistence, tab synchronization, JSON polling |
| `src/participant.ts` | Setup, player/avatar forms, guesses, attempt history |
| `src/main.ts` | View selection, initialization, explicit demo modes |
| `src/director.ts` | Ranking transitions and podium orchestration |
| `src/place.ts`, `src/actor.ts`, `src/list.ts` | Rockets, characters, scrolling standings |
| `src/stage.ts`, `src/styles.css` | Scene, scaling, layout, and mission form styles |
| `src/art/`, `src/choreo/` | SVG character/prop art and GSAP sequences |

## Checks

```powershell
npm test
npm run build
```

Tests exercise scoring, best attempts, stable identity, ties, CST timestamps, config locking, validation, and persistence snapshots. Build runs strict TypeScript checking and outputs static assets to `dist/`. `npm run preview` serves the build.
