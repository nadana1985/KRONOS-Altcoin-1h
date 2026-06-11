"""
Point 35: Combinatorial Purging & Embargo
"""
import logging
from typing import Optional, Dict, Any
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

_logger = logging.getLogger("kronos.bias_override.point_35")

_DEFAULT_CONFIG = {
    "embargo_window": 5,
    "purge_buffer": 1,
    "min_data_density": 100,
    "fallback_purge_ratio": 0.2,
    "max_purge_ratio": 0.8
}

def _load_point_35_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_35", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_35_override(raw_train_size: int, event_index: int, horizon: int = 4, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> int:
    try:
        cfg = _load_point_35_config(engine)
        override_val = int(raw_train_size * (1 - cfg["fallback_purge_ratio"]))
        if engine:
            return engine.apply_override(point_id="35", raw_value=raw_train_size, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_35] Error: {e}")
        return raw_train_size