"""
KRONOS V1-ALT — Bias Override Point 54: "Homoskedastic Multi-Asset Volatility Matrices"

Manual description:
  "Calculating covariance matrices under flat homoskedastic assumptions ignores volatility spillovers across assets."

Quant replacement:
  "Dynamic Conditional Correlation (DCC-GARCH). Model the time-varying correlation matrix of returns dynamically: H_t = D_t R_t D_t."

Practical implementation for per-symbol context: uses GARCH vols + dynamic correlation to a market proxy (or shrinkage).

Uses shared utilities for GARCH and dynamic corr proxy.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_garch_vol, compute_close_to_close_vol
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_54")



_DEFAULT_POINT_54_CONFIG = {
            "garch_window": 50,
            "dcc_alpha": 0.05,
            "dcc_beta": 0.9,
            "min_data_density": 100,
            "fallback_vol": 0.01,
            "shrinkage": 0.1,
        }


def compute_dcc_garch_adjusted_vol(
    local_returns: pd.Series,
    market_returns: Optional[pd.Series] = None,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Practical DCC-style adjusted vol (local GARCH with dynamic corr to market or shrinkage)."""
    cfg = config or {}
    w = int(cfg.get("garch_window", 50))
    dcc_a = float(cfg.get("dcc_alpha", 0.05))
    dcc_b = float(cfg.get("dcc_beta", 0.9))
    shrink = float(cfg.get("shrinkage", 0.1))
    min_d = int(cfg.get("min_data_density", 100))
    fb = float(cfg.get("fallback_vol", 0.01))

    if len(local_returns) < min_d:
        return fb

    # Local GARCH vol
    local_vol = compute_garch_vol(local_returns, 1e-6, 0.08, 0.85, w)
    if not np.isfinite(local_vol) or local_vol <= 0:
        local_vol = fb

    if market_returns is None or len(market_returns) < min_d:
        # Fallback to shrinkage toward average
        avg_vol = compute_close_to_close_vol(local_returns, w)
        adj = (1 - shrink) * local_vol + shrink * avg_vol
        return float(adj)

    # Simple dynamic corr proxy (EWMA corr)
    lr = local_returns.tail(w).dropna()
    mr = market_returns.tail(w).dropna()
    if len(lr) < 5 or len(mr) < 5:
        return local_vol

    corr = np.corrcoef(lr, mr)[0, 1]
    # DCC-like update (simplified)
    dyn_corr = dcc_a * corr + dcc_b * (corr if 'prev' not in locals() else 0.5)  # rough
    dyn_corr = np.clip(dyn_corr, -0.9, 0.9)

    # Adjust local vol by dyn corr effect (spillover)
    m_vol = compute_garch_vol(market_returns, 1e-6, 0.08, 0.85, w)
    adj_vol = local_vol * (1 + abs(dyn_corr) * 0.2)  # modest spillover adjustment
    adj_vol = (1 - shrink) * adj_vol + shrink * local_vol
    return float(max(adj_vol, fb * 0.5))


def compute_point_54_override(
    raw_vol: float,
    df: pd.DataFrame,
    symbol: str,
    market_returns: Optional[pd.Series] = None,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_54_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    r = (c / c.shift(1) - 1.0).dropna()

    raw_val = float(raw_vol) if np.isfinite(raw_vol) else compute_close_to_close_vol(c, int(cfg.get("garch_window", 50)))
    new_val = compute_dcc_garch_adjusted_vol(r, market_returns, config=cfg)

    final = engine.apply_override(
        point_id="54",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_54] decision | %s raw=%.5f new=%.5f final=%.5f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 54 DCC-GARCH Smoke ===")
    engine = BiasOverrideEngine()
    n = 100
    rng = np.random.default_rng(54)
    local_r = rng.normal(0, 0.01, n)
    mkt_r = rng.normal(0, 0.008, n) * 0.7 + rng.normal(0, 0.005, n)
    c = 100 * np.exp(np.cumsum(local_r))
    df = pd.DataFrame({"close": c})
    raw = 0.012
    final = compute_point_54_override(raw, df, "TEST54", market_returns=pd.Series(mkt_r), engine=engine)
    print(f"raw={raw:.4f} -> final={final:.4f}")

def _load_point_54_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_54", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_54_CONFIG

def compute_dcc_garch_adjusted_vol(
    local_returns: pd.Series,
    market_returns: Optional[pd.Series] = None,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Practical DCC-style adjusted vol (local GARCH with dynamic corr to market or shrinkage)."""
    cfg = config or {}
    w = int(cfg.get("garch_window", 50))
    dcc_a = float(cfg.get("dcc_alpha", 0.05))
    dcc_b = float(cfg.get("dcc_beta", 0.9))
    shrink = float(cfg.get("shrinkage", 0.1))
    min_d = int(cfg.get("min_data_density", 100))
    fb = float(cfg.get("fallback_vol", 0.01))

    if len(local_returns) < min_d:
        return fb

    # Local GARCH vol
    local_vol = compute_garch_vol(local_returns, 1e-6, 0.08, 0.85, w)
    if not np.isfinite(local_vol) or local_vol <= 0:
        local_vol = fb

    if market_returns is None or len(market_returns) < min_d:
        # Fallback to shrinkage toward average
        avg_vol = compute_close_to_close_vol(local_returns, w)
        adj = (1 - shrink) * local_vol + shrink * avg_vol
        return float(adj)

    # Simple dynamic corr proxy (EWMA corr)
    lr = local_returns.tail(w).dropna()
    mr = market_returns.tail(w).dropna()
    if len(lr) < 5 or len(mr) < 5:
        return local_vol

    corr = np.corrcoef(lr, mr)[0, 1]
    # DCC-like update (simplified)
    dyn_corr = dcc_a * corr + dcc_b * (corr if 'prev' not in locals() else 0.5)  # rough
    dyn_corr = np.clip(dyn_corr, -0.9, 0.9)

    # Adjust local vol by dyn corr effect (spillover)
    m_vol = compute_garch_vol(market_returns, 1e-6, 0.08, 0.85, w)
    adj_vol = local_vol * (1 + abs(dyn_corr) * 0.2)  # modest spillover adjustment
    adj_vol = (1 - shrink) * adj_vol + shrink * local_vol
    return float(max(adj_vol, fb * 0.5))


def compute_point_54_override(
    raw_vol: float,
    df: pd.DataFrame,
    symbol: str,
    market_returns: Optional[pd.Series] = None,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_54_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    r = (c / c.shift(1) - 1.0).dropna()

    raw_val = float(raw_vol) if np.isfinite(raw_vol) else compute_close_to_close_vol(c, int(cfg.get("garch_window", 50)))
    new_val = compute_dcc_garch_adjusted_vol(r, market_returns, config=cfg)

    final = engine.apply_override(
        point_id="54",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_54] decision | %s raw=%.5f new=%.5f final=%.5f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 54 DCC-GARCH Smoke ===")
    engine = BiasOverrideEngine()
    n = 100
    rng = np.random.default_rng(54)
    local_r = rng.normal(0, 0.01, n)
    mkt_r = rng.normal(0, 0.008, n) * 0.7 + rng.normal(0, 0.005, n)
    c = 100 * np.exp(np.cumsum(local_r))
    df = pd.DataFrame({"close": c})
    raw = 0.012
    final = compute_point_54_override(raw, df, "TEST54", market_returns=pd.Series(mkt_r), engine=engine)
    print(f"raw={raw:.4f} -> final={final:.4f}")
    print("Smoke done (simplified DCC).")