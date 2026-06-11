"""
KRONOS V1-ALT — Bias Override Point 27: "Symmetrical Order Flow Pressure Assumptions"

Manual description (from bias_override_registry.yaml):
  "Short liquidations have equal microstructural patterns (assumes symmetry
   in buy/sell pressure)."

Quant replacement:
  "Causal Semivariance Directional Scaling. Scale the denominator of the
   VPIN proxy relative to downside variance:
   sigma_down,t^2 = sum min(0, ln(C_{t-i}/C_{t-i-1}))^2 / W."

This module provides the pure quant replacement logic + a convenience wrapper
that routes through BiasOverrideEngine.apply_override().
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import logging
import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

logger = logging.getLogger("kronos.bias_override.point_27")


def _load_point_27_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    """Load Point 27 parameters from liquidity_tiers.yaml overrides.point_27."""
    fallback = {
        "downside_window": 20,
        "asymmetry_scale": 0.5,
        "min_data_density": 150,
        "fallback_directional_weight": 0.5,
    }
    if engine is None:
        return fallback
    try:
        cfg = engine.get_config("point_27") or {}
        return {
            "downside_window": int(cfg.get("downside_window", fallback["downside_window"])),
            "asymmetry_scale": float(cfg.get("asymmetry_scale", fallback["asymmetry_scale"])),
            "min_data_density": int(cfg.get("min_data_density", fallback["min_data_density"])),
            "fallback_directional_weight": float(cfg.get("fallback_directional_weight", fallback["fallback_directional_weight"])),
        }
    except Exception as e:
        logger.warning("Point 27 config load failed: %s", e)
        return fallback


def compute_semivariance_directional_scaling(
    close: pd.Series,
    window: int,
    asymmetry_scale: float = 0.5,
    min_data_density: int = 150,
) -> dict:
    """
    Causal Semivariance Directional Scaling (Point 27).

    Computes downside semivariance and uses it to scale directional
    order flow pressure, breaking the symmetry assumption.
    """
    from kronos.quant_spec.overrides.utils import compute_downside_semivariance

    if len(close) < min_data_density:
        return {
            "directional_weight": 0.5,
            "downside_semivar": 0.01,
            "quality_proxy": 0.5,
        }

    downside_sv = compute_downside_semivariance(close, window)
    # Directional weight: higher downside semivariance -> stronger downside bias
    # Normalize: baseline variance vs downside
    r = np.log((close / close.shift(1)).clip(lower=1e-12))
    total_var = float(r.tail(window).var()) if len(r) >= window else 1e-4
    if total_var <= 0:
        total_var = 1e-4

    directional_weight = 0.5 + asymmetry_scale * (downside_sv / total_var - 0.5)
    directional_weight = float(np.clip(directional_weight, 0.1, 0.9))

    return {
        "directional_weight": directional_weight,
        "downside_semivar": float(downside_sv),
        "quality_proxy": directional_weight,
    }


def compute_point_27_override(
    vpin_raw: float,
    close: pd.Series,
    df: Optional[pd.DataFrame] = None,
    symbol: Optional[str] = None,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    """Production wrapper for Point 27: Causal Semivariance Directional Scaling."""
    cfg = _load_point_27_config(engine)

    raw_val = vpin_raw
    result = compute_semivariance_directional_scaling(
        close=close,
        window=cfg["downside_window"],
        asymmetry_scale=cfg["asymmetry_scale"],
        min_data_density=cfg["min_data_density"],
    )
    override_val = result["directional_weight"]

    if engine is not None:
        engine_final = engine.apply_override(
            point_id="27",
            raw_value=raw_val,
            override_value=override_val,
            df=df,
            symbol=symbol,
            **kwargs,
        )
        return float(engine_final)

    return float(override_val)


if __name__ == "__main__":
    n = 300
    rng = np.random.RandomState(42)
    close = pd.Series(np.cumsum(rng.randn(n) * 0.01) + 100)
    cfg = _load_point_27_config()
    result = compute_semivariance_directional_scaling(
        close, cfg["downside_window"], cfg["asymmetry_scale"], cfg["min_data_density"]
    )
    print(f"Point 27: direction={result['directional_weight']:.4f}, "
          f"dsvar={result['downside_semivar']:.6f}")
    print("Smoke done.")
