"""
KRONOS V1-ALT — Bias Override Point 55: "Temporal Volatility Resolution Loss"

Manual description:
  "Measuring volatility using only the standard deviation of low-frequency close prices."

Quant replacement:
  "Integrated Variance via High-Frequency Counts. Reconstruct local realized variance using
   sessional volume and transaction intensities: RV_t = sum (ln(C_i/O_i))^2 * (C_i / Q_i + eps)."

Uses shared compute_integrated_var_high_freq (proxy via count for high-freq intensity).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_integrated_var_high_freq, compute_close_to_close_vol
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_55")



_DEFAULT_POINT_55_CONFIG = {"vol_window": 20, "intensity_window": 20, "min_data_density": 50, "fallback_vol": 0.01}


def compute_high_freq_integrated_var(
    close: pd.Series,
    count: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    cfg = config or {}
    w = int(cfg.get("vol_window", 20))
    i_win = int(cfg.get("intensity_window", 20))
    min_d = int(cfg.get("min_data_density", 50))
    fb = float(cfg.get("fallback_vol", 0.01))

    if len(close) < min_d or len(count) < min_d:
        return fb

    vol = compute_integrated_var_high_freq(close, count, w)
    if not np.isfinite(vol) or vol <= 0:
        vol = fb
    logger.info("[POINT_55] integrated_hf | w=%d -> vol=%.5f", w, vol)
    return float(vol)


def compute_point_55_override(
    raw_vol: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_55_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    cnt = pd.to_numeric(df.get("count", df.get("volume", 1.0)), errors="coerce")

    raw_val = float(raw_vol) if np.isfinite(raw_vol) else compute_close_to_close_vol(c, int(cfg.get("vol_window", 20)))
    new_val = compute_high_freq_integrated_var(c, cnt, config=cfg)

    final = engine.apply_override(
        point_id="55",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_55] decision | %s raw=%.5f new=%.5f final=%.5f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 55 High-Freq Integrated Var Smoke ===")
    engine = BiasOverrideEngine()
    n = 80
    rng = np.random.default_rng(55)
    c = 100 + np.cumsum(rng.normal(0, 0.4, n))
    cnt = rng.randint(100, 5000, n)
    df = pd.DataFrame({"close": c, "count": cnt})
    raw = 0.01
    final = compute_point_55_override(raw, df, "TEST55", engine=engine)
    print(f"raw={raw:.4f} -> final={final:.4f}")

def _load_point_55_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_55", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_55_CONFIG





