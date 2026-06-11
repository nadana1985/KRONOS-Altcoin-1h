"""
Point 47: Rogers-Satchell Volatility
"""
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_rogers_satchell_vol

_logger = logging.getLogger("kronos.bias_override.point_47")

_DEFAULT_CONFIG = {
    "vol_window": 20,
    "min_data_density": 30,
    "fallback_vol": 0.01
}

def _load_point_47_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_47", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_47_override(raw_vol: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_47_config(engine)
        override_val = cfg["fallback_vol"]
        if df is not None and all(col in df.columns for col in ["open", "high", "low", "close"]):
            override_val = compute_rogers_satchell_vol(df["open"], df["high"], df["low"], df["close"], cfg["vol_window"])
            if np.isnan(override_val):
                override_val = cfg["fallback_vol"]
        if engine:
            return engine.apply_override(point_id="47", raw_value=raw_vol, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_47] Error: {e}")
        return raw_vol