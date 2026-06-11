"""
KRONOS V1-ALT — Bias Override Point 80: "Model Selection via Inflated Sharpe Metrics"

Manual description:
  "Selecting models based on the standard Sharpe ratio, which is easily inflated by data-snooping over multiple tests."

Quant replacement:
  "Deflated Sharpe Ratio (DSR) Adjustment. Correct the Sharpe ratio for the number of tested alternative models."

Uses shared deflated_sharpe_ratio.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import deflated_sharpe_ratio
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_80")



_DEFAULT_POINT_80_CONFIG = {"sharpe_confidence": 0.95, "num_trials": 100, "min_data_density": 100, "fallback_sharpe": 0.5}


def compute_deflated_sharpe(
    sharpe: float,
    n_trials: int,
    t: int,
    skew: float = 0.0,
    kurt: float = 3.0,
    confidence: float = 0.95,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure DSR computation."""
    cfg = config or {}
    conf = float(cfg.get("sharpe_confidence", confidence))
    trials = int(cfg.get("num_trials", n_trials))
    dsr = deflated_sharpe_ratio(sharpe, trials, t, skew, kurt, conf)
    logger.info("[POINT_80] dsr | trials=%d T=%d sharpe=%.3f -> dsr=%.4f", trials, t, sharpe, dsr)
    return float(dsr)


def compute_point_80_override(
    raw_sharpe: float,
    n_trials: int,
    t: int,
    df: pd.DataFrame,
    symbol: str,
    skew: float = 0.0,
    kurt: float = 3.0,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_80_config(engine)

    min_d = int(cfg.get("min_data_density", 100))
    fb = float(cfg.get("fallback_sharpe", 0.5))

    if len(df) < min_d:
        logger.info("[POINT_80] insufficient data — fallback sharpe %.3f", fb)
        dsr = fb
    else:
        dsr = compute_deflated_sharpe(raw_sharpe, n_trials, t, skew, kurt, config=cfg)

    final = engine.apply_override(
        point_id="80",
        raw_value=raw_sharpe,
        override_value=dsr,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_80] decision | %s raw_sharpe=%.4f dsr=%.4f final=%.4f", symbol, raw_sharpe, dsr, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 80 DSR Smoke ===")
    engine = BiasOverrideEngine()
    n = 200
    df = pd.DataFrame({"close": np.cumsum(np.random.randn(n) * 0.01)})
    raw_sharpe = 1.8
    final = compute_point_80_override(raw_sharpe, n_trials=50, t=n, df=df, symbol="TEST80", engine=engine)
    print(f"raw_sharpe={raw_sharpe:.3f} -> final_dsr={final:.4f}")

def _load_point_80_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_80", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_80_CONFIG

def compute_deflated_sharpe(
    sharpe: float,
    n_trials: int,
    t: int,
    skew: float = 0.0,
    kurt: float = 3.0,
    confidence: float = 0.95,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure DSR computation."""
    cfg = config or {}
    conf = float(cfg.get("sharpe_confidence", confidence))
    trials = int(cfg.get("num_trials", n_trials))
    dsr = deflated_sharpe_ratio(sharpe, trials, t, skew, kurt, conf)
    logger.info("[POINT_80] dsr | trials=%d T=%d sharpe=%.3f -> dsr=%.4f", trials, t, sharpe, dsr)
    return float(dsr)


def compute_point_80_override(
    raw_sharpe: float,
    n_trials: int,
    t: int,
    df: pd.DataFrame,
    symbol: str,
    skew: float = 0.0,
    kurt: float = 3.0,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_80_config(engine)

    min_d = int(cfg.get("min_data_density", 100))
    fb = float(cfg.get("fallback_sharpe", 0.5))

    if len(df) < min_d:
        logger.info("[POINT_80] insufficient data — fallback sharpe %.3f", fb)
        dsr = fb
    else:
        dsr = compute_deflated_sharpe(raw_sharpe, n_trials, t, skew, kurt, config=cfg)

    final = engine.apply_override(
        point_id="80",
        raw_value=raw_sharpe,
        override_value=dsr,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_80] decision | %s raw_sharpe=%.4f dsr=%.4f final=%.4f", symbol, raw_sharpe, dsr, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 80 DSR Smoke ===")
    engine = BiasOverrideEngine()
    n = 200
    df = pd.DataFrame({"close": np.cumsum(np.random.randn(n) * 0.01)})
    raw_sharpe = 1.8
    final = compute_point_80_override(raw_sharpe, n_trials=50, t=n, df=df, symbol="TEST80", engine=engine)
    print(f"raw_sharpe={raw_sharpe:.3f} -> final_dsr={final:.4f}")
    print("Smoke done.")