"""
KRONOS V1-ALT — Bias Override Point 21: "Order Book Depth Ignorance"

Manual description:
  "Discarding the predictive signals of localized limit-order interactions because standard kline feeds lack depth metrics."

Quant replacement:
  "Amihud Illiquidity Volume Impact Proxy. Reconstruct a real-time price impact indicator:
   lambda_t = sum |ln(C_{t-i}/O_{t-i})| / sum Q_{t-i} ; w = e ^ (-lambda * Illiq)."

Uses shared compute_amihud_illiq (from prior work) and applies it as a weight.

This turns volume into a liquidity-impact adjusted weight.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_amihud_illiq
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_21")



_DEFAULT_POINT_21_CONFIG = {"amihud_window": 20, "amihud_lambda": 0.5, "min_data_density": 50, "fallback_illiq": 0.0}


def compute_amihud_illiq_weight(
    close: pd.Series,
    volume: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure Amihud illiquidity weight replacement."""
    cfg = config or {}
    w = int(cfg.get("amihud_window", 20))
    lam = float(cfg.get("amihud_lambda", 0.5))
    min_d = int(cfg.get("min_data_density", 50))
    fb = float(cfg.get("fallback_illiq", 0.0))

    if len(close) < min_d or len(volume) < min_d:
        logger.info("[POINT_21] insufficient data — fallback illiq weight %.4f", fb)
        return fb

    ill = compute_amihud_illiq(volume, (close / close.shift(1) - 1.0).dropna(), w)
    weight = np.exp(-lam * ill)
    weight = float(np.clip(weight, 0.01, 1.0))
    logger.info("[POINT_21] amihud_illiq | lambda=%.2f -> weight=%.4f", lam, weight)
    return weight


def compute_point_21_override(
    raw_weight: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_21_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    v = pd.to_numeric(df.get("volume", df.get("quote_volume", 1.0)), errors="coerce")

    raw_val = float(raw_weight) if np.isfinite(raw_weight) else 1.0
    new_val = compute_amihud_illiq_weight(c, v, config=cfg)

    final = engine.apply_override(
        point_id="21",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_21] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 21 Amihud Illiq Smoke ===")
    engine = BiasOverrideEngine()
    n = 60
    rng = np.random.default_rng(21)
    c = 100 + np.cumsum(rng.normal(0, 0.4, n))
    v = rng.uniform(1e5, 5e6, n)
    df = pd.DataFrame({"close": c, "volume": v})
    raw = 1.0
    final = compute_point_21_override(raw, df, "TEST21", engine=engine)
    print(f"raw={raw:.3f} -> final={final:.4f}")

def _load_point_21_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_21", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_21_CONFIG

def compute_amihud_illiq_weight(
    close: pd.Series,
    volume: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure Amihud illiquidity weight replacement."""
    cfg = config or {}
    w = int(cfg.get("amihud_window", 20))
    lam = float(cfg.get("amihud_lambda", 0.5))
    min_d = int(cfg.get("min_data_density", 50))
    fb = float(cfg.get("fallback_illiq", 0.0))

    if len(close) < min_d or len(volume) < min_d:
        logger.info("[POINT_21] insufficient data — fallback illiq weight %.4f", fb)
        return fb

    ill = compute_amihud_illiq(volume, (close / close.shift(1) - 1.0).dropna(), w)
    weight = np.exp(-lam * ill)
    weight = float(np.clip(weight, 0.01, 1.0))
    logger.info("[POINT_21] amihud_illiq | lambda=%.2f -> weight=%.4f", lam, weight)
    return weight


def compute_point_21_override(
    raw_weight: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_21_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    v = pd.to_numeric(df.get("volume", df.get("quote_volume", 1.0)), errors="coerce")

    raw_val = float(raw_weight) if np.isfinite(raw_weight) else 1.0
    new_val = compute_amihud_illiq_weight(c, v, config=cfg)

    final = engine.apply_override(
        point_id="21",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_21] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 21 Amihud Illiq Smoke ===")
    engine = BiasOverrideEngine()
    n = 60
    rng = np.random.default_rng(21)
    c = 100 + np.cumsum(rng.normal(0, 0.4, n))
    v = rng.uniform(1e5, 5e6, n)
    df = pd.DataFrame({"close": c, "volume": v})
    raw = 1.0
    final = compute_point_21_override(raw, df, "TEST21", engine=engine)
    print(f"raw={raw:.3f} -> final={final:.4f}")
    print("Smoke done.")