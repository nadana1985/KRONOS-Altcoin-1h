"""
KRONOS V1-ALT — Bias Override Point 61: "Normal Distribution Assumptions"

Manual description:
  "Assuming altcoin returns follow a symmetric normal distribution leads to severe model underestimations of downside risk."

Quant replacement:
  "Extreme Value Theory (EVT) Generalized Pareto Distribution (GPD). Parameterize distribution tails using GPD parameters:
   G(x) = 1 - (1 + xi * x / beta) ^ (-1/xi)."

Uses shared compute_evt_gpd_tail (simplified moment-based GPD scale proxy) + tail adjustment on base vol.

For production tail risk this would be paired with proper threshold exceedance modeling and GPD parameter fitting.
Here we provide a practical, causal, contained implementation with clear fallback.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_evt_gpd_tail, compute_close_to_close_vol
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_61")



_DEFAULT_POINT_61_CONFIG = {
            "threshold_quantile": 0.95,
            "gpd_xi": 0.2,
            "gpd_beta": 0.01,
            "min_data_density": 100,
            "fallback_tail_vol": 0.02,
        }


def compute_evt_gpd_tail_risk(
    close: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure (simplified) EVT GPD tail adjustment for Point 61."""
    cfg = config or {}
    q = float(cfg.get("threshold_quantile", 0.95))
    w = 100  # internal window for tail estimation (can be tuned via min_data)
    min_d = int(cfg.get("min_data_density", 100))
    fb = float(cfg.get("fallback_tail_vol", 0.02))

    if len(close) < min_d:
        logger.info("[POINT_61] insufficient data — fallback tail vol %.4f", fb)
        return fb

    tail_vol = compute_evt_gpd_tail(close, q, w)
    if not np.isfinite(tail_vol) or tail_vol <= 0:
        tail_vol = fb
    logger.info("[POINT_61] evt_gpd | q=%.2f -> tail_vol=%.5f", q, tail_vol)
    return float(tail_vol)


def compute_point_61_override(
    raw_vol: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_61_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    raw_val = float(raw_vol) if np.isfinite(raw_vol) else compute_close_to_close_vol(c, 50)

    new_val = compute_evt_gpd_tail_risk(c, config=cfg)

    final = engine.apply_override(
        point_id="61",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_61] decision | %s raw=%.5f new=%.5f final=%.5f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 61 EVT GPD Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(61)
    # Heavy tail regime
    rets = rng.normal(0.0005, 0.006, n)
    rets[40:60] = rng.normal(-0.03, 0.025, 20)
    c = 100 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({"close": c})
    raw = 0.01
    final = compute_point_61_override(raw, df, "TEST61", engine=engine)
    print(f"raw={raw:.4f} -> final={final:.4f}")

def _load_point_61_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_61", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_61_CONFIG





