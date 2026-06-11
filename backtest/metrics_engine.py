"""
KRONOS V1-ALT — Metrics Engine for Backtesting

Computes comprehensive performance, risk, and trade metrics.
All parameters config-driven — zero inline literals.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("kronos.backtest.metrics")

_DEFAULT_METRICS_CONFIG = {
    "risk_free_rate": 0.0,
    "annualization_factor": 8760,  # hourly bars: 24 * 365
    "var_confidence": 0.95,
    "var_horizon": 1,
    "max_drawdown_window": 200,
}

# Cached config — loaded once per process
_CACHED_METRICS_CONFIG: Optional[Dict[str, Any]] = None


def _load_metrics_config() -> Dict[str, Any]:
    """Load metrics config from sovereign params (cached)."""
    global _CACHED_METRICS_CONFIG
    if _CACHED_METRICS_CONFIG is not None:
        return _CACHED_METRICS_CONFIG
    try:
        import os, sys
        _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _proj not in sys.path:
            sys.path.insert(0, _proj)
        from config.utils.sovereign_entrypoint import get_sovereign_config
        cfg = get_sovereign_config().get("backtest", {})
        _CACHED_METRICS_CONFIG = {
            "risk_free_rate": cfg.get("risk_free_rate", 0.0),
            "annualization_factor": cfg.get("annualization_factor", 8760),
            "var_confidence": cfg.get("var_confidence", 0.95),
            "var_horizon": 1,
            "max_drawdown_window": 200,
        }
    except Exception:
        _CACHED_METRICS_CONFIG = dict(_DEFAULT_METRICS_CONFIG)
    return _CACHED_METRICS_CONFIG


def compute_all_metrics(
    returns: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """
    Compute a comprehensive set of performance metrics from a return series.

    Parameters
    ----------
    returns : pd.Series
        Simple returns (not log returns).
    config : dict, optional
        Override metric computation parameters.

    Returns
    -------
    dict
        All computed metrics.
    """
    cfg = config or _load_metrics_config()
    rf = float(cfg.get("risk_free_rate", 0.0))
    ann = int(cfg.get("annualization_factor", 8760))
    var_conf = float(cfg.get("var_confidence", 0.95))

    r = returns.dropna()
    if len(r) < 10:
        return _empty_metrics()

    metrics = {}

    # ── Return Metrics ──
    total_return = float((1 + r).prod() - 1)
    n_bars = len(r)
    years = n_bars / ann
    cagr = float((1 + total_return) ** (1 / max(years, 1e-6)) - 1) if total_return > -1 else -1.0

    wins = r[r > 0]
    losses = r[r < 0]
    win_rate = len(wins) / max(len(r), 1)
    avg_win = float(wins.mean()) if len(wins) > 0 else 0.0
    avg_loss = float(losses.mean()) if len(losses) > 0 else 0.0
    profit_factor = float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 1e-12 else float("inf")
    expectancy = float(r.mean())

    metrics["total_return"] = total_return
    metrics["cagr"] = cagr
    metrics["profit_factor"] = profit_factor
    metrics["expectancy"] = expectancy
    metrics["win_rate"] = win_rate
    metrics["avg_win"] = avg_win
    metrics["avg_loss"] = avg_loss
    metrics["n_trades"] = n_bars
    metrics["years"] = years

    # ── Risk Metrics ──
    daily_vol = float(r.std())
    annual_vol = daily_vol * np.sqrt(ann)
    sharpe = float((r.mean() - rf / ann) / daily_vol * np.sqrt(ann)) if daily_vol > 0 else 0.0

    downside = r[r < 0]
    downside_vol = float(downside.std()) if len(downside) > 5 else 1e-12
    sortino = float((r.mean() - rf / ann) / downside_vol * np.sqrt(ann)) if downside_vol > 0 else 0.0

    cumulative = (1 + r).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = float(drawdown.min())
    calmar = float(cagr / abs(max_drawdown)) if abs(max_drawdown) > 1e-12 else 0.0

    # VaR and Expected Shortfall
    var = float(r.quantile(1 - var_conf))
    tail = r[r <= var]
    es = float(tail.mean()) if len(tail) > 0 else var

    metrics["annual_vol"] = annual_vol
    metrics["sharpe"] = sharpe
    metrics["sortino"] = sortino
    metrics["max_drawdown"] = max_drawdown
    metrics["calmar"] = calmar
    metrics["var"] = var
    metrics["expected_shortfall"] = es

    # ── Tail Risk Metrics ──
    skew = float(r.skew()) if len(r) > 10 else 0.0
    kurt = float(r.kurtosis()) if len(r) > 10 else 0.0
    tail_ratio = float(abs(r.quantile(0.95)) / abs(r.quantile(0.05))) if abs(r.quantile(0.05)) > 1e-12 else 0.0

    metrics["skewness"] = skew
    metrics["kurtosis"] = kurt
    metrics["tail_ratio"] = tail_ratio

    # ── Robustness Metrics ──
    # Rolling Sharpe stability (lower std = more stable)
    rolling_sharpe = (r.rolling(100, min_periods=50).mean() / (r.rolling(100, min_periods=50).std() + 1e-12)).dropna()
    metrics["sharpe_stability"] = float(rolling_sharpe.std()) if len(rolling_sharpe) > 10 else 0.0
    metrics["positive_months_pct"] = float((r > 0).mean())

    return metrics


def compute_trade_metrics(
    returns: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """
    Compute trade-level metrics by treating sign-crossings in returns as trade entries.

    Parameters
    ----------
    returns : pd.Series
        Simple returns.
    config : dict, optional
        Metric configuration (unused in round-trip detection, reserved for future).
    """
    r = returns.dropna()
    if len(r) < 20:
        return {"avg_trade_duration": 0.0, "n_round_trips": 0}

    # Simulate round-trip trades: enter when returns are positive, exit when negative
    in_trade = False
    durations = []
    pnls = []
    entry_bar = 0

    for i in range(len(r)):
        if not in_trade and r.iloc[i] > 0:
            in_trade = True
            entry_bar = i
        elif in_trade and r.iloc[i] < 0:
            in_trade = False
            durations.append(i - entry_bar)
            pnl = float(r.iloc[entry_bar:i + 1].sum())
            pnls.append(pnl)

    avg_duration = float(np.mean(durations)) if durations else 0.0
    n_round_trips = len(durations)
    win_trades = sum(1 for p in pnls if p > 0)
    win_rate_trades = win_trades / max(n_round_trips, 1)
    avg_pnl = float(np.mean(pnls)) if pnls else 0.0

    return {
        "avg_trade_duration": avg_duration,
        "n_round_trips": n_round_trips,
        "trade_win_rate": win_rate_trades,
        "avg_trade_pnl": avg_pnl,
    }


def _empty_metrics() -> Dict[str, float]:
    """Return empty metrics dict with zero values."""
    keys = [
        "total_return", "cagr", "profit_factor", "expectancy",
        "win_rate", "avg_win", "avg_loss", "n_trades", "years",
        "annual_vol", "sharpe", "sortino", "max_drawdown", "calmar",
        "var", "expected_shortfall", "skewness", "kurtosis", "tail_ratio",
        "sharpe_stability", "positive_months_pct",
    ]
    return {k: 0.0 for k in keys}
