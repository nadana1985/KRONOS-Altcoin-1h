"""
KRONOS V1-ALT — Bias Override Point 79: "Point-in-Time Prediction Evaluation"

Manual description:
  "Backtesting models using simple point-in-time predictions."

Quant replacement:
  "Combinatorial Purged Cross-Validation (CPCV) Path Calculations. Test across combinations of historical blocks to generate a distribution of out-of-sample paths:
   S = {Combinations of N blocks taken k at a time}."

This returns (or operates on) a set of CPCV paths. The "value" can be the number of paths or a summary statistic from the paths.

Uses shared generate_cpcv_paths.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, List, Tuple

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import generate_cpcv_paths
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_79")



_DEFAULT_POINT_79_CONFIG = {"n_blocks": 6, "k_test": 2, "embargo_window": 5, "min_data_density": 200, "n_paths_fallback": 10}


def generate_cpcv_paths_for_data(
    n_blocks: int,
    k_test: int,
    embargo: int = 0,
    config: Optional[Dict[str, Any]] = None,
) -> List[Tuple[List[int], List[int]]]:
    """Pure CPCV path generator."""
    cfg = config or {}
    paths = generate_cpcv_paths(n_blocks, k_test)
    # Note: full purging/embargo per path is applied in the calling evaluation harness using Point 35 logic.
    logger.info("[POINT_79] cpcv_paths | n_blocks=%d k_test=%d -> %d paths", n_blocks, k_test, len(paths))
    return paths


def compute_point_79_override(
    raw_n_paths: int,
    n_blocks: int,
    k_test: int,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> int:
    """
    Wrapper for Point 79.
    raw_n_paths: number of paths from a naive (e.g. single walk-forward) approach.
    Returns the number of CPCV paths (or a representative count) after engine decision.
    """
    if engine is None:
        engine = BiasOverrideEngine()

    cfg = _load_point_79_config(engine)
    n_b = int(cfg.get("n_blocks", n_blocks))
    k_t = int(cfg.get("k_test", k_test))
    min_d = int(cfg.get("min_data_density", 200))
    fb = int(cfg.get("n_paths_fallback", 10))

    if len(df) < min_d:
        logger.info("[POINT_79] insufficient data — fallback to %d paths", fb)
        n_paths = fb
    else:
        paths = generate_cpcv_paths_for_data(n_b, k_t, config=cfg)
        n_paths = len(paths)

    final_n = engine.apply_override(
        point_id="79",
        raw_value=raw_n_paths,
        override_value=n_paths,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_79] decision | %s raw_paths=%d cpcv_paths=%d final=%d", symbol, raw_n_paths, n_paths, int(final_n))
    return int(final_n)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 79 CPCV Paths Smoke ===")
    engine = BiasOverrideEngine()
    n = 200
    df = pd.DataFrame({"close": np.cumsum(np.random.randn(n))})
    raw_paths = 5
    final = compute_point_79_override(raw_paths, n_blocks=6, k_test=2, df=df, symbol="TEST79", engine=engine)
    print(f"raw_paths={raw_paths} -> final_cpcv_paths={final}")

def _load_point_79_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_79", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_79_CONFIG

def generate_cpcv_paths_for_data(
    n_blocks: int,
    k_test: int,
    embargo: int = 0,
    config: Optional[Dict[str, Any]] = None,
) -> List[Tuple[List[int], List[int]]]:
    """Pure CPCV path generator."""
    cfg = config or {}
    paths = generate_cpcv_paths(n_blocks, k_test)
    # Note: full purging/embargo per path is applied in the calling evaluation harness using Point 35 logic.
    logger.info("[POINT_79] cpcv_paths | n_blocks=%d k_test=%d -> %d paths", n_blocks, k_test, len(paths))
    return paths


def compute_point_79_override(
    raw_n_paths: int,
    n_blocks: int,
    k_test: int,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> int:
    """
    Wrapper for Point 79.
    raw_n_paths: number of paths from a naive (e.g. single walk-forward) approach.
    Returns the number of CPCV paths (or a representative count) after engine decision.
    """
    if engine is None:
        engine = BiasOverrideEngine()

    cfg = _load_point_79_config(engine)
    n_b = int(cfg.get("n_blocks", n_blocks))
    k_t = int(cfg.get("k_test", k_test))
    min_d = int(cfg.get("min_data_density", 200))
    fb = int(cfg.get("n_paths_fallback", 10))

    if len(df) < min_d:
        logger.info("[POINT_79] insufficient data — fallback to %d paths", fb)
        n_paths = fb
    else:
        paths = generate_cpcv_paths_for_data(n_b, k_t, config=cfg)
        n_paths = len(paths)

    final_n = engine.apply_override(
        point_id="79",
        raw_value=raw_n_paths,
        override_value=n_paths,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_79] decision | %s raw_paths=%d cpcv_paths=%d final=%d", symbol, raw_n_paths, n_paths, int(final_n))
    return int(final_n)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 79 CPCV Paths Smoke ===")
    engine = BiasOverrideEngine()
    n = 200
    df = pd.DataFrame({"close": np.cumsum(np.random.randn(n))})
    raw_paths = 5
    final = compute_point_79_override(raw_paths, n_blocks=6, k_test=2, df=df, symbol="TEST79", engine=engine)
    print(f"raw_paths={raw_paths} -> final_cpcv_paths={final}")
    print("Smoke done.")