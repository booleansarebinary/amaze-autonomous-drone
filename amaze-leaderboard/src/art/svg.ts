// Shared palette and SVG drawing helpers. Every shape here is the same markup the Figma file was built from.
export const P = "#5D3BC3", INK = "#1E1442", WH = "#FFFFFF", G = "#F4C95D", C = "#E96A5B", M = "#9BD6C0", L = "#B8A7E8", PK = "#E8B6C7", PERI = "#7F8FD4", BG = "#F1F0F5";
export const CD = "#C9493C", TAN = "#C99A3A", TAND = "#A87D2B", KRAFT = "#D9B27A", GREEN = "#6FB59B", GREENL = "#B7E0C4", CHEESED = "#D9AE3F", DECK3 = "#BF574B", SOIL = "#A8453C", YH = "#DBB554";

/** Character canvas: 200×340 units, body starting 50 units from the top. */
export const char = (inner: string) => `<svg viewBox="0 -40 200 340" fill="none" xmlns="http://www.w3.org/2000/svg">${inner}</svg>`;
/** Storyboard tile canvas, anchored so (290, 420) is the centre-top of the deck being acted on. */
export const tile = (inner: string) => `<svg width="580" height="680" viewBox="0 0 580 680" fill="none" overflow="visible" xmlns="http://www.w3.org/2000/svg">${inner}</svg>`;
export const box = (w: number, h: number, inner: string, vb = `0 0 ${w} ${h}`) => `<svg width="${w}" height="${h}" viewBox="${vb}" fill="none" overflow="visible" xmlns="http://www.w3.org/2000/svg">${inner}</svg>`;

export const hex = (h: string) => { const v = h.replace("#", ""); return [0, 2, 4].map(i => parseInt(v.slice(i, i + 2), 16)); };
export const darken = (h: string, k: number) => "#" + hex(h).map(c => Math.round(c * k).toString(16).padStart(2, "0")).join("");

export const sp = (cx: number, cy: number, r: number, f: string) =>
  `<path d="M${cx} ${cy - r}C${cx + r * 0.08} ${cy - r * 0.42} ${cx + r * 0.42} ${cy - r * 0.08} ${cx + r} ${cy}C${cx + r * 0.42} ${cy + r * 0.08} ${cx + r * 0.08} ${cy + r * 0.42} ${cx} ${cy + r}C${cx - r * 0.08} ${cy + r * 0.42} ${cx - r * 0.42} ${cy + r * 0.08} ${cx - r} ${cy}C${cx - r * 0.42} ${cy - r * 0.08} ${cx - r * 0.08} ${cy - r * 0.42} ${cx} ${cy - r}Z" fill="${f}"/>`;
export const star = (cx: number, cy: number, ro: number, ri: number, n: number, f: string) => {
  let d = "";
  for (let i = 0; i < n * 2; i++) { const r = i % 2 ? ri : ro, a = (Math.PI * i) / n - Math.PI / 2; d += `${i ? "L" : "M"}${(cx + r * Math.cos(a)).toFixed(1)} ${(cy + r * Math.sin(a)).toFixed(1)}`; }
  return `<path d="${d}Z" fill="${f}"/>`;
};
export const puff = (cx: number, cy: number, r: number) => `<circle cx="${cx + 4}" cy="${cy + 6}" r="${r}" fill="${L}" fill-opacity="0.55"/><circle cx="${cx}" cy="${cy}" r="${r}" fill="${WH}"/>`;
export const vl = (x: number, y: number, len: number) => `<rect x="${x - 6}" y="${y}" width="12" height="${len}" rx="6" fill="${L}"/>`;
export const hl = (x: number, y: number, len: number) => `<rect x="${x}" y="${y - 5}" width="${len}" height="10" rx="5" fill="${L}"/>`;
export const heart = (cx: number, cy: number, s: number, f: string) => `<path d="M${cx} ${cy + s * 0.9}C${cx - s * 1.6} ${cy - s * 0.2} ${cx - s * 0.6} ${cy - s * 1.3} ${cx} ${cy - s * 0.4}C${cx + s * 0.6} ${cy - s * 1.3} ${cx + s * 1.6} ${cy - s * 0.2} ${cx} ${cy + s * 0.9}Z" fill="${f}"/>`;
