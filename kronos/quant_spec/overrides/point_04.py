"""
KRONOS V1-ALT — Bias Override Point 04: "Manual Linear Multiplier Bias"

Manual description:
  "Using arbitrary multipliers assumes linear pricing relationships that do not hold across regimes or assets."

Quant replacement:
  "Rolling Percentile Rank Transform. Transform multipliers through a rolling percentile rank transform:
   Rank(X_t) = sum I[X_tau <= X_t] / W for tau=t-W."

This replaces raw multipliers (e.g. 4.2, 1.5) with their empirical rank within recent history.
The rank is bounded and regime-adaptive.

Reusable helper: kronos.quant_spec.overrides.utils.rolling_percentile_rank

Follows the exact engine-routed pattern of Points 01/02.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import rolling_percentile_rank
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_04")



_DEFAULT_POINT_04_CONFIG = {
            "rank_window": 100,
            "min_data_density": 100,
            "fallback_rank": 0.5,
            "clip_min": 0.05,
            "clip_max": 0.95,
        }

def _load_point_04_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_04", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_04_CONFIG

def compute_rolling_percentile_rank_multiplier(
    raw_multiplier: float,
    history_proxy: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Pure quant replacement for Point 04.

    Returns the rank-transformed version of the multiplier (in [clip_min, clip_max]).
    """
    cfg = config or {}
    window = int(cfg.get("rank_window", 100))
    min_dens = int(cfg.get("min_data_density", 100))
    fallback = float(cfg.get("fallback_rank", 0.5))
    cmin = float(cfg.get("clip_min", 0.05))
    cmax = float(cfg.get("clip_max", 0.95))

    if len(history_proxy.dropna()) < min_dens:
        logger.info("[POINT_04] insufficient history for rank — using fallback %.2f", fallback)
        return float(np.clip(fallback * raw_multiplier, cmin * raw_multiplier, cmax * raw_multiplier))  # conservative scaling

    rank = rolling_percentile_rank(history_proxy, window)
    transformed = rank * raw_multiplier   # scale the multiplier by its rank in distribution
    return float(np.clip(transformed, cmin * raw_multiplier, cmax * raw_multiplier))


def compute_point_04_override(
    raw_multiplier: float,
    df: pd.DataFrame,
    symbol: str,
    history_proxy: Optional[pd.Series] = None,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    """
    Full wrapper for Point 04.

    Computes raw (original multiplier) and new (rank-transformed).
    Routes decision through BiasOverrideEngine.
    """
    if engine is None:
        engine = BiasOverrideEngine()

    cfg = _load_point_04_config(engine)

    # Build proxy history if not supplied: use recent |log returns| * volume as "strength" distribution
    if history_proxy is None or len(history_proxy) < 10:
        close = pd.to_numeric(df.get("close", pd.Series(dtype=float)), errors="coerce")
        vol = pd.to_numeric(df.get("volume", pd.Series(1.0, index=df.index)), errors="coerce")
        logret = (close / close.shift(1) - 1.0).abs()
        history_proxy = (logret * vol).dropna()

    raw_val = float(raw_multiplier)
    new_val = compute_rolling_percentile_rank_multiplier(raw_val, history_proxy, config=cfg)

    final = engine.apply_override(
        point_id="04",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )

    logger.debug(
        "[POINT_04] engine_decision | symbol=%s | raw_mult=%.3f | new_mult=%.3f | final=%.3f",
        symbol, raw_val, new_val, final
    )
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

    print("=== Point 04 (Manual Linear Multiplier Bias) Smoke ===")
    engine = BiasOverrideEngine()
    cfg = _load_point_04_config(engine)
    print("Config:", {k: cfg[k] for k in ["rank_window", "fallback_rank"]})

    np.random.seed(42)
    n = 200
    proxy = pd.Series(np.random.lognormal(0, 0.8, n))  # proxy for past multiplier applications / strength

    for raw in [4.2, 1.5, 0.8, 3.0]:
        new = compute_rolling_percentile_rank_multiplier(raw, proxy, config=cfg)
        print(f"raw_mult={raw:.2f} -> rank_transformed={new:.3f}")

    # Engine path (raw until status flipped)
    dummy_df = pd.DataFrame({"close": np.linspace(100, 101, 50), "volume": np.random.uniform(1e6, 3e6, 50)})
    final = compute_point_04_override(4.2, dummy_df, "TEST04", engine=engine)
    print(f"Via engine (raw expected): {final:.3f}")

    print("Point 04 smoke complete.")