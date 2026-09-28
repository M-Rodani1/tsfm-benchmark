import { useTooltip, type TipRow } from "../Tooltip";
import { binClass, fmt, fmtp, type RunPayload } from "./common";

/** Relative loss vs the reference for every (model, target, horizon): ★ Holm-significant, ● in the MCS. */
export function DmMatrix({ run, period, window, asset }: { run: RunPayload; period: string; window: string; asset: string }) {
  const tip = useTooltip();
  const pooled = asset === "POOLED";
  const rows = pooled ? run.dm.filter((d) => d.period === period && d.window === window)
    : period === "common_clean" && window === "expanding" ? run.dm_asset.filter((d) => d.period === "common_clean" && d.ticker === asset) : [];
  const mcs = run.mcs.filter((c) => c.period === period && c.ticker === (pooled ? "POOLED" : asset));
  const cols: [string, number][] = [];
  for (const t of ["returns", "rv", "volume"]) for (const h of [1, 5, 20]) cols.push([t, h]);
  const models = [...new Set(rows.map((d) => d.model))].sort();
  if (!rows.length)
    return <p className="muted">Per-asset tests are stored for the common clean window with the expanding window only: switch Period and Window.</p>;
  return (
    <>
      <div className="tablewrap">
        <table className="matrix" data-testid="dm-matrix">
          <thead><tr><th>model</th>{cols.map(([t, h]) => <th key={`${t}${h}`}>{t} h={h}</th>)}</tr></thead>
          <tbody>
            {models.map((mo) => (
              <tr key={mo}>
                <td>{mo}</td>
                {cols.map(([t, h]) => {
                  const d = rows.find((x) => x.model === mo && x.target === t && x.horizon === h);
                  const mc = mcs.find((x) => x.model === mo && x.target === t && x.horizon === h);
                  if (!d) return <td key={`${t}${h}`} className="cell c-na">{mc ? (mc.in_mcs ? "ref ●" : "ref") : ""}</td>;
                  const tr: TipRow[] = [
                    { value: mo, label: `vs ${d.reference} · ${t} h=${h}` },
                    { value: d.rel_loss_lo !== null && d.rel_loss_lo !== undefined ? `${fmt(d.rel_loss)} [${fmt(d.rel_loss_lo)}, ${fmt(d.rel_loss_hi)}]` : fmt(d.rel_loss), label: "relative loss [95% CI]" },
                    { value: fmt(d.dm_stat, 2), label: "DM statistic" }, { value: fmtp(d.p_value), label: "p" }, { value: fmtp(d.p_holm), label: "Holm p" },
                    { value: mc ? fmtp(mc.mcs_pvalue) : "–", label: "MCS p" }, { value: String(d.T ?? "–"), label: "origins (T)" },
                  ];
                  if (d.flag) tr.push({ value: d.flag, label: "flags" });
                  return (
                    <td key={`${t}${h}`} tabIndex={0} className={`cell ${binClass(d.rel_loss)}`}
                      onPointerMove={(e) => tip.show(e.clientX, e.clientY, tr)} onPointerLeave={tip.hide}
                      onFocus={(e) => { const r = e.currentTarget.getBoundingClientRect(); tip.show(r.right, r.top, tr); }} onBlur={tip.hide}>
                      {fmt(d.rel_loss, 2)}{d.reject_holm ? " ★" : ""}{mc?.in_mcs ? " ●" : ""}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="scale">
        <span>model better&nbsp;</span>
        {["c-b3", "c-b2", "c-b1", "c-0", "c-r1", "c-r2", "c-r3"].map((c) => <span key={c} className={`sw ${c}`} />)}
        <span>&nbsp;model worse · bins at relative loss ≈ 0.86, 0.95, 0.98, 1.02, 1.05, 1.16 · ★ Holm-significant · ● in the MCS</span>
      </div>
    </>
  );
}
