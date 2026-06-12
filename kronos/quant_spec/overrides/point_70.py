"""
KRONOS V1-ALT — Bias Override Point 70: "Heavy-Tail Excess Kurtosis Ignorance"

Manual description:
  "Ignoring changes in tail fatness, which leads to model failures during market crises."

Quant replacement:
  "Rolling Fisher Kurtosis Estimator. Track distribution fat-tailedness:
   gamma_2,t = (1/W) * sum (r_i - mu)^4 / sigma^4 - 3."

Uses shared compute_rolling_kurtosis.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_rolling_kurtosis
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_70")



_DEFAULT_POINT_70_CONFIG = {"kurt_window": 50, "min_data_density": 40, "fallback_kurt": 0.0}


def compute_rolling_fisher_kurtosis(
    close: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    cfg = config or {}
    w = int(cfg.get("kurt_window", 50))
    min_d = int(cfg.get("min_data_density", 40))
    fb = float(cfg.get("fallback_kurt", 0.0))

    if len(close) < min_d:
        logger.info("[POINT_70] insufficient data — fallback kurt %.3f", fb)
        return fb

    r = (close / close.shift(1) - 1.0).dropna()
    kurt = compute_rolling_kurtosis(r, w)
    if not np.isfinite(kurt):
        kurt = fb
    logger.info("[POINT_70] rolling_kurt | window=%d -> kurt=%.4f", w, kurt)
    return float(kurt)


def compute_point_70_override(
    raw_kurt: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_70_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    r = (c / c.shift(1) - 1.0).dropna()
    raw_val = float(raw_kurt) if np.isfinite(raw_kurt) else float(r.tail(int(cfg.get("kurt_window", 50))).kurt() or 0.0)

    new_val = compute_rolling_fisher_kurtosis(c, config=cfg)

    final = engine.apply_override(
        point_id="70",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_70] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 70 Kurtosis Smoke ===")
    engine = BiasOverrideEngine()
    n = 80
    rng = np.random.default_rng(70)
    rets = rng.normal(0.0005, 0.008, n)
    rets[30:50] = rng.normal(0, 0.025, 20)  # fat tails
    c = 100 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({"close": c})
    raw = 2.5
    final = compute_point_70_override(raw, df, "TEST70", engine=engine)
    print(f"raw={raw:.3f} -> final={final:.3f}")

def _load_point_70_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_70", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_70_CONFIG





