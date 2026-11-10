# Product

A self-contained distance-guessing mission for a live demo. A participant registers a name and avatar, guesses a distance, and sees their best result on a shared animated leaderboard. No Crazyflie connection is needed.

## Stack

Vite, TypeScript, GSAP, inline SVG, and browser localStorage. Domain logic lives in `src/mission.ts` for later dashboard/service integration.

## Rules

- Configure one positive target distance and a shared unit before guesses begin.
- Each player has a unique stable ID; display their name and avatar.
- Record every attempt and calculate absolute percentage error against the target.
- Rank each player by their best (lowest-error) attempt, with equal errors sharing rank.
- Timestamps record submission wall-clock time in CST (fixed UTC-6); speed is irrelevant.
- Keep the best attempt's timestamp when later attempts are worse or equal.
- Lock target/unit once submissions exist; clear results before reconfiguration.

## Views

- Operator setup: target and unit.
- Participant entry: register/select player, customize avatar, submit guesses, view history.
- Leaderboard: three rocket positions and scrolling remaining entries, up to 20 players total.
- Developer demo, animation preview, and art gallery are explicit optional views.

## Demo boundaries

Local persistence and tab synchronization work in the same browser profile and origin. Use a single participant-entry writer. Multi-device use requires a shared backend. Setup is not authenticated and browser data is inspectable.

## Visual direction

Preserve the cosmic theme, jellybean SVG characters, rocket podiums, Space Grotesk text, Space Mono data, purple background accents, and reduced-motion option. The leaderboard is designed at 1920 by 1080 and scales to fit the display; input forms adapt to smaller screens.
