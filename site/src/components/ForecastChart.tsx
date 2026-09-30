// A "what happens next?" chart for a predict question (figure data from tsfm_rc.learn, built by
// `make lessons`). Data semantics (site/DESIGN.md): observed values are a solid graphite line,
// continuing into what happened once revealed; a forecast is a blue dashed line. Every line also
// has a label, so colour is never the only signal.
import { useEffect, useId, useRef, useState } from "react";
import type { ForecastFigure } from "../lib/types";

/** Up to five round gridlines above zero. */
function niceMax(v: number): { max: number; step: number } {
  const raw = v / 5;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((k) => k * mag).find((s) => s >= raw) ?? raw;
  return { max: Math.ceil(v / step) * step, step };
}

/** The drawing is laid out at the width it is shown at, so its text stays 12px on a phone. */
function useWidth(fallback: number) {
  const ref = useRef<HTMLElement>(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([e]) => setW(Math.round(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

const pct = (v: number) => `${Number(v.toFixed(2))}%`;

export function ForecastChart({ fig, selected, revealed, animate, forecastLabel = "Your forecast" }: {
  fig: ForecastFigure; selected: number | null; revealed: boolean; animate: boolean; forecastLabel?: string;
}) {
  const id = useId();
  const [box, width] = useWidth(760);
  const W = Math.max(300, Math.min(760, width || 760));
  const narrow = W < 560;
  const H = narrow ? 240 : 300;
  const M = { l: 40, r: narrow ? 96 : 112, t: 28, b: 30 };
  const before = fig.observed.length - 1; // the shock is the last observed day
  const days = before + fig.realised.length;
  const all = [...fig.observed, ...fig.realised, ...fig.options.flat()];
  const { max, step } = niceMax(Math.max(...all) * 1.04);
  const X = (d: number) => M.l + (d / days) * (W - M.l - M.r);
  const Y = (v: number) => M.t + (1 - v / max) * (H - M.t - M.b);
  const line = (pts: [number, number][]) => pts.map(([d, v], i) => `${i ? "L" : "M"}${X(d).toFixed(1)},${Y(v).toFixed(1)}`).join("");
  const shock = fig.observed[before];
  const observed = line(fig.observed.map((v, i) => [i, v]));
  const future = (vals: number[]) => line([[before, shock], ...vals.map((v, k) => [before + 1 + k, v] as [number, number])]);
  const ticks = Array.from({ length: Math.round(max / step) + 1 }, (_, i) => i * step);
  const plotBottom = H - M.b;
  // direct labels at the right end of the future lines, nudged apart if they would collide
  const ends: { y: number; text: string; cls: string }[] = [];
  if (revealed) ends.push({ y: Y(fig.realised[fig.realised.length - 1]), text: "What happened", cls: "annot" });
  if (selected !== null) ends.push({ y: Y(fig.options[selected][fig.options[selected].length - 1]), text: forecastLabel, cls: "annot forecast-label" });
  if (ends.length === 2 && Math.abs(ends[0].y - ends[1].y) < 16) {
    const [a, b] = ends[0].y <= ends[1].y ? [ends[0], ends[1]] : [ends[1], ends[0]];
    const mid = (a.y + b.y) / 2;
    a.y = mid - 8;
    b.y = mid + 8;
  }
  const r = fig.realised;
  const desc = [
    `${before} days of the true daily volatility of a simulated series, around ${pct(fig.levels.calm_median)} a day, then a shock to ${pct(shock)} on day ${before}.`,
    revealed ? `What happened next: ${pct(r[Math.min(9, r.length - 1)])} ten days later and ${pct(r[r.length - 1])} on day ${days}.`
      : `Days ${before + 1} to ${days} are not shown until you check.`,
    selected !== null ? `${forecastLabel} is drawn as a dashed line.` : "",
  ].join(" ");
  return (
    <figure className="fchart" data-testid="forecast-chart" data-revealed={revealed} ref={box as React.RefObject<HTMLElement>}>
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-labelledby={`${id}-t ${id}-d`}>
        <title id={`${id}-t`}>{fig.measure}, in {fig.unit}</title>
        <desc id={`${id}-d`}>{desc}</desc>
        {!revealed && <rect className="unseen" x={X(before)} y={M.t - 12} width={X(days) - X(before)} height={plotBottom - M.t + 12} />}
        <g className="grid">
          {ticks.slice(1).map((v) => <line key={v} x1={M.l} x2={X(days)} y1={Y(v)} y2={Y(v)} />)}
        </g>
        {ticks.slice(1).map((v) => <text key={v} x={M.l - 8} y={Y(v) + 4} textAnchor="end">{`${Number(v.toFixed(2))}%`}</text>)}
        <line className="axis" x1={M.l} x2={X(days)} y1={plotBottom} y2={plotBottom} />
        <line className="cut" x1={X(before)} x2={X(before)} y1={M.t - 12} y2={plotBottom} />
        <text x={X(0)} y={H - 8} textAnchor="start">Day 0</text>
        <text x={X(before)} y={H - 8} textAnchor="middle">Day {before}</text>
        <text x={X(days)} y={H - 8} textAnchor="end">Day {days}</text>
        {!revealed && <text x={(X(before) + X(days)) / 2} y={plotBottom - 10} textAnchor="middle">Not yet seen</text>}
        <text className="annot" x={X(before) - 6} y={Y(shock) - 8} textAnchor="end">{narrow ? "Shock" : `Shock on day ${before}`}</text>
        <path className="observed" d={observed} />
        {revealed && <path key={animate ? "draw" : "still"} className={`observed realised${animate ? " draw" : ""}`} d={future(fig.realised)} pathLength={1} />}
        {selected !== null && <path className="forecast" d={future(fig.options[selected])} data-testid="forecast-line" />}
        {ends.map((e) => (
          <text key={e.text} className={e.cls} x={X(days) + 8} y={e.y + 4}>{e.text}</text>
        ))}
      </svg>
      <figcaption>
        <span className="key-line"><svg viewBox="0 0 24 6" aria-hidden="true"><line className="solid" x1="0" x2="24" y1="3" y2="3" /></svg>Observed</span>
        <span className="key-line"><svg viewBox="0 0 24 6" aria-hidden="true"><line className="dashed" x1="0" x2="24" y1="3" y2="3" /></svg>{forecastLabel}</span>
        <span>Illustrative synthetic series from the course fixtures</span>
      </figcaption>
    </figure>
  );
}
