"""
KRONOS V1-ALT — Bias Override Point 71: "Static Beta Systematic Risk Scaling"

Manual description:
  "Static beta systematic risk scaling."

Quant replacement:
  "Kalman-Filter Dynamic Beta Estimator. Update beta coefficients recursively on each new bar."

Uses shared compute_kalman_dynamic_beta.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_kalman_dynamic_beta
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_71")



_DEFAULT_POINT_71_CONFIG = {"beta_window": 100, "process_noise": 0.01, "measurement_noise": 0.05, "min_data_density": 50, "fallback_beta": 1.0}


def compute_dynamic_beta(
    local_returns: pd.Series,
    market_returns: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure Kalman-Filter dynamic beta estimation."""
    cfg = config or {}
    w = int(cfg.get("beta_window", 100))
    pn = float(cfg.get("process_noise", 0.01))
    mn = float(cfg.get("measurement_noise", 0.05))
    min_d = int(cfg.get("min_data_density", 50))

    if len(local_returns) < min_d or len(market_returns) < min_d:
        return float(cfg.get("fallback_beta", 1.0))

    result = compute_kalman_dynamic_beta(local_returns, market_returns, pn, mn, w)
    beta = result["beta"]
    logger.info("[POINT_71] kalman_beta=%.4f alpha=%.6f", beta, result["alpha"])
    return float(beta)


def compute_point_71_override(
    raw_beta: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    market_returns: pd.Series = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_71_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    raw_val = float(raw_beta) if np.isfinite(raw_beta) else 1.0
    local_rets = np.log((c / c.shift(1)).clip(lower=1e-12))

    if market_returns is not None:
        new_val = compute_dynamic_beta(local_rets, market_returns, config=cfg)
    else:
        new_val = raw_val  # fallback: no market data

    final = engine.apply_override(
        point_id="71",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_71] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 71 Kalman Dynamic Beta Smoke ===")
    engine = BiasOverrideEngine()
    n = 200
    rng = np.random.default_rng(71)
    mkt = rng.normal(0, 0.01, n)
    beta_true = np.where(np.arange(n) < 100, 1.2, 0.8)
    local = beta_true * mkt + rng.normal(0, 0.005, n)
    df = pd.DataFrame({"close": 100 * np.exp(np.cumsum(local))})
    mkt_s = pd.Series(mkt)
    final = compute_point_71_override(1.0, df, "TEST71", engine=engine, market_returns=mkt_s)
    print(f"raw_beta=1.000 -> final={final:.4f}")

def _load_point_71_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_71", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_71_CONFIG

def compute_dynamic_beta(
    local_returns: pd.Series,
    market_returns: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure Kalman-Filter dynamic beta estimation."""
    cfg = config or {}
    w = int(cfg.get("beta_window", 100))
    pn = float(cfg.get("process_noise", 0.01))
    mn = float(cfg.get("measurement_noise", 0.05))
    min_d = int(cfg.get("min_data_density", 50))

    if len(local_returns) < min_d or len(market_returns) < min_d:
        return float(cfg.get("fallback_beta", 1.0))

    result = compute_kalman_dynamic_beta(local_returns, market_returns, pn, mn, w)
    beta = result["beta"]
    logger.info("[POINT_71] kalman_beta=%.4f alpha=%.6f", beta, result["alpha"])
    return float(beta)


def compute_point_71_override(
    raw_beta: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    market_returns: pd.Series = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_71_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    raw_val = float(raw_beta) if np.isfinite(raw_beta) else 1.0
    local_rets = np.log((c / c.shift(1)).clip(lower=1e-12))

    if market_returns is not None:
        new_val = compute_dynamic_beta(local_rets, market_returns, config=cfg)
    else:
        new_val = raw_val  # fallback: no market data

    final = engine.apply_override(
        point_id="71",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_71] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 71 Kalman Dynamic Beta Smoke ===")
    engine = BiasOverrideEngine()
    n = 200
    rng = np.random.default_rng(71)
    mkt = rng.normal(0, 0.01, n)
    beta_true = np.where(np.arange(n) < 100, 1.2, 0.8)
    local = beta_true * mkt + rng.normal(0, 0.005, n)
    df = pd.DataFrame({"close": 100 * np.exp(np.cumsum(local))})
    mkt_s = pd.Series(mkt)
    final = compute_point_71_override(1.0, df, "TEST71", engine=engine, market_returns=mkt_s)
    print(f"raw_beta=1.000 -> final={final:.4f}")
    print("Smoke done.")
