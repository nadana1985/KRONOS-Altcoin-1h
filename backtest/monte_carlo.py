"""
KRONOS V1-ALT — Monte Carlo Robustness Simulation

Generates synthetic return path permutations to evaluate performance
robustness against overfitting. Produces distribution of Sharpe ratios,
max drawdowns, and total returns across N simulations.

All parameters from config — zero inline literals. Seed-controlled.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("kronos.backtest.monte_carlo")

_DEFAULT_MC_CONFIG = {
    "n_simulations": 1000,
    "block_size": 20,
    "confidence_level": 0.95,
}


def _load_mc_config() -> Dict[str, Any]:
    """Load Monte Carlo config from sovereign params (cached)."""
    try:
        import os, sys
        _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _proj not in sys.path:
            sys.path.insert(0, _proj)
        from config.utils.sovereign_entrypoint import get_sovereign_config
        cfg = get_sovereign_config().get("backtest", {})
        return {
            "n_simulations": cfg.get("mc_n_simulations", 1000),
            "block_size": cfg.get("mc_block_size", 20),
            "confidence_level": cfg.get("mc_confidence_level", 0.95),
        }
    except Exception:
        return dict(_DEFAULT_MC_CONFIG)


def block_bootstrap_returns(
    returns: pd.Series,
    n_simulations: int = 1000,
    block_size: int = 20,
    seed: int = 42,
) -> np.ndarray:
    """
    Generate block-bootstrapped return paths.

    Preserves short-term autocorrelation by resampling blocks of returns.

    Returns array of shape (n_simulations, len(returns)).
    """
    rng = np.random.default_rng(seed)
    r = returns.dropna().values
    n = len(r)
    if n < block_size * 2:
        # Fallback: simple iid bootstrap
        return np.array([rng.choice(r, size=n, replace=True) for _ in range(n_simulations)])

    n_blocks = int(np.ceil(n / block_size))
    results = np.zeros((n_simulations, n))

    for sim in range(n_simulations):
        blocks = []
        for _ in range(n_blocks):
            start = rng.integers(0, n - block_size + 1)
            blocks.append(r[start:start + block_size])
        sim_path = np.concatenate(blocks)[:n]
        results[sim] = sim_path

    return results


def run_monte_carlo(
    returns: pd.Series,
    seed: int = 42,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run Monte Carlo robustness simulation on a return series.

    Returns distribution statistics for key metrics across simulations.
    """
    from backtest.metrics_engine import compute_all_metrics

    cfg = config or _load_mc_config()
    n_sim = int(cfg.get("n_simulations", 1000))
    block_sz = int(cfg.get("block_size", 20))
    conf = float(cfg.get("confidence_level", 0.95))

    # Generate bootstrap paths
    sim_returns = block_bootstrap_returns(returns, n_sim, block_sz, seed)

    # Compute metrics for each simulation
    sim_sharpes = []
    sim_returns_total = []
    sim_max_dds = []
    sim_sortinos = []

    for i in range(n_sim):
        sim_series = pd.Series(sim_returns[i])
        m = compute_all_metrics(sim_series)
        sim_sharpes.append(m.get("sharpe", 0.0))
        sim_returns_total.append(m.get("total_return", 0.0))
        sim_max_dds.append(m.get("max_drawdown", 0.0))
        sim_sortinos.append(m.get("sortino", 0.0))

    sim_sharpes = np.array(sim_sharpes)
    sim_returns_total = np.array(sim_returns_total)
    sim_max_dds = np.array(sim_max_dds)
    sim_sortinos = np.array(sim_sortinos)

    alpha = (1 - conf) / 2

    return {
        "n_simulations": n_sim,
        "block_size": block_sz,
        "confidence_level": conf,
        "original_metrics": compute_all_metrics(returns),
        "sharpe": {
            "mean": float(np.mean(sim_sharpes)),
            "std": float(np.std(sim_sharpes)),
            "ci_lower": float(np.percentile(sim_sharpes, alpha * 100)),
            "ci_upper": float(np.percentile(sim_sharpes, (1 - alpha) * 100)),
            "pct_positive": float((sim_sharpes > 0).mean()),
        },
        "total_return": {
            "mean": float(np.mean(sim_returns_total)),
            "std": float(np.std(sim_returns_total)),
            "ci_lower": float(np.percentile(sim_returns_total, alpha * 100)),
            "ci_upper": float(np.percentile(sim_returns_total, (1 - alpha) * 100)),
        },
        "max_drawdown": {
            "mean": float(np.mean(sim_max_dds)),
            "std": float(np.std(sim_max_dds)),
            "ci_lower": float(np.percentile(sim_max_dds, alpha * 100)),
            "ci_upper": float(np.percentile(sim_max_dds, (1 - alpha) * 100)),
        },
        "sortino": {
            "mean": float(np.mean(sim_sortinos)),
            "std": float(np.std(sim_sortinos)),
            "ci_lower": float(np.percentile(sim_sortinos, alpha * 100)),
            "ci_upper": float(np.percentile(sim_sortinos, (1 - alpha) * 100)),
            "pct_positive": float((sim_sortinos > 0).mean()),
        },
    }


def generate_mc_report(
    mc_results: List[Dict[str, Any]],
    output_path: Optional[str] = None,
) -> str:
    """Generate a markdown Monte Carlo robustness report."""
    lines = []
    lines.append("# KRONOS V1-ALT — Monte Carlo Robustness Report")
    lines.append("")

    for res in mc_results:
        sym = res.get("symbol", "aggregate")
        n_sim = res.get("n_simulations", 0)
        orig = res.get("original_metrics", {})

        lines.append(f"## {sym}")
        lines.append(f"- Simulations: {n_sim} | Block Size: {res.get('block_size', '?')}")
        lines.append(f"- Original Sharpe: {orig.get('sharpe', 0):.4f}")
        lines.append(f"- Original Total Return: {orig.get('total_return', 0):.4f}")
        lines.append("")

        for metric_name in ["sharpe", "total_return", "max_drawdown", "sortino"]:
            m = res.get(metric_name, {})
            pct_pos = m.get("pct_positive")
            pos_str = f" | % Positive: {pct_pos:.1%}" if pct_pos is not None else ""
            lines.append(
                f"- **{metric_name.replace('_', ' ').title()}**: "
                f"mean={m.get('mean', 0):.4f} "
                f"std={m.get('std', 0):.4f} "
                f"CI=[{m.get('ci_lower', 0):.4f}, {m.get('ci_upper', 0):.4f}]"
                f"{pos_str}"
            )
        lines.append("")

    report_text = "\n".join(lines)
    if output_path:
        import os
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        logger.info("[MC] Report written to %s", output_path)

    return report_text
