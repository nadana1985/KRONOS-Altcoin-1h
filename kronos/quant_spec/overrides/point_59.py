"""
KRONOS V1-ALT — Bias Override Point 59: "Symmetric Volatility Memory Spans"

Manual description:
  "Volatility memory decays at identical chronological intervals across different assets."

Quant replacement:
  "Hurst-Adaptive Volatility Memory Half-Life. Scale decay parameters based on local
   persistent memory: lambda_vol,t = lambda_base * e ^ -(H_t - 0.5)."

Uses shared compute_hurst_exponent.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_hurst_exponent
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_59")



_DEFAULT_POINT_59_CONFIG = {"hurst_window": 50, "base_lambda": 0.1, "min_data_density": 60, "fallback_lambda": 0.1}


def compute_hurst_adaptive_lambda(
    close: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    cfg = config or {}
    w = int(cfg.get("hurst_window", 50))
    base_l = float(cfg.get("base_lambda", 0.1))
    min_d = int(cfg.get("min_data_density", 60))
    fb = float(cfg.get("fallback_lambda", 0.1))

    if len(close) < min_d:
        return fb

    h = compute_hurst_exponent((close / close.shift(1) - 1.0).dropna(), w)
    lam = base_l * np.exp(-(h - 0.5))
    lam = float(np.clip(lam, 0.01, 0.5))
    logger.info("[POINT_59] hurst_adapt | H=%.3f -> lambda=%.4f", h, lam)
    return lam


def compute_point_59_override(
    raw_lambda: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_59_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    raw_val = float(raw_lambda) if np.isfinite(raw_lambda) else float(cfg.get("base_lambda", 0.1))
    new_val = compute_hurst_adaptive_lambda(c, config=cfg)

    final = engine.apply_override(
        point_id="59",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_59] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 59 Hurst-Adaptive Smoke ===")
    engine = BiasOverrideEngine()
    n = 80
    rng = np.random.default_rng(59)
    # Persistent series (H > 0.5)
    c = 100 + np.cumsum(rng.normal(0.001, 0.4, n))
    df = pd.DataFrame({"close": c})
    raw = 0.12
    final = compute_point_59_override(raw, df, "TEST59", engine=engine)
    print(f"raw={raw:.4f} -> final={final:.4f}")

def _load_point_59_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_59", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_59_CONFIG





