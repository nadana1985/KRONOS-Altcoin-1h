"""
KRONOS V1-ALT — Bias Override Point 39: "Rigid Sessional Periodicity Mapping"

Quant replacement:
  "Discrete Fourier Transform (DFT) Dominant Cycle Extraction. Identify
   the dominant seasonal frequency components from the volume power
   spectrum dynamically: P(f) = |F(V)|^2; Period = argmax_f P(f)."
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import logging
import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

logger = logging.getLogger("kronos.bias_override.point_39")


def _load_point_39_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    fallback = {"window": 288, "min_freq": 3, "min_data_density": 300, "fallback_period": 24}
    if engine is None:
        return fallback
    try:
        cfg = engine.get_config("point_39") or {}
        return {
            "window": int(cfg.get("window", fallback["window"])),
            "min_freq": int(cfg.get("min_freq", fallback["min_freq"])),
            "min_data_density": int(cfg.get("min_data_density", fallback["min_data_density"])),
            "fallback_period": int(cfg.get("fallback_period", fallback["fallback_period"])),
        }
    except Exception as e:
        logger.warning("Point 39 config load failed: %s", e)
        return fallback


def compute_dft_dominant_cycle(volume: pd.Series, cfg: dict) -> dict:
    from kronos.quant_spec.overrides.utils import compute_dft_dominant_cycle as _compute
    if len(volume) < cfg["min_data_density"]:
        return {"dominant_period": cfg["fallback_period"], "quality_proxy": 0.5}
    period = _compute(volume, cfg["window"], cfg["min_freq"])
    return {"dominant_period": period, "quality_proxy": 0.8}


def compute_point_39_override(
    period_raw: int, volume: pd.Series, df=None, symbol=None, engine=None, **kwargs
) -> float:
    cfg = _load_point_39_config(engine)
    result = compute_dft_dominant_cycle(volume, cfg)
    override_val = float(result["dominant_period"])
    if engine is not None:
        engine_final = engine.apply_override(
            point_id="39", raw_value=float(period_raw), override_value=override_val,
            df=df, symbol=symbol, **kwargs,
        )
        return float(engine_final)
    return override_val


if __name__ == "__main__":
    n = 400
    rng = np.random.RandomState(42)
    vol = pd.Series(rng.uniform(1e5, 1e7, n) + np.sin(np.linspace(0, 10, n)) * 1e5)
    cfg = _load_point_39_config()
    result = compute_dft_dominant_cycle(vol, cfg)
    print(f"Point 39: dominant_period={result['dominant_period']}")
    print("Smoke done.")
