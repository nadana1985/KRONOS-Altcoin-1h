"""
KRONOS V1-ALT — Bias Override Point 38: "Standard Moving Average Temporal Lag Bias"

Quant replacement:
  "Zero-Lag Hull Moving Average (HMA). Eliminate lag by utilizing weighted
   moving average differentials:
   HMA_t = WMA(2 * WMA(C, W/2) - WMA(C, W), sqrt(W))."
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import logging
import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

logger = logging.getLogger("kronos.bias_override.point_38")


def _load_point_38_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    fallback = {"window": 20, "min_data_density": 100, "fallback_ma": 0.0}
    if engine is None:
        return fallback
    try:
        cfg = engine.get_config("point_38") or {}
        return {
            "window": int(cfg.get("window", fallback["window"])),
            "min_data_density": int(cfg.get("min_data_density", fallback["min_data_density"])),
            "fallback_ma": float(cfg.get("fallback_ma", fallback["fallback_ma"])),
        }
    except Exception as e:
        logger.warning("Point 38 config load failed: %s", e)
        return fallback


def compute_hma_override(close: pd.Series, window: int, min_data_density: int) -> dict:
    from kronos.quant_spec.overrides.utils import compute_hull_moving_average
    if len(close) < min_data_density:
        return {"hma_value": close.iloc[-1] if len(close) > 0 else 0.0, "quality_proxy": 0.5}
    hma = compute_hull_moving_average(close, window)
    # Lag reduction score: HMA vs SMA lag comparison
    sma = close.rolling(window).mean().iloc[-1] if len(close) >= window else close.mean()
    hma_val = hma
    lag_proxy = abs(hma_val - close.iloc[-1]) / max(abs(sma - close.iloc[-1]), 1e-12) if abs(sma - close.iloc[-1]) > 1e-10 else 1.0
    return {"hma_value": hma_val, "quality_proxy": float(np.clip(lag_proxy, 0.0, 1.0))}


def compute_point_38_override(
    ma_raw: float, close: pd.Series, df=None, symbol=None, engine=None, **kwargs
) -> float:
    cfg = _load_point_38_config(engine)
    result = compute_hma_override(close, cfg["window"], cfg["min_data_density"])
    override_val = result["hma_value"]
    if engine is not None:
        engine_final = engine.apply_override(
            point_id="38", raw_value=ma_raw, override_value=override_val,
            df=df, symbol=symbol, **kwargs,
        )
        return float(engine_final)
    return override_val


if __name__ == "__main__":
    n = 200
    rng = np.random.RandomState(42)
    close = pd.Series(np.cumsum(rng.randn(n) * 0.01) + 100)
    cfg = _load_point_38_config()
    result = compute_hma_override(close, cfg["window"], cfg["min_data_density"])
    print(f"Point 38: hma={result['hma_value']:.4f}, quality={result['quality_proxy']:.4f}")
    print("Smoke done.")
