"""
KRONOS V1-ALT — Bias Override Point 92: "Static Compute Shard Sizes"

Manual description:
  "Hardcoding exact resource limits (memory_adaptive_shard_size: 8192) assumes
   static, uniform system resources."

Quant replacement:
  "Dynamic Compute-Aware Adaptive Resource Allocation. Adjust shard and batch sizes
   dynamically based on system memory usage:
   Shard_Size_t = round(System_Memory_available * lambda_safety)."

Uses shared compute_adaptive_shard_size and compute_system_memory_available_gb
from utils.

This provides adaptive resource allocation that scales with available hardware.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import (
    compute_system_memory_available_gb,
    compute_adaptive_shard_size,
)
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_92")



_DEFAULT_POINT_92_CONFIG = {
            "base_shard_size": 8192,
            "min_shard_size": 512,
            "max_shard_size": 32768,
            "safety_factor": 0.6,
            "memory_per_shard_mb": 50.0,
            "min_data_density": 0,
        }


def compute_dynamic_resource_allocation(
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compute dynamic resource allocation parameters.
    Returns a dict with shard_size, memory_info, and safety diagnostics.
    """
    cfg = config or {}
    base = int(cfg.get("base_shard_size", 8192))
    min_s = int(cfg.get("min_shard_size", 512))
    max_s = int(cfg.get("max_shard_size", 32768))
    safety = float(cfg.get("safety_factor", 0.6))
    mem_per_shard = float(cfg.get("memory_per_shard_mb", 50.0))

    avail_gb = compute_system_memory_available_gb()
    shard = compute_adaptive_shard_size(base, min_s, max_s, safety, mem_per_shard)

    # Memory headroom diagnostics
    used_by_shards = shard * mem_per_shard / 1024.0  # GB
    headroom_gb = avail_gb - used_by_shards

    return {
        "shard_size": shard,
        "base_shard_size": base,
        "memory_available_gb": float(avail_gb),
        "memory_used_by_shards_gb": float(used_by_shards),
        "headroom_gb": float(headroom_gb),
        "safety_factor": safety,
        "was_scaled_down": shard < base,
    }


def compute_point_92_override(
    raw_shard_size: int,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> int:
    """
    Wrapper for Point 92.
    raw_shard_size: the legacy static shard size.
    Returns the dynamically adjusted shard size.
    """
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_92_config(engine)

    raw_val = int(raw_shard_size) if np.isfinite(raw_shard_size) else int(cfg.get("base_shard_size", 8192))
    resources = compute_dynamic_resource_allocation(cfg)
    new_val = resources["shard_size"]

    final = engine.apply_override(
        point_id="92",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug(
        "[POINT_92] decision | %s raw=%d final=%d mem_avail=%.1fGB",
        symbol, raw_val, final, resources["memory_available_gb"],
    )
    return int(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

    print("=== Point 92 Dynamic Compute Resource Allocation Smoke ===")
    engine = BiasOverrideEngine()
    n = 20
    df = pd.DataFrame({"close": np.random.randn(n) + 100})

    raw = 8192
    final = compute_point_92_override(raw, df, "TEST92", engine=engine)
    resources = compute_dynamic_resource_allocation()
    print(f"raw={raw} -> final={final}")
    print(f"Memory: avail={resources['memory_available_gb']:.1f}GB, "
          f"used={resources['memory_used_by_shards_gb']:.1f}GB, "
          f"headroom={resources['headroom_gb']:.1f}GB")
    print(f"Was scaled down: {resources['was_scaled_down']}")

def _load_point_92_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_92", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_92_CONFIG





