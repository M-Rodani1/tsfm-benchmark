"""Economic evaluation (secondary, ILLUSTRATIVE ONLY; not a trading claim).

Volatility targeting on one asset (SPY in the default study). At each forecast origin t:

    sigma_hat = sqrt(252 * yhat_rv(t, H)) / 100       (annualised, decimal)
    w_t       = min(max_leverage, target_vol / sigma_hat)

The weight is held until the next origin; the rest is cash earning 0. A cost of
``cost_bps`` basis points per unit of turnover |w_t - w_{t-1}| is charged at rebalancing.
Because the GK target omits the overnight gap, every model under-estimates close-to-close
volatility by a similar factor, so realised volatility will sit above the target for all
of them (DECISIONS D-019); compare models with each other, not with the target.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def backtest(
    daily_r: pd.Series,
    forecasts: pd.DataFrame,
    *,
    target_vol: float,
    max_leverage: float,
    cost_bps: float,
) -> tuple[dict, pd.Series]:
    """Run one model. ``forecasts``: rows with asset_date and y_pred (rv, horizon H)."""
    f = forecasts.sort_values("asset_date").drop_duplicates("asset_date")
    simple = np.exp(daily_r / 100.0) - 1.0
    dates = daily_r.index
    port = pd.Series(np.nan, index=dates)
    prev_w = 0.0
    turnover = 0.0
    costs = 0.0
    weights = []
    for i, row in enumerate(f.itertuples(index=False)):
        start = dates.searchsorted(row.asset_date, side="right")
        end = dates.searchsorted(f["asset_date"].iloc[i + 1], side="right") if i + 1 < len(f) else start + 5
        if start >= len(dates):
            break
        sig = np.sqrt(252.0 * max(row.y_pred, 1e-12)) / 100.0
        w = float(min(max_leverage, target_vol / sig))
        seg = simple.iloc[start:end] * w
        c = cost_bps / 1e4 * abs(w - prev_w)
        if len(seg):
            seg.iloc[0] -= c
        port.iloc[start:end] = seg.to_numpy()
        turnover += abs(w - prev_w)
        costs += c
        prev_w = w
        weights.append(w)
    port = port.dropna()
    return summarise(port, turnover, costs, weights, target_vol), port


def summarise(port: pd.Series, turnover: float, costs: float, weights, target_vol: float) -> dict:
    if len(port) < 20:
        return {"n_days": len(port)}
    years = len(port) / 252.0
    ann_ret = float(port.mean() * 252)
    ann_vol = float(port.std(ddof=1) * np.sqrt(252))
    wealth = (1 + port).cumprod()
    dd = float((wealth / wealth.cummax() - 1).min())
    return {
        "n_days": int(len(port)),
        "start": str(port.index[0].date()),
        "end": str(port.index[-1].date()),
        "ann_return": ann_ret,
        "ann_vol": ann_vol,
        "sharpe": ann_ret / ann_vol if ann_vol > 0 else np.nan,
        "max_drawdown": dd,
        "avg_weight": float(np.mean(weights)) if weights else np.nan,
        "turnover_per_year": turnover / years,
        "cost_drag_per_year": costs / years,
        "vol_gap_vs_target": ann_vol - target_vol,
    }


def buy_and_hold(daily_r: pd.Series, start, end, target_vol: float) -> dict:
    simple = np.exp(daily_r / 100.0) - 1.0
    seg = simple[(simple.index > start) & (simple.index <= end)]
    return summarise(seg, 0.0, 0.0, [1.0], target_vol)
