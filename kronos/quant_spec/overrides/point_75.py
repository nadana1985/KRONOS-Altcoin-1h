"""
KRONOS V1-ALT — Bias Override Point 75: "Multicollinear Feature Dependency"

Manual description:
  "Directly inputting highly collinear structural variables into linear or deep neural networks."

Quant replacement:
  "VIF (Variance Inflation Factor) Filtering.
   Drop collinear features with VIF scores crossing threshold boundaries."

Uses shared compute_vif_scores.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_vif_scores
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_75")



_DEFAULT_POINT_75_CONFIG = {"vif_threshold": 10.0, "min_data_density": 50, "fallback_drop_count": 0}


def compute_vif_filtering(
    features: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Pure VIF filtering."""
    cfg = config or {}
    threshold = float(cfg.get("vif_threshold", 10.0))
    min_d = int(cfg.get("min_data_density", 50))

    if len(features) < min_d or features.shape[1] < 2:
        return {"vifs": [], "drop_features": [], "max_vif": 1.0}

    X = features.dropna().values
    if len(X) < min_d:
        return {"vifs": [], "drop_features": [], "max_vif": 1.0}

    result = compute_vif_scores(X, list(features.columns))
    # Filter by threshold
    drop = [f for f, v in zip(features.columns, result["vifs"]) if v > threshold]
    logger.info("[POINT_75] vif | max=%.2f drop_count=%d", result["max_vif"], len(drop))
    return {"vifs": result["vifs"], "drop_features": drop, "max_vif": result["max_vif"]}


def compute_point_75_override(
    raw_vif_score: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    features: pd.DataFrame = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_75_config(engine)

    raw_val = float(raw_vif_score) if np.isfinite(raw_vif_score) else 1.0

    if features is not None and features.shape[1] >= 2:
        result = compute_vif_filtering(features, config=cfg)
        new_val = float(len(result["drop_features"]))
    else:
        new_val = float(cfg.get("fallback_drop_count", 0))

    final = engine.apply_override(
        point_id="75",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_75] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 75 VIF Filtering Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(75)
    x1 = rng.normal(0, 1, n)
    x2 = x1 + rng.normal(0, 0.01, n)  # highly collinear
    x3 = rng.normal(0, 1, n)
    feats = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3})
    final = compute_point_75_override(1.0, pd.DataFrame({"close": x1}), "TEST75", engine=engine, features=feats)
    print(f"raw_vif=1.000 -> final={final:.4f}")

def _load_point_75_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_75", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_75_CONFIG

def compute_vif_filtering(
    features: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Pure VIF filtering."""
    cfg = config or {}
    threshold = float(cfg.get("vif_threshold", 10.0))
    min_d = int(cfg.get("min_data_density", 50))

    if len(features) < min_d or features.shape[1] < 2:
        return {"vifs": [], "drop_features": [], "max_vif": 1.0}

    X = features.dropna().values
    if len(X) < min_d:
        return {"vifs": [], "drop_features": [], "max_vif": 1.0}

    result = compute_vif_scores(X, list(features.columns))
    # Filter by threshold
    drop = [f for f, v in zip(features.columns, result["vifs"]) if v > threshold]
    logger.info("[POINT_75] vif | max=%.2f drop_count=%d", result["max_vif"], len(drop))
    return {"vifs": result["vifs"], "drop_features": drop, "max_vif": result["max_vif"]}


def compute_point_75_override(
    raw_vif_score: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    features: pd.DataFrame = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_75_config(engine)

    raw_val = float(raw_vif_score) if np.isfinite(raw_vif_score) else 1.0

    if features is not None and features.shape[1] >= 2:
        result = compute_vif_filtering(features, config=cfg)
        new_val = float(len(result["drop_features"]))
    else:
        new_val = float(cfg.get("fallback_drop_count", 0))

    final = engine.apply_override(
        point_id="75",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_75] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 75 VIF Filtering Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(75)
    x1 = rng.normal(0, 1, n)
    x2 = x1 + rng.normal(0, 0.01, n)  # highly collinear
    x3 = rng.normal(0, 1, n)
    feats = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3})
    final = compute_point_75_override(1.0, pd.DataFrame({"close": x1}), "TEST75", engine=engine, features=feats)
    print(f"raw_vif=1.000 -> final={final:.4f}")
    print("Smoke done.")
