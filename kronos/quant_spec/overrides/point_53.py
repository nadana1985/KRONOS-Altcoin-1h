"""
KRONOS V1-ALT — Bias Override Point 53: "Relative Spread-Volume Volatility Distortions"

Manual description (from bias_override_registry.yaml):
  "Assuming price volatility scales uniformly across both illiquid altcoins and blue-chip tokens."

Quant replacement:
  "Amihud-Adjusted Realized Volatility. Scale volatility directly by relative transaction friction:
   sigma_t = sigma_rolling,t * e ^ (lambda * Illiq_t)."

Uses shared compute_amihud_adjusted_vol and compute_amihud_illiq.

Follows the established engine-routed pattern with raw (close-to-close) vs adjusted.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_amihud_adjusted_vol, compute_close_to_close_vol
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_53")



_DEFAULT_POINT_53_CONFIG = {
            "vol_window": 20,
            "amihud_lambda": 0.5,
            "min_data_density": 50,
            "fallback_vol": 0.01,
            "amihud_window": 20,
        }


def compute_amihud_adjusted_realized_vol(
    close: pd.Series,
    volume: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure Amihud-adjusted vol replacement for Point 53."""
    cfg = config or {}
    w = int(cfg.get("vol_window", 20))
    lam = float(cfg.get("amihud_lambda", 0.5))
    min_d = int(cfg.get("min_data_density", 50))
    fb = float(cfg.get("fallback_vol", 0.01))
    a_win = int(cfg.get("amihud_window", 20))

    if len(close) < min_d or len(volume) < min_d:
        logger.info("[POINT_53] insufficient data — fallback vol %.4f", fb)
        return fb

    vol = compute_amihud_adjusted_vol(close, volume, w, lam)
    if not np.isfinite(vol) or vol <= 0:
        vol = fb
    logger.info("[POINT_53] amihud_adj | lambda=%.2f w=%d -> vol=%.5f", lam, w, vol)
    return float(vol)


def compute_point_53_override(
    raw_vol: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    """Wrapper for Point 53: raw = c2c, new = Amihud-adjusted, engine route."""
    if engine is None:
        engine = BiasOverrideEngine()

    cfg = _load_point_53_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    v = pd.to_numeric(df.get("volume", df.get("quote_volume", 1.0)), errors="coerce")

    raw_val = float(raw_vol) if np.isfinite(raw_vol) else compute_close_to_close_vol(c, int(cfg.get("vol_window", 20)))
    new_val = compute_amihud_adjusted_realized_vol(c, v, config=cfg)

    final = engine.apply_override(
        point_id="53",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_53] decision | %s raw=%.5f new=%.5f final=%.5f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 53 Amihud-Adjusted Smoke ===")
    engine = BiasOverrideEngine()
    n = 80
    rng = np.random.default_rng(53)
    c = 100 + np.cumsum(rng.normal(0, 0.5, n))
    v = rng.uniform(1e5, 5e6, n)
    df = pd.DataFrame({"close": c, "volume": v})
    raw = 0.012
    final = compute_point_53_override(raw, df, "TEST53", engine=engine)
    print(f"raw={raw:.4f} -> final={final:.4f}")

def _load_point_53_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_53", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_53_CONFIG

def compute_amihud_adjusted_realized_vol(
    close: pd.Series,
    volume: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure Amihud-adjusted vol replacement for Point 53."""
    cfg = config or {}
    w = int(cfg.get("vol_window", 20))
    lam = float(cfg.get("amihud_lambda", 0.5))
    min_d = int(cfg.get("min_data_density", 50))
    fb = float(cfg.get("fallback_vol", 0.01))
    a_win = int(cfg.get("amihud_window", 20))

    if len(close) < min_d or len(volume) < min_d:
        logger.info("[POINT_53] insufficient data — fallback vol %.4f", fb)
        return fb

    vol = compute_amihud_adjusted_vol(close, volume, w, lam)
    if not np.isfinite(vol) or vol <= 0:
        vol = fb
    logger.info("[POINT_53] amihud_adj | lambda=%.2f w=%d -> vol=%.5f", lam, w, vol)
    return float(vol)


def compute_point_53_override(
    raw_vol: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    """Wrapper for Point 53: raw = c2c, new = Amihud-adjusted, engine route."""
    if engine is None:
        engine = BiasOverrideEngine()

    cfg = _load_point_53_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    v = pd.to_numeric(df.get("volume", df.get("quote_volume", 1.0)), errors="coerce")

    raw_val = float(raw_vol) if np.isfinite(raw_vol) else compute_close_to_close_vol(c, int(cfg.get("vol_window", 20)))
    new_val = compute_amihud_adjusted_realized_vol(c, v, config=cfg)

    final = engine.apply_override(
        point_id="53",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_53] decision | %s raw=%.5f new=%.5f final=%.5f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 53 Amihud-Adjusted Smoke ===")
    engine = BiasOverrideEngine()
    n = 80
    rng = np.random.default_rng(53)
    c = 100 + np.cumsum(rng.normal(0, 0.5, n))
    v = rng.uniform(1e5, 5e6, n)
    df = pd.DataFrame({"close": c, "volume": v})
    raw = 0.012
    final = compute_point_53_override(raw, df, "TEST53", engine=engine)
    print(f"raw={raw:.4f} -> final={final:.4f}")
    print("Smoke done.")