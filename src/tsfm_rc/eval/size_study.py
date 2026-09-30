"""Monte Carlo size study for DM-type tests on stride-1 origins (amendment A4, DECISIONS D-039).

Under H0 (E d_t = 0) we simulate T loss differentials of h-day targets whose origins are one
trading day apart (so consecutive targets overlap in h - 1 days) and record how often each
candidate test rejects at nominal 5%.

Data-generating processes (all mean zero):

- ``ar0``, ``ar0.3``, ``ar0.6``: d_t = sum_{j=1..h} u_{t+j}, u a Gaussian AR(1) with
  coefficient phi (the A2 design, now with stride 1; phi = 0.6 is a persistence stress case);
- ``garch_sq``: d_t = S1_t^2 - S2_t^2, S_i,t the h-day sums of two independent error series
  sharing one GARCH(1,1) volatility (omega = 0.05, alpha = 0.08, beta = 0.90): a squared-error
  differential with heavy tails and volatility clustering.

Candidate tests:

- ``rect``:  rectangular kernel, lag h - 1, HLN factor (k = h), t_{T-1} (A2's overlap rule);
             a non-positive variance falls back to Bartlett with the same lag (share reported);
- ``bartlett``: Bartlett kernel, lag max(h - 1, floor(4 (T/100)^(2/9))), HLN, t_{T-1};
- ``kv_b1``: Kiefer-Vogelsang fixed-b, Bartlett kernel with bandwidth T, exact fixed-b p-values;
- ``bartlett_fixedb``: the ``bartlett`` variance with fixed-b critical values for its own
  b = (L + 1)/T (simulated under i.i.d. Gaussian data at the same T), no HLN factor.

Everything is vectorised over replications and seeded, so a run is reproducible.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from tsfm_rc.eval.fixedb import kv_pvalue

DGPS = ("ar0", "ar0.3", "ar0.6", "garch_sq")

# Documented run (R = 5000, seed 20260928; DECISIONS D-039): the largest rejection rate of
# the chosen test (kv_b1) over the four DGPs at each (T, h). Nominal size 0.05.
# tests/test_stats.py re-simulates the grid and checks these values.
KV_SIM_MAX_SIZE = {
    (100, 1): 0.064, (100, 5): 0.068, (100, 20): 0.122,
    (250, 1): 0.056, (250, 5): 0.056, (250, 20): 0.079,
    (450, 1): 0.060, (450, 5): 0.058, (450, 20): 0.063,
}


def kv_simulated_size(T: int, h: int) -> float:
    """Worst simulated size of the kv_b1 test at the largest grid T <= ``T`` (conservative),
    for this h; NaN if T is below the simulated range (T < 100) or h is not on the grid."""
    grid_T = [t for t in sorted({t for t, _ in KV_SIM_MAX_SIZE}) if t <= T]
    if not grid_T or (grid_T[-1], h) not in KV_SIM_MAX_SIZE:
        return float("nan")
    return KV_SIM_MAX_SIZE[(grid_T[-1], h)]
TESTS = ("rect", "bartlett", "kv_b1", "bartlett_fixedb")
BURN = 200


def _acov(D: np.ndarray, L: int) -> np.ndarray:
    R, T = D.shape
    out = np.empty((R, L + 1))
    for k in range(L + 1):
        out[:, k] = np.einsum("ij,ij->i", D[:, k:], D[:, : T - k]) / T
    return out


def _lrv(D: np.ndarray, L: int, kernel: str) -> np.ndarray:
    g = _acov(D, L)
    if L == 0:
        return g[:, 0]
    k = np.arange(1, L + 1)
    w = 1.0 - k / (L + 1.0) if kernel == "bartlett" else np.ones(L)
    return g[:, 0] + 2.0 * (g[:, 1:] * w).sum(1)


def _kv_lrv(D: np.ndarray) -> np.ndarray:
    T = D.shape[1]
    S = np.cumsum(D, axis=1)
    return 2.0 * np.einsum("ij,ij->i", S, S) / T**2


def _nw(T: int) -> int:
    return int(math.floor(4.0 * (T / 100.0) ** (2.0 / 9.0)))


def _hln(T: int, k: int) -> float:
    return math.sqrt(max((T + 1 - 2 * k + k * (k - 1) / T) / T, 0.0))


def simulate(rng: np.random.Generator, R: int, T: int, h: int, dgp: str) -> np.ndarray:
    """(R, T) matrix of loss differentials under H0."""
    n = T + h + BURN
    if dgp.startswith("ar"):
        phi = float(dgp[2:])
        e = rng.standard_normal((R, n))
        u = np.empty_like(e)
        u[:, 0] = e[:, 0]
        for t in range(1, n):
            u[:, t] = phi * u[:, t - 1] + e[:, t]
        c = np.concatenate([np.zeros((R, 1)), np.cumsum(u[:, BURN:], axis=1)], axis=1)
        return c[:, h : h + T] - c[:, :T]
    if dgp == "garch_sq":
        om, a, b = 0.05, 0.08, 0.90
        s2 = np.full(R, om / (1.0 - a - b))
        z1, z2, zy = (rng.standard_normal((R, n)) for _ in range(3))
        e1 = np.empty((R, n))
        e2 = np.empty((R, n))
        y_prev = np.zeros(R)
        for t in range(n):
            if t:
                s2 = om + a * y_prev**2 + b * s2
            s = np.sqrt(s2)
            e1[:, t] = s * z1[:, t]
            e2[:, t] = s * z2[:, t]
            y_prev = s * zy[:, t]
        c1 = np.concatenate([np.zeros((R, 1)), np.cumsum(e1[:, BURN:], axis=1)], axis=1)
        c2 = np.concatenate([np.zeros((R, 1)), np.cumsum(e2[:, BURN:], axis=1)], axis=1)
        return (c1[:, h : h + T] - c1[:, :T]) ** 2 - (c2[:, h : h + T] - c2[:, :T]) ** 2
    raise ValueError(f"unknown DGP {dgp!r}")


def fixedb_critical_value(T: int, lag: int, alpha: float = 0.05, R: int = 40_000, seed: int = 20260928) -> float:
    """Two-sided fixed-b critical value for the Bartlett variance with this lag at this T,
    simulated under i.i.d. Gaussian data (the fixed-b reference distribution at finite T)."""
    rng = np.random.default_rng([seed, T, lag])
    vals = []
    chunk = 5_000
    for _ in range(max(1, R // chunk)):
        D = rng.standard_normal((chunk, T))
        dbar = D.mean(1)
        om = _lrv(D - dbar[:, None], lag, "bartlett")
        vals.append(np.abs(dbar / np.sqrt(om / T)))
    return float(np.quantile(np.concatenate(vals), 1.0 - alpha))


def rejection_rates(D: np.ndarray, h: int, alpha: float = 0.05) -> dict[str, float]:
    R, T = D.shape
    dbar = D.mean(1)
    Dc = D - dbar[:, None]
    out: dict[str, float] = {}
    # rect: rectangular lag h-1 (lag 0 at h = 1), Bartlett fallback when the estimate is <= 0
    om = _lrv(Dc, h - 1, "rectangular")
    bad = om <= 0
    if bad.any():
        om[bad] = _lrv(Dc[bad], h - 1, "bartlett")
    st = dbar / np.sqrt(om / T) * _hln(T, h)
    out["rect"] = float(np.mean(2 * stats.t.sf(np.abs(st), T - 1) < alpha))
    out["rect_nonpositive_share"] = float(bad.mean())
    # bartlett: lag max(h-1, NW)
    L2 = max(h - 1, _nw(T))
    om2 = _lrv(Dc, L2, "bartlett")
    st2 = dbar / np.sqrt(om2 / T) * _hln(T, h)
    out["bartlett"] = float(np.mean(2 * stats.t.sf(np.abs(st2), T - 1) < alpha))
    # kv_b1: bandwidth T, exact fixed-b p-values
    st3 = dbar / np.sqrt(_kv_lrv(Dc) / T)
    out["kv_b1"] = float(np.mean(np.array([kv_pvalue(s) for s in st3]) < alpha))
    # bartlett_fixedb: same variance as "bartlett", fixed-b critical value for b = (L2+1)/T
    out["bartlett_fixedb"] = float(np.mean(np.abs(dbar / np.sqrt(om2 / T)) > fixedb_critical_value(T, L2, alpha)))
    return out


def size_grid(
    R: int = 5_000,
    seed: int = 20260928,
    Ts: tuple[int, ...] = (100, 250, 450),
    hs: tuple[int, ...] = (1, 5, 20),
    dgps: tuple[str, ...] = DGPS,
) -> pd.DataFrame:
    rows = []
    for dgp in dgps:
        for T in Ts:
            for h in hs:
                rng = np.random.default_rng([seed, T, h, DGPS.index(dgp)])
                rows.append({"dgp": dgp, "T": T, "h": h, **rejection_rates(simulate(rng, R, T, h, dgp), h)})
    return pd.DataFrame(rows)


def summarise(grid: pd.DataFrame, nominal: float = 0.05) -> pd.DataFrame:
    """Selection criterion fixed before the final run: smallest worst-case |size - 5%| over
    the grid; ties broken by the mean absolute deviation."""
    rows = []
    for t in TESTS:
        dev = (grid[t] - nominal).abs()
        rows.append({"test": t, "max_abs_dev": float(dev.max()), "mean_abs_dev": float(dev.mean()),
                     "min_size": float(grid[t].min()), "max_size": float(grid[t].max())})
    return pd.DataFrame(rows).sort_values(["max_abs_dev", "mean_abs_dev"]).reset_index(drop=True)


if __name__ == "__main__":  # pragma: no cover - documentation run (DECISIONS D-039)
    import sys

    R = int(sys.argv[1]) if len(sys.argv) > 1 else 5_000
    g = size_grid(R=R)
    pd.set_option("display.width", 200)
    print(g.round(3).to_string(index=False))
    print(summarise(g).round(4).to_string(index=False))
