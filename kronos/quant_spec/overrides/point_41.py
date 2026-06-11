"""
KRONOS V1-ALT — Bias Override Point 41: "Fixed Lookback Phase Shift Assumptions"

Quant replacement:
  "Dynamic Time Warping (DTW) Metric Alignment. Align temporal series
   of target assets dynamically to establish structurally matching
   phase scales: min sum d(x_p, y_q) over warping path."
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import logging
import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

logger = logging.getLogger("kronos.bias_override.point_41")


def _load_point_41_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    fallback = {"max_shift": 50, "min_data_density": 300, "fallback_shift": 0}
    if engine is None:
        return fallback
    try:
        cfg = engine.get_config("point_41") or {}
        return {
            "max_shift": int(cfg.get("max_shift", fallback["max_shift"])),
            "min_data_density": int(cfg.get("min_data_density", fallback["min_data_density"])),
            "fallback_shift": int(cfg.get("fallback_shift", fallback["fallback_shift"])),
        }
    except Exception as e:
        logger.warning("Point 41 config load failed: %s", e)
        return fallback


def compute_dtw_alignment(series_a: pd.Series, series_b: pd.Series, cfg: dict) -> dict:
    from kronos.quant_spec.overrides.utils import compute_dtw_phase_shift
    n = min(len(series_a), len(series_b))
    if n < cfg["min_data_density"]:
        return {"optimal_shift": cfg["fallback_shift"], "quality_proxy": 0.5}
    shift = compute_dtw_phase_shift(series_a, series_b, cfg["max_shift"])
    return {"optimal_shift": shift, "quality_proxy": 0.7}


def compute_point_41_override(
    shift_raw: int, series_a: pd.Series, series_b: pd.Series,
    df=None, symbol=None, engine=None, **kwargs,
) -> float:
    cfg = _load_point_41_config(engine)
    result = compute_dtw_alignment(series_a, series_b, cfg)
    override_val = float(result["optimal_shift"])
    if engine is not None:
        engine_final = engine.apply_override(
            point_id="41", raw_value=float(shift_raw), override_value=override_val,
            df=df, symbol=symbol, **kwargs,
        )
        return float(engine_final)
    return override_val


if __name__ == "__main__":
    n = 300
    rng = np.random.RandomState(42)
    base = np.cumsum(rng.randn(n) * 0.01)
    a = pd.Series(base)
    b = pd.Series(np.roll(base, 5) + rng.randn(n) * 0.002)  # shifted + noisy
    cfg = _load_point_41_config()
    result = compute_dtw_alignment(a, b, cfg)
    print(f"Point 41: optimal_shift={result['optimal_shift']}")
    print("Smoke done.")
