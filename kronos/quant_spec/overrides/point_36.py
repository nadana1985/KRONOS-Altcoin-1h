"""
Point 36: Symmetric Missing Data Imputation - Ornstein-Uhlenbeck Volatility-Preserving Stochastic Bridging
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any, List
import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_ou_stochastic_bridge

_logger = logging.getLogger("kronos.bias_override.point_36")

_DEFAULT_CONFIG = {
    "theta": 0.15,
    "sigma_scale": 1.0,
    "min_periods": 20
}


def _load_point_36_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_36", engine)
    return cfg if cfg else _DEFAULT_CONFIG


def compute_point_36_override(
    fill_raw: float,
    close: pd.Series,
    gap_indices: List[Any],
    df: Optional[pd.DataFrame] = None,
    symbol: str = '',
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs
) -> pd.Series:
    """
    Apply Ornstein-Uhlenbeck stochastic bridge imputation over kline gap periods.
    """
    try:
        cfg = _load_point_36_config(engine)
        theta = float(cfg.get("theta", 0.15))
        sigma_scale = float(cfg.get("sigma_scale", 1.0))
        min_periods = int(cfg.get("min_periods", 20))
        
        if not gap_indices or len(close) < min_periods:
            return close
            
        # Run stochastic bridge
        filled_close = compute_ou_stochastic_bridge(
            close=close,
            gap_indices=gap_indices,
            theta=theta,
            sigma_scale=sigma_scale,
            min_periods=min_periods
        )
        
        override_val = filled_close
        if engine is not None:
            status = engine.registry.get_point_status("36")
            if status in ["implemented", "validated", "active", "backtest_only"]:
                override_val = engine.apply_override(
                    point_id="36",
                    raw_value=close,  # Pass Series to match override type
                    override_value=filled_close,
                    df=df,
                    symbol=symbol
                )
                
        if df is not None and "close" in df.columns:
            df["close"] = override_val
            
        return override_val
    except Exception as e:
        _logger.error(f"[POINT_36] OU Stochastic Bridge failed for {symbol}: {e}")
        filled_close = close.ffill().bfill()
        if df is not None and "close" in df.columns:
            df["close"] = filled_close
        return filled_close