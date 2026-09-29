// Shared by the Results charts: number formats and the diverging bins of the offline dashboard
// (reports/dashboard), so both views read identically. Line colours follow the data semantics of
// site/DESIGN.md (the selected model blue and dashed, others grey and dashed, reference graphite).
export const fmt = (x: number | null | undefined, d = 3) => (x === null || x === undefined || !Number.isFinite(x) ? "–" : Number(x).toFixed(d));
export const fmtp = (p: number | null | undefined) =>
  p === null || p === undefined || !Number.isFinite(p) ? "–" : p < 0.001 ? "<0.001" : Number(p).toFixed(3);
export const dayToDate = (d: number) => new Date(d * 86400000).toISOString().slice(0, 10);

/** Diverging bins of relative loss (log scale), identical to the dashboard. */
export function binClass(rel: number | null | undefined): string {
  if (rel === null || rel === undefined || !Number.isFinite(rel) || rel <= 0) return "c-na";
  const z = Math.log(rel);
  if (z <= -0.15) return "c-b3";
  if (z <= -0.05) return "c-b2";
  if (z <= -0.02) return "c-b1";
  if (z < 0.02) return "c-0";
  if (z < 0.05) return "c-r1";
  if (z < 0.15) return "c-r2";
  return "c-r3";
}

export interface RunPayload {
  run: string; source: string; config_hash: string; data_hash: string; git: string; created: string;
  synthetic: boolean; label: string; limitations_md: string;
  status: Record<string, { status: string; reason: string; release: string }>;
  primary: PrimaryRow[];
  dm: DmRow[];
  dm_asset: (DmRow & { ticker: string })[];
  mcs: { period: string; target: string; horizon: number; ticker: string; model: string; mcs_pvalue: number; in_mcs: boolean; mean_loss: number; T: number }[];
  contamination: ContamRow[];
  windows: { model: string; release_date: string; weights_date: string | null; effective_release: string; clean_start: string; common_clean_start: string }[];
  series: { keys: SeriesKey[]; data: { d: number[]; y: (number | null)[] }[] };
}
export interface PrimaryRow {
  model: string; target: string; horizon: number; reference: string; status: string; rel_loss?: number; rel_loss_lo?: number; rel_loss_hi?: number;
  dm_stat?: number; p_value?: number; p_holm?: number; reject_holm?: boolean; mean_diff?: number; T?: number; flag?: string;
  stride?: number; method?: string; sim_size_max?: number;
}
export interface DmRow {
  period: string; window: string; target: string; horizon: number; model: string; reference: string; loss: string; rel_loss: number;
  rel_loss_lo: number | null; rel_loss_hi: number | null; dm_stat: number; p_value: number; p_holm: number; reject_holm: boolean;
  mean_diff: number; T: number; flag: string | null;
}
export interface ContamRow {
  windows_of: string; model: string; role: string; target: string; horizon: number; status: string; delta: number | null;
  ci_lo: number | null; ci_hi: number | null; p_one_sided: number | null; p_holm: number | null; T_seen: number | null; T_clean: number | null;
}
export interface SeriesKey { target: string; horizon: number; window: string; model: string; reference: string; ticker: string }
