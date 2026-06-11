"""
KRONOS V1-ALT — Bias Override Point 17: "Constant Spread Assumptions"

Manual description:
  "Assuming zero execution spread or static execution fees across all altcoins ignores highly volatile microstructural slippage."

Quant replacement:
  "Corwin-Schultz High-Low Range Spread Estimator. Estimate continuous spread dynamically from adjacent bars:
   gamma = [ln(H_t / L_t)]^2 + [ln(H_{t+1} / L_{t+1})]^2 ; Spread = 2*(e^gamma -1) / (1+e^gamma)."

Uses shared compute_corwin_schultz_spread.

This provides a dynamic, high-low based spread estimate that can be used for execution modeling or volatility filters (e.g. Point 57).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_corwin_schultz_spread
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_17")



_DEFAULT_POINT_17_CONFIG = {"cs_window": 2, "min_data_density": 50, "fallback_spread": 0.001}


def compute_corwin_schultz_spread_estimate(
    high: pd.Series,
    low: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure Corwin-Schultz spread replacement."""
    cfg = config or {}
    w = int(cfg.get("cs_window", 2))
    min_d = int(cfg.get("min_data_density", 50))
    fb = float(cfg.get("fallback_spread", 0.001))

    if len(high) < min_d or len(low) < min_d:
        logger.info("[POINT_17] insufficient data — fallback spread %.4f", fb)
        return fb

    spread = compute_corwin_schultz_spread(high, low, w)
    if not np.isfinite(spread) or spread <= 0:
        spread = fb
    logger.info("[POINT_17] corwin_schultz | window=%d -> spread=%.5f", w, spread)
    return float(spread)


def compute_point_17_override(
    raw_spread: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_17_config(engine)

    h = pd.to_numeric(df.get("high"), errors="coerce")
    l = pd.to_numeric(df.get("low"), errors="coerce")

    raw_val = float(raw_spread) if np.isfinite(raw_spread) else float(cfg.get("fallback_spread", 0.001))
    new_val = compute_corwin_schultz_spread_estimate(h, l, config=cfg)

    final = engine.apply_override(
        point_id="17",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_17] decision | %s raw=%.5f new=%.5f final=%.5f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 17 Corwin-Schultz Spread Smoke ===")
    engine = BiasOverrideEngine()
    n = 60
    rng = np.random.default_rng(17)
    c = 100 + np.cumsum(rng.normal(0, 0.3, n))
    h = c + rng.uniform(0.1, 0.6, n)
    l = c - rng.uniform(0.1, 0.6, n)
    df = pd.DataFrame({"high": h, "low": l})
    raw = 0.002
    final = compute_point_17_override(raw, df, "TEST17", engine=engine)
    print(f"raw={raw:.5f} -> final={final:.5f}")

def _load_point_17_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_17", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_17_CONFIG

def compute_corwin_schultz_spread_estimate(
    high: pd.Series,
    low: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Pure Corwin-Schultz spread replacement."""
    cfg = config or {}
    w = int(cfg.get("cs_window", 2))
    min_d = int(cfg.get("min_data_density", 50))
    fb = float(cfg.get("fallback_spread", 0.001))

    if len(high) < min_d or len(low) < min_d:
        logger.info("[POINT_17] insufficient data — fallback spread %.4f", fb)
        return fb

    spread = compute_corwin_schultz_spread(high, low, w)
    if not np.isfinite(spread) or spread <= 0:
        spread = fb
    logger.info("[POINT_17] corwin_schultz | window=%d -> spread=%.5f", w, spread)
    return float(spread)


def compute_point_17_override(
    raw_spread: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_17_config(engine)

    h = pd.to_numeric(df.get("high"), errors="coerce")
    l = pd.to_numeric(df.get("low"), errors="coerce")

    raw_val = float(raw_spread) if np.isfinite(raw_spread) else float(cfg.get("fallback_spread", 0.001))
    new_val = compute_corwin_schultz_spread_estimate(h, l, config=cfg)

    final = engine.apply_override(
        point_id="17",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_17] decision | %s raw=%.5f new=%.5f final=%.5f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 17 Corwin-Schultz Spread Smoke ===")
    engine = BiasOverrideEngine()
    n = 60
    rng = np.random.default_rng(17)
    c = 100 + np.cumsum(rng.normal(0, 0.3, n))
    h = c + rng.uniform(0.1, 0.6, n)
    l = c - rng.uniform(0.1, 0.6, n)
    df = pd.DataFrame({"high": h, "low": l})
    raw = 0.002
    final = compute_point_17_override(raw, df, "TEST17", engine=engine)
    print(f"raw={raw:.5f} -> final={final:.5f}")
    print("Smoke done.")