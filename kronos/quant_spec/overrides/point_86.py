"""
KRONOS V1-ALT — Bias Override Point 86: "Information-Theoretic Feature Redundancy"

Manual description:
  "Training models with collinear structural features."

Quant replacement:
  "Max-Relevance Min-Redundancy (mRMR) Feature Selection.
   Filter features to maximize target relevance while minimizing mutual redundancy."

Uses shared compute_mrmr_scores.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_mrmr_scores
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_86")



_DEFAULT_POINT_86_CONFIG = {"n_features": 5, "n_bins": 10, "min_data_density": 50, "fallback_selected": 0}


def compute_mrmr_feature_selection(
    features: pd.DataFrame,
    target: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> list:
    """Pure mRMR feature selection."""
    cfg = config or {}
    n_feat = int(cfg.get("n_features", 5))
    n_bins = int(cfg.get("n_bins", 10))
    min_d = int(cfg.get("min_data_density", 50))

    if len(features) < min_d or features.shape[1] < 2:
        return list(features.columns[:n_feat])

    selected = compute_mrmr_scores(features, target, n_feat, n_bins)
    logger.info("[POINT_86] mrmr_selected=%s", selected)
    return selected


def compute_point_86_override(
    raw_redundancy_score: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    features: pd.DataFrame = None,
    target: pd.Series = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_86_config(engine)

    raw_val = float(raw_redundancy_score) if np.isfinite(raw_redundancy_score) else 0.0

    if features is not None and target is not None:
        selected = compute_mrmr_feature_selection(features, target, config=cfg)
        new_val = float(len(selected))
    else:
        new_val = float(cfg.get("fallback_selected", 0))

    final = engine.apply_override(
        point_id="86",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_86] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 86 mRMR Feature Selection Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(86)
    x1 = rng.normal(0, 1, n)
    x2 = x1 + rng.normal(0, 0.01, n)  # redundant
    x3 = rng.normal(0, 1, n)
    target = pd.Series(0.5 * x1 + 0.3 * x3 + rng.normal(0, 0.1, n))
    feats = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3})
    final = compute_point_86_override(0.0, pd.DataFrame({"close": x1}), "TEST86", engine=engine, features=feats, target=target)
    print(f"raw_redundancy=0.000 -> final={final:.4f}")

def _load_point_86_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_86", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_86_CONFIG





