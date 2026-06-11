"""
Point 82: Causal Lagged Cross-Sectional Priors
"""
import logging
from typing import Optional, Dict, Any, Union
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import causal_lag_cross_sectional

_logger = logging.getLogger("kronos.bias_override.point_82")

_DEFAULT_CONFIG = {
    "global_lag": 1,
    "min_data_density": 50,
    "fallback_local_only": True
}

def _load_point_82_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_82", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_82_override(local_signal: pd.Series, raw_value: float, cross_section: pd.DataFrame, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> Union[pd.Series, pd.DataFrame]:
    try:
        cfg = _load_point_82_config(engine)
        
        status = "not_started"
        if engine:
            status = engine.registry.get_point_status("82")
            
        if status in ["implemented", "backtest_only"] and cross_section is not None:
            override_val = causal_lag_cross_sectional(local_signal, cross_section, cfg["global_lag"])
            return override_val
            
        # Default behavior if not enabled or cross_section is None
        return local_signal if isinstance(local_signal, pd.Series) else pd.Series([raw_value])
    except Exception as e:
        _logger.debug(f"[POINT_82] Error: {e}")
        return local_signal if isinstance(local_signal, pd.Series) else pd.Series([raw_value])