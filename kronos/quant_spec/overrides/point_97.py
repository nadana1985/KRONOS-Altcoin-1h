"""
KRONOS V1-ALT — Bias Override Point 97: "Uniform Performance Attributions"

Manual description:
  "Evaluating performance using unadjusted total return metrics, ignoring systemic risk and coin beta."

Quant replacement:
  "Beta-Neutral Risk-Adjusted Attribution (Jensen's Alpha).
   alpha_i,t = R_i,t - [R_f,t + beta_i,t * (R_m,t - R_f,t)]."

Uses shared compute_jensen_alpha.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_jensen_alpha
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_97")



_DEFAULT_POINT_97_CONFIG = {"window": 50, "risk_free_rate": 0.0, "min_data_density": 30, "fallback_alpha": 0.0}


def compute_risk_adjusted_alpha(
    local_returns: pd.Series,
    market_returns: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure Jensen's Alpha computation."""
    cfg = config or {}
    w = int(cfg.get("window", 50))
    rf = float(cfg.get("risk_free_rate", 0.0))
    min_d = int(cfg.get("min_data_density", 30))

    if len(local_returns) < min_d or len(market_returns) < min_d:
        return float(cfg.get("fallback_alpha", 0.0))

    alpha = compute_jensen_alpha(local_returns, market_returns, rf, w)
    logger.info("[POINT_97] jensen_alpha=%.6f", alpha)
    return alpha


def compute_point_97_override(
    raw_attribution: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    market_returns: pd.Series = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_97_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    raw_val = float(raw_attribution) if np.isfinite(raw_attribution) else 0.0
    local_rets = np.log((c / c.shift(1)).clip(lower=1e-12))

    if market_returns is not None:
        new_val = compute_risk_adjusted_alpha(local_rets, market_returns, config=cfg)
    else:
        new_val = raw_val

    final = engine.apply_override(
        point_id="97",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_97] decision | %s raw=%.6f new=%.6f final=%.6f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 97 Jensen's Alpha Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(97)
    mkt = rng.normal(0.001, 0.01, n)
    local = 0.0015 + 0.8 * mkt + rng.normal(0, 0.005, n)  # alpha = 0.0005
    c = 100 * np.exp(np.cumsum(local))
    df = pd.DataFrame({"close": c})
    final = compute_point_97_override(0.0, df, "TEST97", engine=engine, market_returns=pd.Series(mkt))
    print(f"raw_attr=0.000 -> final={final:.6f}")

def _load_point_97_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_97", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_97_CONFIG





