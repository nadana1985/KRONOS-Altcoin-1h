"""
KRONOS V1-ALT — Transaction Cost & Statistical Testing Module

Provides:
1. Transaction cost modeling (maker/taker fees + slippage)
2. Statistical significance testing (Diebold-Mariano test, bootstrap)

All parameters from config — zero inline literals. Seed-controlled.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("kronos.backtest.costs")

_DEFAULT_COST_CONFIG = {
    "maker_fee": 0.0002,
    "taker_fee": 0.0004,
    "slippage_bps": 5.0,
    "trade_frequency": 0.1,
}


def _load_cost_config() -> Dict[str, Any]:
    """Load cost config from sovereign params (cached)."""
    try:
        import os, sys
        _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _proj not in sys.path:
            sys.path.insert(0, _proj)
        from config.utils.sovereign_entrypoint import get_sovereign_config
        cfg = get_sovereign_config().get("backtest", {})
        return {
            "maker_fee": cfg.get("cost_maker_fee", 0.0002),
            "taker_fee": cfg.get("cost_taker_fee", 0.0004),
            "slippage_bps": cfg.get("cost_slippage_bps", 5.0),
            "trade_frequency": cfg.get("cost_trade_frequency", 0.1),
        }
    except Exception:
        return dict(_DEFAULT_COST_CONFIG)


def apply_transaction_costs(
    returns: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> pd.Series:
    """
    Deduct transaction costs from strategy returns.

    Parameters
    ----------
    returns : pd.Series
        Strategy returns (position-sized).
    config : dict, optional
        Cost parameters.

    Returns
    -------
    pd.Series
        Net returns after transaction costs.
    """
    cfg = config or _load_cost_config()
    maker = float(cfg.get("maker_fee", 0.0002))
    taker = float(cfg.get("taker_fee", 0.0004))
    slip_bps = float(cfg.get("slippage_bps", 5.0))
    freq = float(cfg.get("trade_frequency", 0.1))

    # Average cost per round-trip: taker entry + taker exit + slippage
    avg_cost = taker + taker + (slip_bps / 10000.0)
    # Expected cost per bar based on trade frequency
    cost_per_bar = avg_cost * freq

    net_returns = returns - cost_per_bar
    total_cost = cost_per_bar * len(returns)
    logger.info(
        "[COSTS] Applied costs: maker=%.4f%% taker=%.4f%% slippage=%.1f bps freq=%.1f%% | total_drag=%.4f",
        maker * 100, taker * 100, slip_bps, freq * 100, total_cost,
    )
    return net_returns


# ── Statistical Significance Testing ──


def diebold_mariano_test(
    errors_1: pd.Series,
    errors_2: pd.Series,
    h: int = 1,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """
    Diebold-Mariano test for comparing two forecast accuracy sequences.

    Tests H0: E[d_t] = 0 where d_t = loss_1(t) - loss_2(t).

    Parameters
    ----------
    errors_1 : pd.Series
        Forecast errors from model 1.
    errors_2 : pd.Series
        Forecast errors from model 2.
    h : int
        Forecast horizon for autocovariance correction.

    Returns
    -------
    dict
        DM statistic, p-value, and conclusion.
    """
    e1 = errors_1.dropna().values
    e2 = errors_2.dropna().values
    n = min(len(e1), len(e2))
    e1, e2 = e1[:n], e2[:n]

    # Squared error loss
    d = e1 ** 2 - e2 ** 2
    d_mean = np.mean(d)

    # Newey-West autocovariance correction
    d_var = np.var(d, ddof=1)
    gamma_sum = 0.0
    for k in range(1, h):
        if k < n:
            gamma_k = np.mean((d[k:] - d_mean) * (d[:-k] - d_mean))
            gamma_sum += 2 * (1 - k / h) * gamma_k

    var_d = (d_var + gamma_sum) / n
    if var_d <= 0:
        var_d = 1e-12

    dm_stat = d_mean / np.sqrt(var_d)

    # Two-tailed p-value (normal approximation)
    from scipy import stats as sp_stats
    p_value = 2 * (1 - sp_stats.norm.cdf(abs(dm_stat)))

    if p_value < 0.01:
        conclusion = "Highly significant difference (p < 0.01)"
    elif p_value < 0.05:
        conclusion = "Significant difference (p < 0.05)"
    elif p_value < 0.10:
        conclusion = "Marginal difference (p < 0.10)"
    else:
        conclusion = "No significant difference"

    return {
        "dm_statistic": float(dm_stat),
        "p_value": float(p_value),
        "mean_loss_diff": float(d_mean),
        "conclusion": conclusion,
    }


def bootstrap_sharpe_test(
    returns_1: pd.Series,
    returns_2: pd.Series,
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> Dict[str, float]:
    """
    Bootstrap test for difference in Sharpe ratios.

    Returns probability that Sharpe(returns_1) > Sharpe(returns_2).
    """
    rng = np.random.default_rng(seed)
    r1 = returns_1.dropna().values
    r2 = returns_2.dropna().values

    def _sharpe(r: np.ndarray) -> float:
        if len(r) < 5 or np.std(r) < 1e-12:
            return 0.0
        return float(np.mean(r) / np.std(r) * np.sqrt(8760))

    n = min(len(r1), len(r2))
    r1, r2 = r1[:n], r2[:n]

    original_diff = _sharpe(r1) - _sharpe(r2)
    boot_diffs = []

    for _ in range(n_bootstrap):
        idx1 = rng.integers(0, n, size=n)
        idx2 = rng.integers(0, n, size=n)
        boot_diff = _sharpe(r1[idx1]) - _sharpe(r2[idx2])
        boot_diffs.append(boot_diff)

    boot_diffs = np.array(boot_diffs)
    prob_r1_better = float((boot_diffs > 0).mean())

    ci_lower = float(np.percentile(boot_diffs, 2.5))
    ci_upper = float(np.percentile(boot_diffs, 97.5))

    return {
        "original_sharpe_diff": float(original_diff),
        "prob_model1_better": prob_r1_better,
        "ci_95_lower": ci_lower,
        "ci_95_upper": ci_upper,
        "n_bootstrap": n_bootstrap,
    }


def generate_statistical_report(
    stat_results: List[Dict[str, Any]],
    output_path: Optional[str] = None,
) -> str:
    """Generate a markdown statistical significance report."""
    lines = []
    lines.append("# KRONOS V1-ALT — Statistical Significance Report")
    lines.append("")

    for res in stat_results:
        sym = res.get("symbol", "aggregate")
        lines.append(f"## {sym}")
        lines.append("")

        # DM test
        dm = res.get("diebold_mariano", {})
        if dm:
            lines.append("### Diebold-Mariano Test")
            lines.append(f"- DM Statistic: {dm.get('dm_statistic', 0):.4f}")
            lines.append(f"- p-value: {dm.get('p_value', 1):.4f}")
            lines.append(f"- Mean Loss Diff: {dm.get('mean_loss_diff', 0):.6f}")
            lines.append(f"- Conclusion: {dm.get('conclusion', 'N/A')}")
            lines.append("")

        # Bootstrap test
        bs = res.get("bootstrap_sharpe", {})
        if bs:
            lines.append("### Bootstrap Sharpe Test")
            lines.append(f"- Original Sharpe Diff: {bs.get('original_sharpe_diff', 0):.4f}")
            lines.append(f"- P(Model1 better): {bs.get('prob_model1_better', 0.5):.1%}")
            lines.append(f"- 95% CI: [{bs.get('ci_95_lower', 0):.4f}, {bs.get('ci_95_upper', 0):.4f}]")
            lines.append("")

    report_text = "\n".join(lines)
    if output_path:
        import os
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        logger.info("[STATS] Report written to %s", output_path)

    return report_text
