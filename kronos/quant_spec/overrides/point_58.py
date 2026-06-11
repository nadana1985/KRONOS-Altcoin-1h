"""
KRONOS V1-ALT — Bias Override Point 58: "Linear Trend Volatility Normalization"

Manual description:
  "Calculating volatility over trending phases linearly, which artificially inflates regime metrics."

Quant replacement:
  "Detrended Fluctuation Analysis (DFA) Volatility Scaling. Detrend local series windows
   before measuring fluctuations: F(s) = sum (y_k - Y_k)^2 ; sigma_DFA,t = F(X_t, s)."

Uses shared compute_dfa_vol_scaling.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_dfa_vol_scaling, compute_close_to_close_vol
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_58")



_DEFAULT_POINT_58_CONFIG = {"dfa_window": 50, "dfa_scale": 1.0, "min_data_density": 100, "fallback_vol": 0.01}


def compute_dfa_scaled_volatility(
    close: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    cfg = config or {}
    w = int(cfg.get("dfa_window", 50))
    sc = float(cfg.get("dfa_scale", 1.0))
    min_d = int(cfg.get("min_data_density", 100))
    fb = float(cfg.get("fallback_vol", 0.01))

    if len(close) < min_d:
        return fb

    vol = compute_dfa_vol_scaling(close, w, sc)
    if not np.isfinite(vol) or vol <= 0:
        vol = fb
    logger.info("[POINT_58] dfa_scale | w=%d scale=%.2f -> vol=%.5f", w, sc, vol)
    return float(vol)


def compute_point_58_override(
    raw_vol: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_58_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    raw_val = float(raw_vol) if np.isfinite(raw_vol) else compute_close_to_close_vol(c, int(cfg.get("dfa_window", 50)))
    new_val = compute_dfa_scaled_volatility(c, config=cfg)

    final = engine.apply_override(
        point_id="58",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_58] decision | %s raw=%.5f new=%.5f final=%.5f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 58 DFA Scaling Smoke ===")
    engine = BiasOverrideEngine()
    n = 100
    rng = np.random.default_rng(58)
    # Trending series
    trend = np.linspace(0, 5, n)
    c = 100 + trend + np.cumsum(rng.normal(0, 0.3, n))
    df = pd.DataFrame({"close": c})
    raw = 0.01
    final = compute_point_58_override(raw, df, "TEST58", engine=engine)
    print(f"raw={raw:.4f} -> final={final:.4f}")

def _load_point_58_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_58", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_58_CONFIG

def compute_dfa_scaled_volatility(
    close: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    cfg = config or {}
    w = int(cfg.get("dfa_window", 50))
    sc = float(cfg.get("dfa_scale", 1.0))
    min_d = int(cfg.get("min_data_density", 100))
    fb = float(cfg.get("fallback_vol", 0.01))

    if len(close) < min_d:
        return fb

    vol = compute_dfa_vol_scaling(close, w, sc)
    if not np.isfinite(vol) or vol <= 0:
        vol = fb
    logger.info("[POINT_58] dfa_scale | w=%d scale=%.2f -> vol=%.5f", w, sc, vol)
    return float(vol)


def compute_point_58_override(
    raw_vol: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_58_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    raw_val = float(raw_vol) if np.isfinite(raw_vol) else compute_close_to_close_vol(c, int(cfg.get("dfa_window", 50)))
    new_val = compute_dfa_scaled_volatility(c, config=cfg)

    final = engine.apply_override(
        point_id="58",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_58] decision | %s raw=%.5f new=%.5f final=%.5f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 58 DFA Scaling Smoke ===")
    engine = BiasOverrideEngine()
    n = 100
    rng = np.random.default_rng(58)
    # Trending series
    trend = np.linspace(0, 5, n)
    c = 100 + trend + np.cumsum(rng.normal(0, 0.3, n))
    df = pd.DataFrame({"close": c})
    raw = 0.01
    final = compute_point_58_override(raw, df, "TEST58", engine=engine)
    print(f"raw={raw:.4f} -> final={final:.4f}")
    print("Smoke done (simplified DFA).")