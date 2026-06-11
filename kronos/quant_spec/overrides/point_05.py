"""
KRONOS V1-ALT — Bias Override Point 05: "Calendar-Time Rigidity Bias"

Manual description:
  "Sampling data strictly on chronological boundaries treats active liquidation
   hours and dead Asian sessions identically."

Quant replacement:
  "Synthetic Quote Volume-Imbalance Aggregation. Recalculate features over
   dynamic windows required to clear rolling volume density targets:
   W_t = min {k | sum Q_{t-i} >= median({Q_tau})}."

Uses shared compute_volume_density_window.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_volume_density_window
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_05")



_DEFAULT_POINT_05_CONFIG = {
            "target_multiplier": 1.0,
            "min_window": 5,
            "max_window": 100,
            "min_data_density": 200,
            "fallback_window": 24,
        }


def compute_volume_density_window_size(
    volume_series: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> int:
    """Compute dynamic window size based on volume density accumulation target."""
    cfg = config or {}
    target_mult = float(cfg.get("target_multiplier", 1.0))
    min_w = int(cfg.get("min_window", 5))
    max_w = int(cfg.get("max_window", 100))
    min_d = int(cfg.get("min_data_density", 200))
    fb_w = int(cfg.get("fallback_window", 24))

    v = pd.to_numeric(volume_series, errors="coerce").dropna()
    if len(v) < min_d:
        logger.info("[POINT_05] insufficient data density (%d < %d) — fallback window %d", len(v), min_d, fb_w)
        return fb_w

    w = compute_volume_density_window(v, target_mult, min_w, max_w)
    logger.info("[POINT_05] volume_density_window | target_mult=%.2f -> window=%d", target_mult, w)
    return w


def compute_point_05_override(
    raw_window: int,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    volume_col: str = "volume",
    **kwargs,
) -> int:
    """Wrapper for Point 05. Returns dynamic volume-density window size."""
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_05_config(engine)

    raw_val = int(raw_window) if np.isfinite(raw_window) else int(cfg.get("fallback_window", 24))
    vol = pd.to_numeric(df.get(volume_col), errors="coerce")
    new_val = compute_volume_density_window_size(vol, config=cfg)

    final = engine.apply_override(
        point_id="05",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_05] decision | %s raw=%d new=%d final=%d", symbol, raw_val, new_val, int(final))
    return int(final)


if __name__ == "__main__":
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 05 Volume-Density Window Smoke ===")
    engine = BiasOverrideEngine()
    n = 200
    rng = np.random.default_rng(5)
    # Simulate varying volume (some bars much higher — liquidation bars)
    vol = rng.uniform(500_000, 2_000_000, n)
    vol[50:55] = 10_000_000  # liquidation spike
    vol[120:125] = 8_000_000  # another spike
    df = pd.DataFrame({"volume": vol, "close": 100 + np.cumsum(rng.normal(0, 0.5, n))})
    raw_w = 24
    final_w = compute_point_05_override(raw_w, df, "TEST05", engine=engine)
    print(f"  raw_window={raw_w} -> final_window={final_w}")

def _load_point_05_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_05", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_05_CONFIG

def compute_volume_density_window_size(
    volume_series: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> int:
    """Compute dynamic window size based on volume density accumulation target."""
    cfg = config or {}
    target_mult = float(cfg.get("target_multiplier", 1.0))
    min_w = int(cfg.get("min_window", 5))
    max_w = int(cfg.get("max_window", 100))
    min_d = int(cfg.get("min_data_density", 200))
    fb_w = int(cfg.get("fallback_window", 24))

    v = pd.to_numeric(volume_series, errors="coerce").dropna()
    if len(v) < min_d:
        logger.info("[POINT_05] insufficient data density (%d < %d) — fallback window %d", len(v), min_d, fb_w)
        return fb_w

    w = compute_volume_density_window(v, target_mult, min_w, max_w)
    logger.info("[POINT_05] volume_density_window | target_mult=%.2f -> window=%d", target_mult, w)
    return w


def compute_point_05_override(
    raw_window: int,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    volume_col: str = "volume",
    **kwargs,
) -> int:
    """Wrapper for Point 05. Returns dynamic volume-density window size."""
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_05_config(engine)

    raw_val = int(raw_window) if np.isfinite(raw_window) else int(cfg.get("fallback_window", 24))
    vol = pd.to_numeric(df.get(volume_col), errors="coerce")
    new_val = compute_volume_density_window_size(vol, config=cfg)

    final = engine.apply_override(
        point_id="05",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_05] decision | %s raw=%d new=%d final=%d", symbol, raw_val, new_val, int(final))
    return int(final)


if __name__ == "__main__":
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 05 Volume-Density Window Smoke ===")
    engine = BiasOverrideEngine()
    n = 200
    rng = np.random.default_rng(5)
    # Simulate varying volume (some bars much higher — liquidation bars)
    vol = rng.uniform(500_000, 2_000_000, n)
    vol[50:55] = 10_000_000  # liquidation spike
    vol[120:125] = 8_000_000  # another spike
    df = pd.DataFrame({"volume": vol, "close": 100 + np.cumsum(rng.normal(0, 0.5, n))})
    raw_w = 24
    final_w = compute_point_05_override(raw_w, df, "TEST05", engine=engine)
    print(f"  raw_window={raw_w} -> final_window={final_w}")
    print("Smoke done.")
