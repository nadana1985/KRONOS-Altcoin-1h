"""
KRONOS V1-ALT — Bias Override Point 45: "Symmetric Volume-Price Drift Adjustments"

Quant replacement:
  "Asymmetric Copula-Based Dependent Transforms. Model the non-linear
   dependency between returns and volume using a Gumbel Copula to
   capture extreme tail relationships."
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import logging
import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

logger = logging.getLogger("kronos.bias_override.point_45")


def _load_point_45_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    fallback = {"window": 100, "min_data_density": 300, "fallback_copula": 0.5}
    if engine is None:
        return fallback
    try:
        cfg = engine.get_config("point_45") or {}
        return {
            "window": int(cfg.get("window", fallback["window"])),
            "min_data_density": int(cfg.get("min_data_density", fallback["min_data_density"])),
            "fallback_copula": float(cfg.get("fallback_copula", fallback["fallback_copula"])),
        }
    except Exception as e:
        logger.warning("Point 45 config load failed: %s", e)
        return fallback


def compute_copula_transform(
    returns: pd.Series, volume: pd.Series, cfg: dict,
) -> dict:
    from kronos.quant_spec.overrides.utils import compute_gumbel_copula_transform
    n = min(len(returns), len(volume))
    if n < cfg["min_data_density"]:
        return {"copula_value": cfg["fallback_copula"], "quality_proxy": 0.5}
    val = compute_gumbel_copula_transform(returns, volume, cfg["window"])
    return {"copula_value": val, "quality_proxy": 0.7}


def compute_point_45_override(
    drift_raw: float, returns: pd.Series, volume: pd.Series,
    df=None, symbol=None, engine=None, **kwargs,
) -> float:
    cfg = _load_point_45_config(engine)
    result = compute_copula_transform(returns, volume, cfg)
    override_val = result["copula_value"]
    if engine is not None:
        engine_final = engine.apply_override(
            point_id="45", raw_value=drift_raw, override_value=override_val,
            df=df, symbol=symbol, **kwargs,
        )
        return float(engine_final)
    return override_val


if __name__ == "__main__":
    n = 300
    rng = np.random.RandomState(42)
    returns = pd.Series(rng.randn(n) * 0.01)
    volume = pd.Series(rng.uniform(1e5, 1e7, n))
    cfg = _load_point_45_config()
    result = compute_copula_transform(returns, volume, cfg)
    print(f"Point 45: copula={result['copula_value']:.4f}")
    print("Smoke done.")
