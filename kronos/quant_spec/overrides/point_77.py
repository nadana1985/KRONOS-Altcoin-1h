"""
KRONOS V1-ALT — Bias Override Point 77: "Equal Component Weights in Clustering"

Manual description:
  "Clustering spatial matrices without adjusting for variable contributions to overall variance."

Quant replacement:
  "PCA-Principal Component Distance Projections.
   Perform clustering on the coordinate projection space of the top principal components."

Uses shared compute_pca_distance_projections.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_pca_distance_projections
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_77")



_DEFAULT_POINT_77_CONFIG = {"n_components": 3, "min_data_density": 50, "fallback_variance": 0.5}


def compute_pca_projection(
    features: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Pure PCA projection for clustering distance."""
    cfg = config or {}
    k = int(cfg.get("n_components", 3))
    min_d = int(cfg.get("min_data_density", 50))

    if len(features) < min_d or features.shape[1] < k:
        return {"n_components": 0, "variance_explained": [1.0]}

    X = features.dropna().values
    if len(X) < min_d:
        return {"n_components": 0, "variance_explained": [1.0]}

    result = compute_pca_distance_projections(X, k)
    logger.info("[POINT_77] pca | n_comp=%d var_explained=%s", result["n_components"], result["variance_explained"])
    return result


def compute_point_77_override(
    raw_cluster_distance: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    features: pd.DataFrame = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_77_config(engine)

    raw_val = float(raw_cluster_distance) if np.isfinite(raw_cluster_distance) else 1.0

    if features is not None and features.shape[1] >= 2:
        result = compute_pca_projection(features, config=cfg)
        new_val = float(np.sum(result["variance_explained"]))
    else:
        new_val = float(cfg.get("fallback_variance", 0.5))

    final = engine.apply_override(
        point_id="77",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_77] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 77 PCA Distance Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(77)
    x1 = rng.normal(0, 1, n)
    x2 = x1 * 0.8 + rng.normal(0, 0.2, n)
    x3 = rng.normal(0, 1, n)
    feats = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3})
    final = compute_point_77_override(1.0, pd.DataFrame({"close": x1}), "TEST77", engine=engine, features=feats)
    print(f"raw_dist=1.000 -> final={final:.4f}")

def _load_point_77_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_77", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_77_CONFIG

def compute_pca_projection(
    features: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Pure PCA projection for clustering distance."""
    cfg = config or {}
    k = int(cfg.get("n_components", 3))
    min_d = int(cfg.get("min_data_density", 50))

    if len(features) < min_d or features.shape[1] < k:
        return {"n_components": 0, "variance_explained": [1.0]}

    X = features.dropna().values
    if len(X) < min_d:
        return {"n_components": 0, "variance_explained": [1.0]}

    result = compute_pca_distance_projections(X, k)
    logger.info("[POINT_77] pca | n_comp=%d var_explained=%s", result["n_components"], result["variance_explained"])
    return result


def compute_point_77_override(
    raw_cluster_distance: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    features: pd.DataFrame = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_77_config(engine)

    raw_val = float(raw_cluster_distance) if np.isfinite(raw_cluster_distance) else 1.0

    if features is not None and features.shape[1] >= 2:
        result = compute_pca_projection(features, config=cfg)
        new_val = float(np.sum(result["variance_explained"]))
    else:
        new_val = float(cfg.get("fallback_variance", 0.5))

    final = engine.apply_override(
        point_id="77",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_77] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 77 PCA Distance Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(77)
    x1 = rng.normal(0, 1, n)
    x2 = x1 * 0.8 + rng.normal(0, 0.2, n)
    x3 = rng.normal(0, 1, n)
    feats = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3})
    final = compute_point_77_override(1.0, pd.DataFrame({"close": x1}), "TEST77", engine=engine, features=feats)
    print(f"raw_dist=1.000 -> final={final:.4f}")
    print("Smoke done.")
