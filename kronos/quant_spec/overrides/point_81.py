"""
KRONOS V1-ALT — Bias Override Point 81: "Overfitting to Noisy Multi-Asset Networks"

Manual description:
  "Modeling relationships across all 530 tokens linearly without pruning weak links."

Quant replacement:
  "Minimum Spanning Tree (MST) Correlation Network Pruning.
   Filter asset networks using MST metrics: d_i,j = 2*(1 - rho_i,j).
   Prune weak connections to minimize tree path length."

Uses shared compute_mst_pruning.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_mst_pruning
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_81")



_DEFAULT_POINT_81_CONFIG = {"threshold": 0.3, "min_data_density": 50, "fallback_edges": 0}


def compute_mst_pruned_network(
    returns: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Pure MST pruning of correlation network."""
    cfg = config or {}
    threshold = float(cfg.get("threshold", 0.3))
    min_d = int(cfg.get("min_data_density", 50))

    if len(returns) < min_d or returns.shape[1] < 2:
        return {"n_edges": int(cfg.get("fallback_edges", 0)), "adjacency": pd.DataFrame()}

    corr = returns.tail(min_d).corr()
    result = compute_mst_pruning(corr, threshold)
    logger.info("[POINT_81] mst | n_edges=%d", result["n_edges"])
    return result


def compute_point_81_override(
    raw_network_complexity: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    returns: pd.DataFrame = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_81_config(engine)

    raw_val = float(raw_network_complexity) if np.isfinite(raw_network_complexity) else 0.0

    if returns is not None and returns.shape[1] >= 2:
        result = compute_mst_pruned_network(returns, config=cfg)
        new_val = float(result["n_edges"])
    else:
        new_val = float(cfg.get("fallback_edges", 0))

    final = engine.apply_override(
        point_id="81",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_81] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 81 MST Pruning Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(81)
    x = rng.normal(0, 0.01, n)
    y = x * 0.7 + rng.normal(0, 0.005, n)
    z = rng.normal(0, 0.01, n)
    rets = pd.DataFrame({"A": x, "B": y, "C": z})
    final = compute_point_81_override(0.0, pd.DataFrame({"close": x}), "TEST81", engine=engine, returns=rets)
    print(f"raw_complexity=0.000 -> final={final:.4f}")

def _load_point_81_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_81", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_81_CONFIG





