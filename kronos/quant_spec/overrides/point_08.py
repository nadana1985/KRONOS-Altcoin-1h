"""
KRONOS V1-ALT — Bias Override Point 08: "Hardcoded Lookback Scaling Ratios"

Manual description:
  "Binding minimum and maximum windows using a flat constant assumes uniform, static cycle scales."

Quant replacement:
  "Empirical Mode Decomposition Wavelet Alignment. Isolate the highest-amplitude
   Intrinsic Mode Function (IMF) wavelength to drive sessional windows dynamically:
   W_adaptive,t = round(alpha * Lambda_t)."

Practical contained implementation:
  Uses a lightweight cycle proxy (recent price excursion / volatility) instead of full EMD.
  This follows the adaptive scaling spirit of Point 02 while remaining numpy/pandas only.

Reusable helper: kronos.quant_spec.overrides.utils.compute_adaptive_cycle_window
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_adaptive_cycle_window
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_08")



_DEFAULT_POINT_08_CONFIG = {
            "cycle_window": 50,
            "alpha": 1.0,
            "min_lookback": 20,
            "max_lookback": 400,
            "min_data_density": 50,
            "fallback_multiplier": 1.0,
        }

def _load_point_08_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_08", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_08_CONFIG

def compute_adaptive_cycle_lookback(
    base_window: int,
    price_series: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> int:
    """Pure (proxy) quant replacement for Point 08."""
    cfg = config or {}
    cwin = int(cfg.get("cycle_window", 50))
    alpha = float(cfg.get("alpha", 1.0))
    min_lb = int(cfg.get("min_lookback", 20))
    max_lb = int(cfg.get("max_lookback", 400))
    min_d = int(cfg.get("min_data_density", 50))
    fb_mult = float(cfg.get("fallback_multiplier", 1.0))

    if len(price_series.dropna()) < min_d:
        logger.info("[POINT_08] insufficient data for cycle — fallback * %.2f", fb_mult)
        return int(round(base_window * fb_mult))

    w = compute_adaptive_cycle_window(price_series, cwin, alpha, min_lb, max_lb)
    logger.info("[POINT_08] adaptive_cycle | base=%d -> W=%d (proxy IMF)", base_window, w)
    return w


def compute_point_08_override(
    raw_window: int,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> int:
    """
    Wrapper for Point 08.
    Replaces a hardcoded scaling ratio / fixed window with an adaptive cycle-derived window.
    """
    if engine is None:
        engine = BiasOverrideEngine()

    cfg = _load_point_08_config(engine)
    close = pd.to_numeric(df.get("close", pd.Series(dtype=float)), errors="coerce")

    raw_val = int(raw_window)
    new_val = compute_adaptive_cycle_lookback(raw_val, close, config=cfg)

    final = engine.apply_override(
        point_id="08",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )

    logger.debug(
        "[POINT_08] engine_decision | symbol=%s | raw_w=%d | new_w=%d | final=%d",
        symbol, raw_val, new_val, int(final)
    )
    return int(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

    print("=== Point 08 (Hardcoded Lookback Scaling Ratios) Smoke ===")
    engine = BiasOverrideEngine()
    cfg = _load_point_08_config(engine)

    np.random.seed(8)
    n = 220
    # Simulate price with varying cycle lengths
    t = np.linspace(0, 8 * np.pi, n)
    price = 100 + 8 * np.sin(t) + np.random.randn(n) * 1.5
    df = pd.DataFrame({"close": price})

    raw = 120
    new = compute_adaptive_cycle_lookback(raw, df["close"], config=cfg)
    print(f"raw_window={raw} -> adaptive_cycle_w={new}")

    final = compute_point_08_override(raw, df, "TEST08", engine=engine)
    print(f"Via engine (raw expected): {final}")

    print("Point 08 smoke complete. (Uses practical IMF proxy; full EMD can be swapped later.)")