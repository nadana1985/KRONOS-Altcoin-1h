"""
KRONOS V1-ALT — Bias Override Point 13: "Fixed Order Flow Proxy Splits"

Manual description:
  "Assuming buy and sell volumes are split symmetrically ignores order execution
   velocity and concentration."

Quant replacement:
  "Trade-Intensity Weighted Imbalance. Scale the volume imbalance by average
   trade size metrics:
   OFI = (TBV - (V - TBV)) * ln(V / Count + eps)."

Uses shared compute_trade_intensity_imbalance.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_trade_intensity_imbalance
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_13")



_DEFAULT_POINT_13_CONFIG = {
            "intensity_window": 20,
            "min_data_density": 150,
            "fallback_imbalance": 0.0,
        }


def compute_weighted_imbalance(
    taker_buy_volume: pd.Series,
    total_volume: pd.Series,
    trade_count: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Compute trade-intensity weighted order flow imbalance."""
    cfg = config or {}
    w = int(cfg.get("intensity_window", 20))
    min_d = int(cfg.get("min_data_density", 150))
    fb = float(cfg.get("fallback_imbalance", 0.0))

    n = min(len(taker_buy_volume.dropna()), len(total_volume.dropna()), len(trade_count.dropna()))
    if n < min_d:
        logger.info("[POINT_13] insufficient data — fallback imbalance %.4f", fb)
        return fb

    imbalance = compute_trade_intensity_imbalance(taker_buy_volume, total_volume, trade_count, w)
    logger.info("[POINT_13] trade_intensity_imbalance | window=%d -> imbalance=%.4f", w, imbalance)
    return imbalance


def compute_point_13_override(
    raw_imbalance: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    taker_buy_col: str = "taker_buy_volume",
    volume_col: str = "volume",
    count_col: str = "count",
    **kwargs,
) -> float:
    """Wrapper for Point 13. Returns trade-intensity weighted imbalance."""
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_13_config(engine)

    raw_val = float(raw_imbalance) if np.isfinite(raw_imbalance) else float(cfg.get("fallback_imbalance", 0.0))

    tbv = pd.to_numeric(df.get(taker_buy_col), errors="coerce")
    v = pd.to_numeric(df.get(volume_col), errors="coerce")
    cnt = pd.to_numeric(df.get(count_col), errors="coerce")

    if tbv is None or v is None or cnt is None:
        return raw_val

    new_val = compute_weighted_imbalance(tbv, v, cnt, config=cfg)

    final = engine.apply_override(
        point_id="13",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_13] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 13 Trade-Intensity Imbalance Smoke ===")
    engine = BiasOverrideEngine()
    n = 200
    rng = np.random.default_rng(13)
    vol = rng.uniform(500_000, 5_000_000, n)
    # Simulate taker buy: ~50% with some imbalance
    tbv = vol * (0.5 + rng.normal(0, 0.1, n))
    tbv = np.clip(tbv, 0, vol)
    # Trade count: more trades = smaller average size
    count = rng.randint(500, 5000, n).astype(float)
    df = pd.DataFrame({
        "taker_buy_volume": tbv,
        "volume": vol,
        "count": count,
        "close": 100 + np.cumsum(rng.normal(0, 0.5, n)),
    })
    imb = compute_point_13_override(0.0, df, "TEST13", engine=engine)
    print(f"  trade-intensity imbalance: {imb:.4f}")

def _load_point_13_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_13", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_13_CONFIG

def compute_weighted_imbalance(
    taker_buy_volume: pd.Series,
    total_volume: pd.Series,
    trade_count: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Compute trade-intensity weighted order flow imbalance."""
    cfg = config or {}
    w = int(cfg.get("intensity_window", 20))
    min_d = int(cfg.get("min_data_density", 150))
    fb = float(cfg.get("fallback_imbalance", 0.0))

    n = min(len(taker_buy_volume.dropna()), len(total_volume.dropna()), len(trade_count.dropna()))
    if n < min_d:
        logger.info("[POINT_13] insufficient data — fallback imbalance %.4f", fb)
        return fb

    imbalance = compute_trade_intensity_imbalance(taker_buy_volume, total_volume, trade_count, w)
    logger.info("[POINT_13] trade_intensity_imbalance | window=%d -> imbalance=%.4f", w, imbalance)
    return imbalance


def compute_point_13_override(
    raw_imbalance: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    taker_buy_col: str = "taker_buy_volume",
    volume_col: str = "volume",
    count_col: str = "count",
    **kwargs,
) -> float:
    """Wrapper for Point 13. Returns trade-intensity weighted imbalance."""
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_13_config(engine)

    raw_val = float(raw_imbalance) if np.isfinite(raw_imbalance) else float(cfg.get("fallback_imbalance", 0.0))

    tbv = pd.to_numeric(df.get(taker_buy_col), errors="coerce")
    v = pd.to_numeric(df.get(volume_col), errors="coerce")
    cnt = pd.to_numeric(df.get(count_col), errors="coerce")

    if tbv is None or v is None or cnt is None:
        return raw_val

    new_val = compute_weighted_imbalance(tbv, v, cnt, config=cfg)

    final = engine.apply_override(
        point_id="13",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_13] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 13 Trade-Intensity Imbalance Smoke ===")
    engine = BiasOverrideEngine()
    n = 200
    rng = np.random.default_rng(13)
    vol = rng.uniform(500_000, 5_000_000, n)
    # Simulate taker buy: ~50% with some imbalance
    tbv = vol * (0.5 + rng.normal(0, 0.1, n))
    tbv = np.clip(tbv, 0, vol)
    # Trade count: more trades = smaller average size
    count = rng.randint(500, 5000, n).astype(float)
    df = pd.DataFrame({
        "taker_buy_volume": tbv,
        "volume": vol,
        "count": count,
        "close": 100 + np.cumsum(rng.normal(0, 0.5, n)),
    })
    imb = compute_point_13_override(0.0, df, "TEST13", engine=engine)
    print(f"  trade-intensity imbalance: {imb:.4f}")
    print("Smoke done.")
