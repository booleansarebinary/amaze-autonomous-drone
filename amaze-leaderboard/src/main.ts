import "./styles.css";
import "./ease";
import { createStage } from "./stage";
import { Director } from "./director";
import { LeaderboardApi } from "./api";
import { seed, startDemo, startPreview, newPlayer } from "./demo";
import { calm } from "./ease";
import { renderGallery } from "./gallery";

const params = new URLSearchParams(location.search);
const host = document.getElementById("app")!;

if (params.get("view") === "gallery") {
  document.body.style.overflow = "auto";
  renderGallery(host);
} else {
  const stage = createStage(host);
  const director = new Director(stage);
  const api = new LeaderboardApi(director);
  (window as unknown as { Leaderboard: LeaderboardApi }).Leaderboard = api;

  const hud = document.createElement("div");
  hud.className = "hud";
  document.body.appendChild(hud);
  const say = (s: string) => { hud.innerHTML = `<b>${s}</b><br>N new player · 1/2/3 new player on that step · C calm mode (${calm.on ? "on" : "off"}) · H hide`; };
  director.onSeq = s => say(s);
  if (params.get("hud") === "1") hud.classList.add("on");

  const source = params.get("data");
  const preview = params.get("preview");
  if (source) api.poll(source, Number(params.get("every") ?? 3000));
  else seed(api);
  if (preview) { hud.classList.add("on"); setTimeout(() => startPreview(api, preview, say), 1500); }
  else if (!source && params.get("demo") !== "0") setTimeout(() => startDemo(api), 4000);

  addEventListener("keydown", e => {
    if (e.key === "n" || e.key === "N") newPlayer(api);
    if (e.key === "1" || e.key === "2" || e.key === "3") newPlayer(api, Number(e.key) as 1 | 2 | 3);
    if (e.key === "c" || e.key === "C") { calm.on = !calm.on; say(`Calm mode ${calm.on ? "on" : "off"}`); }
    if (e.key === "h" || e.key === "H") hud.classList.toggle("on");
  });
}
