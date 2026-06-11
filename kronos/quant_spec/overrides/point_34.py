"""
KRONOS V1-ALT — Bias Override Point 34: "Static Prediction Target Horizons"

Quant replacement:
  "VPIN-Synchronized Dynamic Forecast Horizons. Scale targets relative
   to volume turnover speeds:
   Horizon_t = min { k | sum V_{t+i} >= mu_V * phi }."
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import logging
import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

logger = logging.getLogger("kronos.bias_override.point_34")


def _load_point_34_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    fallback = {"base_horizon": 4, "phi_target": 1.5, "min_window": 1, "max_window": 12, "min_data_density": 150}
    if engine is None:
        return fallback
    try:
        cfg = engine.get_config("point_34") or {}
        return {
            "base_horizon": int(cfg.get("base_horizon", fallback["base_horizon"])),
            "phi_target": float(cfg.get("phi_target", fallback["phi_target"])),
            "min_window": int(cfg.get("min_window", fallback["min_window"])),
            "max_window": int(cfg.get("max_window", fallback["max_window"])),
            "min_data_density": int(cfg.get("min_data_density", fallback["min_data_density"])),
        }
    except Exception as e:
        logger.warning("Point 34 config load failed: %s", e)
        return fallback


def compute_vpin_synced_horizon(volume: pd.Series, cfg: dict) -> dict:
    from kronos.quant_spec.overrides.utils import compute_vpin_synced_horizon as _compute
    if len(volume) < cfg["min_data_density"]:
        return {"dynamic_horizon": cfg["base_horizon"], "quality_proxy": 0.5}
    mu_vol = float(volume.mean())
    h = _compute(volume, cfg["base_horizon"], mu_vol, cfg["phi_target"], cfg["min_window"], cfg["max_window"])
    return {"dynamic_horizon": h, "quality_proxy": 0.8}


def compute_point_34_override(
    horizon_raw: int, volume: pd.Series, df=None, symbol=None, engine=None, **kwargs
) -> float:
    cfg = _load_point_34_config(engine)
    result = compute_vpin_synced_horizon(volume, cfg)
    override_val = float(result["dynamic_horizon"])
    if engine is not None:
        engine_final = engine.apply_override(
            point_id="34", raw_value=float(horizon_raw), override_value=override_val,
            df=df, symbol=symbol, **kwargs,
        )
        return float(engine_final)
    return override_val


if __name__ == "__main__":
    n = 300
    rng = np.random.RandomState(42)
    vol = pd.Series(rng.uniform(1e5, 1e7, n))
    cfg = _load_point_34_config()
    result = compute_vpin_synced_horizon(vol, cfg)
    print(f"Point 34: horizon={result['dynamic_horizon']}")
    print("Smoke done.")
