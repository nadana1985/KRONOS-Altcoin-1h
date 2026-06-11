"""
Point 11: Arbitrary EWM Smoothing Span Bias - Volume-Synchronized EWM alpha
"""
import logging
from typing import Optional, Dict, Any
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_volume_synced_alpha

_logger = logging.getLogger("kronos.bias_override.point_11")

_DEFAULT_CONFIG = {
    "base_alpha": 0.1,
    "vol_window": 50,
    "min_data_density": 50,
    "fallback_alpha": 0.1,
    "min_alpha": 0.01,
    "max_alpha": 0.5
}

def _load_point_11_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_11", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_11_override(raw_alpha: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_11_config(engine)
        override_val = cfg.get("fallback_alpha", 0.1)
        if df is not None and "volume" in df.columns:
            override_val = compute_volume_synced_alpha(cfg["base_alpha"], df["volume"], cfg["vol_window"], cfg["min_alpha"], cfg["max_alpha"])
        
        if engine:
            return engine.apply_override(point_id="11", raw_value=raw_alpha, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_11] Error: {e}")
        return raw_alpha