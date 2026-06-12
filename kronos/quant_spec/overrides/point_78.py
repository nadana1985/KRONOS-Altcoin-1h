"""
KRONOS V1-ALT — Bias Override Point 78: "Symmetric Target Labeling Loss Boundaries"

Manual description:
  "Defining target labels using symmetric percentage boundaries, ignoring historical asymmetry."

Quant replacement:
  "Volatility-Symmetric Dynamic Multi-Barrier Target Labels.
   Set barriers relative to local volatility: Barrier_t = +/- sigma_rolling,t * phi."

Uses shared compute_vol_symmetric_barrier_labels.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_vol_symmetric_barrier_labels
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_78")



_DEFAULT_POINT_78_CONFIG = {"barrier_phi": 2.0, "window": 50, "horizon": 10, "min_data_density": 50, "fallback_label": 0}


def compute_dynamic_barrier_label(
    returns: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Pure volatility-symmetric barrier labeling."""
    cfg = config or {}
    phi = float(cfg.get("barrier_phi", 2.0))
    w = int(cfg.get("window", 50))
    h = int(cfg.get("horizon", 10))
    min_d = int(cfg.get("min_data_density", 50))

    if len(returns) < min_d:
        return {"label": int(cfg.get("fallback_label", 0)), "barrier_upper": 0.01, "barrier_lower": -0.01}

    result = compute_vol_symmetric_barrier_labels(returns, phi, w, h)
    logger.info("[POINT_78] barrier | label=%d upper=%.6f lower=%.6f", result["label"], result["barrier_upper"], result["barrier_lower"])
    return result


def compute_point_78_override(
    raw_label: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_78_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    raw_val = float(raw_label) if np.isfinite(raw_label) else 0.0
    rets = np.log((c / c.shift(1)).clip(lower=1e-12))

    result = compute_dynamic_barrier_label(rets, config=cfg)
    new_val = float(result["label"])

    final = engine.apply_override(
        point_id="78",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_78] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 78 Vol-Symmetric Barriers Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(78)
    rets = rng.normal(0.0005, 0.01, n)
    rets[90:95] = rng.normal(-0.03, 0.01, 5)  # crash
    c = 100 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({"close": c})
    final = compute_point_78_override(0.0, df, "TEST78", engine=engine)
    print(f"raw_label=0.000 -> final={final:.4f}")

def _load_point_78_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_78", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_78_CONFIG





