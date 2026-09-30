import { useRef, useState } from "react";
import { useTooltip } from "../Tooltip";
import { dayToDate, fmt, type RunPayload } from "./common";

const TSFMS = ["chronos_bolt_tiny", "timesfm_2p5_200m", "moirai_1p1_small"];

/** Cumulative loss differential (model − reference) over origins: falling line = model better.
 * Data semantics (site/DESIGN.md): every model line is dashed and labelled at its end; the
 * selected model is blue, the others grey; the reference (zero) is solid graphite. */
export function LossDiffChart({ run, target, h, window, asset, model }: {
  run: RunPayload; target: string; h: number; window: string; asset: string; model: string;
}) {
  const tip = useTooltip();
  const ref = useRef<SVGSVGElement>(null);
  const [cross, setCross] = useState<number | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const want = run.series.keys
    .map((k, i) => ({ k, i }))
    .filter(({ k }) => k.target === target && k.horizon === h && k.window === window && k.ticker === asset && (model === "all" || k.model === model));
  if (!want.length) return <p className="empty">No stored series for this selection{window !== "expanding" && asset !== "POOLED" ? " (per-asset series exist for the expanding window only)" : ""}.</p>;
  const series = want.map(({ k, i }) => ({ k, d: run.series.data[i].d, y: run.series.data[i].y.map((v) => v ?? 0) }));
  const names = series.map((s) => s.k.model);
  const selected = picked && names.includes(picked) ? picked : names.find((m) => TSFMS.includes(m)) ?? names[0];
  const reference = series[0].k.reference;
  const W = 900, H = 320, m = { l: 56, r: 132, t: 12, b: 28 };
  const xs = series.flatMap((s) => s.d), ys = series.flatMap((s) => s.y).concat([0]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const X = (d: number) => m.l + ((d - x0) / Math.max(1, x1 - x0)) * (W - m.l - m.r);
  const Y = (v: number) => m.t + (1 - (v - y0) / Math.max(1e-12, y1 - y0)) * (H - m.t - m.b);
  const dec = Math.abs(y1 - y0) < 1 ? 3 : 1;
  // end labels, sorted by position and pushed apart so they never overlap
  const labels = [...series.map((s) => ({ text: s.k.model, y: Y(s.y[s.y.length - 1]), sel: s.k.model === selected })),
    { text: `${reference} (reference)`, y: Y(0), sel: false }].sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i++) labels[i].y = Math.max(labels[i].y, labels[i - 1].y + 14);
  const onMove = (e: React.PointerEvent) => {
    const rect = ref.current!.getBoundingClientRect();
    const d = x0 + (((e.clientX - rect.left) * W) / rect.width - m.l) / (W - m.l - m.r) * (x1 - x0);
    let nearest = series[0].d[0];
    const rows = series.map((s) => {
      let j = 0;
      let best = Infinity;
      s.d.forEach((v, k) => { if (Math.abs(v - d) < best) { best = Math.abs(v - d); j = k; } });
      if (Math.abs(s.d[j] - d) < Math.abs(nearest - d)) nearest = s.d[j];
      return { value: fmt(s.y[j]), label: s.k.model, color: s.k.model === selected ? "var(--forecast)" : "var(--muted)" };
    });
    setCross(nearest);
    tip.show(e.clientX, e.clientY, [{ value: dayToDate(nearest), label: "origin" }, ...rows]);
  };
  const ordered = [...series].sort((a, b) => Number(a.k.model === selected) - Number(b.k.model === selected));
  return (
    <>
      <div className="legend" role="group" aria-label="Highlight a model">
        {series.map((s) => (
          <button key={s.k.model} type="button" aria-pressed={s.k.model === selected} onClick={() => setPicked(s.k.model)}>
            <svg width="22" height="6" aria-hidden="true"><line x1="0" x2="22" y1="3" y2="3" className={`series${s.k.model === selected ? " selected" : ""}`} /></svg>
            {s.k.model}
          </button>
        ))}
        <span className="key-line"><svg viewBox="0 0 24 6" aria-hidden="true"><line className="solid" x1="0" x2="24" y1="3" y2="3" /></svg>{reference}, the reference (zero)</span>
      </div>
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} width="100%" role="img" className="chart" data-testid="lossdiff-chart"
        aria-label={`Cumulative loss differential against ${reference} for ${names.join(", ")}; ${selected} highlighted. Falling means the model is better.`}>
        <g className="grid">
          {[0, 1, 2, 3, 4].map((i) => { const v = y0 + ((y1 - y0) * i) / 4; return <line key={i} x1={m.l} x2={W - m.r} y1={Y(v)} y2={Y(v)} />; })}
        </g>
        {[0, 1, 2, 3, 4].map((i) => { const v = y0 + ((y1 - y0) * i) / 4; return <text key={i} x={m.l - 6} y={Y(v) + 4} textAnchor="end">{fmt(v, dec)}</text>; })}
        {[0, 1, 2, 3, 4, 5].map((i) => { const d = x0 + ((x1 - x0) * i) / 5; return <text key={i} x={X(d)} y={H - 8} textAnchor={i === 0 ? "start" : i === 5 ? "end" : "middle"}>{dayToDate(Math.round(d)).slice(0, 7)}</text>; })}
        <line className="zero" x1={m.l} x2={W - m.r} y1={Y(0)} y2={Y(0)} />
        {ordered.map((s) => (
          <path key={s.k.model} d={s.d.map((d, j) => `${j ? "L" : "M"}${X(d).toFixed(1)},${Y(s.y[j]).toFixed(1)}`).join("")}
            className={`series${s.k.model === selected ? " selected" : ""}`} />
        ))}
        {labels.map((l) => <text key={l.text} x={W - m.r + 8} y={l.y + 4} className={`series-label${l.sel ? " selected" : ""}`}>{l.text}</text>)}
        {cross !== null && <line x1={X(cross)} x2={X(cross)} y1={m.t} y2={H - m.b} stroke="var(--muted)" strokeWidth={1} />}
        <rect x={m.l} y={m.t} width={W - m.l - m.r} height={H - m.t - m.b} fill="transparent" onPointerMove={onMove}
          onPointerLeave={() => { setCross(null); tip.hide(); }} />
      </svg>
    </>
  );
}
