"""
KRONOS V1-ALT — Bias Override Point 60: "Volatility Jump Discontinuity Ignorance"

Manual description:
  "Modeling volatility as a continuous Brownian motion, ignoring jump-discontinuity risk."

Quant replacement:
  "Bar-Level Realized Kernel with Jump Component. Separate continuous and jump components:
   RV_t = sum (ln(C_i/O_i))^2 * (C_i / Q_i + eps) ; Jump = max(0, RV_t - BV_t) where BV is bipower variation."

Uses shared compute_realized_kernel_with_jump (proxy).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_realized_kernel_with_jump, compute_close_to_close_vol
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_60")



_DEFAULT_POINT_60_CONFIG = {"vol_window": 20, "min_data_density": 50, "fallback_vol": 0.01, "jump_threshold": 2.0}


def compute_kernel_with_jump_vol(
    close: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    cfg = config or {}
    w = int(cfg.get("vol_window", 20))
    thresh = float(cfg.get("jump_threshold", 2.0))
    min_d = int(cfg.get("min_data_density", 50))
    fb = float(cfg.get("fallback_vol", 0.01))

    if len(close) < min_d:
        return fb

    res = compute_realized_kernel_with_jump(close, w, thresh)
    # Return continuous + jump component (total or continuous; here total for vol)
    total = res["cont"] + res["jump"]
    vol = np.sqrt(total) if total > 0 else fb
    logger.info("[POINT_60] kernel_jump | cont=%.5f jump=%.5f -> vol=%.5f", res["cont"], res["jump"], vol)
    return float(vol)


def compute_point_60_override(
    raw_vol: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_60_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    raw_val = float(raw_vol) if np.isfinite(raw_vol) else compute_close_to_close_vol(c, int(cfg.get("vol_window", 20)))
    new_val = compute_kernel_with_jump_vol(c, config=cfg)

    final = engine.apply_override(
        point_id="60",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_60] decision | %s raw=%.5f new=%.5f final=%.5f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 60 Kernel + Jump Smoke ===")
    engine = BiasOverrideEngine()
    n = 80
    rng = np.random.default_rng(60)
    rets = rng.normal(0, 0.008, n)
    rets[30] = -0.08  # jump
    c = 100 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({"close": c})
    raw = 0.01
    final = compute_point_60_override(raw, df, "TEST60", engine=engine)
    print(f"raw={raw:.4f} -> final={final:.4f}")

def _load_point_60_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_60", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_60_CONFIG

def compute_kernel_with_jump_vol(
    close: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    cfg = config or {}
    w = int(cfg.get("vol_window", 20))
    thresh = float(cfg.get("jump_threshold", 2.0))
    min_d = int(cfg.get("min_data_density", 50))
    fb = float(cfg.get("fallback_vol", 0.01))

    if len(close) < min_d:
        return fb

    res = compute_realized_kernel_with_jump(close, w, thresh)
    # Return continuous + jump component (total or continuous; here total for vol)
    total = res["cont"] + res["jump"]
    vol = np.sqrt(total) if total > 0 else fb
    logger.info("[POINT_60] kernel_jump | cont=%.5f jump=%.5f -> vol=%.5f", res["cont"], res["jump"], vol)
    return float(vol)


def compute_point_60_override(
    raw_vol: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_60_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    raw_val = float(raw_vol) if np.isfinite(raw_vol) else compute_close_to_close_vol(c, int(cfg.get("vol_window", 20)))
    new_val = compute_kernel_with_jump_vol(c, config=cfg)

    final = engine.apply_override(
        point_id="60",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_60] decision | %s raw=%.5f new=%.5f final=%.5f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 60 Kernel + Jump Smoke ===")
    engine = BiasOverrideEngine()
    n = 80
    rng = np.random.default_rng(60)
    rets = rng.normal(0, 0.008, n)
    rets[30] = -0.08  # jump
    c = 100 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({"close": c})
    raw = 0.01
    final = compute_point_60_override(raw, df, "TEST60", engine=engine)
    print(f"raw={raw:.4f} -> final={final:.4f}")
    print("Smoke done (proxy kernel).")