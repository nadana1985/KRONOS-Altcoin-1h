"""
KRONOS V1-ALT — Bias Override Point 09: "Static Percentage Threshold Bias"

Manual description:
  "Defining key level bounds using a static percentage threshold fails to adjust
   for structural volatility variations of high-beta tokens."

Quant replacement:
  "ATR-Weighted Volatility Bandwidths. Scale boundaries using a dynamic Average
   True Range Multiple: Bandwidth = (sum (H-L)) * kappa / W."

Reusable helper: kronos.quant_spec.overrides.utils.compute_atr_bandwidth
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_atr_bandwidth
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_09")



_DEFAULT_POINT_09_CONFIG = {
            "atr_window": 20,
            "kappa": 1.5,
            "min_data_density": 50,
            "fallback_bandwidth": 0.005,
            "min_bandwidth": 0.001,
            "max_bandwidth": 0.05,
        }

def _load_point_09_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_09", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_09_CONFIG

def compute_atr_weighted_bandwidth(
    high: pd.Series,
    low: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure quant replacement for Point 09."""
    cfg = config or {}
    w = int(cfg.get("atr_window", 20))
    kappa = float(cfg.get("kappa", 1.5))
    min_d = int(cfg.get("min_data_density", 50))
    fb = float(cfg.get("fallback_bandwidth", 0.005))
    cmin = float(cfg.get("min_bandwidth", 0.001))
    cmax = float(cfg.get("max_bandwidth", 0.05))

    if len(high) < min_d or len(low) < min_d:
        logger.info("[POINT_09] insufficient data for ATR — fallback bandwidth %.4f", fb)
        return fb

    bw = compute_atr_bandwidth(high, low, w, kappa, cmin, cmax)
    logger.info("[POINT_09] atr_bandwidth | window=%d kappa=%.2f -> bw=%.5f", w, kappa, bw)
    return bw


def compute_point_09_override(
    raw_bandwidth: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    """
    Wrapper for Point 09.
    raw_bandwidth is the legacy static percentage (e.g. 0.005).
    New value is the ATR-weighted dynamic bandwidth.
    """
    if engine is None:
        engine = BiasOverrideEngine()

    cfg = _load_point_09_config(engine)

    high = pd.to_numeric(df.get("high", df.get("close", pd.Series(dtype=float))), errors="coerce")
    low = pd.to_numeric(df.get("low", df.get("close", pd.Series(dtype=float))), errors="coerce")

    raw_val = float(raw_bandwidth)
    new_val = compute_atr_weighted_bandwidth(high, low, config=cfg)

    final = engine.apply_override(
        point_id="09",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )

    logger.debug(
        "[POINT_09] engine_decision | symbol=%s | raw_bw=%.5f | new_bw=%.5f | final=%.5f",
        symbol, raw_val, new_val, final
    )
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

    print("=== Point 09 (Static Percentage Threshold Bias) Smoke ===")
    engine = BiasOverrideEngine()
    cfg = _load_point_09_config(engine)

    np.random.seed(7)
    n = 150
    close = 100 + np.cumsum(np.random.randn(n) * 0.5)
    high = close + np.abs(np.random.randn(n)) * 0.8
    low = close - np.abs(np.random.randn(n)) * 0.8
    df = pd.DataFrame({"high": high, "low": low, "close": close})

    raw = 0.005
    new = compute_atr_weighted_bandwidth(df["high"], df["low"], config=cfg)
    print(f"raw_bw={raw:.4f} -> atr_bw={new:.5f}")

    final = compute_point_09_override(raw, df, "TEST09", engine=engine)
    print(f"Via engine (raw expected pre-flip): {final:.5f}")

    print("Point 09 smoke complete.")