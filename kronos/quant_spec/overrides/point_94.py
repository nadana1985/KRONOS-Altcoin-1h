"""
KRONOS V1-ALT — Bias Override Point 94: "Constant Execution Fee Scaling"

Manual description:
  "Applying flat, unchanging execution fee parameters across all asset classes."

Quant replacement:
  "Spread-Scaled Dynamic Execution Cost Models. Adjust transaction fees dynamically
   to match estimated execution spreads:
   Cost_t = Fee_base + delta_t * Spread_t + market_impact."

Uses shared compute_dynamic_execution_cost from utils.

This provides realistic execution cost modeling that adapts to market conditions
and order size relative to available liquidity.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import (
    compute_dynamic_execution_cost,
    compute_corwin_schultz_spread,
)
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_94")



_DEFAULT_POINT_94_CONFIG = {
            "base_fee_bps": 5.0,
            "fee_scale_factor": 1.0,
            "max_fee_bps": 50.0,
            "order_size_usd": 10000.0,
            "min_volume_ratio": 0.001,
            "min_data_density": 20,
            "fallback_cost_bps": 15.0,
        }


def estimate_execution_cost(
    order_size_usd: float,
    volume_usd: float,
    high: pd.Series,
    low: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """
    Estimate total execution cost (fees + spread + impact).
    Returns dict with cost breakdown.
    """
    cfg = config or {}
    base_fee = float(cfg.get("base_fee_bps", 5.0))
    scale = float(cfg.get("fee_scale_factor", 1.0))
    max_fee = float(cfg.get("max_fee_bps", 50.0))
    min_vol_ratio = float(cfg.get("min_volume_ratio", 0.001))
    min_d = int(cfg.get("min_data_density", 20))
    fb = float(cfg.get("fallback_cost_bps", 15.0))

    if len(high) < min_d or len(low) < min_d:
        logger.info("[POINT_94] insufficient data — fallback cost %.1f bps", fb)
        return {
            "total_cost_bps": fb,
            "base_fee_bps": base_fee,
            "spread_cost_bps": fb - base_fee,
            "impact_bps": 0.0,
            "spread": fb / 10000.0,
        }

    spread = compute_corwin_schultz_spread(high, low, window=2)
    if not np.isfinite(spread) or spread < 0:
        spread = 0.001

    result = compute_dynamic_execution_cost(
        base_fee_bps=base_fee,
        spread=spread,
        order_size_usd=order_size_usd,
        volume_usd=volume_usd,
        fee_scale_factor=scale,
        max_fee_bps=max_fee,
        min_volume_ratio=min_vol_ratio,
    )
    result["spread"] = spread

    logger.info(
        "[POINT_94] exec_cost | order_usd=%.0f spread=%.5f -> total=%.1f bps (fee=%.1f + spread=%.1f + impact=%.1f)",
        order_size_usd, spread, result["total_cost_bps"],
        result["base_fee_bps"], result["spread_cost_bps"], result["impact_bps"],
    )
    return result


def compute_point_94_override(
    raw_cost_bps: float,
    df: pd.DataFrame,
    symbol: str,
    order_size_usd: float = 10000.0,
    volume_usd: float = 1_000_000.0,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> dict:
    """
    Wrapper for Point 94.
    raw_cost_bps: the legacy static fee in bps.
    Returns a dict with cost breakdown.
    """
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_94_config(engine)

    h = pd.to_numeric(df.get("high"), errors="coerce")
    l = pd.to_numeric(df.get("low"), errors="coerce")

    raw_val = float(raw_cost_bps) if np.isfinite(raw_cost_bps) else float(cfg.get("fallback_cost_bps", 15.0))
    result = estimate_execution_cost(order_size_usd, volume_usd, h, l, config=cfg)

    # Engine routes on total_cost_bps
    final_cost = engine.apply_override(
        point_id="94",
        raw_value=raw_val,
        override_value=result["total_cost_bps"],
        df=df,
        symbol=symbol,
        **kwargs,
    )

    result["engine_final_cost_bps"] = float(final_cost)
    logger.debug(
        "[POINT_94] decision | %s raw=%.1f final=%.1f bps",
        symbol, raw_val, final_cost,
    )
    return result


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

    print("=== Point 94 Dynamic Execution Cost Smoke ===")
    engine = BiasOverrideEngine()
    n = 60
    rng = np.random.default_rng(94)
    c = 100 + np.cumsum(rng.normal(0, 0.3, n))
    h = c + rng.uniform(0.1, 0.5, n)
    l = c - rng.uniform(0.1, 0.5, n)
    df = pd.DataFrame({"close": c, "high": h, "low": l, "volume": rng.uniform(1e6, 5e6, n)})

    raw = 10.0  # static 10 bps fee
    for order_usd, vol_usd in [(5000, 1e6), (50000, 1e6), (5000, 1e5), (50000, 1e5)]:
        res = compute_point_94_override(
            raw, df, "TEST94", order_size_usd=order_usd, volume_usd=vol_usd, engine=engine
        )
        print(f"  order=${order_usd:>6.0f} vol=${vol_usd:.0e} -> "
              f"cost={res['engine_final_cost_bps']:.1f}bps "
              f"(fee={res['base_fee_bps']:.1f} + spread={res['spread_cost_bps']:.1f} + impact={res['impact_bps']:.1f})")


def _load_point_94_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_94", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_94_CONFIG

def estimate_execution_cost(
    order_size_usd: float,
    volume_usd: float,
    high: pd.Series,
    low: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """
    Estimate total execution cost (fees + spread + impact).
    Returns dict with cost breakdown.
    """
    cfg = config or {}
    base_fee = float(cfg.get("base_fee_bps", 5.0))
    scale = float(cfg.get("fee_scale_factor", 1.0))
    max_fee = float(cfg.get("max_fee_bps", 50.0))
    min_vol_ratio = float(cfg.get("min_volume_ratio", 0.001))
    min_d = int(cfg.get("min_data_density", 20))
    fb = float(cfg.get("fallback_cost_bps", 15.0))

    if len(high) < min_d or len(low) < min_d:
        logger.info("[POINT_94] insufficient data — fallback cost %.1f bps", fb)
        return {
            "total_cost_bps": fb,
            "base_fee_bps": base_fee,
            "spread_cost_bps": fb - base_fee,
            "impact_bps": 0.0,
            "spread": fb / 10000.0,
        }

    spread = compute_corwin_schultz_spread(high, low, window=2)
    if not np.isfinite(spread) or spread < 0:
        spread = 0.001

    result = compute_dynamic_execution_cost(
        base_fee_bps=base_fee,
        spread=spread,
        order_size_usd=order_size_usd,
        volume_usd=volume_usd,
        fee_scale_factor=scale,
        max_fee_bps=max_fee,
        min_volume_ratio=min_vol_ratio,
    )
    result["spread"] = spread

    logger.info(
        "[POINT_94] exec_cost | order_usd=%.0f spread=%.5f -> total=%.1f bps (fee=%.1f + spread=%.1f + impact=%.1f)",
        order_size_usd, spread, result["total_cost_bps"],
        result["base_fee_bps"], result["spread_cost_bps"], result["impact_bps"],
    )
    return result


def compute_point_94_override(
    raw_cost_bps: float,
    df: pd.DataFrame,
    symbol: str,
    order_size_usd: float = 10000.0,
    volume_usd: float = 1_000_000.0,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> dict:
    """
    Wrapper for Point 94.
    raw_cost_bps: the legacy static fee in bps.
    Returns a dict with cost breakdown.
    """
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_94_config(engine)

    h = pd.to_numeric(df.get("high"), errors="coerce")
    l = pd.to_numeric(df.get("low"), errors="coerce")

    raw_val = float(raw_cost_bps) if np.isfinite(raw_cost_bps) else float(cfg.get("fallback_cost_bps", 15.0))
    result = estimate_execution_cost(order_size_usd, volume_usd, h, l, config=cfg)

    # Engine routes on total_cost_bps
    final_cost = engine.apply_override(
        point_id="94",
        raw_value=raw_val,
        override_value=result["total_cost_bps"],
        df=df,
        symbol=symbol,
        **kwargs,
    )

    result["engine_final_cost_bps"] = float(final_cost)
    logger.debug(
        "[POINT_94] decision | %s raw=%.1f final=%.1f bps",
        symbol, raw_val, final_cost,
    )
    return result


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

    print("=== Point 94 Dynamic Execution Cost Smoke ===")
    engine = BiasOverrideEngine()
    n = 60
    rng = np.random.default_rng(94)
    c = 100 + np.cumsum(rng.normal(0, 0.3, n))
    h = c + rng.uniform(0.1, 0.5, n)
    l = c - rng.uniform(0.1, 0.5, n)
    df = pd.DataFrame({"close": c, "high": h, "low": l, "volume": rng.uniform(1e6, 5e6, n)})

    raw = 10.0  # static 10 bps fee
    for order_usd, vol_usd in [(5000, 1e6), (50000, 1e6), (5000, 1e5), (50000, 1e5)]:
        res = compute_point_94_override(
            raw, df, "TEST94", order_size_usd=order_usd, volume_usd=vol_usd, engine=engine
        )
        print(f"  order=${order_usd:>6.0f} vol=${vol_usd:.0e} -> "
              f"cost={res['engine_final_cost_bps']:.1f}bps "
              f"(fee={res['base_fee_bps']:.1f} + spread={res['spread_cost_bps']:.1f} + impact={res['impact_bps']:.1f})")

    print("Smoke done.")
