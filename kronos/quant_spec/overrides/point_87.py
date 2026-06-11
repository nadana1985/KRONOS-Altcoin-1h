"""
KRONOS V1-ALT — Bias Override Point 87: "Stationary Linear Model Projections"

Manual description:
  "Predicting forward returns under linear, stationary regression assumptions."

Quant replacement:
  "Local Polynomial Regression (LOESS).
   Model relationships using localized, non-parametric weighted regressions."

Uses shared compute_loess_prediction.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_loess_prediction
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_87")



_DEFAULT_POINT_87_CONFIG = {"span": 20, "degree": 1, "min_data_density": 30, "fallback_prediction": 0.0}


def compute_loess_fit_prediction(
    x: pd.Series,
    y: pd.Series,
    x_pred: float,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure LOESS prediction."""
    cfg = config or {}
    span = int(cfg.get("span", 20))
    degree = int(cfg.get("degree", 1))
    min_d = int(cfg.get("min_data_density", 30))

    if len(x) < min_d:
        return float(cfg.get("fallback_prediction", 0.0))

    pred = compute_loess_prediction(x, y, x_pred, span, degree)
    logger.info("[POINT_87] loess_prediction=%.6f", pred)
    return pred


def compute_point_87_override(
    raw_prediction: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    x_series: pd.Series = None,
    y_series: pd.Series = None,
    x_pred: float = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_87_config(engine)

    raw_val = float(raw_prediction) if np.isfinite(raw_prediction) else 0.0

    if x_series is not None and y_series is not None and x_pred is not None:
        new_val = compute_loess_fit_prediction(x_series, y_series, x_pred, config=cfg)
    else:
        new_val = raw_val

    final = engine.apply_override(
        point_id="87",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_87] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 87 LOESS Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(87)
    x = pd.Series(np.linspace(0, 1, n))
    y = pd.Series(np.sin(2 * np.pi * x) + rng.normal(0, 0.1, n))
    final = compute_point_87_override(0.0, pd.DataFrame({"close": x}), "TEST87", engine=engine, x_series=x, y_series=y, x_pred=0.5)
    print(f"raw_pred=0.000 -> final={final:.4f}")

def _load_point_87_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_87", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_87_CONFIG

def compute_loess_fit_prediction(
    x: pd.Series,
    y: pd.Series,
    x_pred: float,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure LOESS prediction."""
    cfg = config or {}
    span = int(cfg.get("span", 20))
    degree = int(cfg.get("degree", 1))
    min_d = int(cfg.get("min_data_density", 30))

    if len(x) < min_d:
        return float(cfg.get("fallback_prediction", 0.0))

    pred = compute_loess_prediction(x, y, x_pred, span, degree)
    logger.info("[POINT_87] loess_prediction=%.6f", pred)
    return pred


def compute_point_87_override(
    raw_prediction: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    x_series: pd.Series = None,
    y_series: pd.Series = None,
    x_pred: float = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_87_config(engine)

    raw_val = float(raw_prediction) if np.isfinite(raw_prediction) else 0.0

    if x_series is not None and y_series is not None and x_pred is not None:
        new_val = compute_loess_fit_prediction(x_series, y_series, x_pred, config=cfg)
    else:
        new_val = raw_val

    final = engine.apply_override(
        point_id="87",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_87] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 87 LOESS Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(87)
    x = pd.Series(np.linspace(0, 1, n))
    y = pd.Series(np.sin(2 * np.pi * x) + rng.normal(0, 0.1, n))
    final = compute_point_87_override(0.0, pd.DataFrame({"close": x}), "TEST87", engine=engine, x_series=x, y_series=y, x_pred=0.5)
    print(f"raw_pred=0.000 -> final={final:.4f}")
    print("Smoke done.")
