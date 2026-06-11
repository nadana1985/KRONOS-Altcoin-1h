"""
KRONOS V1-ALT — Bias Override Point 42: "Uniform High-Low Range Truncation"

Quant replacement:
  "Variance-Stabilized Normalized Range Estimator. Convert raw high-low
   metrics to units of standard deviation:
   R_t = (H_t - L_t) / (sigma_rolling,t * Delta_t)."
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import logging
import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

logger = logging.getLogger("kronos.bias_override.point_42")


def _load_point_42_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    fallback = {"window": 20, "min_data_density": 100, "fallback_norm_range": 1.0}
    if engine is None:
        return fallback
    try:
        cfg = engine.get_config("point_42") or {}
        return {
            "window": int(cfg.get("window", fallback["window"])),
            "min_data_density": int(cfg.get("min_data_density", fallback["min_data_density"])),
            "fallback_norm_range": float(cfg.get("fallback_norm_range", fallback["fallback_norm_range"])),
        }
    except Exception as e:
        logger.warning("Point 42 config load failed: %s", e)
        return fallback


def compute_range_normalization(high: pd.Series, low: pd.Series, cfg: dict) -> dict:
    from kronos.quant_spec.overrides.utils import compute_variance_stabilized_range
    if len(high) < cfg["min_data_density"]:
        return {"normalized_range": cfg["fallback_norm_range"], "quality_proxy": 0.5}
    nr = compute_variance_stabilized_range(high, low, cfg["window"])
    return {"normalized_range": nr, "quality_proxy": 0.7}


def compute_point_42_override(
    range_raw: float, high: pd.Series, low: pd.Series,
    df=None, symbol=None, engine=None, **kwargs,
) -> float:
    cfg = _load_point_42_config(engine)
    result = compute_range_normalization(high, low, cfg)
    override_val = result["normalized_range"]
    if engine is not None:
        engine_final = engine.apply_override(
            point_id="42", raw_value=range_raw, override_value=override_val,
            df=df, symbol=symbol, **kwargs,
        )
        return float(engine_final)
    return override_val


if __name__ == "__main__":
    n = 200
    rng = np.random.RandomState(42)
    h = pd.Series(100 + rng.uniform(0, 2, n))
    l = pd.Series(100 - rng.uniform(0, 2, n))
    cfg = _load_point_42_config()
    result = compute_range_normalization(h, l, cfg)
    print(f"Point 42: normalized_range={result['normalized_range']:.4f}")
    print("Smoke done.")
