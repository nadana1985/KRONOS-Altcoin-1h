"""
KRONOS V1-ALT — Bias Override Point 63: "Absolute Value Normalization (Min-Max Scaling)"

Manual description:
  "Normalizing features using static min-max calculations fails when encountering out-of-sample extreme events."

Quant replacement:
  "Quantile Transformer Mapping (Uniform CDF Transforms). Map features to standard normal distributions:
   X_t = Phi^{-1}( F(X_t) )."

Uses shared compute_quantile_transform for the core rank + normal-inverse mapping.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_quantile_transform
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_63")



_DEFAULT_POINT_63_CONFIG = {"rank_window": 100, "min_data_density": 100, "fallback_rank": 0.5, "clip_min": 0.05, "clip_max": 0.95}


def compute_quantile_transform_value(
    values: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure quantile transform: rank -> normal inverse."""
    cfg = config or {}
    w = int(cfg.get("rank_window", 100))
    min_d = int(cfg.get("min_data_density", 100))
    clip_min = float(cfg.get("clip_min", 0.05))
    clip_max = float(cfg.get("clip_max", 0.95))
    fb = float(cfg.get("fallback_rank", 0.5))

    if len(values) < min_d:
        logger.info("[POINT_63] insufficient data — fallback rank %.3f", fb)
        return fb

    z = compute_quantile_transform(values, w, clip_min=clip_min, clip_max=clip_max)
    logger.info("[POINT_63] quantile_transform | window=%d -> z=%.4f", w, z)
    return z


def compute_point_63_override(
    raw_value: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    feature_series: pd.Series = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_63_config(engine)

    raw_val = float(raw_value) if np.isfinite(raw_value) else 0.0
    series = feature_series if feature_series is not None else pd.to_numeric(df.get("close"), errors="coerce")

    new_val = compute_quantile_transform_value(series, config=cfg)

    final = engine.apply_override(
        point_id="63",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_63] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 63 Quantile Transformer Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(63)
    vals = pd.Series(rng.normal(0.5, 0.2, n))
    vals.iloc[100] = 3.0  # extreme outlier
    final = compute_point_63_override(2.5, pd.DataFrame({"close": vals}), "TEST63", engine=engine, feature_series=vals)
    print(f"raw=2.500 -> final={final:.4f}")

def _load_point_63_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_63", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_63_CONFIG

def compute_quantile_transform_value(
    values: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure quantile transform: rank -> normal inverse."""
    cfg = config or {}
    w = int(cfg.get("rank_window", 100))
    min_d = int(cfg.get("min_data_density", 100))
    clip_min = float(cfg.get("clip_min", 0.05))
    clip_max = float(cfg.get("clip_max", 0.95))
    fb = float(cfg.get("fallback_rank", 0.5))

    if len(values) < min_d:
        logger.info("[POINT_63] insufficient data — fallback rank %.3f", fb)
        return fb

    z = compute_quantile_transform(values, w, clip_min=clip_min, clip_max=clip_max)
    logger.info("[POINT_63] quantile_transform | window=%d -> z=%.4f", w, z)
    return z


def compute_point_63_override(
    raw_value: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    feature_series: pd.Series = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_63_config(engine)

    raw_val = float(raw_value) if np.isfinite(raw_value) else 0.0
    series = feature_series if feature_series is not None else pd.to_numeric(df.get("close"), errors="coerce")

    new_val = compute_quantile_transform_value(series, config=cfg)

    final = engine.apply_override(
        point_id="63",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_63] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 63 Quantile Transformer Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(63)
    vals = pd.Series(rng.normal(0.5, 0.2, n))
    vals.iloc[100] = 3.0  # extreme outlier
    final = compute_point_63_override(2.5, pd.DataFrame({"close": vals}), "TEST63", engine=engine, feature_series=vals)
    print(f"raw=2.500 -> final={final:.4f}")
    print("Smoke done.")
