"""
KRONOS V1-ALT — Bias Override Point 93: "Zero Execution Latency Assumptions"

Manual description:
  "Assuming instant order execution, ignoring execution latency and price
   slippage in backtests."

Quant replacement:
  "Estimated Execution Delay Latency Slippage Modifiers. Incorporate dynamic delay
   parameters scaled by local volatility:
   P_executed,t = P_signal,t + sigma_t * Delta_t_delay."

Uses shared compute_latency_slippage_modifier from utils.

This provides realistic execution modeling by incorporating latency-driven
price slippage that scales with volatility.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import (
    compute_latency_slippage_modifier,
    compute_close_to_close_vol,
)
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_93")



_DEFAULT_POINT_93_CONFIG = {
            "latency_bars": 0.1,
            "vol_window": 20,
            "base_slippage_bps": 5.0,
            "vol_scale_factor": 1.0,
            "max_slippage_bps": 50.0,
            "min_data_density": 20,
            "fallback_slippage_bps": 10.0,
        }


def estimate_execution_latency_slippage(
    signal_price: float,
    close: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """
    Estimate execution slippage from latency and volatility.
    Returns dict with executed_price and slippage details.
    """
    cfg = config or {}
    latency_bars = float(cfg.get("latency_bars", 0.1))
    vol_window = int(cfg.get("vol_window", 20))
    base_bps = float(cfg.get("base_slippage_bps", 5.0))
    vol_scale = float(cfg.get("vol_scale_factor", 1.0))
    max_bps = float(cfg.get("max_slippage_bps", 50.0))
    min_d = int(cfg.get("min_data_density", 20))
    fb_bps = float(cfg.get("fallback_slippage_bps", 10.0))

    if len(close) < min_d:
        logger.info("[POINT_93] insufficient data — fallback slippage %.1f bps", fb_bps)
        return {
            "executed_price": signal_price * (1 + fb_bps / 10000.0),
            "slippage_bps": fb_bps,
            "slippage_type": "fallback",
        }

    volatility = compute_close_to_close_vol(close, vol_window)
    if not np.isfinite(volatility):
        volatility = 0.01

    result = compute_latency_slippage_modifier(
        signal_price=signal_price,
        volatility=volatility,
        latency_bars=latency_bars,
        base_slippage_bps=base_bps,
        vol_scale_factor=vol_scale,
        max_slippage_bps=max_bps,
    )

    logger.info(
        "[POINT_93] latency_slippage | price=%.4f vol=%.4f latency=%.2f -> slippage=%.1f bps",
        signal_price, volatility, latency_bars, result["slippage_bps"],
    )
    return result


def compute_point_93_override(
    raw_price: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> dict:
    """
    Wrapper for Point 93.
    raw_price: the naive signal price (instant execution assumption).
    Returns a dict with executed_price and slippage details.
    """
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_93_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")

    raw_val = float(raw_price) if np.isfinite(raw_price) else float(c.iloc[-1]) if len(c) > 0 else 100.0
    result = estimate_execution_latency_slippage(raw_val, c, config=cfg)

    # The engine routes on a scalar (executed_price)
    final_price = engine.apply_override(
        point_id="93",
        raw_value=raw_val,
        override_value=result["executed_price"],
        df=df,
        symbol=symbol,
        **kwargs,
    )

    result["engine_final_price"] = float(final_price)
    logger.debug(
        "[POINT_93] decision | %s raw=%.4f final=%.4f slippage=%.1f bps",
        symbol, raw_val, final_price, result["slippage_bps"],
    )
    return result


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

    print("=== Point 93 Execution Latency Slippage Smoke ===")
    engine = BiasOverrideEngine()
    n = 60
    rng = np.random.default_rng(93)
    close = pd.Series(100 + np.cumsum(rng.normal(0, 0.3, n)))
    df = pd.DataFrame({"close": close})

    raw = 100.0
    res = compute_point_93_override(raw, df, "TEST93", engine=engine)
    print(f"signal_price={raw:.4f} -> executed={res['engine_final_price']:.4f} """
          f"slippage={res['slippage_bps']:.1f}bps")

    # Show volatility sensitivity
    for vol_mult in [0.5, 1.0, 2.0, 4.0]:
        volatile_close = pd.Series(100 + np.cumsum(rng.normal(0, 0.3 * vol_mult, n)))
        vdf = pd.DataFrame({"close": volatile_close})
        vr = estimate_execution_latency_slippage(100.0, volatile_close)
        print(f"  vol_mult={vol_mult:.1f} -> slippage={vr['slippage_bps']:.1f}")

def _load_point_93_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_93", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_93_CONFIG





