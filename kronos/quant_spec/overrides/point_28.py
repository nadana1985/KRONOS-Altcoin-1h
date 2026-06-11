"""
Point 28: Hurst-Adaptive Profile Lookback
"""
import logging
from typing import Optional, Dict, Any
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_hurst_exponent

_logger = logging.getLogger("kronos.bias_override.point_28")

_DEFAULT_CONFIG = {
    "base_lookback": 288,
    "hurst_window": 50,
    "min_lookback": 20,
    "max_lookback": 400,
    "min_data_density": 200,
    "fallback_lookback": 288
}

def _load_point_28_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_28", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_28_override(horizon_raw: int, close: pd.Series, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> int:
    try:
        cfg = _load_point_28_config(engine)
        hurst = compute_hurst_exponent(close, cfg["hurst_window"])
        
        # Lookback = round(base_lookback * (1.5 - H_t))
        scaled = int(round(cfg["base_lookback"] * (1.5 - hurst)))
        scaled = max(cfg["min_lookback"], min(scaled, cfg["max_lookback"]))
        
        if engine:
            return engine.apply_override(point_id="28", raw_value=horizon_raw, override_value=scaled, df=df, symbol=symbol)
        return scaled
    except Exception as e:
        _logger.debug(f"[POINT_28] Error: {e}")
        return horizon_raw