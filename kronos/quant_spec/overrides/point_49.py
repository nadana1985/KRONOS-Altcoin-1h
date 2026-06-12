"""
KRONOS V1-ALT — Bias Override Point 49: "Overnight Gap Blindness"

Manual description:
  "Classical range estimators (e.g., Parkinson) ignore price gaps occurring between
   adjacent sessional candles."

Quant replacement:
  "Garman-Klass Volatility Estimator with Overnight Corrections. Estimate volatility
   incorporating opening jumps: sigma_GK^2 = 1/W * sum [a * (ln(O_i/C_{i-1}))^2 + (1-a) * (0.5*(ln(H_i/L_i))^2 - (2*ln(2)-1)*(ln(C_i/O_i))^2 ) ]."

Uses shared compute_garman_klass_vol.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_garman_klass_vol, compute_close_to_close_vol
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_49")



_DEFAULT_POINT_49_CONFIG = {"vol_window": 20, "gk_overnight_weight": 0.5, "min_data_density": 50, "fallback_vol": 0.01}


def compute_garman_klass_volatility(
    open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    cfg = config or {}
    w = int(cfg.get("vol_window", 20))
    a = float(cfg.get("gk_overnight_weight", 0.5))
    min_d = int(cfg.get("min_data_density", 50))
    fb = float(cfg.get("fallback_vol", 0.01))

    if len(close) < min_d:
        return fb
    pc = close.shift(1)
    vol = compute_garman_klass_vol(open_, high, low, close, pc, w, a)
    if not np.isfinite(vol) or vol <= 0:
        vol = fb
    logger.info("[POINT_49] garman_klass | a=%.2f w=%d -> vol=%.5f", a, w, vol)
    return float(vol)


def compute_point_49_override(
    raw_vol: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_49_config(engine)

    o = pd.to_numeric(df.get("open", df.get("close")), errors="coerce")
    h = pd.to_numeric(df.get("high"), errors="coerce")
    l = pd.to_numeric(df.get("low"), errors="coerce")
    c = pd.to_numeric(df.get("close"), errors="coerce")

    raw_val = float(raw_vol) if np.isfinite(raw_vol) else compute_close_to_close_vol(c, int(cfg.get("vol_window", 20)))
    new_val = compute_garman_klass_volatility(o, h, l, c, config=cfg)

    final = engine.apply_override(
        point_id="49",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_49] decision | %s raw=%.5f new=%.5f final=%.5f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 49 GK Smoke ===")
    engine = BiasOverrideEngine()
    n = 80
    rng = np.random.default_rng(49)
    rets = rng.normal(0.0002, 0.007, n)
    c = 100 * np.exp(np.cumsum(rets))
    # Simulate gaps
    gap = rng.normal(0, 0.003, n)
    o = c * (1 + gap)
    h = np.maximum(c, o) * (1 + rng.uniform(0, 0.004, n))
    l = np.minimum(c, o) * (1 - rng.uniform(0, 0.004, n))
    df = pd.DataFrame({"open": o, "high": h, "low": l, "close": c})
    raw = 0.01
    final = compute_point_49_override(raw, df, "TEST49", engine=engine)
    print(f"raw={raw:.4f} -> final={final:.4f}")

def _load_point_49_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_49", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_49_CONFIG





