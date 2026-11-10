import "./styles.css";
import "./ease";
import { createStage } from "./stage";
import { Director } from "./director";
import { LeaderboardApi } from "./api";
import { seed, startDemo, startPreview, newPlayer } from "./demo";
import { calm } from "./ease";
import { renderGallery } from "./gallery";
import { renderParticipant } from "./participant";

const params = new URLSearchParams(location.search);
const host = document.getElementById("app")!;

if (params.get("view") === "gallery") {
  document.body.style.overflow = "auto";
  renderGallery(host);
} else if (params.get("view") === "input" || params.get("view") === "setup") {
  const api = new LeaderboardApi(null);
  (window as unknown as { Leaderboard: LeaderboardApi }).Leaderboard = api;
  renderParticipant(host, api, params.get("view") === "setup");
} else {
  const stage = createStage(host);
  const director = new Director(stage);
  const source = params.get("data");
  const preview = params.get("preview");
  const demo = params.get("demo") === "1";
  const api = new LeaderboardApi(director, !source && !preview && !demo);
  (window as unknown as { Leaderboard: LeaderboardApi }).Leaderboard = api;

  const hud = document.createElement("div");
  hud.className = "hud";
  document.body.appendChild(hud);
  const say = (s: string) => { hud.innerHTML = `<b>${s}</b><br>N new player · 1/2/3 new player on that step · C calm mode (${calm.on ? "on" : "off"}) · H hide`; };
  director.onSeq = s => say(s);
  if (params.get("hud") === "1") hud.classList.add("on");

  if (source) api.poll(source, Number(params.get("every") ?? 3000));
  else if (demo || preview) seed(api);
  if (preview) { hud.classList.add("on"); setTimeout(() => startPreview(api, preview, say), 1500); }
  else if (!source && demo) setTimeout(() => startDemo(api), 4000);

  const nav = document.createElement("nav");
  nav.className = "mission-nav";
  nav.innerHTML = `<a href="?view=input">Enter a guess</a><a href="?view=setup">Mission setup</a><span>Best attempt · Submitted time in CST</span>`;
  document.body.appendChild(nav);
  const notice = document.createElement("div");
  notice.className = "mission-notice";
  const refresh = () => { notice.textContent = api.storageError || (!api.players().length ? "Waiting for the first guess" : ""); };
  api.onChange(refresh); refresh(); document.body.appendChild(notice);

  addEventListener("keydown", e => {
    if ((demo || preview) && (e.key === "n" || e.key === "N")) newPlayer(api);
    if ((demo || preview) && (e.key === "1" || e.key === "2" || e.key === "3")) newPlayer(api, Number(e.key) as 1 | 2 | 3);
    if (e.key === "c" || e.key === "C") { calm.on = !calm.on; say(`Calm mode ${calm.on ? "on" : "off"}`); }
    if (e.key === "h" || e.key === "H") hud.classList.toggle("on");
  });
}
