"""
KRONOS V1-ALT — Bias Override Point 37: "Unweighted Timestamp Alignment"

Quant replacement:
  "Causal Latency Outlier Filtering. Exclude any kline from the feature
   generator where the exchange timestamp gap exceeds critical bounds:
   DeltaTS_t = CT_t - TS_t >= Quantile({DeltaTS}, q=0.99)."
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import logging
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

logger = logging.getLogger("kronos.bias_override.point_37")


def _load_point_37_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    fallback = {"window": 50, "quantile_threshold": 0.99, "min_data_density": 100, "fallback_filtered_pct": 0.0}
    if engine is None:
        return fallback
    try:
        cfg = engine.get_config("point_37") or {}
        return {
            "window": int(cfg.get("window", fallback["window"])),
            "quantile_threshold": float(cfg.get("quantile_threshold", fallback["quantile_threshold"])),
            "min_data_density": int(cfg.get("min_data_density", fallback["min_data_density"])),
            "fallback_filtered_pct": float(cfg.get("fallback_filtered_pct", fallback["fallback_filtered_pct"])),
        }
    except Exception as e:
        logger.warning("Point 37 config load failed: %s", e)
        return fallback


def compute_latency_outlier_filter(
    bar_timestamps: pd.Series, cfg: dict,
) -> dict:
    from kronos.quant_spec.overrides.utils import compute_causal_latency_outlier_filter
    if len(bar_timestamps) < cfg["min_data_density"]:
        return {"filtered_count": 0, "filtered_pct": 0.0, "threshold_ms": 0.0, "quality_proxy": 0.5}
    result = compute_causal_latency_outlier_filter(
        bar_timestamps, cfg["window"], cfg["quantile_threshold"]
    )
    n_filtered = int(result["filter_mask"].sum())
    pct = n_filtered / max(len(bar_timestamps), 1)
    return {
        "filtered_count": n_filtered,
        "filtered_pct": pct,
        "threshold_ms": result["threshold_ms"],
        "quality_proxy": 1.0 - min(pct, 1.0),
    }


def compute_point_37_override(
    alignment_raw: float, bar_timestamps: pd.Series,
    df=None, symbol=None, engine=None, **kwargs,
) -> float:
    cfg = _load_point_37_config(engine)
    result = compute_latency_outlier_filter(bar_timestamps, cfg)
    override_val = result["quality_proxy"]
    if engine is not None:
        engine_final = engine.apply_override(
            point_id="37", raw_value=alignment_raw, override_value=override_val,
            df=df, symbol=symbol, **kwargs,
        )
        return float(engine_final)
    return override_val


if __name__ == "__main__":
    n = 300
    ts = pd.Series(range(0, n * 3600000, 3600000))
    # Inject a few outliers
    ts.iloc[100] += 10_000_000
    ts.iloc[200] += 50_000_000
    cfg = _load_point_37_config()
    result = compute_latency_outlier_filter(ts, cfg)
    print(f"Point 37: filtered={result['filtered_count']}, pct={result['filtered_pct']:.4f}, "
          f"threshold={result['threshold_ms']:.0f}ms")
    print("Smoke done.")
