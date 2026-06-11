"""
Point 25: Entropy-Adaptive Memory Half-Life
"""
import logging
from typing import Optional, Dict, Any
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_entropy_adaptive_lambda

_logger = logging.getLogger("kronos.bias_override.point_25")

_DEFAULT_CONFIG = {
    "entropy_window": 24,
    "base_lambda": 0.1,
    "min_data_density": 50,
    "fallback_lambda": 0.1
}

def _load_point_25_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_25", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_25_override(raw_lambda: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_25_config(engine)
        override_val = cfg["fallback_lambda"]
        if df is not None and "volume" in df.columns:
            override_val = compute_entropy_adaptive_lambda(df["volume"], cfg["base_lambda"], cfg["entropy_window"])
        if engine:
            return engine.apply_override(point_id="25", raw_value=raw_lambda, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_25] Error: {e}")
        return raw_lambda