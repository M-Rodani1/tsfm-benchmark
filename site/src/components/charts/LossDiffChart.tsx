import { useRef, useState } from "react";
import { useTooltip } from "../Tooltip";
import { colorOf, dayToDate, fmt, type RunPayload } from "./common";

/** Cumulative loss differential (model − reference) over origins: falling line = model better. */
export function LossDiffChart({ run, target, h, window, asset, model }: {
  run: RunPayload; target: string; h: number; window: string; asset: string; model: string;
}) {
  const tip = useTooltip();
  const ref = useRef<SVGSVGElement>(null);
  const [cross, setCross] = useState<number | null>(null);
  const want = run.series.keys
    .map((k, i) => ({ k, i }))
    .filter(({ k }) => k.target === target && k.horizon === h && k.window === window && k.ticker === asset && (model === "all" || k.model === model));
  if (!want.length) return <p className="muted">No stored series for this selection{window !== "expanding" && asset !== "POOLED" ? " (per-asset series exist for the expanding window only)" : ""}.</p>;
  const series = want.map(({ k, i }) => ({ k, d: run.series.data[i].d, y: run.series.data[i].y.map((v) => v ?? 0) }));
  const W = 900, H = 300, m = { l: 56, r: 16, t: 10, b: 28 };
  const xs = series.flatMap((s) => s.d), ys = series.flatMap((s) => s.y).concat([0]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const X = (d: number) => m.l + ((d - x0) / Math.max(1, x1 - x0)) * (W - m.l - m.r);
  const Y = (v: number) => m.t + (1 - (v - y0) / Math.max(1e-12, y1 - y0)) * (H - m.t - m.b);
  const dec = Math.abs(y1 - y0) < 1 ? 3 : 1;
  const onMove = (e: React.PointerEvent) => {
    const rect = ref.current!.getBoundingClientRect();
    const d = x0 + (((e.clientX - rect.left) * W) / rect.width - m.l) / (W - m.l - m.r) * (x1 - x0);
    let nearest = series[0].d[0];
    const rows = series.map((s) => {
      let j = 0;
      let best = Infinity;
      s.d.forEach((v, k) => { if (Math.abs(v - d) < best) { best = Math.abs(v - d); j = k; } });
      if (Math.abs(s.d[j] - d) < Math.abs(nearest - d)) nearest = s.d[j];
      return { value: fmt(s.y[j]), label: s.k.model, color: colorOf(s.k.model) };
    });
    setCross(nearest);
    tip.show(e.clientX, e.clientY, [{ value: dayToDate(nearest), label: "origin" }, ...rows]);
  };
  return (
    <>
      <div className="legend">
        {series.map((s) => <span key={s.k.model}><span className="key" style={{ background: colorOf(s.k.model) }} />{s.k.model}</span>)}
      </div>
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Cumulative loss differential chart" className="chart" data-testid="lossdiff-chart">
        <g className="grid">
          {[0, 1, 2, 3, 4].map((i) => { const v = y0 + ((y1 - y0) * i) / 4; return <line key={i} x1={m.l} x2={W - m.r} y1={Y(v)} y2={Y(v)} />; })}
        </g>
        {[0, 1, 2, 3, 4].map((i) => { const v = y0 + ((y1 - y0) * i) / 4; return <text key={i} x={m.l - 6} y={Y(v) + 4} textAnchor="end">{fmt(v, dec)}</text>; })}
        {[0, 1, 2, 3, 4, 5].map((i) => { const d = x0 + ((x1 - x0) * i) / 5; return <text key={i} x={X(d)} y={H - 8} textAnchor={i === 0 ? "start" : i === 5 ? "end" : "middle"}>{dayToDate(Math.round(d)).slice(0, 7)}</text>; })}
        <line x1={m.l} x2={W - m.r} y1={Y(0)} y2={Y(0)} stroke="var(--axis)" strokeWidth={1} />
        {series.map((s) => (
          <path key={s.k.model} d={s.d.map((d, j) => `${j ? "L" : "M"}${X(d).toFixed(1)},${Y(s.y[j]).toFixed(1)}`).join("")}
            fill="none" stroke={colorOf(s.k.model)} strokeWidth={2} strokeLinejoin="round" />
        ))}
        {cross !== null && <line x1={X(cross)} x2={X(cross)} y1={m.t} y2={H - m.b} stroke="var(--muted)" strokeWidth={1} />}
        <rect x={m.l} y={m.t} width={W - m.l - m.r} height={H - m.t - m.b} fill="transparent" onPointerMove={onMove}
          onPointerLeave={() => { setCross(null); tip.hide(); }} />
      </svg>
    </>
  );
}
