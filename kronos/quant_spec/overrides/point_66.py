"""
Point 66: Huber Robust Return
"""
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_huber_robust_mean

_logger = logging.getLogger("kronos.bias_override.point_66")

_DEFAULT_CONFIG = {
    "huber_c": 1.345,
    "huber_window": 50,
    "min_data_density": 40,
    "fallback_return": 0.0
}

def _load_point_66_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_66", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_66_override(raw_return: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_66_config(engine)
        override_val = cfg["fallback_return"]
        if df is not None and "close" in df.columns:
            close = pd.to_numeric(df["close"], errors="coerce")
            returns = np.log((close / close.shift(1).clip(lower=1e-12)).clip(lower=1e-12)).dropna()
            recent_ret = returns.tail(cfg["huber_window"]).dropna()
            override_val = compute_huber_robust_mean(recent_ret, cfg["huber_c"])
        if engine:
            return engine.apply_override(point_id="66", raw_value=raw_return, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_66] Error: {e}")
        return raw_return