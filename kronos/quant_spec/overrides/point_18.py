"""
KRONOS V1-ALT — Bias Override Point 18: "Linear Volume Impact Scaling"

Manual description:
  "Linear volume impact scaling ignores capitalization scales across the
   530 tokens."

Quant replacement:
  "Logarithmic Volume Z-Score Normalization. Scale the volume series using
   rolling log-transformed distributions:
   V = (ln(Q_t) - mu_ln(Q)) / sigma_ln(Q)."

Uses shared compute_log_volume_zscore.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_log_volume_zscore
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_18")



_DEFAULT_POINT_18_CONFIG = {
            "log_vol_window": 50,
            "min_data_density": 150,
            "fallback_zscore": 0.0,
        }


def compute_log_vol_zscore(
    volume: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Compute log-transformed volume z-score."""
    cfg = config or {}
    w = int(cfg.get("log_vol_window", 50))
    min_d = int(cfg.get("min_data_density", 150))
    fb = float(cfg.get("fallback_zscore", 0.0))

    v = pd.to_numeric(volume, errors="coerce").dropna()
    if len(v) < min_d:
        logger.info("[POINT_18] insufficient data — fallback zscore %.3f", fb)
        return fb

    zscore = compute_log_volume_zscore(v, w)
    logger.info("[POINT_18] log_vol_zscore | window=%d -> z=%.3f", w, zscore)
    return zscore


def compute_point_18_override(
    raw_vol_zscore: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    volume_col: str = "volume",
    **kwargs,
) -> float:
    """Wrapper for Point 18. Returns log-transformed volume z-score."""
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_18_config(engine)

    v = pd.to_numeric(df.get(volume_col), errors="coerce")
    raw_val = float(raw_vol_zscore) if np.isfinite(raw_vol_zscore) else float(cfg.get("fallback_zscore", 0.0))
    new_val = compute_log_vol_zscore(v, config=cfg)

    final = engine.apply_override(
        point_id="18",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_18] decision | %s raw=%.3f new=%.3f final=%.3f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 18 Log Volume Z-Score Smoke ===")
    engine = BiasOverrideEngine()
    rng = np.random.default_rng(18)
    n = 200
    # Mix of low-cap and high-cap volume patterns
    vol_low = rng.uniform(10_000, 100_000, n // 2)
    vol_high = rng.uniform(5_000_000, 50_000_000, n // 2)
    vol = np.concatenate([vol_low, vol_high])
    df = pd.DataFrame({"volume": vol, "close": 100 + np.cumsum(rng.normal(0, 0.5, n))})
    # Current bar has very high volume (should show positive z)
    zscore = compute_point_18_override(0.0, df, "TEST18", engine=engine)
    print(f"  log volume z-score: {zscore:.3f}")

def _load_point_18_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_18", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_18_CONFIG

def compute_log_vol_zscore(
    volume: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Compute log-transformed volume z-score."""
    cfg = config or {}
    w = int(cfg.get("log_vol_window", 50))
    min_d = int(cfg.get("min_data_density", 150))
    fb = float(cfg.get("fallback_zscore", 0.0))

    v = pd.to_numeric(volume, errors="coerce").dropna()
    if len(v) < min_d:
        logger.info("[POINT_18] insufficient data — fallback zscore %.3f", fb)
        return fb

    zscore = compute_log_volume_zscore(v, w)
    logger.info("[POINT_18] log_vol_zscore | window=%d -> z=%.3f", w, zscore)
    return zscore


def compute_point_18_override(
    raw_vol_zscore: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    volume_col: str = "volume",
    **kwargs,
) -> float:
    """Wrapper for Point 18. Returns log-transformed volume z-score."""
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_18_config(engine)

    v = pd.to_numeric(df.get(volume_col), errors="coerce")
    raw_val = float(raw_vol_zscore) if np.isfinite(raw_vol_zscore) else float(cfg.get("fallback_zscore", 0.0))
    new_val = compute_log_vol_zscore(v, config=cfg)

    final = engine.apply_override(
        point_id="18",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_18] decision | %s raw=%.3f new=%.3f final=%.3f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 18 Log Volume Z-Score Smoke ===")
    engine = BiasOverrideEngine()
    rng = np.random.default_rng(18)
    n = 200
    # Mix of low-cap and high-cap volume patterns
    vol_low = rng.uniform(10_000, 100_000, n // 2)
    vol_high = rng.uniform(5_000_000, 50_000_000, n // 2)
    vol = np.concatenate([vol_low, vol_high])
    df = pd.DataFrame({"volume": vol, "close": 100 + np.cumsum(rng.normal(0, 0.5, n))})
    # Current bar has very high volume (should show positive z)
    zscore = compute_point_18_override(0.0, df, "TEST18", engine=engine)
    print(f"  log volume z-score: {zscore:.3f}")
    print("Smoke done.")
