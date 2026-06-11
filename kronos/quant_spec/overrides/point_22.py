"""
KRONOS V1-ALT — Bias Override Point 22: "Linear Bid-Ask Absorption Scaling"

Manual description:
  "Slot 00 absorption formulas evaluate volume at extremes symmetrically, ignoring the unequal force of aggressive buy/sell actions during trend runs."

Quant replacement:
  "Spread-Weighted Directional Delta Absorption. Scale buying and selling volumes based on local closing locations:
   Absorp_t = TBV_t * (C_t - L_t) - (V_t - TBV_t) * (H_t - C_t) / ( (H_t - L_t + eps) * V_t )."

Uses shared compute_spread_weighted_absorption (requires a spread series; falls back to small constant if not provided).

This makes absorption directional and spread-aware.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_spread_weighted_absorption
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_22")



_DEFAULT_POINT_22_CONFIG = {"absorption_window": 20, "min_data_density": 50, "fallback_absorption": 0.0}


def compute_spread_weighted_absorption_value(
    taker_buy: pd.Series,
    volume: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    spread: Optional[pd.Series] = None,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure spread-weighted absorption replacement."""
    cfg = config or {}
    w = int(cfg.get("absorption_window", 20))
    min_d = int(cfg.get("min_data_density", 50))
    fb = float(cfg.get("fallback_absorption", 0.0))

    if len(volume) < min_d:
        logger.info("[POINT_22] insufficient data — fallback absorption %.4f", fb)
        return fb

    if spread is None:
        spread = pd.Series(0.001, index=volume.index)

    val = compute_spread_weighted_absorption(taker_buy, volume, high, low, close, spread, w)
    if not np.isfinite(val):
        val = fb
    logger.info("[POINT_22] spread_weighted_abs | window=%d -> val=%.5f", w, val)
    return float(val)


def compute_point_22_override(
    raw_absorption: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_22_config(engine)

    tb = pd.to_numeric(df.get("taker_buy_base_volume", df.get("taker_buy_quote_volume", df.get("volume", 0.0) * 0.5)), errors="coerce")
    v = pd.to_numeric(df.get("volume", df.get("quote_volume", 1.0)), errors="coerce")
    h = pd.to_numeric(df.get("high"), errors="coerce")
    l = pd.to_numeric(df.get("low"), errors="coerce")
    c = pd.to_numeric(df.get("close"), errors="coerce")

    # Use Corwin-Schultz if available via prior point, else small constant
    raw_val = float(raw_absorption) if np.isfinite(raw_absorption) else 0.0
    new_val = compute_spread_weighted_absorption_value(tb, v, h, l, c, None, config=cfg)

    final = engine.apply_override(
        point_id="22",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_22] decision | %s raw=%.5f new=%.5f final=%.5f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 22 Spread-Weighted Absorption Smoke ===")
    engine = BiasOverrideEngine()
    n = 60
    rng = np.random.default_rng(22)
    c = 100 + np.cumsum(rng.normal(0, 0.4, n))
    h = c + rng.uniform(0.2, 0.8, n)
    l = c - rng.uniform(0.2, 0.8, n)
    v = rng.uniform(5e5, 3e6, n)
    tb = v * rng.uniform(0.3, 0.7, n)
    df = pd.DataFrame({"high": h, "low": l, "close": c, "volume": v, "taker_buy_base_volume": tb})
    raw = 0.1
    final = compute_point_22_override(raw, df, "TEST22", engine=engine)
    print(f"raw={raw:.3f} -> final={final:.4f}")

def _load_point_22_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_22", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_22_CONFIG

def compute_spread_weighted_absorption_value(
    taker_buy: pd.Series,
    volume: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    spread: Optional[pd.Series] = None,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure spread-weighted absorption replacement."""
    cfg = config or {}
    w = int(cfg.get("absorption_window", 20))
    min_d = int(cfg.get("min_data_density", 50))
    fb = float(cfg.get("fallback_absorption", 0.0))

    if len(volume) < min_d:
        logger.info("[POINT_22] insufficient data — fallback absorption %.4f", fb)
        return fb

    if spread is None:
        spread = pd.Series(0.001, index=volume.index)

    val = compute_spread_weighted_absorption(taker_buy, volume, high, low, close, spread, w)
    if not np.isfinite(val):
        val = fb
    logger.info("[POINT_22] spread_weighted_abs | window=%d -> val=%.5f", w, val)
    return float(val)


def compute_point_22_override(
    raw_absorption: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_22_config(engine)

    tb = pd.to_numeric(df.get("taker_buy_base_volume", df.get("taker_buy_quote_volume", df.get("volume", 0.0) * 0.5)), errors="coerce")
    v = pd.to_numeric(df.get("volume", df.get("quote_volume", 1.0)), errors="coerce")
    h = pd.to_numeric(df.get("high"), errors="coerce")
    l = pd.to_numeric(df.get("low"), errors="coerce")
    c = pd.to_numeric(df.get("close"), errors="coerce")

    # Use Corwin-Schultz if available via prior point, else small constant
    raw_val = float(raw_absorption) if np.isfinite(raw_absorption) else 0.0
    new_val = compute_spread_weighted_absorption_value(tb, v, h, l, c, None, config=cfg)

    final = engine.apply_override(
        point_id="22",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_22] decision | %s raw=%.5f new=%.5f final=%.5f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 22 Spread-Weighted Absorption Smoke ===")
    engine = BiasOverrideEngine()
    n = 60
    rng = np.random.default_rng(22)
    c = 100 + np.cumsum(rng.normal(0, 0.4, n))
    h = c + rng.uniform(0.2, 0.8, n)
    l = c - rng.uniform(0.2, 0.8, n)
    v = rng.uniform(5e5, 3e6, n)
    tb = v * rng.uniform(0.3, 0.7, n)
    df = pd.DataFrame({"high": h, "low": l, "close": c, "volume": v, "taker_buy_base_volume": tb})
    raw = 0.1
    final = compute_point_22_override(raw, df, "TEST22", engine=engine)
    print(f"raw={raw:.3f} -> final={final:.4f}")
    print("Smoke done.")