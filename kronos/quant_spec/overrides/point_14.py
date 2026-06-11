"""
KRONOS V1-ALT — Bias Override Point 14: "Hardcoded Denominator Epsilon Guards"

Manual description:
  "Injecting a uniform constant to prevent division-by-zero errors distorts scale
   metrics on low-nominal-priced tokens."

Quant replacement:
  "Numerical Standard Deviation Precision Scale. Dynamically scale epsilons relative
   to the moving variance of the target denominator: eps_t = sigma(X[t-W:t]) * 1e-7."

Reusable helper: kronos.quant_spec.overrides.utils.compute_dynamic_epsilon
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_dynamic_epsilon
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_14")



_DEFAULT_POINT_14_CONFIG = {
            "eps_scale": 1e-7,
            "sigma_window": 50,
            "min_data_density": 30,
            "fallback_eps": 1e-8,
            "min_eps": 1e-12,
            "max_eps": 1e-3,
        }

def _load_point_14_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_14", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_14_CONFIG

def compute_dynamic_sigma_epsilon(
    series: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure quant replacement for Point 14."""
    cfg = config or {}
    w = int(cfg.get("sigma_window", 50))
    scale = float(cfg.get("eps_scale", 1e-7))
    min_d = int(cfg.get("min_data_density", 30))
    fb = float(cfg.get("fallback_eps", 1e-8))
    cmin = float(cfg.get("min_eps", 1e-12))
    cmax = float(cfg.get("max_eps", 1e-3))

    if len(series.dropna()) < min_d:
        logger.info("[POINT_14] insufficient history for sigma — fallback eps %.2e", fb)
        return fb

    eps = compute_dynamic_epsilon(series, w, scale, cmin, cmax)
    logger.info("[POINT_14] dynamic_eps | scale=%.1e sigma_window=%d -> eps=%.2e", scale, w, eps)
    return eps


def compute_point_14_override(
    raw_eps: float,
    df: pd.DataFrame,
    symbol: str,
    series: Optional[pd.Series] = None,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    """
    Wrapper for Point 14.
    Replaces a hardcoded eps with a dynamic sigma-scaled guard.
    If no series provided, uses recent |logret| or volume as proxy denominator volatility.
    """
    if engine is None:
        engine = BiasOverrideEngine()

    cfg = _load_point_14_config(engine)

    if series is None:
        close = pd.to_numeric(df.get("close", pd.Series(dtype=float)), errors="coerce")
        logret = (close / close.shift(1) - 1.0).abs()
        series = logret.dropna()

    raw_val = float(raw_eps)
    new_val = compute_dynamic_sigma_epsilon(series, config=cfg)

    final = engine.apply_override(
        point_id="14",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )

    logger.debug(
        "[POINT_14] engine_decision | symbol=%s | raw_eps=%.2e | new_eps=%.2e | final=%.2e",
        symbol, raw_val, new_val, final
    )
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

    print("=== Point 14 (Hardcoded Denominator Epsilon Guards) Smoke ===")
    engine = BiasOverrideEngine()
    cfg = _load_point_14_config(engine)

    np.random.seed(14)
    n = 160
    proxy = pd.Series(np.random.randn(n).cumsum() * 0.3 + 50)  # price-like series for sigma

    raw = 1e-8
    new = compute_dynamic_sigma_epsilon(proxy, config=cfg)
    print(f"raw_eps={raw:.2e} -> dyn_eps={new:.2e}")

    dummy_df = pd.DataFrame({"close": proxy.values})
    final = compute_point_14_override(raw, dummy_df, "TEST14", engine=engine)
    print(f"Via engine (raw expected): {final:.2e}")

    print("Point 14 smoke complete.")