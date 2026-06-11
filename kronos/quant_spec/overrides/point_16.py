"""
KRONOS V1-ALT — Bias Override Point 16: "Volume-at-Price Fixed Discretization Bias"

Manual description:
  "Segmenting volume profiles into fixed price buckets creates boundary errors
   when assets experience rapid, wide price expansions."

Quant replacement:
  "Gaussian Kernel Density Estimation (KDE) Volume Profiling. Calculate
   continuous volume density over price levels:
   exp f(P) = sum V_i * exp( - (P - C_i)^2 / (N * h^2) )."

Uses shared compute_kde_volume_profile.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_kde_volume_profile
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_16")



_DEFAULT_POINT_16_CONFIG = {
            "bandwidth_factor": 1.0,
            "n_price_levels": 50,
            "min_data_density": 200,
            "fallback_poc": 0.0,
        }


def compute_kde_profile(
    close: pd.Series,
    volume: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Compute KDE volume profile and Point of Control (POC)."""
    cfg = config or {}
    bw = float(cfg.get("bandwidth_factor", 1.0))
    n_levels = int(cfg.get("n_price_levels", 50))
    min_d = int(cfg.get("min_data_density", 200))

    c = pd.to_numeric(close, errors="coerce").dropna()
    v = pd.to_numeric(volume, errors="coerce").dropna()

    if len(c) < min_d or len(v) < min_d:
        fb_poc = float(cfg.get("fallback_poc", 0.0))
        logger.info("[POINT_16] insufficient data — fallback POC %.4f", fb_poc)
        return {"price_levels": np.array([]), "density": np.array([]), "poc": fb_poc}

    result = compute_kde_volume_profile(c, v, n_levels, bw)
    logger.info("[POINT_16] kde_profile | levels=%d bw=%.2f -> poc=%.4f", n_levels, bw, result["poc"])
    return result


def compute_point_16_override(
    raw_poc: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> dict:
    """Wrapper for Point 16. Returns KDE profile with POC."""
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_16_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    v = pd.to_numeric(df.get("volume"), errors="coerce")
    raw_val = float(raw_poc) if np.isfinite(raw_poc) else float(cfg.get("fallback_poc", 0.0))
    result = compute_kde_profile(c, v, config=cfg)

    final = engine.apply_override(
        point_id="16",
        raw_value=raw_val,
        override_value=result["poc"],
        df=df,
        symbol=symbol,
        **kwargs,
    )
    result["engine_final_poc"] = float(final)
    return result


if __name__ == "__main__":
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 16 KDE Volume Profile Smoke ===")
    engine = BiasOverrideEngine()
    rng = np.random.default_rng(16)
    n = 200
    c = 100 + np.cumsum(rng.normal(0, 0.5, n))
    # Higher volume near certain price levels (support/resistance)
    v = rng.uniform(500_000, 2_000_000, n)
    v[c > 102] *= 2.0  # more volume above 102
    df = pd.DataFrame({"close": c, "volume": v})
    result = compute_point_16_override(100.0, df, "TEST16", engine=engine)
    print(f"  POC: {result['engine_final_poc']:.4f}")
    print(f"  n_price_levels: {len(result['price_levels'])}")

def _load_point_16_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_16", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_16_CONFIG

def compute_kde_profile(
    close: pd.Series,
    volume: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Compute KDE volume profile and Point of Control (POC)."""
    cfg = config or {}
    bw = float(cfg.get("bandwidth_factor", 1.0))
    n_levels = int(cfg.get("n_price_levels", 50))
    min_d = int(cfg.get("min_data_density", 200))

    c = pd.to_numeric(close, errors="coerce").dropna()
    v = pd.to_numeric(volume, errors="coerce").dropna()

    if len(c) < min_d or len(v) < min_d:
        fb_poc = float(cfg.get("fallback_poc", 0.0))
        logger.info("[POINT_16] insufficient data — fallback POC %.4f", fb_poc)
        return {"price_levels": np.array([]), "density": np.array([]), "poc": fb_poc}

    result = compute_kde_volume_profile(c, v, n_levels, bw)
    logger.info("[POINT_16] kde_profile | levels=%d bw=%.2f -> poc=%.4f", n_levels, bw, result["poc"])
    return result


def compute_point_16_override(
    raw_poc: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> dict:
    """Wrapper for Point 16. Returns KDE profile with POC."""
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_16_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    v = pd.to_numeric(df.get("volume"), errors="coerce")
    raw_val = float(raw_poc) if np.isfinite(raw_poc) else float(cfg.get("fallback_poc", 0.0))
    result = compute_kde_profile(c, v, config=cfg)

    final = engine.apply_override(
        point_id="16",
        raw_value=raw_val,
        override_value=result["poc"],
        df=df,
        symbol=symbol,
        **kwargs,
    )
    result["engine_final_poc"] = float(final)
    return result


if __name__ == "__main__":
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 16 KDE Volume Profile Smoke ===")
    engine = BiasOverrideEngine()
    rng = np.random.default_rng(16)
    n = 200
    c = 100 + np.cumsum(rng.normal(0, 0.5, n))
    # Higher volume near certain price levels (support/resistance)
    v = rng.uniform(500_000, 2_000_000, n)
    v[c > 102] *= 2.0  # more volume above 102
    df = pd.DataFrame({"close": c, "volume": v})
    result = compute_point_16_override(100.0, df, "TEST16", engine=engine)
    print(f"  POC: {result['engine_final_poc']:.4f}")
    print(f"  n_price_levels: {len(result['price_levels'])}")
    print("Smoke done.")
