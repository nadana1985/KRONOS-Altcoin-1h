"""
KRONOS V1-ALT — Bias Override Point 10: "Sessional Latency Bias"

Manual description:
  "Restricting execution pipelines using a static calendar buffer to guarantee
   data settlement ignores actual system latencies."

Quant replacement:
  "Systemic Timestamp Latency Truncation. Truncate calculations based on
   actual elapsed millisecond offsets:
   Truncate = I[SystemTime - CT >= tau_measured_latency]."

Uses shared compute_timestamp_latency_truncation.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_timestamp_latency_truncation
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_10")



_DEFAULT_POINT_10_CONFIG = {
            "base_latency_ms": 100.0,
            "latency_window": 50,
            "latency_tolerance": 0.15,
            "min_data_density": 100,
            "fallback_buffer_days": 1,
        }


def compute_latency_truncation(
    bar_timestamps: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Compute timestamp-based latency truncation mask."""
    cfg = config or {}
    base_lat = float(cfg.get("base_latency_ms", 100.0))
    lat_w = int(cfg.get("latency_window", 50))
    min_d = int(cfg.get("min_data_density", 100))

    if len(bar_timestamps) < min_d:
        fb_days = int(cfg.get("fallback_buffer_days", 1))
        return {
            "truncate_mask": pd.Series(False, index=bar_timestamps.index),
            "measured_latency_ms": base_lat,
            "threshold_ms": base_lat,
            "truncated_count": 0,
            "fallback_days": fb_days,
        }

    lat_tol = float(cfg.get("latency_tolerance", 0.15))
    result = compute_timestamp_latency_truncation(bar_timestamps, base_lat, lat_w, latency_tolerance=lat_tol)
    truncated_count = int(result["truncate_mask"].sum())
    result["truncated_count"] = truncated_count
    logger.info(
        "[POINT_10] latency_truncation | base=%.0fms measured=%.0fms threshold=%.0fms truncated=%d",
        base_lat, result["measured_latency_ms"], result["threshold_ms"], truncated_count,
    )
    return result


def compute_point_10_override(
    raw_buffer_days: int,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    timestamp_col: str = "timestamp",
    **kwargs,
) -> dict:
    """Wrapper for Point 10. Returns truncation diagnostics."""
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_10_config(engine)

    raw_val = int(raw_buffer_days) if np.isfinite(raw_buffer_days) else int(cfg.get("fallback_buffer_days", 1))

    ts = pd.to_numeric(df.get(timestamp_col, df.index), errors="coerce")
    if ts is None or len(ts) == 0:
        ts = pd.Series(range(len(df)))

    result = compute_latency_truncation(ts, config=cfg)

    # Engine routing: use truncated count as proxy (fewer truncations = better)
    quality_proxy = max(0.0, 1.0 - result["truncated_count"] / max(len(ts), 1))
    engine_final = engine.apply_override(
        point_id="10",
        raw_value=float(raw_val),
        override_value=quality_proxy,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    result["engine_final_quality"] = float(engine_final)
    return result


if __name__ == "__main__":
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 10 Timestamp Latency Truncation Smoke ===")
    engine = BiasOverrideEngine()
    n = 100
    # Regular timestamps (hourly, in ms)
    ts = np.arange(n) * 3_600_000.0
    ts[30] += 500_000  # 500s delay (stale bar)
    ts[60] += 1_000_000  # 1000s delay
    df = pd.DataFrame({"timestamp": ts, "close": 100 + np.cumsum(np.random.randn(n) * 0.5)})
    result = compute_point_10_override(1, df, "TEST10", engine=engine, timestamp_col="timestamp")
    print(f"  truncated_count: {result['truncated_count']}")
    print(f"  measured_latency: {result['measured_latency_ms']:.0f}")

def _load_point_10_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_10", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_10_CONFIG

def compute_latency_truncation(
    bar_timestamps: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Compute timestamp-based latency truncation mask."""
    cfg = config or {}
    base_lat = float(cfg.get("base_latency_ms", 100.0))
    lat_w = int(cfg.get("latency_window", 50))
    min_d = int(cfg.get("min_data_density", 100))

    if len(bar_timestamps) < min_d:
        fb_days = int(cfg.get("fallback_buffer_days", 1))
        return {
            "truncate_mask": pd.Series(False, index=bar_timestamps.index),
            "measured_latency_ms": base_lat,
            "threshold_ms": base_lat,
            "truncated_count": 0,
            "fallback_days": fb_days,
        }

    lat_tol = float(cfg.get("latency_tolerance", 0.15))
    result = compute_timestamp_latency_truncation(bar_timestamps, base_lat, lat_w, latency_tolerance=lat_tol)
    truncated_count = int(result["truncate_mask"].sum())
    result["truncated_count"] = truncated_count
    logger.info(
        "[POINT_10] latency_truncation | base=%.0fms measured=%.0fms threshold=%.0fms truncated=%d",
        base_lat, result["measured_latency_ms"], result["threshold_ms"], truncated_count,
    )
    return result


def compute_point_10_override(
    raw_buffer_days: int,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    timestamp_col: str = "timestamp",
    **kwargs,
) -> dict:
    """Wrapper for Point 10. Returns truncation diagnostics."""
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_10_config(engine)

    raw_val = int(raw_buffer_days) if np.isfinite(raw_buffer_days) else int(cfg.get("fallback_buffer_days", 1))

    ts = pd.to_numeric(df.get(timestamp_col, df.index), errors="coerce")
    if ts is None or len(ts) == 0:
        ts = pd.Series(range(len(df)))

    result = compute_latency_truncation(ts, config=cfg)

    # Engine routing: use truncated count as proxy (fewer truncations = better)
    quality_proxy = max(0.0, 1.0 - result["truncated_count"] / max(len(ts), 1))
    engine_final = engine.apply_override(
        point_id="10",
        raw_value=float(raw_val),
        override_value=quality_proxy,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    result["engine_final_quality"] = float(engine_final)
    return result


if __name__ == "__main__":
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 10 Timestamp Latency Truncation Smoke ===")
    engine = BiasOverrideEngine()
    n = 100
    # Regular timestamps (hourly, in ms)
    ts = np.arange(n) * 3_600_000.0
    ts[30] += 500_000  # 500s delay (stale bar)
    ts[60] += 1_000_000  # 1000s delay
    df = pd.DataFrame({"timestamp": ts, "close": 100 + np.cumsum(np.random.randn(n) * 0.5)})
    result = compute_point_10_override(1, df, "TEST10", engine=engine, timestamp_col="timestamp")
    print(f"  truncated_count: {result['truncated_count']}")
    print(f"  measured_latency: {result['measured_latency_ms']:.0f}ms")
    print("Smoke done.")
