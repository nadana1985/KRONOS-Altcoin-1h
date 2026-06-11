"""
KRONOS V1-ALT — Bias Override Point 50: "Micro-Crash Ignorance"

Manual description:
  "Simple volatility metrics miss sudden, sub-bar flash liquidations that quickly
   pull back before the hourly close."

Quant replacement:
  "High-Low Range Parkinson Estimator. Track intra-bar extremes directly to capture
   extreme tail deviations: sigma_P^2 = 1/(4*W*ln(2)) * sum (ln(H_i/L_i))^2."

Uses shared compute_parkinson_vol.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_parkinson_vol, compute_close_to_close_vol
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_50")



_DEFAULT_POINT_50_CONFIG = {"vol_window": 20, "min_data_density": 30, "fallback_vol": 0.01}


def compute_parkinson_volatility(
    high: pd.Series, low: pd.Series, config: Optional[Dict[str, Any]] = None,
) -> float:
    cfg = config or {}
    w = int(cfg.get("vol_window", 20))
    min_d = int(cfg.get("min_data_density", 30))
    fb = float(cfg.get("fallback_vol", 0.01))

    if len(high) < min_d or len(low) < min_d:
        return fb
    vol = compute_parkinson_vol(high, low, w)
    if not np.isfinite(vol) or vol <= 0:
        vol = fb
    logger.info("[POINT_50] parkinson | window=%d -> vol=%.5f", w, vol)
    return float(vol)


def compute_point_50_override(
    raw_vol: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_50_config(engine)

    h = pd.to_numeric(df.get("high"), errors="coerce")
    l = pd.to_numeric(df.get("low"), errors="coerce")
    c = pd.to_numeric(df.get("close"), errors="coerce")

    raw_val = float(raw_vol) if np.isfinite(raw_vol) else compute_close_to_close_vol(c, int(cfg.get("vol_window", 20)))
    new_val = compute_parkinson_volatility(h, l, config=cfg)

    final = engine.apply_override(
        point_id="50",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_50] decision | %s raw=%.5f new=%.5f final=%.5f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 50 Parkinson Smoke ===")
    engine = BiasOverrideEngine()
    n = 80
    rng = np.random.default_rng(50)
    c = 100 + np.cumsum(rng.normal(0, 0.4, n))
    # micro crash
    c[40:43] = [98, 85, 97]
    h = c + rng.uniform(0, 0.5, n)
    l = c - rng.uniform(0, 0.5, n)
    df = pd.DataFrame({"high": h, "low": l, "close": c})
    raw = 0.009
    final = compute_point_50_override(raw, df, "TEST50", engine=engine)
    print(f"raw={raw:.4f} -> final={final:.4f}")

def _load_point_50_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_50", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_50_CONFIG

def compute_parkinson_volatility(
    high: pd.Series, low: pd.Series, config: Optional[Dict[str, Any]] = None,
) -> float:
    cfg = config or {}
    w = int(cfg.get("vol_window", 20))
    min_d = int(cfg.get("min_data_density", 30))
    fb = float(cfg.get("fallback_vol", 0.01))

    if len(high) < min_d or len(low) < min_d:
        return fb
    vol = compute_parkinson_vol(high, low, w)
    if not np.isfinite(vol) or vol <= 0:
        vol = fb
    logger.info("[POINT_50] parkinson | window=%d -> vol=%.5f", w, vol)
    return float(vol)


def compute_point_50_override(
    raw_vol: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_50_config(engine)

    h = pd.to_numeric(df.get("high"), errors="coerce")
    l = pd.to_numeric(df.get("low"), errors="coerce")
    c = pd.to_numeric(df.get("close"), errors="coerce")

    raw_val = float(raw_vol) if np.isfinite(raw_vol) else compute_close_to_close_vol(c, int(cfg.get("vol_window", 20)))
    new_val = compute_parkinson_volatility(h, l, config=cfg)

    final = engine.apply_override(
        point_id="50",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_50] decision | %s raw=%.5f new=%.5f final=%.5f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 50 Parkinson Smoke ===")
    engine = BiasOverrideEngine()
    n = 80
    rng = np.random.default_rng(50)
    c = 100 + np.cumsum(rng.normal(0, 0.4, n))
    # micro crash
    c[40:43] = [98, 85, 97]
    h = c + rng.uniform(0, 0.5, n)
    l = c - rng.uniform(0, 0.5, n)
    df = pd.DataFrame({"high": h, "low": l, "close": c})
    raw = 0.009
    final = compute_point_50_override(raw, df, "TEST50", engine=engine)
    print(f"raw={raw:.4f} -> final={final:.4f}")
    print("Smoke done.")