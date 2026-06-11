"""
KRONOS V1-ALT — Bias Override Point 83: "Homogeneous Error Term Weights in Loss Architectures"

Manual description:
  "Training models using uniform weights across all training samples."

Quant replacement:
  "Information-Weighted Loss Training.
   Weight the loss of each sample by its relative information density."

Uses shared compute_information_weighted_loss.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_information_weighted_loss
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_83")



_DEFAULT_POINT_83_CONFIG = {"min_data_density": 50, "fallback_loss": 0.0}


def compute_info_weighted_loss(
    predictions: np.ndarray,
    actuals: np.ndarray,
    information_density: np.ndarray = None,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure information-weighted loss."""
    cfg = config or {}
    min_d = int(cfg.get("min_data_density", 50))

    preds = np.asarray(predictions, dtype=float)
    acts = np.asarray(actuals, dtype=float)
    n = min(len(preds), len(acts))

    if n < min_d:
        return float(cfg.get("fallback_loss", 0.0))

    if information_density is not None:
        w = np.asarray(information_density, dtype=float)[:n]
    else:
        w = np.ones(n)

    loss = compute_information_weighted_loss(preds[:n], acts[:n], w)
    logger.info("[POINT_83] info_weighted_loss=%.6f", loss)
    return loss


def compute_point_83_override(
    raw_loss: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    predictions: np.ndarray = None,
    actuals: np.ndarray = None,
    information_density: np.ndarray = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_83_config(engine)

    raw_val = float(raw_loss) if np.isfinite(raw_loss) else 0.0

    if predictions is not None and actuals is not None:
        new_val = compute_info_weighted_loss(predictions, actuals, information_density, config=cfg)
    else:
        new_val = raw_val

    final = engine.apply_override(
        point_id="83",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_83] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 83 Information-Weighted Loss Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(83)
    preds = rng.normal(0.5, 0.1, n)
    actuals = preds + rng.normal(0, 0.05, n)
    info_d = rng.uniform(0.1, 1.0, n)
    final = compute_point_83_override(0.01, pd.DataFrame({"close": np.arange(n)}), "TEST83", engine=engine, predictions=preds, actuals=actuals, information_density=info_d)
    print(f"raw_loss=0.010 -> final={final:.6f}")

def _load_point_83_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_83", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_83_CONFIG

def compute_info_weighted_loss(
    predictions: np.ndarray,
    actuals: np.ndarray,
    information_density: np.ndarray = None,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure information-weighted loss."""
    cfg = config or {}
    min_d = int(cfg.get("min_data_density", 50))

    preds = np.asarray(predictions, dtype=float)
    acts = np.asarray(actuals, dtype=float)
    n = min(len(preds), len(acts))

    if n < min_d:
        return float(cfg.get("fallback_loss", 0.0))

    if information_density is not None:
        w = np.asarray(information_density, dtype=float)[:n]
    else:
        w = np.ones(n)

    loss = compute_information_weighted_loss(preds[:n], acts[:n], w)
    logger.info("[POINT_83] info_weighted_loss=%.6f", loss)
    return loss


def compute_point_83_override(
    raw_loss: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    predictions: np.ndarray = None,
    actuals: np.ndarray = None,
    information_density: np.ndarray = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_83_config(engine)

    raw_val = float(raw_loss) if np.isfinite(raw_loss) else 0.0

    if predictions is not None and actuals is not None:
        new_val = compute_info_weighted_loss(predictions, actuals, information_density, config=cfg)
    else:
        new_val = raw_val

    final = engine.apply_override(
        point_id="83",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_83] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 83 Information-Weighted Loss Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(83)
    preds = rng.normal(0.5, 0.1, n)
    actuals = preds + rng.normal(0, 0.05, n)
    info_d = rng.uniform(0.1, 1.0, n)
    final = compute_point_83_override(0.01, pd.DataFrame({"close": np.arange(n)}), "TEST83", engine=engine, predictions=preds, actuals=actuals, information_density=info_d)
    print(f"raw_loss=0.010 -> final={final:.6f}")
    print("Smoke done.")
