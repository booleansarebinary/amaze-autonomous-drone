import { gsap } from "gsap";
import { CustomEase } from "gsap/CustomEase";

gsap.registerPlugin(CustomEase);

// Motion tokens from the Figma component sheet (06).
export const EASE = {
  out: CustomEase.create("uiOut", "M0,0 C0.23,1 0.32,1 1,1"),
  inOut: CustomEase.create("uiInOut", "M0,0 C0.77,0 0.175,1 1,1"),
  sine: CustomEase.create("bobSine", "M0,0 C0.37,0 0.63,1 1,1"),
  gravityUp: "power1.out",
  gravityDown: "power1.in",
  spring: "back.out(1.7)",
  springSoft: "back.out(1.2)",
  bouncy: "elastic.out(1, 0.45)",
} as const;

export const calm = { on: new URLSearchParams(location.search).get("calm") === "1" };
