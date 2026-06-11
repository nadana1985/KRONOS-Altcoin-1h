"""
KRONOS V1-ALT — Bias Override Point 88: "Symmetrical Model Evaluation Loss Functions"

Manual description:
  "Evaluating model predictions using symmetrical loss metrics (e.g., MSE)."

Quant replacement:
  "Asymmetric Imbalance Penalized Loss (Linex Loss).
   Penalize downside execution risk heavily."

Uses shared compute_linex_loss.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_linex_loss
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_88")



_DEFAULT_POINT_88_CONFIG = {"asymmetry": 1.0, "min_data_density": 50, "fallback_loss": 0.0}


def compute_asymmetric_loss(
    errors: np.ndarray,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure Linex loss computation."""
    cfg = config or {}
    a = float(cfg.get("asymmetry", 1.0))
    min_d = int(cfg.get("min_data_density", 50))

    e = np.asarray(errors, dtype=float)
    if len(e) < min_d:
        return float(cfg.get("fallback_loss", 0.0))

    loss = compute_linex_loss(e, a)
    logger.info("[POINT_88] linex_loss=%.6f (asymmetry=%.2f)", loss, a)
    return loss


def compute_point_88_override(
    raw_loss: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    errors: np.ndarray = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_88_config(engine)

    raw_val = float(raw_loss) if np.isfinite(raw_loss) else 0.0

    if errors is not None:
        new_val = compute_asymmetric_loss(errors, config=cfg)
    else:
        new_val = raw_val

    final = engine.apply_override(
        point_id="88",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_88] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 88 Linex Loss Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(88)
    errors = rng.normal(0, 0.01, n)
    errors[80:90] = rng.normal(-0.05, 0.02, 10)  # large negative errors
    final = compute_point_88_override(0.001, pd.DataFrame({"close": np.arange(n)}), "TEST88", engine=engine, errors=errors)
    print(f"raw_loss=0.001 -> final={final:.6f}")

def _load_point_88_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_88", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_88_CONFIG

def compute_asymmetric_loss(
    errors: np.ndarray,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure Linex loss computation."""
    cfg = config or {}
    a = float(cfg.get("asymmetry", 1.0))
    min_d = int(cfg.get("min_data_density", 50))

    e = np.asarray(errors, dtype=float)
    if len(e) < min_d:
        return float(cfg.get("fallback_loss", 0.0))

    loss = compute_linex_loss(e, a)
    logger.info("[POINT_88] linex_loss=%.6f (asymmetry=%.2f)", loss, a)
    return loss


def compute_point_88_override(
    raw_loss: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    errors: np.ndarray = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_88_config(engine)

    raw_val = float(raw_loss) if np.isfinite(raw_loss) else 0.0

    if errors is not None:
        new_val = compute_asymmetric_loss(errors, config=cfg)
    else:
        new_val = raw_val

    final = engine.apply_override(
        point_id="88",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_88] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 88 Linex Loss Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(88)
    errors = rng.normal(0, 0.01, n)
    errors[80:90] = rng.normal(-0.05, 0.02, 10)  # large negative errors
    final = compute_point_88_override(0.001, pd.DataFrame({"close": np.arange(n)}), "TEST88", engine=engine, errors=errors)
    print(f"raw_loss=0.001 -> final={final:.6f}")
    print("Smoke done.")
