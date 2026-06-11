"""
Point 15: Skewness-Weighted Asymmetric Barriers
"""
import logging
from typing import Optional, Dict, Any, Union
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_skewness_weighted_barriers

_logger = logging.getLogger("kronos.bias_override.point_15")

_DEFAULT_CONFIG = {
    "phi_base": 2.0,
    "skew_window": 50,
    "min_data_density": 50,
    "fallback_upper": 0.02,
    "fallback_lower": -0.02
}

def _load_point_15_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_15", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_15_override(raw_barrier: Union[float, Dict[str, float]], df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> Dict[str, float]:
    # handle raw_barrier as float
    rb_val = raw_barrier if isinstance(raw_barrier, float) else raw_barrier.get("barrier_upper", 0.02)
    raw_dict = {"barrier_upper": rb_val, "barrier_lower": -rb_val}
    try:
        cfg = _load_point_15_config(engine)
        override_val = {"barrier_upper": cfg["fallback_upper"], "barrier_lower": cfg["fallback_lower"]}
        
        if df is not None and "close" in df.columns:
            # check if compute_skewness_weighted_barriers exists and is callable
            try:
                override_val = compute_skewness_weighted_barriers(df["close"], cfg["phi_base"], cfg["skew_window"], cfg["min_data_density"], cfg["fallback_upper"], cfg["fallback_lower"])
            except Exception:
                pass
                
        status = "not_started"
        if engine:
            status = engine.registry.get_point_status("15")
        if status in ["implemented", "backtest_only"]:
            # Route through engine
            if engine:
                engine.apply_override(point_id="15", raw_value=rb_val, override_value=override_val["barrier_upper"], df=df, symbol=symbol)
            return override_val
        return raw_dict
    except Exception as e:
        _logger.debug(f"[POINT_15] Error: {e}")
        return raw_dict