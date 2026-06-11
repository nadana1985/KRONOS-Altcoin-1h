"""
KRONOS V1-ALT — Bias Override Point 100: "Non-Adaptive Execution Sizing Bias"

Manual description:
  "Using fixed position sizing rules without incorporating real-time market impact
   or execution cost feedback."

Quant replacement:
  "Impact-Aware Adaptive Position Sizing. Scale position size inversely with
   estimated market impact and execution cost:
   Size_t = Target_Risk / (sigma_t * (1 + lambda * Estimated_Impact_t))."

Uses shared compute_impact_aware_position_size from utils.

This is the final operational firewall for execution — it prevents oversized
positions that would move the market against themselves.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import (
    compute_impact_aware_position_size,
    compute_close_to_close_vol,
    compute_corwin_schultz_spread,
)
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_100")



_DEFAULT_POINT_100_CONFIG = {
            "target_risk_pct": 0.02,
            "vol_window": 20,
            "lambda_impact": 1.0,
            "max_position_pct": 0.10,
            "min_position_usd": 100.0,
            "portfolio_value_usd": 100000.0,
            "min_data_density": 20,
            "fallback_position_pct": 0.02,
        }


def compute_adaptive_position_size(
    volume_usd: float,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """
    Compute impact-aware adaptive position size.
    Returns dict with position_size_usd and diagnostic details.
    """
    cfg = config or {}
    target_risk_pct = float(cfg.get("target_risk_pct", 0.02))
    vol_window = int(cfg.get("vol_window", 20))
    lambda_imp = float(cfg.get("lambda_impact", 1.0))
    max_pct = float(cfg.get("max_position_pct", 0.10))
    min_usd = float(cfg.get("min_position_usd", 100.0))
    portfolio_usd = float(cfg.get("portfolio_value_usd", 100000.0))
    min_d = int(cfg.get("min_data_density", 20))
    fb_pct = float(cfg.get("fallback_position_pct", 0.02))

    if len(close) < min_d:
        logger.info("[POINT_100] insufficient data — fallback position %.1f%%", fb_pct * 100)
        fallback_size = portfolio_usd * fb_pct
        return {
            "position_size_usd": max(min_usd, fallback_size),
            "impact_adjustment": 1.0,
            "estimated_impact": 0.0,
            "raw_size_usd": fallback_size,
            "target_risk_usd": portfolio_usd * fb_pct,
            "volatility": 0.0,
            "fallback": True,
        }

    volatility = compute_close_to_close_vol(close, vol_window)
    if not np.isfinite(volatility) or volatility <= 0:
        volatility = 0.01

    h = pd.to_numeric(high, errors="coerce")
    l = pd.to_numeric(low, errors="coerce")
    cs_window = int(cfg.get("cs_window", 2))
    spread = compute_corwin_schultz_spread(h, l, window=cs_window)
    if not np.isfinite(spread) or spread < 0:
        spread = 0.001

    target_risk_usd = portfolio_usd * target_risk_pct

    result = compute_impact_aware_position_size(
        target_risk_usd=target_risk_usd,
        volatility=volatility,
        spread=spread,
        volume_usd=volume_usd,
        lambda_impact=lambda_imp,
        max_position_pct=max_pct,
        min_position_usd=min_usd,
        portfolio_value_usd=portfolio_usd,
    )
    result["target_risk_usd"] = target_risk_usd
    result["volatility"] = volatility
    result["fallback"] = False

    logger.info(
        "[POINT_100] position_size | vol=%.4f spread=%.5f -> size=$%.0f (impact_adj=%.3f)",
        volatility, spread, result["position_size_usd"], result["impact_adjustment"],
    )
    return result


def compute_point_100_override(
    raw_size: float,
    df: pd.DataFrame,
    symbol: str,
    volume_usd: float = 1_000_000.0,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> dict:
    """
    Wrapper for Point 100.
    raw_size: the naive fixed position size in USD.
    Returns a dict with adaptive position sizing details.
    """
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_100_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    h = pd.to_numeric(df.get("high"), errors="coerce")
    l = pd.to_numeric(df.get("low"), errors="coerce")

    raw_val = float(raw_size) if np.isfinite(raw_size) else float(cfg.get("portfolio_value_usd", 100000.0) * cfg.get("fallback_position_pct", 0.02))
    result = compute_adaptive_position_size(volume_usd, h, l, c, config=cfg)

    # Engine routes on position_size_usd
    final_size = engine.apply_override(
        point_id="100",
        raw_value=raw_val,
        override_value=result["position_size_usd"],
        df=df,
        symbol=symbol,
        **kwargs,
    )

    result["engine_final_size"] = float(final_size)
    logger.debug(
        "[POINT_100] decision | %s raw=$%.0f final=$%.0f impact_adj=%.3f",
        symbol, raw_val, final_size, result["impact_adjustment"],
    )
    return result


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

    print("=== Point 100 Impact-Aware Position Sizing Smoke ===")
    engine = BiasOverrideEngine()
    n = 60
    rng = np.random.default_rng(100)
    c = 100 + np.cumsum(rng.normal(0, 0.3, n))
    h = c + rng.uniform(0.1, 0.5, n)
    l = c - rng.uniform(0.1, 0.5, n)
    df = pd.DataFrame({"close": c, "high": h, "low": l, "volume": rng.uniform(1e6, 5e6, n)})

    raw = 5000.0  # naive fixed $5k
    for vol_mult, label in [(0.5, "low_vol"), (1.0, "normal"), (3.0, "high_vol")]:
        vdf = pd.DataFrame({
            "close": 100 + np.cumsum(rng.normal(0, 0.3 * vol_mult, n)),
            "high": 100 + np.cumsum(rng.normal(0, 0.3 * vol_mult, n)) + rng.uniform(0, 0.5, n),
            "low": 100 + np.cumsum(rng.normal(0, 0.3 * vol_mult, n)) - rng.uniform(0, 0.5, n),
            "volume": rng.uniform(1e5, 5e6, n),
        })
        res = compute_point_100_override(raw, vdf, "TEST100", volume_usd=1e6, engine=engine)
        print(f"  {label:10s} -> size=${res['engine_final_size']:.0f} """
              f"(impact_adj={res['impact_adjustment']:.3f}, vol={res['volatility']:.4f})")

def _load_point_100_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_100", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_100_CONFIG

def compute_adaptive_position_size(
    volume_usd: float,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """
    Compute impact-aware adaptive position size.
    Returns dict with position_size_usd and diagnostic details.
    """
    cfg = config or {}
    target_risk_pct = float(cfg.get("target_risk_pct", 0.02))
    vol_window = int(cfg.get("vol_window", 20))
    lambda_imp = float(cfg.get("lambda_impact", 1.0))
    max_pct = float(cfg.get("max_position_pct", 0.10))
    min_usd = float(cfg.get("min_position_usd", 100.0))
    portfolio_usd = float(cfg.get("portfolio_value_usd", 100000.0))
    min_d = int(cfg.get("min_data_density", 20))
    fb_pct = float(cfg.get("fallback_position_pct", 0.02))

    if len(close) < min_d:
        logger.info("[POINT_100] insufficient data — fallback position %.1f%%", fb_pct * 100)
        fallback_size = portfolio_usd * fb_pct
        return {
            "position_size_usd": max(min_usd, fallback_size),
            "impact_adjustment": 1.0,
            "estimated_impact": 0.0,
            "raw_size_usd": fallback_size,
            "target_risk_usd": portfolio_usd * fb_pct,
            "volatility": 0.0,
            "fallback": True,
        }

    volatility = compute_close_to_close_vol(close, vol_window)
    if not np.isfinite(volatility) or volatility <= 0:
        volatility = 0.01

    h = pd.to_numeric(high, errors="coerce")
    l = pd.to_numeric(low, errors="coerce")
    cs_window = int(cfg.get("cs_window", 2))
    spread = compute_corwin_schultz_spread(h, l, window=cs_window)
    if not np.isfinite(spread) or spread < 0:
        spread = 0.001

    target_risk_usd = portfolio_usd * target_risk_pct

    result = compute_impact_aware_position_size(
        target_risk_usd=target_risk_usd,
        volatility=volatility,
        spread=spread,
        volume_usd=volume_usd,
        lambda_impact=lambda_imp,
        max_position_pct=max_pct,
        min_position_usd=min_usd,
        portfolio_value_usd=portfolio_usd,
    )
    result["target_risk_usd"] = target_risk_usd
    result["volatility"] = volatility
    result["fallback"] = False

    logger.info(
        "[POINT_100] position_size | vol=%.4f spread=%.5f -> size=$%.0f (impact_adj=%.3f)",
        volatility, spread, result["position_size_usd"], result["impact_adjustment"],
    )
    return result


def compute_point_100_override(
    raw_size: float,
    df: pd.DataFrame,
    symbol: str,
    volume_usd: float = 1_000_000.0,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> dict:
    """
    Wrapper for Point 100.
    raw_size: the naive fixed position size in USD.
    Returns a dict with adaptive position sizing details.
    """
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_100_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    h = pd.to_numeric(df.get("high"), errors="coerce")
    l = pd.to_numeric(df.get("low"), errors="coerce")

    raw_val = float(raw_size) if np.isfinite(raw_size) else float(cfg.get("portfolio_value_usd", 100000.0) * cfg.get("fallback_position_pct", 0.02))
    result = compute_adaptive_position_size(volume_usd, h, l, c, config=cfg)

    # Engine routes on position_size_usd
    final_size = engine.apply_override(
        point_id="100",
        raw_value=raw_val,
        override_value=result["position_size_usd"],
        df=df,
        symbol=symbol,
        **kwargs,
    )

    result["engine_final_size"] = float(final_size)
    logger.debug(
        "[POINT_100] decision | %s raw=$%.0f final=$%.0f impact_adj=%.3f",
        symbol, raw_val, final_size, result["impact_adjustment"],
    )
    return result


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

    print("=== Point 100 Impact-Aware Position Sizing Smoke ===")
    engine = BiasOverrideEngine()
    n = 60
    rng = np.random.default_rng(100)
    c = 100 + np.cumsum(rng.normal(0, 0.3, n))
    h = c + rng.uniform(0.1, 0.5, n)
    l = c - rng.uniform(0.1, 0.5, n)
    df = pd.DataFrame({"close": c, "high": h, "low": l, "volume": rng.uniform(1e6, 5e6, n)})

    raw = 5000.0  # naive fixed $5k
    for vol_mult, label in [(0.5, "low_vol"), (1.0, "normal"), (3.0, "high_vol")]:
        vdf = pd.DataFrame({
            "close": 100 + np.cumsum(rng.normal(0, 0.3 * vol_mult, n)),
            "high": 100 + np.cumsum(rng.normal(0, 0.3 * vol_mult, n)) + rng.uniform(0, 0.5, n),
            "low": 100 + np.cumsum(rng.normal(0, 0.3 * vol_mult, n)) - rng.uniform(0, 0.5, n),
            "volume": rng.uniform(1e5, 5e6, n),
        })
        res = compute_point_100_override(raw, vdf, "TEST100", volume_usd=1e6, engine=engine)
        print(f"  {label:10s} -> size=${res['engine_final_size']:.0f} """
              f"(impact_adj={res['impact_adjustment']:.3f}, vol={res['volatility']:.4f})")

    print("Smoke done.")
