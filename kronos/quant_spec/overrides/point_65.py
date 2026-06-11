"""
KRONOS V1-ALT — Bias Override Point 65: "Stationary Autoregressive Parameter Assumptions"

Manual description:
  "Modeling returns using stationary autoregressive models."

Quant replacement:
  "Kalman-Filter Dynamic Autoregressive Parameters. Update AR parameters as state variables
   using Kalman Filter updates: y_t = x_t * beta_t + epsilon."

Uses shared compute_kalman_dynamic_ar.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_kalman_dynamic_ar
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_65")



_DEFAULT_POINT_65_CONFIG = {"ar_order": 2, "process_noise": 0.01, "measurement_noise": 0.05, "min_data_density": 100, "fallback_ar_coeff": 0.1}


def compute_dynamic_ar_params(
    returns: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Pure Kalman-Filter dynamic AR estimation."""
    cfg = config or {}
    ar_order = int(cfg.get("ar_order", 2))
    pn = float(cfg.get("process_noise", 0.01))
    mn = float(cfg.get("measurement_noise", 0.05))
    w = 100
    min_d = int(cfg.get("min_data_density", 100))

    if len(returns) < min_d:
        return {"phis": [0.0] * ar_order, "resid_var": 1e-4}

    result = compute_kalman_dynamic_ar(returns, ar_order, pn, mn, w)
    logger.info("[POINT_65] kalman_ar | phis=%s resid_var=%.6f", result["phis"], result["resid_var"])
    return result


def compute_point_65_override(
    raw_ar_coeff: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_65_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    raw_val = float(raw_ar_coeff) if np.isfinite(raw_ar_coeff) else float(cfg.get("fallback_ar_coeff", 0.1))

    result = compute_dynamic_ar_params(c, config=cfg)
    # Use sum of absolute AR coefficients as dynamic replacement
    new_val = float(np.sum(np.abs(result["phis"]))) if result["phis"] else raw_val

    final = engine.apply_override(
        point_id="65",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_65] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 65 Kalman Dynamic AR Smoke ===")
    engine = BiasOverrideEngine()
    n = 200
    rng = np.random.default_rng(65)
    # AR(1) with changing coefficient
    rets = np.zeros(n)
    rets[0] = rng.normal(0, 0.01)
    for i in range(1, n):
        phi = 0.3 if i < 100 else 0.1
        rets[i] = phi * rets[i-1] + rng.normal(0, 0.01)
    df = pd.DataFrame({"close": 100 * np.exp(np.cumsum(rets))})
    final = compute_point_65_override(0.3, df, "TEST65", engine=engine)
    print(f"raw=0.3000 -> final={final:.4f}")

def _load_point_65_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_65", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_65_CONFIG

def compute_dynamic_ar_params(
    returns: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Pure Kalman-Filter dynamic AR estimation."""
    cfg = config or {}
    ar_order = int(cfg.get("ar_order", 2))
    pn = float(cfg.get("process_noise", 0.01))
    mn = float(cfg.get("measurement_noise", 0.05))
    w = 100
    min_d = int(cfg.get("min_data_density", 100))

    if len(returns) < min_d:
        return {"phis": [0.0] * ar_order, "resid_var": 1e-4}

    result = compute_kalman_dynamic_ar(returns, ar_order, pn, mn, w)
    logger.info("[POINT_65] kalman_ar | phis=%s resid_var=%.6f", result["phis"], result["resid_var"])
    return result


def compute_point_65_override(
    raw_ar_coeff: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_65_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    raw_val = float(raw_ar_coeff) if np.isfinite(raw_ar_coeff) else float(cfg.get("fallback_ar_coeff", 0.1))

    result = compute_dynamic_ar_params(c, config=cfg)
    # Use sum of absolute AR coefficients as dynamic replacement
    new_val = float(np.sum(np.abs(result["phis"]))) if result["phis"] else raw_val

    final = engine.apply_override(
        point_id="65",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_65] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 65 Kalman Dynamic AR Smoke ===")
    engine = BiasOverrideEngine()
    n = 200
    rng = np.random.default_rng(65)
    # AR(1) with changing coefficient
    rets = np.zeros(n)
    rets[0] = rng.normal(0, 0.01)
    for i in range(1, n):
        phi = 0.3 if i < 100 else 0.1
        rets[i] = phi * rets[i-1] + rng.normal(0, 0.01)
    df = pd.DataFrame({"close": 100 * np.exp(np.cumsum(rets))})
    final = compute_point_65_override(0.3, df, "TEST65", engine=engine)
    print(f"raw=0.3000 -> final={final:.4f}")
    print("Smoke done.")
