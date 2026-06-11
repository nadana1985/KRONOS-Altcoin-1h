"""
KRONOS V1-ALT — Bias Override Point 12: "Binary Volatility Regime Boundaries"

Manual description:
  "Splitting volatility states using binary parameters forces continuous state
   transitions into artificial categorical bins."

Quant replacement:
  "Continuous Variance Mixture Z-Scores. Track the rolling Z-score of variance
   ratios across short and long lookbacks:
   Vol_Z = (sigma_short^2 - mu) / sigma_long."

Uses shared compute_variance_mixture_zscore.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_variance_mixture_zscore, _log_returns
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_12")



_DEFAULT_POINT_12_CONFIG = {
            "short_window": 10,
            "long_window": 50,
            "min_data_density": 200,
            "fallback_zscore": 0.0,
        }


def compute_variance_zscore(
    close: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Compute continuous variance mixture z-score from close prices."""
    cfg = config or {}
    short_w = int(cfg.get("short_window", 10))
    long_w = int(cfg.get("long_window", 50))
    min_d = int(cfg.get("min_data_density", 200))
    fb = float(cfg.get("fallback_zscore", 0.0))

    c = pd.to_numeric(close, errors="coerce").dropna()
    if len(c) < min_d:
        logger.info("[POINT_12] insufficient data — fallback zscore %.3f", fb)
        return fb

    r = _log_returns(c)
    zscore = compute_variance_mixture_zscore(r, short_w, long_w)
    logger.info("[POINT_12] variance_zscore | short=%d long=%d -> z=%.3f", short_w, long_w, zscore)
    return zscore


def compute_point_12_override(
    raw_regime: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    """Wrapper for Point 12. Returns continuous volatility regime z-score."""
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_12_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    raw_val = float(raw_regime) if np.isfinite(raw_regime) else float(cfg.get("fallback_zscore", 0.0))
    new_val = compute_variance_zscore(c, config=cfg)

    final = engine.apply_override(
        point_id="12",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_12] decision | %s raw=%.3f new=%.3f final=%.3f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 12 Variance Mixture Z-Score Smoke ===")
    engine = BiasOverrideEngine()
    rng = np.random.default_rng(12)
    n = 200
    # Low vol regime then high vol regime
    rets = np.concatenate([
        rng.normal(0, 0.005, 100),  # low vol
        rng.normal(0, 0.03, 100),   # high vol
    ])
    c = 100 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({"close": c})
    zscore = compute_point_12_override(0.0, df, "TEST12", engine=engine)
    print(f"  regime z-score: {zscore:.3f}")

def _load_point_12_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_12", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_12_CONFIG

def compute_variance_zscore(
    close: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Compute continuous variance mixture z-score from close prices."""
    cfg = config or {}
    short_w = int(cfg.get("short_window", 10))
    long_w = int(cfg.get("long_window", 50))
    min_d = int(cfg.get("min_data_density", 200))
    fb = float(cfg.get("fallback_zscore", 0.0))

    c = pd.to_numeric(close, errors="coerce").dropna()
    if len(c) < min_d:
        logger.info("[POINT_12] insufficient data — fallback zscore %.3f", fb)
        return fb

    r = _log_returns(c)
    zscore = compute_variance_mixture_zscore(r, short_w, long_w)
    logger.info("[POINT_12] variance_zscore | short=%d long=%d -> z=%.3f", short_w, long_w, zscore)
    return zscore


def compute_point_12_override(
    raw_regime: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    """Wrapper for Point 12. Returns continuous volatility regime z-score."""
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_12_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    raw_val = float(raw_regime) if np.isfinite(raw_regime) else float(cfg.get("fallback_zscore", 0.0))
    new_val = compute_variance_zscore(c, config=cfg)

    final = engine.apply_override(
        point_id="12",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_12] decision | %s raw=%.3f new=%.3f final=%.3f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 12 Variance Mixture Z-Score Smoke ===")
    engine = BiasOverrideEngine()
    rng = np.random.default_rng(12)
    n = 200
    # Low vol regime then high vol regime
    rets = np.concatenate([
        rng.normal(0, 0.005, 100),  # low vol
        rng.normal(0, 0.03, 100),   # high vol
    ])
    c = 100 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({"close": c})
    zscore = compute_point_12_override(0.0, df, "TEST12", engine=engine)
    print(f"  regime z-score: {zscore:.3f} (should be positive = high vol detected)")
    print("Smoke done.")
