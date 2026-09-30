// The design tokens of src/styles.css (site/DESIGN.md) meet WCAG AA contrast in both themes, and
// the two copies of the dark theme (system preference and the explicit choice) never drift.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const css = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");

function tokens(block: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of block.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})\b/g)) out[m[1]] = m[2].toLowerCase();
  return out;
}
const blockAfter = (head: string) => {
  const i = css.indexOf(head);
  expect(i, head).toBeGreaterThanOrEqual(0);
  const start = css.indexOf("{", i + head.length - 1);
  return css.slice(start + 1, css.indexOf("}", start));
};
const light = tokens(blockAfter(":root {"));
const dark = tokens(blockAfter(':root[data-theme="dark"] {'));
const darkSystem = tokens(blockAfter(':root:not([data-theme="light"]) {'));

const lin = (c: number) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
const lum = (hex: string) => { const n = parseInt(hex.slice(1), 16); return 0.2126 * lin(n >> 16) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255); };
export const contrast = (a: string, b: string) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

describe("design tokens", () => {
  it("light theme uses the specified palette", () => {
    expect(light).toMatchObject({
      bg: "#f6f7f9", surface: "#ffffff", text: "#1c2330", "text-2": "#3f4855", muted: "#5a6474", rule: "#dde1e7", "rule-faint": "#e7eaee",
      control: "#c9cfd8", blue: "#1f5fbf", "blue-hover": "#174a96", tint: "#e6edf8", ring: "#a3abb6", observed: "#1c2330", forecast: "#1f5fbf",
    });
  });

  it("the dark theme is the same for the system preference and the explicit choice", () => {
    expect(darkSystem).toEqual(dark);
    expect(Object.keys(dark).sort()).toEqual(Object.keys(light).filter((k) => k in dark).sort());
  });

  for (const [name, t] of [["light", light], ["dark", dark]] as const) {
    describe(name, () => {
      const pairs: [string, string, number][] = [];
      for (const fg of ["text", "text-2", "muted", "blue", "blue-hover", "success", "danger"])
        for (const bg of ["bg", "surface", "tint"]) pairs.push([fg, bg, 4.5]);
      pairs.push(["on-btn", "btn", 4.5], ["on-btn", "btn-hover", 4.5], ["text-2", "rule", 4.5], // text on the disabled button
        ["text", "code-bg", 4.5], ["text", "unseen", 4.5], ["muted", "unseen", 4.5],
        ["danger", "danger-tint", 4.5], ["success", "success-tint", 4.5],
        ["observed", "surface", 3], ["observed", "bg", 3], ["forecast", "surface", 3], ["forecast", "bg", 3], ["forecast", "unseen", 3]);
      it.each(pairs)("%s on %s ≥ %s:1", (fg, bg, min) => {
        expect(t[fg], fg).toBeDefined();
        expect(t[bg], bg).toBeDefined();
        expect(contrast(t[fg], t[bg])).toBeGreaterThanOrEqual(min);
      });
      it("the pending ring stays visible (it is always paired with a word)", () => {
        expect(contrast(t.ring, t.surface)).toBeGreaterThanOrEqual(name === "light" ? 2.3 : 3);
      });
    });
  }

  it("text on the Results matrix bins is readable", () => {
    const dm = (fg: string, bg: string) => contrast(fg, bg);
    for (const b of ["mid", "b1", "b2", "r1", "r2"]) expect(dm(light.text, light[b]), `light ${b}`).toBeGreaterThanOrEqual(4.5);
    for (const b of ["b3", "r3"]) expect(dm("#ffffff", light[b]), `light ${b}`).toBeGreaterThanOrEqual(4.5);
    for (const b of ["mid", "b1", "b2", "r1", "r2"]) expect(dm(dark.text, dark[b]), `dark ${b}`).toBeGreaterThanOrEqual(4.5);
    for (const b of ["b3", "r3"]) expect(dm("#111419", dark[b]), `dark ${b}`).toBeGreaterThanOrEqual(4.5);
  });
});
