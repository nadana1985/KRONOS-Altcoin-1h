"""
KRONOS V1-ALT — Bias Override Point 33: "Absolute Genesis Boundary Tracking"

Quant replacement:
  "Cumulative Volume-Density Genesis Thresholding. Define the start of
   the training set where cumulative transactions reach a structural
   baseline density: genesis = min { t | sum CT_{t-i} >= baseline }."
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import logging
import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

logger = logging.getLogger("kronos.bias_override.point_33")


def _load_point_33_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    fallback = {"baseline_density": 1000000.0, "min_data_density": 100, "fallback_genesis": 0}
    if engine is None:
        return fallback
    try:
        cfg = engine.get_config("point_33") or {}
        return {
            "baseline_density": float(cfg.get("baseline_density", fallback["baseline_density"])),
            "min_data_density": int(cfg.get("min_data_density", fallback["min_data_density"])),
            "fallback_genesis": int(cfg.get("fallback_genesis", fallback["fallback_genesis"])),
        }
    except Exception as e:
        logger.warning("Point 33 config load failed: %s", e)
        return fallback


def compute_volume_genesis(volume: pd.Series, cfg: dict) -> dict:
    from kronos.quant_spec.overrides.utils import compute_volume_density_genesis
    if len(volume) < cfg["min_data_density"]:
        return {"genesis_index": cfg["fallback_genesis"], "quality_proxy": 0.5}
    idx = compute_volume_density_genesis(volume, cfg["baseline_density"])
    coverage = min(1.0, idx / max(len(volume), 1))
    return {"genesis_index": idx, "quality_proxy": 1.0 - coverage}


def compute_point_33_override(
    genesis_raw: int, volume: pd.Series, df=None, symbol=None, engine=None, **kwargs
) -> float:
    cfg = _load_point_33_config(engine)
    result = compute_volume_genesis(volume, cfg)
    override_val = float(result["genesis_index"])
    if engine is not None:
        engine_final = engine.apply_override(
            point_id="33", raw_value=float(genesis_raw), override_value=override_val,
            df=df, symbol=symbol, **kwargs,
        )
        return float(engine_final)
    return override_val


if __name__ == "__main__":
    n = 300
    rng = np.random.RandomState(42)
    vol = pd.Series(rng.uniform(1000, 50000, n))
    cfg = _load_point_33_config()
    result = compute_volume_genesis(vol, cfg)
    print(f"Point 33: genesis={result['genesis_index']}, quality={result['quality_proxy']:.4f}")
    print("Smoke done.")
