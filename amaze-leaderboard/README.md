# Amaze Leaderboard

A live 1920×1080 leaderboard: three rocket podiums with bean characters, plus a scrolling list for ranks 4–20. Its designs and animations are ported from the Figma file: the default state, podium changes, 19 exits, 2 combos, 22 entrances, 6 body colors, 65 hats and 65 outfits.

Built with Vite, TypeScript and GSAP. Every piece of art is inline SVG, so there are no image assets to load.

## Run

```bash
npm install
```

```bash
npm run dev
```

Open http://localhost:5173. Use `npm run build` to produce a static `dist/` folder you can host anywhere, and `npm run preview` to serve that build.

The stage is always 1920×1080 and scales to fit any window.

## URL options

| Param | Effect |
| --- | --- |
| `?demo=0` | Turn off the demo (by default a random score arrives every 9 s) |
| `?data=/sample-players.json&every=3000` | Poll a JSON URL every 3 s; changes animate |
| `?preview=all` | Play every sequence in turn (6.5 s apart) |
| `?preview=anvil,meteor` | Play only these sequences |
| `?calm=1` | Calm mode: 300 ms fades instead of travel, squash and spin |
| `?hud=1` | Show the overlay with the current sequence name |
| `?view=gallery` | Every body color, hat and outfit on one page |

## Keys

| Key | Effect |
| --- | --- |
| `N` | Add a random player |
| `1` / `2` / `3` | Add a player who lands on that podium step |
| `C` | Toggle calm mode |
| `H` | Toggle the HUD |

## API (`window.Leaderboard`)

```js
// Add or update a player. Same id (defaults to name) = update.
Leaderboard.submit({ name: "Ada", error: 2.1, time: "0:37" });
Leaderboard.submit({ id: "p42", name: "Ada", error: 1.9, time: 35, look: { color: "Mint", outfit: "Tuxedo", hat: "Top hat" } });

Leaderboard.setPlayers([...]);   // replace everyone at once
Leaderboard.remove("p42");
Leaderboard.clear();
Leaderboard.players();           // current ranking

Leaderboard.load("/players.json");          // once
Leaderboard.poll("/players.json", 3000);    // repeatedly
Leaderboard.stopPolling();

Leaderboard.calm(true);
Leaderboard.forceNext({ exit: "anvil", entrance: "meteor" });  // ids from Leaderboard.sequences()
Leaderboard.onSound(({ cue, id }) => sounds[cue]?.play());
```

- **Ranking:** lowest error wins. Ties go to the faster time, then to whoever submitted first.
- **Error:** given in percent, so `2.5` means 2.5%.
- **Time:** seconds, or a `"m:ss"` string.
- **Looks:** a player without a `look` gets a random one, which they keep from then on. See [public/sample-players.json](public/sample-players.json) for the JSON format: an array, or `{ "players": [...] }`.

## How a ranking change plays

1. Players knocked off the podium leave with an exit. The exit is random, but never one of the last 5 used.
2. Players moving between steps jump down from the bottom step up, so each step is empty before anyone lands on it.
3. New podium players arrive with an entrance. Dive, Meteor and Magician are reserved for 1st place.
4. The list updates at 1 s. New rows get a gold ring and changed ranks get a chevron.
5. When 3rd place is replaced directly, Trading places or Banana peel sometimes plays instead of a separate exit and entrance.

## Sound

No audio ships with the leaderboard. Each sequence fires a `leaderboard:sound` event with a cue name (`boing`, `boom`, `arcade`, and others). Connect your own sounds with `Leaderboard.onSound`.

## Code map

| Path | Contents |
| --- | --- |
| `src/art/` | Palette, character parts (bodies, hats, outfits) and every prop, as SVG strings |
| `src/choreo/` | Exit, combo and entrance keyframes, written in the Figma storyboard's tile coordinates, plus the runner that turns them into GSAP timelines |
| `src/director.ts` | Turns ranking changes into choreography |
| `src/place.ts`, `src/actor.ts`, `src/list.ts` | Rockets, characters and the list |
| `src/stage.ts` | Sky, clouds, title, LIVE pill, scaling |
