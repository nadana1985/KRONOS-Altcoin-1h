"""
KRONOS V1-ALT — Bias Override Point 98: "Equal Cointegration Lifespans"

Manual description:
  "Assuming cointegration relationships between assets persist indefinitely without structural decay."

Quant replacement:
  "Rolling Engle-Granger Cointegration Significance Filters.
   Continually verify cointegration stability."

Uses shared compute_rolling_engle_granger.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_rolling_engle_granger
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_98")



_DEFAULT_POINT_98_CONFIG = {"window": 100, "min_data_density": 50, "fallback_cointegrated": False}


def compute_engle_granger_test(
    series_a: pd.Series,
    series_b: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Pure rolling Engle-Granger cointegration test."""
    cfg = config or {}
    w = int(cfg.get("window", 100))
    min_d = int(cfg.get("min_data_density", 50))

    a = pd.to_numeric(series_a, errors="coerce").dropna()
    b = pd.to_numeric(series_b, errors="coerce").dropna()
    if len(a) < min_d or len(b) < min_d:
        return {"adf_stat": 0.0, "cointegrated": bool(cfg.get("fallback_cointegrated", False))}

    result = compute_rolling_engle_granger(a, b, w)
    logger.info("[POINT_98] engle_granger | adf=%.4f cointegrated=%s", result["adf_stat"], result["cointegrated"])
    return result


def compute_point_98_override(
    raw_cointegration_lifespan: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    series_a: pd.Series = None,
    series_b: pd.Series = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_98_config(engine)

    raw_val = float(raw_cointegration_lifespan) if np.isfinite(raw_cointegration_lifespan) else 0.0

    if series_a is not None and series_b is not None:
        result = compute_engle_granger_test(series_a, series_b, config=cfg)
    else:
        c = pd.to_numeric(df.get("close"), errors="coerce")
        result = compute_engle_granger_test(c, c.shift(1), config=cfg)

    new_val = 1.0 if result["cointegrated"] else 0.0

    final = engine.apply_override(
        point_id="98",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_98] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 98 Engle-Granger Smoke ===")
    engine = BiasOverrideEngine()
    n = 150
    rng = np.random.default_rng(98)
    x = np.cumsum(rng.normal(0, 0.01, n))
    y = x + rng.normal(0, 0.005, n)  # cointegrated
    df = pd.DataFrame({"close": 100 * np.exp(x)})
    final = compute_point_98_override(0.0, df, "TEST98", engine=engine, series_a=pd.Series(x), series_b=pd.Series(y))
    print(f"raw_lifespan=0.000 -> final={final:.4f}")

def _load_point_98_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_98", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_98_CONFIG

def compute_engle_granger_test(
    series_a: pd.Series,
    series_b: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Pure rolling Engle-Granger cointegration test."""
    cfg = config or {}
    w = int(cfg.get("window", 100))
    min_d = int(cfg.get("min_data_density", 50))

    a = pd.to_numeric(series_a, errors="coerce").dropna()
    b = pd.to_numeric(series_b, errors="coerce").dropna()
    if len(a) < min_d or len(b) < min_d:
        return {"adf_stat": 0.0, "cointegrated": bool(cfg.get("fallback_cointegrated", False))}

    result = compute_rolling_engle_granger(a, b, w)
    logger.info("[POINT_98] engle_granger | adf=%.4f cointegrated=%s", result["adf_stat"], result["cointegrated"])
    return result


def compute_point_98_override(
    raw_cointegration_lifespan: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    series_a: pd.Series = None,
    series_b: pd.Series = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_98_config(engine)

    raw_val = float(raw_cointegration_lifespan) if np.isfinite(raw_cointegration_lifespan) else 0.0

    if series_a is not None and series_b is not None:
        result = compute_engle_granger_test(series_a, series_b, config=cfg)
    else:
        c = pd.to_numeric(df.get("close"), errors="coerce")
        result = compute_engle_granger_test(c, c.shift(1), config=cfg)

    new_val = 1.0 if result["cointegrated"] else 0.0

    final = engine.apply_override(
        point_id="98",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_98] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 98 Engle-Granger Smoke ===")
    engine = BiasOverrideEngine()
    n = 150
    rng = np.random.default_rng(98)
    x = np.cumsum(rng.normal(0, 0.01, n))
    y = x + rng.normal(0, 0.005, n)  # cointegrated
    df = pd.DataFrame({"close": 100 * np.exp(x)})
    final = compute_point_98_override(0.0, df, "TEST98", engine=engine, series_a=pd.Series(x), series_b=pd.Series(y))
    print(f"raw_lifespan=0.000 -> final={final:.4f}")
    print("Smoke done.")
