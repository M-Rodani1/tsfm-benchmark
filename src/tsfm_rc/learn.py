"""Stored results for the lessons, identical on your machine and on the website.

The lessons read the study's stored statistics tables. Two places hold the same numbers:

- ``results/<run>/stats/<table>.parquet``: written by the pipeline (``make smoke``);
- ``site/public/data/results/<run>/<version>/tables/<table>.json``: exported from those
  Parquet files by ``make publish-results`` (tests/test_publish.py checks they are equal).

On your machine the Parquet file is used when it exists. In the browser (Pyodide: no
``pyarrow``, no ``results/`` folder) the website mounts the published JSON at the same
relative path under ``TSFM_RC_ROOT``, and the JSON is used. No statistic is ever recomputed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tsfm_rc.paths import RESULTS_DIR, ROOT

PUBLISHED_DIR = ROOT / "site" / "public" / "data" / "results"


def published_index() -> dict:
    p = PUBLISHED_DIR / "index.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"runs": []}


def _published_entry(run: str) -> dict:
    for r in published_index().get("runs", []):
        if r["run"] == run:
            return r
    raise FileNotFoundError(f"run '{run}' is neither in results/ nor published in {PUBLISHED_DIR} (run `make smoke`)")


def _parquet_available() -> bool:
    try:
        import pyarrow  # noqa: F401
    except ImportError:
        return False
    return True


def stats_table(run: str, table: str) -> pd.DataFrame:
    """One stored statistics table, e.g. ``stats_table("smoke", "dm_all")``."""
    pq = RESULTS_DIR / run / "stats" / f"{table}.parquet"
    if pq.exists() and _parquet_available():
        return pd.read_parquet(pq)
    entry = _published_entry(run)
    rel = entry["tables"].get(table)
    if rel is None:
        raise FileNotFoundError(f"table '{table}' is not published for run '{run}'")
    return pd.read_json(PUBLISHED_DIR / rel, orient="table", precise_float=True)


def report_text(run: str) -> str:
    """The run's generated report (``reports/<run>/RESULTS.md``), or its published copy."""
    local = ROOT / "reports" / run / "RESULTS.md"
    if local.exists():
        return local.read_text(encoding="utf-8")
    entry = _published_entry(run)
    return Path(PUBLISHED_DIR / entry["report"]).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------------------------
# Figures for "predict, then check" questions (the website draws them; `make lessons` writes
# site/content/lessons/<lesson>/figures/<name>.json, and tests keep the files in sync).

def _qlike(real_var, f_var) -> float:
    import numpy as np

    x = np.asarray(real_var) / np.asarray(f_var)
    return float(np.mean(x - np.log(x) - 1))


def _shock_events(vol, before: int, after: int, paths) -> list[tuple[int, float, list[float]]]:
    """Calm-then-shock days of one latent volatility series, found without looking ahead.

    A day qualifies if the preceding ``before`` days are calm (max/median <= 1.35) and its
    volatility is at least 1.3x that median. After an event the next ``after`` days are
    skipped (the first event wins). Nothing after the shock day enters the selection.
    Returns (day, calm median, QLIKE of each option's path against what happened).
    """
    import numpy as np

    events = []
    last = -(10**9)
    for t in range(before, len(vol) - after):
        base = float(np.median(vol[t - before:t]))
        if vol[t - before:t].max() / base > 1.35 or vol[t] / base < 1.3 or t - last <= after:
            continue
        last = t
        real = vol[t + 1:t + 1 + after] ** 2
        events.append((t, base, [_qlike(real, p**2) for p in paths(vol[t], base)]))
    return events


def volatility_shock_figure(ticker: str = "SYN_GARCH_B", before: int = 60, after: int = 40) -> dict:
    """A calm stretch, a volatility shock, and what the true volatility did next.

    Uses the committed fixtures' *latent* daily variance (known because the series are
    simulated), so "what happened" is the truth, not a noisy proxy.

    The three answer options are candidate paths after a shock: snap back to the calm level
    within two days; the slow fade a GARCH(1,1) with the series' own parameters expects; keep
    climbing. For every calm-then-shock event (``_shock_events``) the closest option is the one
    with the lowest QLIKE against what happened (the study's loss for volatility). The question
    asks what is *most likely*, so its answer is the option closest most often, pooled over the
    events of every GARCH series in the fixtures. The figure shows the most recent event of
    ``ticker``, and the result reports the tally (pooled and per series) and which option this
    example ended nearest to.

    Honesty note (BUILD-REPORT §12.4). Two earlier versions of this rule were wrong:
    - the first scored with log-MSE on SYN_GARCH_A and showed the largest jump; "snap back"
      won there, and the series and loss were changed after seeing that;
    - the second also required "no larger shock in the next 40 days". That condition looks at
      the future and selects calm aftermaths, so it biased the tally towards "snap back" (on
      SYN_QUIRKS 16 of 18).
    This version never looks past the shock day to select an event, and it pools every GARCH
    series, so no choice of series decides the answer. SYN_GARCH_B is still the series shown.
    """
    import numpy as np

    from tsfm_rc.data.synthetic import FIXTURE_SPECS, GarchSpec
    from tsfm_rc.paths import FIXTURE_DIR

    lat = pd.read_csv(FIXTURE_DIR / "synthetic_latent.csv", parse_dates=["date"])
    k = np.arange(1, after + 1)

    def series(name: str):
        s = lat[lat["ticker"] == name].reset_index(drop=True)
        spec = FIXTURE_SPECS[name][0]
        phi = spec.alpha + spec.beta
        longrun = float(np.sqrt(spec.omega / (1.0 - phi)))

        def paths(shock: float, base: float) -> list:
            return [np.where(k <= 2, shock + (base - shock) * k / 2, base),  # snap back within two days
                    np.sqrt(longrun**2 + phi**k * (shock**2 - longrun**2)),  # the GARCH-expected slow fade
                    shock * (1 + 0.5 * k / after)]  # keeps climbing, to 1.5x the shock

        return s, np.sqrt(s["sigma2"].to_numpy()), paths, phi, longrun

    by_series = {}
    for name, (spec, _) in FIXTURE_SPECS.items():
        if isinstance(spec, GarchSpec):
            _, vol, paths, _, _ = series(name)
            closest = [int(np.argmin(e[2])) for e in _shock_events(vol, before, after, paths)]
            by_series[name] = {"n": len(closest), "closest_by_option": [closest.count(i) for i in range(3)]}
    tally = [sum(v["closest_by_option"][i] for v in by_series.values()) for i in range(3)]
    s, vol, paths, phi, longrun = series(ticker)
    events = _shock_events(vol, before, after, paths)
    assert events, f"no calm-then-shock event in {ticker}"
    t, base, losses = events[-1]  # the most recent event of the series shown
    r = lambda a: [round(float(x), 4) for x in a]  # noqa: E731
    return {
        "generated_by": "tsfm_rc.learn.volatility_shock_figure (make lessons)",
        "series": ticker, "shock_date": str(s["date"][t].date()),
        "unit": "% per day", "measure": "true daily volatility of a simulated series",
        "observed": r(vol[t - before:t + 1]),
        "options": [r(p) for p in paths(vol[t], base)],
        "realised": r(vol[t + 1:t + 1 + after]),
        "answer": int(np.argmax(tally)), "example_closest": int(np.argmin(losses)),
        "qlike_by_option": [round(x, 5) for x in losses],
        "similar_shocks": {"n": sum(tally), "closest_by_option": tally, "series": by_series},
        "levels": {"calm_median": round(base, 3), "shock": round(float(vol[t]), 3), "long_run": round(longrun, 3),
                   "persistence": round(phi, 3)},
    }


PREDICT_FIGURES = {("02-volatility", "vol-clusters"): volatility_shock_figure}


def write_predict_figures(root: Path | None = None) -> list[Path]:
    root = root or ROOT / "site" / "content" / "lessons"
    out = []
    for (lesson, name), fn in PREDICT_FIGURES.items():
        p = root / lesson / "figures" / f"{name}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(fn(), indent=1) + "\n", encoding="utf-8")
        out.append(p)
    return out
