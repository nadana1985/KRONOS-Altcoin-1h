"""
KRONOS V1-ALT — Bias Override Point 95: "Point-in-Time Executions"

Manual description:
  "Executing trades at the precise instant of a hourly close candle assumes
   infinite liquidity is available."

Quant replacement:
  "Time-Weighted Average Price (TWAP) Execution Models. Disperse execution fills
   over a localized sessional window:
   P_TWAP = 1/N * sum P_i for i=1 to N."

Uses shared compute_twap_execution_price from utils.

This provides realistic execution modeling by simulating how a real order
would be sliced and filled across multiple sub-intervals within a bar.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import (
    compute_twap_execution_price,
    compute_corwin_schultz_spread,
)
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_95")



_DEFAULT_POINT_95_CONFIG = {
            "n_slices": 4,
            "lookback_bars": 2,
            "min_slices": 1,
            "min_data_density": 10,
            "fallback_twap_adjustment_bps": 5.0,
        }


def simulate_twap_execution(
    bar_opens: pd.Series,
    bar_closes: pd.Series,
    config: Optional[Dict[str, Any]] = None,
    bar_highs: Optional[pd.Series] = None,
    bar_lows: Optional[pd.Series] = None,
) -> dict:
    """
    Simulate TWAP execution over a window of bars.
    Returns dict with twap_price and comparison metrics.
    """
    cfg = config or {}
    n_slices = int(cfg.get("n_slices", 4))
    min_slices = int(cfg.get("min_slices", 1))
    min_d = int(cfg.get("min_data_density", 10))
    fb_bps = float(cfg.get("fallback_twap_adjustment_bps", 5.0))

    if len(bar_opens) < min_d or len(bar_closes) < min_d:
        logger.info("[POINT_95] insufficient data — fallback TWAP adjustment %.1f bps", fb_bps)
        if len(bar_closes) > 0:
            close_price = float(bar_closes.iloc[-1])
            return {
                "twap_price": close_price * (1 + fb_bps / 10000.0),
                "vs_close": fb_bps / 10000.0,
                "vs_open": 0.0,
                "n_fills": 1,
                "fallback": True,
            }
        return {"twap_price": np.nan, "vs_close": 0.0, "vs_open": 0.0, "n_fills": 0, "fallback": True}

    # Estimate spread for execution cost (use real H/L if provided)
    if bar_highs is not None and bar_lows is not None:
        h = pd.to_numeric(bar_highs, errors="coerce")
        l = pd.to_numeric(bar_lows, errors="coerce")
    else:
        h = bar_closes * 1.001
        l = bar_closes * 0.999
    try:
        spread = compute_corwin_schultz_spread(h, l, window=2)
    except Exception:
        spread = 0.001

    result = compute_twap_execution_price(
        bar_opens=bar_opens.tail(min(n_slices, len(bar_opens))),
        bar_closes=bar_closes.tail(min(n_slices, len(bar_closes))),
        n_slices=n_slices,
        spread=spread,
        min_slices=min_slices,
    )
    result["fallback"] = False

    logger.info(
        "[POINT_95] twap | n_slices=%d -> price=%.4f vs_close=%.4f",
        n_slices, result.get("twap_price", 0), result.get("vs_close", 0),
    )
    return result


def compute_point_95_override(
    raw_price: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> dict:
    """
    Wrapper for Point 95.
    raw_price: the naive point-in-time close price.
    Returns a dict with twap_price and comparison metrics.
    """
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_95_config(engine)

    o = pd.to_numeric(df.get("open"), errors="coerce")
    c = pd.to_numeric(df.get("close"), errors="coerce")

    raw_val = float(raw_price) if np.isfinite(raw_price) else float(c.iloc[-1]) if len(c) > 0 else 100.0
    h = pd.to_numeric(df.get("high"), errors="coerce")
    l = pd.to_numeric(df.get("low"), errors="coerce")
    result = simulate_twap_execution(o, c, config=cfg, bar_highs=h, bar_lows=l)

    # Engine routes on twap_price scalar
    twap = result.get("twap_price", raw_val)
    if not np.isfinite(twap):
        twap = raw_val

    final_price = engine.apply_override(
        point_id="95",
        raw_value=raw_val,
        override_value=twap,
        df=df,
        symbol=symbol,
        **kwargs,
    )

    result["engine_final_price"] = float(final_price)
    logger.debug(
        "[POINT_95] decision | %s raw=%.4f final=%.4f vs_close=%.4f",
        symbol, raw_val, final_price, result.get("vs_close", 0),
    )
    return result


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

    print("=== Point 95 TWAP Execution Smoke ===")
    engine = BiasOverrideEngine()
    n = 30
    rng = np.random.default_rng(95)
    c = 100 + np.cumsum(rng.normal(0, 0.2, n))
    o = c + rng.normal(0, 0.05, n)
    h = np.maximum(c, o) + rng.uniform(0, 0.3, n)
    l = np.minimum(c, o) - rng.uniform(0, 0.3, n)
    df = pd.DataFrame({"open": o, "close": c, "high": h, "low": l, "volume": rng.uniform(1e6, 5e6, n)})

    raw_close = float(c.iloc[-1])
    res = compute_point_95_override(raw_close, df, "TEST95", engine=engine)
    print(f"raw_close={raw_close:.4f} -> twap={res['engine_final_price']:.4f} """
          f"vs_close={res.get('vs_close', 0):.4f}")

    # Show sensitivity to n_slices
    for ns in [1, 2, 4, 8, 16]:
        cfg_test = {"n_slices": ns, "min_data_density": 5}
        tres = simulate_twap_execution(o, c, config=cfg_test)
        print(f"  n_slices={ns:>2} -> twap={tres.get('twap_price', 0):.4f} """
              f"vs_close={tres.get('vs_close', 0):.4f}")

def _load_point_95_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_95", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_95_CONFIG

def simulate_twap_execution(
    bar_opens: pd.Series,
    bar_closes: pd.Series,
    config: Optional[Dict[str, Any]] = None,
    bar_highs: Optional[pd.Series] = None,
    bar_lows: Optional[pd.Series] = None,
) -> dict:
    """
    Simulate TWAP execution over a window of bars.
    Returns dict with twap_price and comparison metrics.
    """
    cfg = config or {}
    n_slices = int(cfg.get("n_slices", 4))
    min_slices = int(cfg.get("min_slices", 1))
    min_d = int(cfg.get("min_data_density", 10))
    fb_bps = float(cfg.get("fallback_twap_adjustment_bps", 5.0))

    if len(bar_opens) < min_d or len(bar_closes) < min_d:
        logger.info("[POINT_95] insufficient data — fallback TWAP adjustment %.1f bps", fb_bps)
        if len(bar_closes) > 0:
            close_price = float(bar_closes.iloc[-1])
            return {
                "twap_price": close_price * (1 + fb_bps / 10000.0),
                "vs_close": fb_bps / 10000.0,
                "vs_open": 0.0,
                "n_fills": 1,
                "fallback": True,
            }
        return {"twap_price": np.nan, "vs_close": 0.0, "vs_open": 0.0, "n_fills": 0, "fallback": True}

    # Estimate spread for execution cost (use real H/L if provided)
    if bar_highs is not None and bar_lows is not None:
        h = pd.to_numeric(bar_highs, errors="coerce")
        l = pd.to_numeric(bar_lows, errors="coerce")
    else:
        h = bar_closes * 1.001
        l = bar_closes * 0.999
    try:
        spread = compute_corwin_schultz_spread(h, l, window=2)
    except Exception:
        spread = 0.001

    result = compute_twap_execution_price(
        bar_opens=bar_opens.tail(min(n_slices, len(bar_opens))),
        bar_closes=bar_closes.tail(min(n_slices, len(bar_closes))),
        n_slices=n_slices,
        spread=spread,
        min_slices=min_slices,
    )
    result["fallback"] = False

    logger.info(
        "[POINT_95] twap | n_slices=%d -> price=%.4f vs_close=%.4f",
        n_slices, result.get("twap_price", 0), result.get("vs_close", 0),
    )
    return result


def compute_point_95_override(
    raw_price: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> dict:
    """
    Wrapper for Point 95.
    raw_price: the naive point-in-time close price.
    Returns a dict with twap_price and comparison metrics.
    """
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_95_config(engine)

    o = pd.to_numeric(df.get("open"), errors="coerce")
    c = pd.to_numeric(df.get("close"), errors="coerce")

    raw_val = float(raw_price) if np.isfinite(raw_price) else float(c.iloc[-1]) if len(c) > 0 else 100.0
    h = pd.to_numeric(df.get("high"), errors="coerce")
    l = pd.to_numeric(df.get("low"), errors="coerce")
    result = simulate_twap_execution(o, c, config=cfg, bar_highs=h, bar_lows=l)

    # Engine routes on twap_price scalar
    twap = result.get("twap_price", raw_val)
    if not np.isfinite(twap):
        twap = raw_val

    final_price = engine.apply_override(
        point_id="95",
        raw_value=raw_val,
        override_value=twap,
        df=df,
        symbol=symbol,
        **kwargs,
    )

    result["engine_final_price"] = float(final_price)
    logger.debug(
        "[POINT_95] decision | %s raw=%.4f final=%.4f vs_close=%.4f",
        symbol, raw_val, final_price, result.get("vs_close", 0),
    )
    return result


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

    print("=== Point 95 TWAP Execution Smoke ===")
    engine = BiasOverrideEngine()
    n = 30
    rng = np.random.default_rng(95)
    c = 100 + np.cumsum(rng.normal(0, 0.2, n))
    o = c + rng.normal(0, 0.05, n)
    h = np.maximum(c, o) + rng.uniform(0, 0.3, n)
    l = np.minimum(c, o) - rng.uniform(0, 0.3, n)
    df = pd.DataFrame({"open": o, "close": c, "high": h, "low": l, "volume": rng.uniform(1e6, 5e6, n)})

    raw_close = float(c.iloc[-1])
    res = compute_point_95_override(raw_close, df, "TEST95", engine=engine)
    print(f"raw_close={raw_close:.4f} -> twap={res['engine_final_price']:.4f} """
          f"vs_close={res.get('vs_close', 0):.4f}")

    # Show sensitivity to n_slices
    for ns in [1, 2, 4, 8, 16]:
        cfg_test = {"n_slices": ns, "min_data_density": 5}
        tres = simulate_twap_execution(o, c, config=cfg_test)
        print(f"  n_slices={ns:>2} -> twap={tres.get('twap_price', 0):.4f} """
              f"vs_close={tres.get('vs_close', 0):.4f}")

    print("Smoke done.")
