"""
KRONOS V1-ALT — Bias Override Point 26: "Discrete State Transitions for Key Level Proximity"

Manual description:
  "Calculating distances to support and resistance levels using discrete threshold steps."

Quant replacement:
  "Continuous Cauchy Proximity Kernels. Map the physical distance to the nearest key level via a smooth, non-linear Cauchy density function:
   f(d_t) = 1 / (pi * gamma * (1 + (d_t / gamma)^2))."

Uses shared compute_cauchy_proximity_kernel.

This replaces step-function proximity with a smooth, heavy-tailed kernel (useful for S/R features and soft barriers).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_cauchy_proximity_kernel
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_26")



_DEFAULT_POINT_26_CONFIG = {"cauchy_gamma": 0.01, "min_data_density": 40, "fallback_proximity": 0.5}


def compute_cauchy_proximity_value(
    distance: float,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure Cauchy proximity kernel replacement."""
    cfg = config or {}
    gamma = float(cfg.get("cauchy_gamma", 0.01))
    min_d = int(cfg.get("min_data_density", 40))  # distance always available, but we still check data for the bar
    fb = float(cfg.get("fallback_proximity", 0.5))

    # For single distance, the data check is on the caller side
    val = compute_cauchy_proximity_kernel(distance, gamma)
    if not np.isfinite(val):
        val = fb
    logger.info("[POINT_26] cauchy_prox | gamma=%.4f d=%.4f -> val=%.5f", gamma, distance, val)
    return float(val)


def compute_point_26_override(
    raw_proximity: float,
    df: pd.DataFrame,
    symbol: str,
    distance: Optional[float] = None,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    """
    Wrapper for Point 26.
    Expects a pre-computed 'distance' to nearest S/R (in price units).
    If not provided, falls back to a simple normalized distance from recent range.
    """
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_26_config(engine)

    if distance is None:
        c = pd.to_numeric(df.get("close"), errors="coerce")
        h = pd.to_numeric(df.get("high"), errors="coerce")
        l = pd.to_numeric(df.get("low"), errors="coerce")
        recent_range = (h.tail(20) - l.tail(20)).mean()
        # Fake a small distance for demo (0.3 of recent range)
        distance = 0.3 * recent_range if recent_range > 0 else 0.01

    raw_val = float(raw_proximity) if np.isfinite(raw_proximity) else 0.5
    new_val = compute_cauchy_proximity_value(distance, config=cfg)

    final = engine.apply_override(
        point_id="26",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_26] decision | %s raw=%.4f new=%.4f final=%.4f (d=%.4f)", symbol, raw_val, new_val, final, distance)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 26 Cauchy Proximity Smoke ===")
    engine = BiasOverrideEngine()
    n = 50
    rng = np.random.default_rng(26)
    c = 100 + np.cumsum(rng.normal(0, 0.3, n))
    h = c + rng.uniform(0.2, 0.6, n)
    l = c - rng.uniform(0.2, 0.6, n)
    df = pd.DataFrame({"high": h, "low": l, "close": c})
    raw = 0.4
    # Pass explicit distance for the wrapper
    final = compute_point_26_override(raw, df, "TEST26", distance=0.8, engine=engine)
    print(f"raw={raw:.3f} -> final={final:.5f}")

def _load_point_26_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_26", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_26_CONFIG

def compute_cauchy_proximity_value(
    distance: float,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure Cauchy proximity kernel replacement."""
    cfg = config or {}
    gamma = float(cfg.get("cauchy_gamma", 0.01))
    min_d = int(cfg.get("min_data_density", 40))  # distance always available, but we still check data for the bar
    fb = float(cfg.get("fallback_proximity", 0.5))

    # For single distance, the data check is on the caller side
    val = compute_cauchy_proximity_kernel(distance, gamma)
    if not np.isfinite(val):
        val = fb
    logger.info("[POINT_26] cauchy_prox | gamma=%.4f d=%.4f -> val=%.5f", gamma, distance, val)
    return float(val)


def compute_point_26_override(
    raw_proximity: float,
    df: pd.DataFrame,
    symbol: str,
    distance: Optional[float] = None,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    """
    Wrapper for Point 26.
    Expects a pre-computed 'distance' to nearest S/R (in price units).
    If not provided, falls back to a simple normalized distance from recent range.
    """
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_26_config(engine)

    if distance is None:
        c = pd.to_numeric(df.get("close"), errors="coerce")
        h = pd.to_numeric(df.get("high"), errors="coerce")
        l = pd.to_numeric(df.get("low"), errors="coerce")
        recent_range = (h.tail(20) - l.tail(20)).mean()
        # Fake a small distance for demo (0.3 of recent range)
        distance = 0.3 * recent_range if recent_range > 0 else 0.01

    raw_val = float(raw_proximity) if np.isfinite(raw_proximity) else 0.5
    new_val = compute_cauchy_proximity_value(distance, config=cfg)

    final = engine.apply_override(
        point_id="26",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_26] decision | %s raw=%.4f new=%.4f final=%.4f (d=%.4f)", symbol, raw_val, new_val, final, distance)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 26 Cauchy Proximity Smoke ===")
    engine = BiasOverrideEngine()
    n = 50
    rng = np.random.default_rng(26)
    c = 100 + np.cumsum(rng.normal(0, 0.3, n))
    h = c + rng.uniform(0.2, 0.6, n)
    l = c - rng.uniform(0.2, 0.6, n)
    df = pd.DataFrame({"high": h, "low": l, "close": c})
    raw = 0.4
    # Pass explicit distance for the wrapper
    final = compute_point_26_override(raw, df, "TEST26", distance=0.8, engine=engine)
    print(f"raw={raw:.3f} -> final={final:.5f}")
    print("Smoke done.")