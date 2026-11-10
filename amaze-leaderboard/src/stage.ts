import titleSvg from "./art/custom/title.svg?raw";
import { G, L, sp } from "./art/svg";

export interface Stage { root: HTMLElement; world: HTMLElement; }

const sparkles: [number, number, number, string][] = [[132, 236, 30, G], [300, 176, 18, L], [690, 206, 22, L], [880, 270, 34, G], [408, 330, 16, L], [118, 470, 20, L], [960, 470, 18, L], [760, 380, 14, G]];
const dots: [number, number, number][] = [[236, 300, 5], [820, 180, 4], [560, 170, 4], [60, 360, 4], [990, 360, 5], [640, 300, 3]];
const puffs: [number, number, number][] = [[-40, 40, 150], [60, 10, 130], [150, 40, 150], [250, 64, 120], [330, 20, 160], [450, 0, 170], [560, 30, 160], [660, 56, 120], [740, 22, 140], [840, 40, 150], [930, 70, 140], [1000, 96, 110]];

function sky() {
  const s = sparkles.map(([x, y, size, c]) => sp(x + size / 2, y + size / 2, size / 2, c)).join("");
  const d = dots.map(([x, y, r]) => `<circle cx="${x + r}" cy="${y + r}" r="${r}" fill="${L}"/>`).join("");
  const planet = `<ellipse cx="500" cy="1288" rx="750" ry="320" fill="#B8A7E8"/><ellipse cx="210" cy="1023" rx="60" ry="13" fill="#A595DE"/><ellipse cx="865" cy="1040" rx="45" ry="10" fill="#A595DE"/><ellipse cx="555" cy="1065" rx="75" ry="15" fill="#A595DE"/>`;
  return `<svg class="bg" width="1920" height="1080" viewBox="0 0 1920 1080">${s}${d}${planet}</svg>`;
}
export function clouds() {
  const sh = puffs.map(([x, y, d]) => `<circle cx="${x + d / 2 + 8}" cy="${960 + y + d / 2 + 18}" r="${d / 2}" fill="#B8A7E8" fill-opacity="0.55"/>`).join("");
  const pf = puffs.map(([x, y, d]) => `<circle cx="${x + d / 2}" cy="${960 + y + d / 2}" r="${d / 2}" fill="#FFFFFF"/>`).join("");
  return `<svg class="abs" style="left:0;top:0;z-index:15" width="1920" height="1080" viewBox="0 0 1920 1080">${sh}${pf}</svg>`;
}

export function createStage(host: HTMLElement): Stage {
  const root = document.createElement("div");
  root.className = "stage";
  root.innerHTML = `${sky()}<div class="world"></div>
    <div class="title">${titleSvg}</div>
    <div class="live"><div class="pulse"><div class="halo"></div><div class="core"></div></div><span>LIVE</span></div>`;
  host.appendChild(root);
  const world = root.querySelector<HTMLElement>(".world")!;
  world.insertAdjacentHTML("beforeend", clouds());
  const fit = () => {
    const s = Math.min(innerWidth / 1920, innerHeight / 1080);
    root.style.transform = `translate(${(innerWidth - 1920 * s) / 2}px, ${(innerHeight - 1080 * s) / 2}px) scale(${s})`;
  };
  addEventListener("resize", fit);
  fit();
  return { root, world };
}
