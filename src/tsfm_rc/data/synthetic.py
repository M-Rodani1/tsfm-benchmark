"""Synthetic OHLCV with known dynamics (fixtures, tests and the synthetic control).

Each simulated trading day has a latent variance ``sigma2_t`` (in %^2). The log price
(in percent units, p = 100 ln P) follows a Brownian motion with drift ``mu`` and
variance ``sigma2_t`` over the day, discretised into ``steps`` intraday increments.
Open = previous close (no overnight gap), high/low = extremes of the path, close = end.
So the Garman-Klass estimator is (nearly) unbiased for ``sigma2_t`` by construction,
up to the small downward bias from discrete monitoring (see :func:`gk_discretisation_factor`).

Variance processes
------------------
- GARCH(1,1):  sigma2_{t+1} = omega + alpha (r_t - mu)^2 + beta sigma2_t
- HAR-MEM:     sigma2_t = [c + b_d s_{t-1} + b_w mean(s_{t-5..t-1}) + b_m mean(s_{t-22..t-1})] * eps_t,
               eps_t lognormal with mean 1 (a multiplicative-error HAR in levels)

Log volume:  ln V_t = level + dow[d(t)] + a_t + b_t + e_t with two AR(1) components
(fast and slow) and iid noise. Volume is independent of volatility in these fixtures.

Oracle forecasts (true conditional expectations given the latent state) are provided
for the synthetic control experiment.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

from tsfm_rc.hashing import sha256_file

# ----------------------------------------------------------------- parameter specs


@dataclass(frozen=True)
class GarchSpec:
    omega: float
    alpha: float
    beta: float
    mu: float = 0.03  # daily drift in % log units

    @property
    def persistence(self) -> float:
        return self.alpha + self.beta

    @property
    def uncond_var(self) -> float:
        return self.omega / (1.0 - self.persistence)


@dataclass(frozen=True)
class HarSpec:
    c: float
    b_d: float
    b_w: float
    b_m: float
    shock_sd: float = 0.5
    mu: float = 0.03

    @property
    def persistence(self) -> float:
        return self.b_d + self.b_w + self.b_m

    @property
    def uncond_var(self) -> float:
        return self.c / (1.0 - self.persistence)


@dataclass(frozen=True)
class VolumeSpec:
    level: float = 15.4  # ~ ln(5 million shares)
    phi_fast: float = 0.6
    phi_slow: float = 0.98
    sd_fast: float = 0.20
    sd_slow: float = 0.03
    sd_noise: float = 0.15
    dow: tuple[float, float, float, float, float] = (0.04, 0.0, -0.01, 0.0, 0.05)


# -------------------------------------------------------------------- calendar


def trading_calendar(start: str | pd.Timestamp, end: str | pd.Timestamp) -> pd.DatetimeIndex:
    """Business days minus US federal holidays (an approximation of the NYSE calendar)."""
    hol = USFederalHolidayCalendar().holidays(start=start, end=end)
    days = pd.bdate_range(start, end)
    return days.difference(hol)


# ------------------------------------------------------------------- simulators


def _intraday_ohlc(p_prev_close: float, mu: float, sigma: np.ndarray, Z: np.ndarray, steps: int) -> tuple[np.ndarray, ...]:
    """Vectorised OHLC in percent-log units from standard normal increments Z (n, steps)."""
    n = len(sigma)
    drift = mu / steps * np.arange(1, steps + 1)
    rel = drift[None, :] + (sigma[:, None] / np.sqrt(steps)) * np.cumsum(Z, axis=1)  # path relative to open
    day_ret = rel[:, -1]
    closes = p_prev_close + np.cumsum(day_ret)
    opens = np.concatenate([[p_prev_close], closes[:-1]])
    # max/min with open and close guard against 1e-13 rounding differences between
    # `open + extreme` and the cumulatively summed close
    highs = np.maximum.reduce([opens + rel.max(axis=1), opens, closes])
    lows = np.minimum.reduce([opens + rel.min(axis=1), opens, closes])
    assert len(opens) == n
    return opens, highs, lows, closes, day_ret


def simulate_garch(spec: GarchSpec, n: int, rng: np.random.Generator, steps: int = 390, burn: int = 500) -> pd.DataFrame:
    """Simulate n days. Columns (percent-log prices) plus latent sigma2 and sigma2_next."""
    total = n + burn
    Z = rng.standard_normal((total, steps))
    z_day = Z.sum(axis=1) / np.sqrt(steps)
    s2 = np.empty(total + 1)
    s2[0] = spec.uncond_var
    for t in range(total):
        eps = np.sqrt(s2[t]) * z_day[t]
        s2[t + 1] = spec.omega + spec.alpha * eps**2 + spec.beta * s2[t]
    sigma2 = s2[burn:total]
    o, h, lo, c, r = _intraday_ohlc(100 * np.log(100.0), spec.mu, np.sqrt(sigma2), Z[burn:], steps)
    return pd.DataFrame(
        {"p_open": o, "p_high": h, "p_low": lo, "p_close": c, "r_true": r,
         "sigma2": sigma2, "sigma2_next": s2[burn + 1 : total + 1]}
    )


def simulate_har(spec: HarSpec, n: int, rng: np.random.Generator, steps: int = 390, burn: int = 500) -> pd.DataFrame:
    total = n + burn
    eta = rng.standard_normal(total)
    eps = np.exp(spec.shock_sd * eta - 0.5 * spec.shock_sd**2)  # mean one
    s2 = np.full(total, spec.uncond_var)
    pred = np.full(total + 1, spec.uncond_var)
    for t in range(22, total):
        pred[t] = _har_step(spec, s2[:t])
        s2[t] = pred[t] * eps[t]
    pred[total] = _har_step(spec, s2)
    Z = rng.standard_normal((n, steps))
    sigma2 = s2[burn:]
    o, h, lo, c, r = _intraday_ohlc(100 * np.log(100.0), spec.mu, np.sqrt(sigma2), Z, steps)
    return pd.DataFrame(
        {"p_open": o, "p_high": h, "p_low": lo, "p_close": c, "r_true": r,
         "sigma2": sigma2, "sigma2_next": pred[burn + 1 : total + 1]}
    )


def _har_step(spec: HarSpec, past: np.ndarray) -> float:
    return spec.c + spec.b_d * past[-1] + spec.b_w * past[-5:].mean() + spec.b_m * past[-22:].mean()


def simulate_volume(spec: VolumeSpec, dates: pd.DatetimeIndex, rng: np.random.Generator, burn: int = 500) -> pd.DataFrame:
    n = len(dates)
    total = n + burn
    ef, es, en = (rng.standard_normal(total) for _ in range(3))
    a = np.zeros(total)
    b = np.zeros(total)
    for t in range(1, total):
        a[t] = spec.phi_fast * a[t - 1] + spec.sd_fast * ef[t]
        b[t] = spec.phi_slow * b[t - 1] + spec.sd_slow * es[t]
    dow = np.asarray(spec.dow)[dates.dayofweek.to_numpy()]
    logv = spec.level + dow + a[burn:] + b[burn:] + spec.sd_noise * en[burn:]
    return pd.DataFrame({"logvol_true": logv, "vol_fast": a[burn:], "vol_slow": b[burn:]}, index=dates)


def simulate_asset(
    variance_spec: GarchSpec | HarSpec,
    volume_spec: VolumeSpec,
    dates: pd.DatetimeIndex,
    rng: np.random.Generator,
    steps: int = 390,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (ohlcv, latent) frames indexed by ``dates``."""
    n = len(dates)
    sim = simulate_garch(variance_spec, n, rng, steps) if isinstance(variance_spec, GarchSpec) else simulate_har(variance_spec, n, rng, steps)
    vol = simulate_volume(volume_spec, dates, rng)
    px = np.exp(sim[["p_open", "p_high", "p_low", "p_close"]].to_numpy() / 100.0)
    ohlcv = pd.DataFrame(
        {
            "open": px[:, 0], "high": px[:, 1], "low": px[:, 2], "close": px[:, 3],
            "adj_close": px[:, 3],
            "volume": np.round(np.exp(vol["logvol_true"].to_numpy())),
            "dividends": 0.0, "splits": 0.0,
        },
        index=dates,
    )
    latent = pd.DataFrame(
        {"sigma2": sim["sigma2"].to_numpy(), "sigma2_next": sim["sigma2_next"].to_numpy(),
         "vol_fast": vol["vol_fast"].to_numpy(), "vol_slow": vol["vol_slow"].to_numpy()},
        index=dates,
    )
    ohlcv.index.name = latent.index.name = "date"
    return ohlcv, latent


# ------------------------------------------------------------------- oracle


def garch_expected_variance(spec: GarchSpec, sigma2_next: np.ndarray, steps: int) -> np.ndarray:
    """E_t[sigma2_{t+i}], i = 1..steps, given sigma2_{t+1} (known at t). Shape (..., steps)."""
    i = np.arange(steps)
    s = np.asarray(sigma2_next, dtype=float)[..., None]
    return spec.uncond_var + spec.persistence**i * (s - spec.uncond_var)


def har_expected_variance(spec: HarSpec, past_sigma2: np.ndarray, steps: int) -> np.ndarray:
    """E_t[sigma2_{t+i}], i = 1..steps, iterating the linear HAR recursion (E[eps] = 1)."""
    buf = list(np.asarray(past_sigma2, dtype=float)[-22:])
    out = []
    for _ in range(steps):
        nxt = _har_step(spec, np.asarray(buf))
        out.append(nxt)
        buf.append(nxt)
    return np.asarray(out)


def volume_expected_logvol(spec: VolumeSpec, a_t: float, b_t: float, future_dates: pd.DatetimeIndex) -> np.ndarray:
    i = np.arange(1, len(future_dates) + 1)
    dow = np.asarray(spec.dow)[future_dates.dayofweek.to_numpy()]
    return spec.level + dow + spec.phi_fast**i * a_t + spec.phi_slow**i * b_t


@lru_cache(maxsize=16)
def gk_discretisation_factor(steps: int, n_paths: int = 200_000, seed: int = 12345) -> float:
    """E[GK] / sigma^2 for a driftless Brownian path observed at ``steps`` points.

    Discrete monitoring misses the true extremes, so GK is biased slightly low
    (factor < 1, approaching 1 as steps grows). Estimated by Monte Carlo with a fixed seed.
    """
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n_paths // 20_000):
        Z = rng.standard_normal((20_000, steps)) / np.sqrt(steps)
        path = np.cumsum(Z, axis=1)
        hi = np.maximum(path.max(axis=1), 0.0)
        lo = np.minimum(path.min(axis=1), 0.0)
        c = path[:, -1]
        out.append(0.5 * (hi - lo) ** 2 - (2 * np.log(2) - 1) * c**2)
    return float(np.mean(np.concatenate(out)))


# ------------------------------------------------------------------- fixtures

FIXTURE_START = "2010-01-04"
FIXTURE_END = "2026-06-30"
FIXTURE_SEED = 20260927

FIXTURE_SPECS: dict[str, tuple[GarchSpec | HarSpec, VolumeSpec]] = {
    "SYN_GARCH_A": (GarchSpec(0.02, 0.08, 0.90, mu=0.04), VolumeSpec(level=17.5)),
    "SYN_GARCH_B": (GarchSpec(0.06, 0.05, 0.93, mu=0.05), VolumeSpec(level=16.2, phi_fast=0.5)),
    "SYN_HAR_A": (HarSpec(0.10, 0.35, 0.35, 0.20, shock_sd=0.5, mu=0.03), VolumeSpec(level=15.8)),
    "SYN_HAR_B": (HarSpec(0.24, 0.25, 0.40, 0.27, shock_sd=0.6, mu=0.02), VolumeSpec(level=15.1, phi_slow=0.99)),
    "SYN_QUIRKS": (GarchSpec(0.03, 0.10, 0.87, mu=0.03), VolumeSpec(level=14.9)),
}


def ex_dividend_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """First trading day on/after the 15th of March, June, September and December."""
    cand = index[index.month.isin([3, 6, 9, 12]) & (index.day >= 15)]
    firsts = pd.Series(cand, index=cand).groupby([cand.year, cand.month]).min()
    return pd.DatetimeIndex(firsts.to_numpy())


def _add_dividends(ohlcv: pd.DataFrame, yield_q: float = 0.005) -> pd.DataFrame:
    """Quarterly dividends worth ``yield_q`` of the previous close.

    On each ex-date all prices from that day on are scaled by (1 - yield_q): the price
    gaps down overnight by the dividend, intraday ratios (and hence GK) are unchanged.
    ``adj_close`` is back-adjusted, so returns computed from it equal the simulated
    total returns, while returns from the raw close show the dividend drops.
    """
    df = ohlcv.copy()
    factor = pd.Series(1.0, index=df.index)
    for d in ex_dividend_dates(df.index):
        pos = df.index.get_loc(d)
        if pos == 0:
            continue
        df.loc[d, "dividends"] = yield_q * df["close"].iloc[pos - 1]
        df.loc[d:, ["open", "high", "low", "close"]] *= 1.0 - yield_q
        factor.iloc[:pos] *= 1.0 - yield_q
    df["adj_close"] = df["close"] * factor
    return df


def _inject_quirks(ohlcv: pd.DataFrame) -> pd.DataFrame:
    """Deterministic data problems so that every cleaning rule is exercised."""
    df = ohlcv.copy()
    idx = df.index
    # a large genuine move (flagged as suspect split, not altered): -40% on one day
    d_crash = idx[1500]
    ratio = 0.6
    df.loc[d_crash:, ["open", "high", "low", "close", "adj_close"]] *= ratio
    df.loc[d_crash, "open"] = df["close"].iloc[1499]  # open at previous close, fall intraday
    df.loc[d_crash, "high"] = max(df.loc[d_crash, "open"], df.loc[d_crash, "close"])
    # zero volume on a trading day (row kept, volume -> NaN)
    df.loc[idx[800], "volume"] = 0.0
    # OHLC violation: high below close
    df.loc[idx[900], "high"] = df.loc[idx[900], "close"] * 0.999
    # stale row: holiday-like row with zero volume and flat price
    p = df.loc[idx[1000], "close"]
    df.loc[idx[1000], ["open", "high", "low", "close", "adj_close"]] = p
    df.loc[idx[1000], "volume"] = 0.0
    # missing day
    df = df.drop(idx[1200])
    # duplicate date (an earlier bad copy followed by the correct row)
    dup = df.loc[[idx[1300]]].copy()
    dup["close"] *= 1.5
    df = pd.concat([df.loc[: idx[1299]], dup, df.loc[idx[1300] :]])
    # weekend row
    sat = idx[1400] + pd.offsets.Week(weekday=5)
    wk = df.loc[[idx[1400]]].copy()
    wk.index = pd.DatetimeIndex([sat])
    df = pd.concat([df, wk]).sort_index(kind="stable")
    df.index.name = "date"
    return df


def make_fixture_panel(seed: int = FIXTURE_SEED, steps: int = 390) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Long-format (ohlcv, latent) frames for all fixture tickers."""
    dates = trading_calendar(FIXTURE_START, FIXTURE_END)
    ohlcv_parts, latent_parts = [], []
    for k, (ticker, (vspec, volspec)) in enumerate(FIXTURE_SPECS.items()):
        rng = np.random.default_rng([seed, k])
        ohlcv, latent = simulate_asset(vspec, volspec, dates, rng, steps)
        if ticker == "SYN_QUIRKS":
            ohlcv = _inject_quirks(_add_dividends(ohlcv))
        ohlcv_parts.append(ohlcv.assign(ticker=ticker).reset_index())
        latent_parts.append(latent.assign(ticker=ticker).reset_index())
    cols = ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume", "dividends", "splits"]
    ohlcv_long = pd.concat(ohlcv_parts, ignore_index=True)[cols]
    latent_long = pd.concat(latent_parts, ignore_index=True)[["date", "ticker", "sigma2", "sigma2_next", "vol_fast", "vol_slow"]]
    return ohlcv_long, latent_long


def write_fixtures(directory: str | Path, seed: int = FIXTURE_SEED) -> dict:
    """Write fixture CSVs and a manifest with SHA-256 hashes and generating parameters."""
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    ohlcv, latent = make_fixture_panel(seed)
    ohlcv.to_csv(d / "synthetic_ohlcv.csv", index=False, float_format="%.6f", date_format="%Y-%m-%d", lineterminator="\n")
    latent.to_csv(d / "synthetic_latent.csv", index=False, float_format="%.8f", date_format="%Y-%m-%d", lineterminator="\n")
    manifest = {
        "generator": "tsfm_rc.data.synthetic.make_fixture_panel",
        "seed": seed,
        "start": FIXTURE_START,
        "end": FIXTURE_END,
        "intraday_steps": 390,
        "specs": {t: {"variance": {"type": type(v).__name__, **asdict(v)}, "volume": asdict(vol)} for t, (v, vol) in FIXTURE_SPECS.items()},
        "files": {
            "synthetic_ohlcv.csv": sha256_file(d / "synthetic_ohlcv.csv"),
            "synthetic_latent.csv": sha256_file(d / "synthetic_latent.csv"),
        },
        "note": "SYNTHETIC DATA. Not market data. SYN_QUIRKS has deliberate data errors and dividends.",
    }
    with open(d / "MANIFEST.json", "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, default=list)
    return manifest
