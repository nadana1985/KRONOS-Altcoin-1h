"""
KRONOS V1-ALT — Bias Override Point 43: "Multi-Timeframe Integration Redundancy"

Quant replacement:
  "Multiresolution Wavelet Decomposition. Extract orthogonal features
   across multiple scales using a Haar wavelet:
   psi_j,k(t) = 2^{j/2} psi(2^j t - k)."
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import logging
import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

logger = logging.getLogger("kronos.bias_override.point_43")


def _load_point_43_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    fallback = {"levels": 3, "min_data_density": 300, "fallback_orthogonality": 0.5}
    if engine is None:
        return fallback
    try:
        cfg = engine.get_config("point_43") or {}
        return {
            "levels": int(cfg.get("levels", fallback["levels"])),
            "min_data_density": int(cfg.get("min_data_density", fallback["min_data_density"])),
            "fallback_orthogonality": float(cfg.get("fallback_orthogonality", fallback["fallback_orthogonality"])),
        }
    except Exception as e:
        logger.warning("Point 43 config load failed: %s", e)
        return fallback


def compute_wavelet_decomp(series: pd.Series, cfg: dict) -> dict:
    from kronos.quant_spec.overrides.utils import compute_wavelet_decomposition
    if len(series) < cfg["min_data_density"]:
        return {"energy_distribution": [1.0], "orthogonality_score": cfg["fallback_orthogonality"]}
    result = compute_wavelet_decomposition(series, cfg["levels"])
    energy = result["energy"]
    # Orthogonality score: how evenly distributed the energy is
    if len(energy) > 1:
        uniform = 1.0 / len(energy)
        ortho = 1.0 - sum((e - uniform) ** 2 for e in energy) * len(energy)
    else:
        ortho = 0.5
    return {"energy_distribution": energy, "orthogonality_score": float(np.clip(ortho, 0, 1))}


def compute_point_43_override(
    redundancy_raw: float, series: pd.Series,
    df=None, symbol=None, engine=None, **kwargs,
) -> float:
    cfg = _load_point_43_config(engine)
    result = compute_wavelet_decomp(series, cfg)
    override_val = result["orthogonality_score"]
    if engine is not None:
        engine_final = engine.apply_override(
            point_id="43", raw_value=redundancy_raw, override_value=override_val,
            df=df, symbol=symbol, **kwargs,
        )
        return float(engine_final)
    return override_val


if __name__ == "__main__":
    n = 300
    rng = np.random.RandomState(42)
    s = pd.Series(np.cumsum(rng.randn(n) * 0.01) + 100)
    cfg = _load_point_43_config()
    result = compute_wavelet_decomp(s, cfg)
    print(f"Point 43: energy={result['energy_distribution']}, ortho={result['orthogonality_score']:.4f}")
    print("Smoke done.")
