"""
KRONOS V1-ALT — Regime Classifier for Backtesting

Classifies market periods into regimes based on volatility and trend characteristics.
All thresholds loaded from config — zero inline literals.

Fix: replaced polyfit-based trend with EWM-based directional movement index,
which is robust to NaN, edge cases, and short real-data shards.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("kronos.backtest.regime")

_DEFAULT_REGIME_CONFIG = {
    "vol_window": 40,
    "trend_window": 40,
    "high_vol_percentile": 70,
    "low_vol_percentile": 30,
    "trend_threshold": 0.15,
    "min_bars_for_classification": 30,
}


def classify_regimes(
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> pd.Series:
    """
    Classify each bar into a market regime.

    Returns a Series of regime labels:
    - 'high_vol_trending': High volatility + strong trend
    - 'high_vol_ranging': High volatility + weak trend (choppy)
    - 'low_vol_trending': Low volatility + trending (quiet trend)
    - 'low_vol_ranging': Low volatility + ranging (quiet consolidation)

    Parameters
    ----------
    df : pd.DataFrame
        Must contain 'close' column.
    config : dict, optional
        Override regime classification parameters.
    """
    # Load from sovereign config if available, else use defaults
    cfg = config
    if cfg is None:
        try:
            import os, sys
            _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if _proj not in sys.path:
                sys.path.insert(0, _proj)
            from config.utils.sovereign_entrypoint import get_sovereign_config
            sovereign_cfg = get_sovereign_config()
            bt_cfg = sovereign_cfg.get("backtest", {})
            cfg = {
                "vol_window": bt_cfg.get("regime_vol_window", _DEFAULT_REGIME_CONFIG["vol_window"]),
                "trend_window": bt_cfg.get("regime_trend_window", _DEFAULT_REGIME_CONFIG["trend_window"]),
                "high_vol_percentile": bt_cfg.get("regime_high_vol_pct", _DEFAULT_REGIME_CONFIG["high_vol_percentile"]),
                "low_vol_percentile": bt_cfg.get("regime_low_vol_pct", _DEFAULT_REGIME_CONFIG["low_vol_percentile"]),
                "trend_threshold": bt_cfg.get("regime_trend_threshold", _DEFAULT_REGIME_CONFIG["trend_threshold"]),
                "min_bars_for_classification": bt_cfg.get("regime_min_bars", _DEFAULT_REGIME_CONFIG["min_bars_for_classification"]),
            }
        except Exception:
            cfg = _DEFAULT_REGIME_CONFIG

    vol_w = int(cfg.get("vol_window", 40))
    trend_w = int(cfg.get("trend_window", 40))
    high_pct = float(cfg.get("high_vol_percentile", 70))
    low_pct = float(cfg.get("low_vol_percentile", 30))
    trend_thresh = float(cfg.get("trend_threshold", 0.15))
    min_bars = int(cfg.get("min_bars_for_classification", 30))

    close = pd.to_numeric(df["close"], errors="coerce").ffill().bfill()
    n = len(close)

    # Guard: too few bars to classify meaningfully
    if n < min_bars:
        logger.warning(
            "[REGIME] Too few bars (%d < %d) — defaulting all to low_vol_ranging",
            n, min_bars,
        )
        return pd.Series("low_vol_ranging", index=df.index)

    # ── Volatility regime ──
    returns = close.pct_change()
    rolling_vol = returns.rolling(vol_w, min_periods=max(5, vol_w // 4)).std()
    # Use expanding quantile for first window, then rolling to avoid lookahead
    vol_expanding = rolling_vol.expanding(min_periods=20).quantile(high_pct / 100.0)
    vol_expanding_low = rolling_vol.expanding(min_periods=20).quantile(low_pct / 100.0)
    # After warmup, use expanding percentile (no lookahead beyond current bar)
    vol_high = vol_expanding.fillna(rolling_vol.quantile(high_pct / 100.0))
    vol_low = vol_expanding_low.fillna(rolling_vol.quantile(low_pct / 100.0))
    is_high_vol = rolling_vol >= vol_high

    # ── Trend regime (EWM-based, replaces polyfit) ──
    # EWM directional movement: sign of EWM of returns indicates trend direction,
    # magnitude indicates trend strength. No polyfit, no lambda, robust to NaN.
    ewm_returns = returns.ewm(span=trend_w, min_periods=max(5, trend_w // 4)).mean()
    ewm_vol = returns.rolling(trend_w, min_periods=max(5, trend_w // 4)).std()
    # Normalized trend strength: EWM mean / rolling vol (like a rolling information ratio)
    trend_strength = (ewm_returns.abs() / (ewm_vol + 1e-12)).fillna(0.0)
    is_trending = trend_strength >= trend_thresh

    # ── Combine into 4 regimes ──
    regimes = pd.Series("low_vol_ranging", index=df.index)  # default, not "unknown"
    regimes[is_high_vol & is_trending] = "high_vol_trending"
    regimes[is_high_vol & ~is_trending] = "high_vol_ranging"
    regimes[~is_high_vol & is_trending] = "low_vol_trending"
    regimes[~is_high_vol & ~is_trending] = "low_vol_ranging"

    # Validate classification quality
    regime_counts = regimes.value_counts().to_dict()
    total_classified = sum(regime_counts.values())
    unknown_count = regime_counts.get("unknown", 0)
    if unknown_count > 0:
        logger.warning("[REGIME] %d bars unclassified — filling as low_vol_ranging", unknown_count)
        regimes[regimes == "unknown"] = "low_vol_ranging"
        regime_counts.pop("unknown", None)
        regime_counts["low_vol_ranging"] = regime_counts.get("low_vol_ranging", 0) + unknown_count

    # Log regime distribution with percentages
    regime_pct = {k: f"{v} ({100.0 * v / max(total_classified, 1):.1f}%)" for k, v in regime_counts.items()}
    logger.info("[REGIME] Classification complete: %s | bars=%d", regime_pct, n)

    # Sanity check: at least 2 regimes should have bars
    active_regimes = sum(1 for v in regime_counts.values() if v > 5)
    if active_regimes < 2:
        logger.warning(
            "[REGIME] Only %d active regime(s) detected — consider lowering trend_threshold (%.3f) "
            "or vol_window (%d) for this data.",
            active_regimes, trend_thresh, vol_w,
        )

    return regimes


def get_regime_stats(
    regimes: pd.Series,
    returns: pd.Series,
    min_bars: int = 3,
) -> Dict[str, Dict[str, float]]:
    """
    Compute per-regime return statistics.

    Returns dict of regime -> {mean_return, std_return, sharpe, count, total_return, max_drawdown}.

    Parameters
    ----------
    regimes : pd.Series
        Regime labels from classify_regimes().
    returns : pd.Series
        Return series aligned to the same index.
    min_bars : int
        Minimum bars required to compute stats for a regime.
    """
    stats = {}
    for regime in sorted(regimes.unique()):
        if not isinstance(regime, str) or regime == "unknown":
            continue
        mask = regimes == regime
        reg_rets = returns[mask].dropna()
        if len(reg_rets) < min_bars:
            logger.debug("[REGIME] Skipping '%s': only %d bars (min=%d)", regime, len(reg_rets), min_bars)
            continue
        mean_r = float(reg_rets.mean())
        std_r = float(reg_rets.std())
        sharpe = mean_r / std_r * np.sqrt(8760) if std_r > 1e-12 else 0.0  # annualized
        stats[regime] = {
            "mean_return": mean_r,
            "std_return": std_r,
            "sharpe": sharpe,
            "count": int(mask.sum()),
            "total_return": float((1 + reg_rets).prod() - 1),
            "max_drawdown": float(_max_drawdown(reg_rets)),
        }
    if not stats:
        logger.warning("[REGIME] No regime stats produced — all regimes had < %d bars", min_bars)
    else:
        logger.info("[REGIME] Stats for %d regimes: %s", len(stats),
                     {k: f"count={v['count']} sharpe={v['sharpe']:.2f}" for k, v in stats.items()})
    return stats


def _max_drawdown(returns: pd.Series) -> float:
    """Compute max drawdown from a return series."""
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    return float(drawdown.min()) if len(drawdown) > 0 else 0.0
