"""
KRONOS V1-ALT — Bias Override Point 30: "Microstructure Noise Blindness"

Quant replacement:
  "Bar-Level Realized Kernel Microstructure Estimator. Estimate local
   noise scales by incorporating open, high, low, and trade counts:
   eta_t = (H_t - L_t) / (Count_t * C_t + eps)."
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import logging
import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

logger = logging.getLogger("kronos.bias_override.point_30")


def _load_point_30_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    fallback = {"noise_window": 20, "noise_scale": 1.0, "min_data_density": 150, "fallback_noise": 0.001}
    if engine is None:
        return fallback
    try:
        cfg = engine.get_config("point_30") or {}
        return {
            "noise_window": int(cfg.get("noise_window", fallback["noise_window"])),
            "noise_scale": float(cfg.get("noise_scale", fallback["noise_scale"])),
            "min_data_density": int(cfg.get("min_data_density", fallback["min_data_density"])),
            "fallback_noise": float(cfg.get("fallback_noise", fallback["fallback_noise"])),
        }
    except Exception as e:
        logger.warning("Point 30 config load failed: %s", e)
        return fallback


def compute_microstructure_noise(
    high: pd.Series, low: pd.Series, close: pd.Series, count: pd.Series,
    window: int, noise_scale: float, min_data_density: int,
) -> dict:
    from kronos.quant_spec.overrides.utils import compute_microstructure_noise_estimator
    if len(close) < min_data_density:
        return {"noise_eta": 0.001, "scaled_noise": 0.001, "quality_proxy": 0.5}
    eta = compute_microstructure_noise_estimator(high, low, close, count, window)
    scaled = eta * noise_scale
    return {"noise_eta": eta, "scaled_noise": scaled, "quality_proxy": 0.5}


def compute_point_30_override(
    vol_raw: float, high: pd.Series, low: pd.Series, close: pd.Series,
    count: pd.Series, df=None, symbol=None, engine=None, **kwargs,
) -> float:
    cfg = _load_point_30_config(engine)
    result = compute_microstructure_noise(high, low, close, count, cfg["noise_window"], cfg["noise_scale"], cfg["min_data_density"])
    override_val = result["scaled_noise"]
    if engine is not None:
        engine_final = engine.apply_override(
            point_id="30", raw_value=vol_raw, override_value=override_val,
            df=df, symbol=symbol, **kwargs,
        )
        return float(engine_final)
    return override_val


if __name__ == "__main__":
    n = 200
    rng = np.random.RandomState(42)
    h = pd.Series(100 + rng.uniform(0, 2, n))
    l = pd.Series(100 - rng.uniform(0, 2, n))
    c = pd.Series(100 + rng.randn(n) * 0.5)
    cnt = pd.Series(rng.randint(100, 1000, n).astype(float))
    result = compute_microstructure_noise(h, l, c, cnt, 20, 1.0, 100)
    print(f"Point 30: noise_eta={result['noise_eta']:.6f}, scaled={result['scaled_noise']:.6f}")
    print("Smoke done.")
