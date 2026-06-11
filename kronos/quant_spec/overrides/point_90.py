"""
KRONOS V1-ALT - Bias Override Point 90: Point-in-Time Predictive Validation.

Quant replacement:
Monte Carlo Path Deflated Sharpe Ratio evaluations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import monte_carlo_deflated_sharpe_paths

logger = logging.getLogger("kronos.bias_override.point_90")

_DEFAULT_POINT_90_CONFIG = {
    "n_mc_paths": 1000,
    "sharpe_confidence": 0.95,
    "num_trials": 100,
    "min_data_density": 200,
    "fallback_sharpe": 0.5,
}


def _load_point_90_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_90", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_90_CONFIG


def run_monte_carlo_dsr_evaluation(
    returns: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Pure Monte Carlo DSR path evaluation."""
    cfg = config or {}
    n_paths = int(cfg.get("n_mc_paths", 1000))
    conf = float(cfg.get("sharpe_confidence", 0.95))
    trials = int(cfg.get("num_trials", 100))
    min_d = int(cfg.get("min_data_density", 200))

    if len(returns) < min_d:
        logger.info("[POINT_90] insufficient data - returning fallback DSR stats")
        return {
            "dsr_mean": float(cfg.get("fallback_sharpe", 0.5)),
            "dsr_std": 0.1,
            "prob_positive": 0.5,
        }

    stats = monte_carlo_deflated_sharpe_paths(returns, n_paths, trials, conf)
    logger.info(
        "[POINT_90] mc_dsr | paths=%d -> mean=%.4f prob_pos=%.3f",
        n_paths,
        stats["dsr_mean"],
        stats["prob_positive"],
    )
    return stats


def compute_point_90_override(
    raw_sharpe: float,
    returns: pd.Series,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> dict:
    """
    Wrapper for Point 90.

    The engine gates the scalar `dsr_mean`; the full Monte Carlo distribution
    remains available in the returned stats dict.
    """
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_90_config(engine)

    min_d = int(cfg.get("min_data_density", 200))
    fb = float(cfg.get("fallback_sharpe", 0.5))

    if len(returns) < min_d:
        stats = {"dsr_mean": fb, "dsr_std": 0.1, "prob_positive": 0.5}
    else:
        stats = run_monte_carlo_dsr_evaluation(returns, config=cfg)

    final_mean = engine.apply_override(
        point_id="90",
        raw_value=raw_sharpe,
        override_value=stats["dsr_mean"],
        df=df,
        symbol=symbol,
        **kwargs,
    )

    stats["engine_final_dsr_mean"] = float(final_mean)
    logger.debug(
        "[POINT_90] decision | %s raw_sharpe=%.4f final_dsr_mean=%.4f",
        symbol,
        raw_sharpe,
        final_mean,
    )
    return stats


if __name__ == "__main__":
    import numpy as np

    print("=== Point 90 Monte Carlo DSR Smoke ===")
    engine = BiasOverrideEngine()
    n = 300
    rets = np.random.randn(n) * 0.001
    df = pd.DataFrame({"close": np.cumsum(rets) + 100})
    raw = 1.2
    res = compute_point_90_override(raw, pd.Series(rets), df, "TEST90", engine=engine)
    print(
        f"raw_sharpe={raw:.3f} -> MC DSR mean={res['dsr_mean']:.4f} "
        f"(engine final={res.get('engine_final_dsr_mean', 0):.4f})"
    )
    print("Smoke done.")
