"""
KRONOS V1-ALT — Bias Override Point 32: "Fixed Sessional Annualization Scales"

Quant replacement:
  "Dynamic Empirical Observation Sampling Rate (EOSR). Compute the
   scaling multiplier using raw database timestamps:
   psi = N_observed / (31_536_000_000 / sample_rate);
   sigma_annual = sigma * psi."
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import logging
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

logger = logging.getLogger("kronos.bias_override.point_32")


def _load_point_32_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    fallback = {"sample_rate_ms": 3600000.0, "min_data_density": 100, "fallback_scale": 1.0}
    if engine is None:
        return fallback
    try:
        cfg = engine.get_config("point_32") or {}
        return {
            "sample_rate_ms": float(cfg.get("sample_rate_ms", fallback["sample_rate_ms"])),
            "min_data_density": int(cfg.get("min_data_density", fallback["min_data_density"])),
            "fallback_scale": float(cfg.get("fallback_scale", fallback["fallback_scale"])),
        }
    except Exception as e:
        logger.warning("Point 32 config load failed: %s", e)
        return fallback


def compute_dynamic_annualization(timestamps: pd.Series, cfg: dict) -> dict:
    from kronos.quant_spec.overrides.utils import compute_dynamic_annualization_scale
    if len(timestamps) < cfg["min_data_density"]:
        return {"annualization_scale": cfg["fallback_scale"], "quality_proxy": 0.5}
    psi = compute_dynamic_annualization_scale(timestamps, cfg["sample_rate_ms"], cfg["min_data_density"])
    return {"annualization_scale": psi, "quality_proxy": 0.8}


def compute_point_32_override(
    annual_raw: float, timestamps: pd.Series, df=None, symbol=None, engine=None, **kwargs
) -> float:
    cfg = _load_point_32_config(engine)
    result = compute_dynamic_annualization(timestamps, cfg)
    override_val = result["annualization_scale"]
    if engine is not None:
        engine_final = engine.apply_override(
            point_id="32", raw_value=annual_raw, override_value=override_val,
            df=df, symbol=symbol, **kwargs,
        )
        return float(engine_final)
    return override_val


if __name__ == "__main__":
    n = 500
    ts = pd.Series(range(0, n * 3600000, 3600000))
    cfg = _load_point_32_config()
    result = compute_dynamic_annualization(ts, cfg)
    print(f"Point 32: scale={result['annualization_scale']:.4f}")
    print("Smoke done.")
