import { BODY_COLORS, HATS, OUTFITS } from "./art/characters";
import { layersHtml } from "./actor";
import { escapeHtml } from "./list";

/** ?view=gallery: every body color, hat and outfit (Figma sheet 05), for checking the art. */
export function renderGallery(host: HTMLElement) {
  const card = (label: string, color: string, outfit: string, hat: string) => `<div class="card"><div class="fig">${layersHtml({ color, outfit, hat })}</div>${escapeHtml(label)}</div>`;
  const colors = Object.keys(BODY_COLORS);
  host.innerHTML = `<div class="gallery">
    <h2>Body colors · ${colors.length}</h2><div class="grid">${colors.map(c => card(c, c, "None", "None")).join("")}</div>
    <h2>Hats · ${Object.keys(HATS).length - 1}</h2><div class="grid">${Object.keys(HATS).filter(h => h !== "None").map(h => card(h, "Pink", "None", h)).join("")}</div>
    <h2>Outfits · ${Object.keys(OUTFITS).length - 1}</h2><div class="grid">${Object.keys(OUTFITS).filter(o => o !== "None").map((o, i) => card(o, colors[(i + 3) % colors.length], o, "None")).join("")}</div>
  </div>`;
}
