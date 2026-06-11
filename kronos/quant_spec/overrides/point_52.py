"""
Point 52: Downside Semi-Volatility
"""
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_downside_semi_vol

_logger = logging.getLogger("kronos.bias_override.point_52")

_DEFAULT_CONFIG = {
    "vol_window": 20,
    "min_data_density": 30,
    "fallback_vol": 0.01
}

def _load_point_52_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_52", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_52_override(raw_vol: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_52_config(engine)
        override_val = cfg["fallback_vol"]
        if df is not None and "close" in df.columns:
            override_val = compute_downside_semi_vol(df["close"], cfg["vol_window"])
            if np.isnan(override_val):
                override_val = cfg["fallback_vol"]
        if engine:
            return engine.apply_override(point_id="52", raw_value=raw_vol, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_52] Error: {e}")
        return raw_vol