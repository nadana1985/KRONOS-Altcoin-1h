"""
KRONOS V1-ALT — Bias Override Point 74: "Structural Break Ignorance"

Manual description:
  "Assuming return distributions are stable across structural regime changes."

Quant replacement:
  "Cusum Structural Break Detector.
   Detect changes in the cumulative sum of recursive residuals."

Uses shared compute_cusum_break_detector.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_cusum_break_detector
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_74")



_DEFAULT_POINT_74_CONFIG = {"window": 100, "critical_value": 1.0, "min_data_density": 50, "fallback_break": False}


def compute_structural_break(
    returns: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Pure CUSUM structural break detection."""
    cfg = config or {}
    w = int(cfg.get("window", 100))
    cv = float(cfg.get("critical_value", 1.0))
    min_d = int(cfg.get("min_data_density", 50))

    if len(returns) < min_d:
        return {"break_detected": bool(cfg.get("fallback_break", False)), "cusum_stat": 0.0}

    result = compute_cusum_break_detector(returns, w, cv)
    logger.info("[POINT_74] cusum | stat=%.4f break=%s", result["cusum_stat"], result["break_detected"])
    return result


def compute_point_74_override(
    raw_break_indicator: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_74_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    raw_val = float(raw_break_indicator) if np.isfinite(raw_break_indicator) else 0.0
    rets = np.log((c / c.shift(1)).clip(lower=1e-12))

    result = compute_structural_break(rets, config=cfg)
    new_val = 1.0 if result["break_detected"] else 0.0

    final = engine.apply_override(
        point_id="74",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_74] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 74 CUSUM Break Detector Smoke ===")
    engine = BiasOverrideEngine()
    n = 150
    rng = np.random.default_rng(74)
    rets = np.concatenate([
        rng.normal(0.001, 0.01, 80),
        rng.normal(-0.002, 0.02, 70),  # regime shift
    ])
    c = 100 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({"close": c})
    final = compute_point_74_override(0.0, df, "TEST74", engine=engine)
    print(f"raw=0.000 -> final={final:.4f}")

def _load_point_74_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_74", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_74_CONFIG





