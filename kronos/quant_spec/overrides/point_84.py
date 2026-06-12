"""
KRONOS V1-ALT — Bias Override Point 84: "Unbalanced Spatial Density Clustering"

Manual description:
  "Applying spatial density clustering without correcting for variable scaling."

Quant replacement:
  "Standardized Mahalanobis Distance Metrics.
   Compute cluster distances using covariance matrices to prevent nominal scale distortions."

Uses shared compute_mahalanobis_distance.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_mahalanobis_distance
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_84")



_DEFAULT_POINT_84_CONFIG = {"window": 50, "min_data_density": 30, "fallback_distance": 0.0}


def compute_mahalanobis_cluster_distance(
    features: pd.DataFrame,
    x_idx: int = -2,
    y_idx: int = -1,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure Mahalanobis distance between two observations."""
    cfg = config or {}
    w = int(cfg.get("window", 50))
    min_d = int(cfg.get("min_data_density", 30))

    if len(features) < min_d or features.shape[1] < 2:
        return float(cfg.get("fallback_distance", 0.0))

    recent = features.tail(w).dropna()
    if len(recent) < min_d:
        return float(cfg.get("fallback_distance", 0.0))

    X = recent.values
    try:
        cov = np.cov(X.T)
        cov_inv = np.linalg.inv(cov + 1e-6 * np.eye(cov.shape[0]))
    except np.linalg.LinAlgError:
        cov_inv = np.eye(X.shape[1])

    x = X[x_idx]
    y = X[y_idx]
    d = compute_mahalanobis_distance(x, y, cov_inv)
    logger.info("[POINT_84] mahalanobis_distance=%.4f", d)
    return d


def compute_point_84_override(
    raw_distance: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    features: pd.DataFrame = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_84_config(engine)

    raw_val = float(raw_distance) if np.isfinite(raw_distance) else 0.0

    if features is not None and features.shape[1] >= 2:
        new_val = compute_mahalanobis_cluster_distance(features, config=cfg)
    else:
        new_val = raw_val

    final = engine.apply_override(
        point_id="84",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_84] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 84 Mahalanobis Distance Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(84)
    x1 = rng.normal(0, 1, n)
    x2 = rng.normal(100, 50, n)  # different scale
    feats = pd.DataFrame({"x1": x1, "x2": x2})
    final = compute_point_84_override(0.0, pd.DataFrame({"close": x1}), "TEST84", engine=engine, features=feats)
    print(f"raw_dist=0.000 -> final={final:.4f}")

def _load_point_84_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_84", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_84_CONFIG





