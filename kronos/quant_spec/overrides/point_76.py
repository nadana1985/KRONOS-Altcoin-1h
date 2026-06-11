"""
KRONOS V1-ALT — Bias Override Point 76: "Unsupervised Feature Clustering Arbitrary Weighting"

Manual description:
  "Passing unweighted, collinear features to unsupervised clustering algorithms."

Quant replacement:
  "Mutual Information (MI) Distance Metric Scaling.
   Scale features by their mutual information relative to the target before clustering."

Uses shared compute_mutual_information_distance.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_mutual_information_distance
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_76")



_DEFAULT_POINT_76_CONFIG = {"n_bins": 10, "min_data_density": 50, "fallback_weight": 1.0}


def compute_mi_weights(
    features: pd.DataFrame,
    target: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> pd.Series:
    """Pure MI distance scaling for feature weighting."""
    cfg = config or {}
    n_bins = int(cfg.get("n_bins", 10))
    min_d = int(cfg.get("min_data_density", 50))

    if len(features) < min_d or features.shape[1] < 1:
        return pd.Series(1.0, index=features.columns)

    mi_weights = compute_mutual_information_distance(features, target, n_bins)
    logger.info("[POINT_76] mi_weights mean=%.4f", mi_weights.mean())
    return mi_weights


def compute_point_76_override(
    raw_cluster_weight: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    features: pd.DataFrame = None,
    target: pd.Series = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_76_config(engine)

    raw_val = float(raw_cluster_weight) if np.isfinite(raw_cluster_weight) else 1.0

    if features is not None and target is not None:
        weights = compute_mi_weights(features, target, config=cfg)
        new_val = float(weights.mean())
    else:
        new_val = float(cfg.get("fallback_weight", 1.0))

    final = engine.apply_override(
        point_id="76",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_76] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 76 MI Distance Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(76)
    x1 = rng.normal(0, 1, n)
    x2 = rng.normal(0, 1, n)
    target = pd.Series(0.5 * x1 + rng.normal(0, 0.1, n))
    feats = pd.DataFrame({"x1": x1, "x2": x2})
    final = compute_point_76_override(1.0, pd.DataFrame({"close": x1}), "TEST76", engine=engine, features=feats, target=target)
    print(f"raw_weight=1.000 -> final={final:.4f}")

def _load_point_76_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_76", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_76_CONFIG

def compute_mi_weights(
    features: pd.DataFrame,
    target: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> pd.Series:
    """Pure MI distance scaling for feature weighting."""
    cfg = config or {}
    n_bins = int(cfg.get("n_bins", 10))
    min_d = int(cfg.get("min_data_density", 50))

    if len(features) < min_d or features.shape[1] < 1:
        return pd.Series(1.0, index=features.columns)

    mi_weights = compute_mutual_information_distance(features, target, n_bins)
    logger.info("[POINT_76] mi_weights mean=%.4f", mi_weights.mean())
    return mi_weights


def compute_point_76_override(
    raw_cluster_weight: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    features: pd.DataFrame = None,
    target: pd.Series = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_76_config(engine)

    raw_val = float(raw_cluster_weight) if np.isfinite(raw_cluster_weight) else 1.0

    if features is not None and target is not None:
        weights = compute_mi_weights(features, target, config=cfg)
        new_val = float(weights.mean())
    else:
        new_val = float(cfg.get("fallback_weight", 1.0))

    final = engine.apply_override(
        point_id="76",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_76] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 76 MI Distance Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(76)
    x1 = rng.normal(0, 1, n)
    x2 = rng.normal(0, 1, n)
    target = pd.Series(0.5 * x1 + rng.normal(0, 0.1, n))
    feats = pd.DataFrame({"x1": x1, "x2": x2})
    final = compute_point_76_override(1.0, pd.DataFrame({"close": x1}), "TEST76", engine=engine, features=feats, target=target)
    print(f"raw_weight=1.000 -> final={final:.4f}")
    print("Smoke done.")
