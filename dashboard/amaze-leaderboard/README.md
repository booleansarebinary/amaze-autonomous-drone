# Amaze Leaderboard

A single-file live leaderboard dashboard: an animated top-3 podium (rockets and bean characters), a scrolling ranks 4–20 list, rank-change animations, a calm mode, and a character builder. No build step and no dependencies. Fonts load from Google Fonts with a system fallback.

## Run it

Open `amaze-leaderboard.html` in any modern browser. The page scales to fit narrow screens.

## Controls

| Control | What it does |
|---|---|
| New leader (dive) | A new player takes 1st. The 3rd-place player is knocked off, 2nd hops to 3rd, 1st hops to 2nd, and the newcomer dives in head first. |
| New 2nd / New 3rd (parachute) | The newcomer parachutes into 2nd or 3rd. The knocked-off player drops to rank 4 in the list. |
| Exit style | Choose how 3rd place leaves: punch box or spring launch. |
| Calm mode | Removes all travel, squash and spin. Players and list pages crossfade, and the rockets and characters hold still. |
| Auto demo | Fires a random rank change every 22 seconds. |
| Submit a score | Enter a name, an error % and a time in seconds. The page picks the right animation, or inserts the player into the list. Names must be new. |
| Character builder | Pick body color, outfit and hat, then apply the result to 1st place. |

## Behavior

- **Ranking:** players are ordered by error %, lowest first. The board keeps the top 20.
- **List auto-scroll:** holds 5 s, then advances one page (6 rows, 648 px) in 700 ms. The strip is duplicated for a seamless loop, and a full loop takes about 17 s. The scroll pauses 3 s after a rank change.
- **Timings:** punch, spring, hop, parachute and dive timings follow the motion notes. Dive and chute durations are 1400 ms.
- **Ambient motion:** sway, bob, flame flicker and the LIVE halo run continuously unless calm mode is on.
- **Characters:** 6 body colors, 7 outfits (Cape, Varsity jacket and Karate gi change with rank) and 11 hats. Every item is drawn on one 200×340 canvas, so any combination lines up.

## Not built yet

- The extended catalog (53 more hats, 59 more outfits) and most per-item behaviors. Animated so far: headband tails, antennae, wizard hat, cat ears and halo.
- The 20th-place row does not fade out when a new entrant pushes it off the list.
- Sound.

## Connect a live backend

The page exposes `window.AMAZE`:

```js
AMAZE.submit("Wren", 2.1, 41);   // name, error %, time in seconds. Returns a status string.
AMAZE.rankChange(0);             // 0 = new leader, 1 = new 2nd, 2 = new 3rd (simulated player)
AMAZE.setCalm(true);
```

A minimal Python relay (a sketch, not tested here):

```python
# pip install fastapi uvicorn   ->   uvicorn server:app --reload
from fastapi import FastAPI, WebSocket

app = FastAPI()
clients = set()

@app.websocket("/ws")
async def ws(sock: WebSocket):
    await sock.accept()
    clients.add(sock)
    try:
        while True:
            await sock.receive_text()
    except Exception:
        clients.discard(sock)

@app.post("/score")
async def score(name: str, error: float, time: int):
    for c in list(clients):
        await c.send_json({"name": name, "error": error, "time": time})
    return {"ok": True}
```

In the page, wire the socket to `submit`:

```js
new WebSocket("ws://localhost:8000/ws").onmessage = e => {
  const d = JSON.parse(e.data);
  AMAZE.submit(d.name, d.error, d.time);
};
```

A page published as an artifact cannot open outside connections, so this only works when the file is served from your own machine or host.

## Files

- `amaze-leaderboard.html`: the whole dashboard (HTML, CSS and JS).
- `README.md`: this file.
