"""
KRONOS V1-ALT — Bias Override Point 85: "Equal-Weighted Neural Model Voting"

Manual description:
  "Combining predictions from multiple neural sub-components linearly."

Quant replacement:
  "Bayesian Model Averaging (BMA) Ensemble Weighting.
   Scale model weights by their posterior probability."

Uses shared compute_bma_weights.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, List

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_bma_weights
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_85")



_DEFAULT_POINT_85_CONFIG = {"min_data_density": 50, "fallback_weight": 1.0}


def compute_bma_ensemble_weights(
    model_likelihoods: List[float],
    prior_weights: List[float] = None,
    config: Optional[Dict[str, Any]] = None,
) -> list:
    """Pure BMA ensemble weighting."""
    cfg = config or {}

    if len(model_likelihoods) == 0:
        return []

    weights = compute_bma_weights(model_likelihoods, prior_weights)
    logger.info("[POINT_85] bma_weights=%s", [f"{w:.4f}" for w in weights])
    return weights


def compute_point_85_override(
    raw_ensemble_weight: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    model_likelihoods: List[float] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_85_config(engine)

    raw_val = float(raw_ensemble_weight) if np.isfinite(raw_ensemble_weight) else 1.0

    if model_likelihoods and len(model_likelihoods) > 1:
        weights = compute_bma_ensemble_weights(model_likelihoods, config=cfg)
        new_val = float(max(weights))  # best model weight
    else:
        new_val = float(cfg.get("fallback_weight", 1.0))

    final = engine.apply_override(
        point_id="85",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_85] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 85 BMA Ensemble Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(85)
    df = pd.DataFrame({"close": rng.normal(0, 1, n)})
    likes = [0.8, 0.5, 0.3]
    final = compute_point_85_override(0.33, df, "TEST85", engine=engine, model_likelihoods=likes)
    print(f"raw_weight=0.333 -> final={final:.4f}")

def _load_point_85_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_85", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_85_CONFIG





