"""
KRONOS V1-ALT — Bias Override Point 96: "Uniform Liquidation Correlation Assumptions"

Manual description:
  "Assuming all altcoins exhibit uniform correlation patterns during systemic liquidations."

Quant replacement:
  "Dynamic Minimum Variance Portfolio Sizing.
   Scale position sizes using conditional covariance estimates to minimize portfolio risk."

Uses shared compute_min_variance_portfolio.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_min_variance_portfolio
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_96")



_DEFAULT_POINT_96_CONFIG = {"window": 100, "min_weight": 0.0, "max_weight": 0.3, "min_data_density": 50, "fallback_weight": 0.25}


def compute_min_var_weights(
    returns: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> np.ndarray:
    """Pure minimum variance portfolio weights."""
    cfg = config or {}
    w = int(cfg.get("window", 100))
    min_w = float(cfg.get("min_weight", 0.0))
    max_w = float(cfg.get("max_weight", 0.3))
    min_d = int(cfg.get("min_data_density", 50))

    if len(returns) < min_d or returns.shape[1] < 2:
        n = returns.shape[1] if returns.shape[1] > 0 else 1
        return np.ones(n) / n

    cov = returns.tail(w).cov().values
    weights = compute_min_variance_portfolio(cov, min_w, max_w)
    logger.info("[POINT_96] min_var_weights=%s", [f"{ww:.4f}" for ww in weights])
    return weights


def compute_point_96_override(
    raw_portfolio_weight: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    returns: pd.DataFrame = None,
    asset_idx: int = 0,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_96_config(engine)

    raw_val = float(raw_portfolio_weight) if np.isfinite(raw_portfolio_weight) else 0.25

    if returns is not None and returns.shape[1] >= 2:
        weights = compute_min_var_weights(returns, config=cfg)
        idx = min(asset_idx, len(weights) - 1)
        new_val = float(weights[idx])
    else:
        new_val = float(cfg.get("fallback_weight", 0.25))

    final = engine.apply_override(
        point_id="96",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_96] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 96 Min Variance Portfolio Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(96)
    x = rng.normal(0, 0.01, n)
    y = rng.normal(0, 0.02, n)
    z = rng.normal(0, 0.005, n)
    rets = pd.DataFrame({"A": x, "B": y, "C": z})
    final = compute_point_96_override(0.25, pd.DataFrame({"close": x}), "TEST96", engine=engine, returns=rets, asset_idx=0)
    print(f"raw_weight=0.250 -> final={final:.4f}")

def _load_point_96_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_96", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_96_CONFIG

def compute_min_var_weights(
    returns: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> np.ndarray:
    """Pure minimum variance portfolio weights."""
    cfg = config or {}
    w = int(cfg.get("window", 100))
    min_w = float(cfg.get("min_weight", 0.0))
    max_w = float(cfg.get("max_weight", 0.3))
    min_d = int(cfg.get("min_data_density", 50))

    if len(returns) < min_d or returns.shape[1] < 2:
        n = returns.shape[1] if returns.shape[1] > 0 else 1
        return np.ones(n) / n

    cov = returns.tail(w).cov().values
    weights = compute_min_variance_portfolio(cov, min_w, max_w)
    logger.info("[POINT_96] min_var_weights=%s", [f"{ww:.4f}" for ww in weights])
    return weights


def compute_point_96_override(
    raw_portfolio_weight: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    returns: pd.DataFrame = None,
    asset_idx: int = 0,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_96_config(engine)

    raw_val = float(raw_portfolio_weight) if np.isfinite(raw_portfolio_weight) else 0.25

    if returns is not None and returns.shape[1] >= 2:
        weights = compute_min_var_weights(returns, config=cfg)
        idx = min(asset_idx, len(weights) - 1)
        new_val = float(weights[idx])
    else:
        new_val = float(cfg.get("fallback_weight", 0.25))

    final = engine.apply_override(
        point_id="96",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_96] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 96 Min Variance Portfolio Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(96)
    x = rng.normal(0, 0.01, n)
    y = rng.normal(0, 0.02, n)
    z = rng.normal(0, 0.005, n)
    rets = pd.DataFrame({"A": x, "B": y, "C": z})
    final = compute_point_96_override(0.25, pd.DataFrame({"close": x}), "TEST96", engine=engine, returns=rets, asset_idx=0)
    print(f"raw_weight=0.250 -> final={final:.4f}")
    print("Smoke done.")
