"""
KRONOS V1-ALT — Bias Override Point 40: "Linear Rescaling of Incomplete Bars"

Quant replacement:
  "Causal Intra-Bar Volume Density Weighting. Scale active bar metrics
   using historical intra-bar transaction curves:
   V_projected,t = V_t * CDF_time(Delta_t_elapsed)."
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import logging
import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

logger = logging.getLogger("kronos.bias_override.point_40")


def _load_point_40_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    fallback = {"window": 50, "min_data_density": 150, "fallback_weight": 1.0}
    if engine is None:
        return fallback
    try:
        cfg = engine.get_config("point_40") or {}
        return {
            "window": int(cfg.get("window", fallback["window"])),
            "min_data_density": int(cfg.get("min_data_density", fallback["min_data_density"])),
            "fallback_weight": float(cfg.get("fallback_weight", fallback["fallback_weight"])),
        }
    except Exception as e:
        logger.warning("Point 40 config load failed: %s", e)
        return fallback


def compute_intra_bar_density(
    volume: pd.Series, time_elapsed_pct: pd.Series, cfg: dict,
) -> dict:
    from kronos.quant_spec.overrides.utils import compute_intra_bar_volume_density
    if len(volume) < cfg["min_data_density"]:
        return {"density_weight": cfg["fallback_weight"], "quality_proxy": 0.5}
    w = compute_intra_bar_volume_density(volume, time_elapsed_pct, cfg["window"])
    return {"density_weight": w, "quality_proxy": 0.7}


def compute_point_40_override(
    bar_raw: float, volume: pd.Series, time_elapsed_pct: pd.Series = None,
    df=None, symbol=None, engine=None, **kwargs,
) -> float:
    cfg = _load_point_40_config(engine)
    if time_elapsed_pct is None:
        n = len(volume)
        time_elapsed_pct = pd.Series(np.linspace(0, 1, n))
    result = compute_intra_bar_density(volume, time_elapsed_pct, cfg)
    override_val = result["density_weight"]
    if engine is not None:
        engine_final = engine.apply_override(
            point_id="40", raw_value=bar_raw, override_value=override_val,
            df=df, symbol=symbol, **kwargs,
        )
        return float(engine_final)
    return override_val


if __name__ == "__main__":
    n = 200
    rng = np.random.RandomState(42)
    vol = pd.Series(rng.uniform(1e5, 1e7, n))
    t_pct = pd.Series(np.linspace(0, 1, n))
    cfg = _load_point_40_config()
    result = compute_intra_bar_density(vol, t_pct, cfg)
    print(f"Point 40: density_weight={result['density_weight']:.4f}")
    print("Smoke done.")
