"""
KRONOS V1-ALT — Bias Override Point 67: "Homoskedastic Error Term Assumptions"

Manual description:
  "Assuming regression error terms are homoskedastic across different assets."

Quant replacement:
  "White's Heteroskedasticity-Consistent Covariance Estimator.
   Adjust regression standard errors: Sigma_b = (X'X)^{-1} X' Omega X (X'X)^{-1}."

Uses shared compute_white_heteroskedastic_se.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_white_heteroskedastic_se
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_67")



_DEFAULT_POINT_67_CONFIG = {"regression_window": 50, "min_data_density": 50, "fallback_se_ratio": 1.0}


def compute_heteroskedastic_se_ratio(
    returns: pd.Series,
    volume: pd.Series = None,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure White's HC SE ratio: HC_se / OLS_se averaged across features."""
    cfg = config or {}
    w = int(cfg.get("regression_window", 50))
    min_d = int(cfg.get("min_data_density", 50))

    r = pd.to_numeric(returns, errors="coerce").dropna().tail(w)
    if len(r) < min_d:
        return float(cfg.get("fallback_se_ratio", 1.0))

    # Simple regression: returns ~ lagged_returns
    y = r.iloc[1:].values
    X = np.column_stack([np.ones(len(y)), r.iloc[:-1].values])
    if len(y) < 3:
        return 1.0

    try:
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        resid = y - X @ beta
        ols_se = np.sqrt(np.diag(np.linalg.inv(X.T @ X + 1e-8 * np.eye(X.shape[1]))))
        hc_se = compute_white_heteroskedastic_se(X, resid)
        ratio = float(np.mean(hc_se / np.maximum(ols_se, 1e-12)))
    except (np.linalg.LinAlgError, ZeroDivisionError):
        ratio = 1.0

    ratio = float(np.clip(ratio, 0.1, 10.0))
    logger.info("[POINT_67] white_hc_se_ratio=%.4f", ratio)
    return ratio


def compute_point_67_override(
    raw_se: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_67_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    raw_val = float(raw_se) if np.isfinite(raw_se) else 1.0

    ratio = compute_heteroskedastic_se_ratio(c, config=cfg)
    new_val = raw_val * ratio

    final = engine.apply_override(
        point_id="67",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_67] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 67 White's HC SE Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(67)
    rets = rng.normal(0, 0.01, n)
    # Heteroskedastic regime change
    rets[60:80] *= 5
    df = pd.DataFrame({"close": 100 * np.exp(np.cumsum(rets))})
    final = compute_point_67_override(0.01, df, "TEST67", engine=engine)
    print(f"raw_se=0.0100 -> final={final:.4f}")

def _load_point_67_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_67", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_67_CONFIG

def compute_heteroskedastic_se_ratio(
    returns: pd.Series,
    volume: pd.Series = None,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure White's HC SE ratio: HC_se / OLS_se averaged across features."""
    cfg = config or {}
    w = int(cfg.get("regression_window", 50))
    min_d = int(cfg.get("min_data_density", 50))

    r = pd.to_numeric(returns, errors="coerce").dropna().tail(w)
    if len(r) < min_d:
        return float(cfg.get("fallback_se_ratio", 1.0))

    # Simple regression: returns ~ lagged_returns
    y = r.iloc[1:].values
    X = np.column_stack([np.ones(len(y)), r.iloc[:-1].values])
    if len(y) < 3:
        return 1.0

    try:
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
        resid = y - X @ beta
        ols_se = np.sqrt(np.diag(np.linalg.inv(X.T @ X + 1e-8 * np.eye(X.shape[1]))))
        hc_se = compute_white_heteroskedastic_se(X, resid)
        ratio = float(np.mean(hc_se / np.maximum(ols_se, 1e-12)))
    except (np.linalg.LinAlgError, ZeroDivisionError):
        ratio = 1.0

    ratio = float(np.clip(ratio, 0.1, 10.0))
    logger.info("[POINT_67] white_hc_se_ratio=%.4f", ratio)
    return ratio


def compute_point_67_override(
    raw_se: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_67_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    raw_val = float(raw_se) if np.isfinite(raw_se) else 1.0

    ratio = compute_heteroskedastic_se_ratio(c, config=cfg)
    new_val = raw_val * ratio

    final = engine.apply_override(
        point_id="67",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_67] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 67 White's HC SE Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(67)
    rets = rng.normal(0, 0.01, n)
    # Heteroskedastic regime change
    rets[60:80] *= 5
    df = pd.DataFrame({"close": 100 * np.exp(np.cumsum(rets))})
    final = compute_point_67_override(0.01, df, "TEST67", engine=engine)
    print(f"raw_se=0.0100 -> final={final:.4f}")
    print("Smoke done.")
