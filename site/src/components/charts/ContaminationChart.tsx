import { useTooltip } from "../Tooltip";
import { fmt, fmtp, type RunPayload } from "./common";

/** Δ = ln R_clean − ln R_seen with 95% CI, for TSFMs and baseline placebo pairs. TSFMs are blue
 * filled dots, placebo pairs graphite hollow squares; zero is a solid graphite line. */
export function ContaminationChart({ run, target, h }: { run: RunPayload; target: string; h: number }) {
  const tip = useTooltip();
  const rows = run.contamination.filter((c) => c.target === target && c.horizon === h && c.delta !== null && c.delta !== undefined);
  if (!rows.length) return <p className="empty">No contamination statistics for this selection.</p>;
  const W = 520, rowH = 28, m = { l: 210, r: 16, t: 8, b: 24 }, H = m.t + m.b + rowH * rows.length;
  const lo = Math.min(0, ...rows.map((x) => x.ci_lo ?? x.delta!)), hi = Math.max(0, ...rows.map((x) => x.ci_hi ?? x.delta!));
  const X = (v: number) => m.l + ((v - lo) / Math.max(1e-9, hi - lo)) * (W - m.l - m.r);
  const colour = (role: string) => (role === "tsfm" ? "var(--forecast)" : "var(--observed)");
  const roles = [...new Set(rows.map((r) => r.role))];
  return (
    <>
      <div className="legend">
        {roles.map((r) => (
          <span key={r} className="key-line">
            <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
              {r === "tsfm" ? <circle cx="6" cy="6" r="4.5" fill="var(--forecast)" /> : <rect x="2" y="2" width="8" height="8" fill="var(--surface)" stroke="var(--observed)" strokeWidth="1.5" />}
            </svg>
            {r === "tsfm" ? "Foundation model" : "Placebo (baseline pair)"}
          </span>
        ))}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Contamination statistic with 95% intervals, one row per model or placebo pair" data-testid="contamination-chart">
        <line className="zero" x1={X(0)} x2={X(0)} y1={m.t} y2={H - m.b} />
        {[0, 1, 2].map((i) => { const v = lo + ((hi - lo) * i) / 2; return <text key={i} x={X(v)} y={H - 6} textAnchor={i === 0 ? "start" : i === 2 ? "end" : "middle"}>{fmt(v, 3)}</text>; })}
        {rows.map((c, i) => {
          const y = m.t + rowH * (i + 0.5);
          const col = colour(c.role);
          const tr = [{ value: fmt(c.delta), label: `Δ · ${c.model} (${c.role})` }, { value: `[${fmt(c.ci_lo)}, ${fmt(c.ci_hi)}]`, label: "95% CI" },
            { value: fmtp(c.p_one_sided), label: "p (Δ > 0)" }, { value: c.role === "tsfm" ? fmtp(c.p_holm) : "–", label: "Holm p" },
            { value: `${c.T_seen ?? "–"}/${c.T_clean ?? "–"}`, label: "origins seen/clean" }];
          return (
            <g key={i}>
              <text x={m.l - 8} y={y + 4} textAnchor="end">{`${c.model} · ${c.windows_of.split("_")[0]} windows`}</text>
              {c.ci_lo !== null && c.ci_hi !== null && <line x1={X(c.ci_lo)} x2={X(c.ci_hi)} y1={y} y2={y} stroke={col} strokeWidth={2} strokeLinecap="round" />}
              {c.role === "tsfm"
                ? <circle cx={X(c.delta!)} cy={y} r={5} fill={col} stroke="var(--surface)" strokeWidth={2} />
                : <rect x={X(c.delta!) - 4.5} y={y - 4.5} width={9} height={9} fill="var(--surface)" stroke={col} strokeWidth={1.75} />}
              <rect x={m.l} y={y - rowH / 2} width={W - m.l - m.r} height={rowH} fill="transparent" tabIndex={0} role="img"
                aria-label={`${c.model}, ${c.role}: delta ${fmt(c.delta)}, 95% interval ${fmt(c.ci_lo)} to ${fmt(c.ci_hi)}`}
                onPointerMove={(e) => tip.show(e.clientX, e.clientY, tr)} onPointerLeave={tip.hide} onBlur={tip.hide}
                onFocus={(e) => { const r = e.currentTarget.getBoundingClientRect(); tip.show(r.right, r.top, tr); }} />
            </g>
          );
        })}
      </svg>
    </>
  );
}
