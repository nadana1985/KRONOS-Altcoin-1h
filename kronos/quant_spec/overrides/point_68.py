"""
KRONOS V1-ALT — Bias Override Point 68: "Linear Stationarity of Asset Correlation"

Manual description:
  "Estimating asset relationships linearly using Pearson's correlation coefficient."

Quant replacement:
  "Rank-Based Spearman's Rho or Kendall's Tau Copula Modeling.
   Capture non-linear joint dependency structures."

Uses shared compute_spearman_rho.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_spearman_rho
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_68")



_DEFAULT_POINT_68_CONFIG = {"correlation_window": 50, "min_data_density": 50, "fallback_rho": 0.0}


def compute_rank_correlation(
    series_a: pd.Series,
    series_b: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure Spearman's Rho rank correlation."""
    cfg = config or {}
    w = int(cfg.get("correlation_window", 50))
    min_d = int(cfg.get("min_data_density", 50))

    a = pd.to_numeric(series_a, errors="coerce").dropna()
    b = pd.to_numeric(series_b, errors="coerce").dropna()
    if len(a) < min_d or len(b) < min_d:
        return float(cfg.get("fallback_rho", 0.0))

    rho = compute_spearman_rho(a, b, w)
    logger.info("[POINT_68] spearman_rho=%.4f", rho)
    return rho


def compute_point_68_override(
    raw_correlation: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    series_a: pd.Series = None,
    series_b: pd.Series = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_68_config(engine)

    raw_val = float(raw_correlation) if np.isfinite(raw_correlation) else 0.0

    if series_a is not None and series_b is not None:
        new_val = compute_rank_correlation(series_a, series_b, config=cfg)
    else:
        c = pd.to_numeric(df.get("close"), errors="coerce")
        # Use close vs lagged close as self-correlation proxy
        new_val = compute_rank_correlation(c, c.shift(1), config=cfg)

    final = engine.apply_override(
        point_id="68",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_68] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 68 Spearman's Rho Smoke ===")
    engine = BiasOverrideEngine()
    n = 120
    rng = np.random.default_rng(68)
    x = pd.Series(rng.normal(0, 1, n))
    y = x ** 2 + rng.normal(0, 0.1, n)  # non-linear
    final = compute_point_68_override(0.0, pd.DataFrame({"close": x}), "TEST68", engine=engine, series_a=x, series_b=y)
    print(f"pearson~0.0 -> spearman_final={final:.4f}")

def _load_point_68_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_68", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_68_CONFIG





