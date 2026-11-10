# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack
Undecided. The current deliverable is a Figma design (file "Space Leaderboard"); code was deferred ("pick-ui-library only if I ask for code later").

## Users
A room of people watching a live leaderboard on a large landscape monitor during a guessing/estimation game. They read it from a distance, at a glance, and never touch it.

## Product Purpose
Shows the live ranking of a guessing/estimation game. Players are ranked by how close their answer is to the correct one: lowest error % is the best rank. Success means anyone in the room can find the top 3 and their own rank within seconds.

## Positioning
The ranking is staged as a show: the top 3 stand on rocket podiums as playful jellybean characters each player built themselves, and rank changes play out as physical gags (punch box, spring launch, parachute and dive arrivals).

## Operating Context
- 16:9 monitor at 1920×1080, always on, non-interactive: no hover states or small UI.
- Viewed from the back of a room: minimum on-air text about 28 px at 1080p, high contrast.
- Top 3 on the podium; ranks 4–20 in an auto-scrolling, looping list.

## Capabilities and Constraints
- Each entry shows rank, name, time and error %; the list rows also show a character avatar.
- Podium places can only move down; 3rd place is knocked off when someone new enters the top 3.
- Players build their character from predefined lists: hat, body color and clothes, on a base 3D jellybean model that has no clothes.
- Undecided: the game's title, the real item list, whether items come in colorways, and how the 3D model renders on screen.

## Brand Commitments
- Fonts: Space Grotesk for headings, names and labels; Space Mono for all data (rank, time, error %).
- Colors: primary #5D3BC3 (dominant accent), #B8A7E8, #F1F0F5 (screen background); secondary #F4C95D, #7F8FD4, #E96A5B, #E8B6C7, #9BD6C0.
- Feel: playful, energetic and cosmic, in the style of Fall Guys (chunky, glossy, soft 3D characters, bouncy motion) on a clean, light space theme.

## Evidence on Hand
- The base 3D character model and the reference image of the pink jellybean were mentioned but not provided yet; the Figma file uses 2D stand-ins.
- All player names, times and error percentages in the designs are synthetic sample data.

## Product Principles
- Legible from the back of the room beats decoration.
- Error % decides the rank, so it is the most prominent number in every entry.
- Motion is news: the resting screen stays calm, and rank changes get the big moments.
- Every character combination must read on every background and at avatar size.

## Accessibility & Inclusion
High contrast for distance viewing (text at least 4.5:1, large text at least 3:1). A calm-mode motion setting exists for venues with motion-sensitive viewers.
