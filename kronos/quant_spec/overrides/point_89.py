"""
KRONOS V1-ALT — Bias Override Point 89: "Rigid Sessional State Categorizations"

Manual description:
  "Splitting price action into fixed categorical states (e.g., Bull, Bear, Range)."

Quant replacement:
  "Continuous Soft Probability State Memberships.
   Model states as soft probabilities using Gaussian Mixture Models (GMM)."

Uses shared compute_gmm_soft_membership.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_gmm_soft_membership
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_89")



_DEFAULT_POINT_89_CONFIG = {"n_components": 3, "min_data_density": 50, "fallback_membership": 0.33}


def compute_soft_state_membership(
    features: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Pure GMM soft membership computation."""
    cfg = config or {}
    k = int(cfg.get("n_components", 3))
    min_d = int(cfg.get("min_data_density", 50))

    if len(features) < min_d or features.shape[1] < 1:
        return {"memberships": np.array([[1.0 / max(k, 1)] * k]), "labels": np.array([0])}

    X = features.dropna().values
    if len(X) < min_d:
        return {"memberships": np.array([[1.0 / max(k, 1)] * k]), "labels": np.array([0])}

    result = compute_gmm_soft_membership(X, k)
    logger.info("[POINT_89] gmm | n_comp=%d labels=%s", k, np.unique(result["labels"]))
    return result


def compute_point_89_override(
    raw_state: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    features: pd.DataFrame = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_89_config(engine)

    raw_val = float(raw_state) if np.isfinite(raw_state) else 0.0

    if features is not None and features.shape[1] >= 1:
        result = compute_soft_state_membership(features, config=cfg)
        # Return max membership probability (softness of state assignment)
        new_val = float(np.max(result["memberships"][-1])) if result["memberships"].size > 0 else 0.5
    else:
        new_val = float(cfg.get("fallback_membership", 0.33))

    final = engine.apply_override(
        point_id="89",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_89] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 89 GMM Soft Membership Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(89)
    x1 = np.concatenate([rng.normal(-1, 0.3, 40), rng.normal(1, 0.3, 40), rng.normal(0, 0.5, 40)])
    x2 = np.concatenate([rng.normal(0, 0.3, 40), rng.normal(2, 0.3, 40), rng.normal(1, 0.5, 40)])
    feats = pd.DataFrame({"x1": x1, "x2": x2})
    final = compute_point_89_override(0.0, pd.DataFrame({"close": x1}), "TEST89", engine=engine, features=feats)
    print(f"raw_state=0.000 -> final={final:.4f}")

def _load_point_89_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_89", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_89_CONFIG

def compute_soft_state_membership(
    features: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Pure GMM soft membership computation."""
    cfg = config or {}
    k = int(cfg.get("n_components", 3))
    min_d = int(cfg.get("min_data_density", 50))

    if len(features) < min_d or features.shape[1] < 1:
        return {"memberships": np.array([[1.0 / max(k, 1)] * k]), "labels": np.array([0])}

    X = features.dropna().values
    if len(X) < min_d:
        return {"memberships": np.array([[1.0 / max(k, 1)] * k]), "labels": np.array([0])}

    result = compute_gmm_soft_membership(X, k)
    logger.info("[POINT_89] gmm | n_comp=%d labels=%s", k, np.unique(result["labels"]))
    return result


def compute_point_89_override(
    raw_state: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    features: pd.DataFrame = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_89_config(engine)

    raw_val = float(raw_state) if np.isfinite(raw_state) else 0.0

    if features is not None and features.shape[1] >= 1:
        result = compute_soft_state_membership(features, config=cfg)
        # Return max membership probability (softness of state assignment)
        new_val = float(np.max(result["memberships"][-1])) if result["memberships"].size > 0 else 0.5
    else:
        new_val = float(cfg.get("fallback_membership", 0.33))

    final = engine.apply_override(
        point_id="89",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_89] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 89 GMM Soft Membership Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(89)
    x1 = np.concatenate([rng.normal(-1, 0.3, 40), rng.normal(1, 0.3, 40), rng.normal(0, 0.5, 40)])
    x2 = np.concatenate([rng.normal(0, 0.3, 40), rng.normal(2, 0.3, 40), rng.normal(1, 0.5, 40)])
    feats = pd.DataFrame({"x1": x1, "x2": x2})
    final = compute_point_89_override(0.0, pd.DataFrame({"close": x1}), "TEST89", engine=engine, features=feats)
    print(f"raw_state=0.000 -> final={final:.4f}")
    print("Smoke done.")
