"""
KRONOS V1-ALT — Bias Override Point 31: "Chronological Sampling Dependency"

Quant replacement:
  "Entropy-Weighted Information Bars. Interpolate kline metrics to
   reconstruct synthetic bars that trigger only when cumulative
   information entropy crosses a specified target."
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import logging
import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

logger = logging.getLogger("kronos.bias_override.point_31")


def _load_point_31_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    fallback = {"entropy_target": 2.0, "min_window": 1, "max_window": 12, "min_data_density": 300, "fallback_window": 1}
    if engine is None:
        return fallback
    try:
        cfg = engine.get_config("point_31") or {}
        return {
            "entropy_target": float(cfg.get("entropy_target", fallback["entropy_target"])),
            "min_window": int(cfg.get("min_window", fallback["min_window"])),
            "max_window": int(cfg.get("max_window", fallback["max_window"])),
            "min_data_density": int(cfg.get("min_data_density", fallback["min_data_density"])),
            "fallback_window": int(cfg.get("fallback_window", fallback["fallback_window"])),
        }
    except Exception as e:
        logger.warning("Point 31 config load failed: %s", e)
        return fallback


def compute_entropy_info_bars(volume: pd.Series, cfg: dict) -> dict:
    from kronos.quant_spec.overrides.utils import compute_entropy_weighted_bar_duration
    if len(volume) < cfg["min_data_density"]:
        return {"bar_duration": cfg["fallback_window"], "quality_proxy": 0.5}
    bd = compute_entropy_weighted_bar_duration(
        volume, cfg["entropy_target"], cfg["min_window"], cfg["max_window"]
    )
    return {"bar_duration": bd, "quality_proxy": 1.0 - abs(bd - cfg["min_window"]) / max(cfg["max_window"], 1)}


def compute_point_31_override(
    bar_raw: int, volume: pd.Series, df=None, symbol=None, engine=None, **kwargs
) -> float:
    cfg = _load_point_31_config(engine)
    result = compute_entropy_info_bars(volume, cfg)
    override_val = float(result["bar_duration"])
    if engine is not None:
        engine_final = engine.apply_override(
            point_id="31", raw_value=float(bar_raw), override_value=override_val,
            df=df, symbol=symbol, **kwargs,
        )
        return float(engine_final)
    return override_val


if __name__ == "__main__":
    n = 400
    rng = np.random.RandomState(42)
    vol = pd.Series(rng.uniform(1e5, 1e7, n))
    cfg = _load_point_31_config()
    result = compute_entropy_info_bars(vol, cfg)
    print(f"Point 31: bar_duration={result['bar_duration']}, quality={result['quality_proxy']:.4f}")
    print("Smoke done.")
