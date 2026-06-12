"""
KRONOS V1-ALT — Bias Override Point 99: "Static Risk Budgeting Bias"

Manual description:
  "Applying fixed risk budgets across assets without adapting to changing market conditions or liquidity."

Quant replacement:
  "Dynamic Risk Parity with Liquidity Adjustment.
   w_i,t = (1 / sigma_i,t) / sum(1/sigma_j,t) * e^(-lambda * Illiq_i,t)."

Uses shared compute_dynamic_risk_parity.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_dynamic_risk_parity
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_99")



_DEFAULT_POINT_99_CONFIG = {"lambda_illiq": 0.5, "min_weight": 0.0, "max_weight": 0.3, "min_data_density": 50, "fallback_weight": 0.25}


def compute_risk_parity_weights(
    returns: pd.DataFrame,
    illiquidity: np.ndarray = None,
    config: Optional[Dict[str, Any]] = None,
) -> np.ndarray:
    """Pure dynamic risk parity with liquidity adjustment."""
    cfg = config or {}
    lam = float(cfg.get("lambda_illiq", 0.5))
    min_w = float(cfg.get("min_weight", 0.0))
    max_w = float(cfg.get("max_weight", 0.3))
    min_d = int(cfg.get("min_data_density", 50))

    if len(returns) < min_d or returns.shape[1] < 1:
        n = returns.shape[1] if returns.shape[1] > 0 else 1
        return np.ones(n) / n

    vols = returns.tail(min_d).std().values
    weights = compute_dynamic_risk_parity(vols, illiquidity, lam, min_w, max_w)
    logger.info("[POINT_99] risk_parity_weights=%s", [f"{ww:.4f}" for ww in weights])
    return weights


def compute_point_99_override(
    raw_risk_budget: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    returns: pd.DataFrame = None,
    asset_idx: int = 0,
    illiquidity: np.ndarray = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_99_config(engine)

    raw_val = float(raw_risk_budget) if np.isfinite(raw_risk_budget) else 0.25

    if returns is not None and returns.shape[1] >= 1:
        weights = compute_risk_parity_weights(returns, illiquidity, config=cfg)
        idx = min(asset_idx, len(weights) - 1)
        new_val = float(weights[idx])
    else:
        new_val = float(cfg.get("fallback_weight", 0.25))

    final = engine.apply_override(
        point_id="99",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_99] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 99 Dynamic Risk Parity Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(99)
    x = rng.normal(0, 0.01, n)
    y = rng.normal(0, 0.02, n)
    z = rng.normal(0, 0.005, n)
    rets = pd.DataFrame({"A": x, "B": y, "C": z})
    illiq = np.array([0.1, 0.5, 0.05])
    final = compute_point_99_override(0.25, pd.DataFrame({"close": x}), "TEST99", engine=engine, returns=rets, asset_idx=0, illiquidity=illiq)
    print(f"raw_budget=0.250 -> final={final:.4f}")

def _load_point_99_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_99", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_99_CONFIG





