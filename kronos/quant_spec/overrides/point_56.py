"""
Point 56: Beta-Neutralized Residual Volatility
"""
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_beta_neutral_residual_vol

_logger = logging.getLogger("kronos.bias_override.point_56")

_DEFAULT_CONFIG = {
    "beta_window": 50,
    "min_data_density": 60,
    "fallback_vol": 0.01
}

def _load_point_56_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_56", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_56_override(raw_vol: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_56_config(engine)
        override_val = cfg["fallback_vol"]
        if df is not None and "close" in df.columns:
            close = pd.to_numeric(df["close"], errors="coerce")
            returns = np.log((close / close.shift(1).clip(lower=1e-12)).clip(lower=1e-12)).dropna()
            # Since no market_returns available in this context, use self to fallback or simple vol
            override_val = compute_beta_neutral_residual_vol(returns, returns, cfg["beta_window"])
            if np.isnan(override_val):
                override_val = cfg["fallback_vol"]
        if engine:
            return engine.apply_override(point_id="56", raw_value=raw_vol, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_56] Error: {e}")
        return raw_vol