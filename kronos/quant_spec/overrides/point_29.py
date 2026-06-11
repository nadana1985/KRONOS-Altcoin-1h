"""
Point 29: Kendall's Tau Trend-Strength
"""
import logging
from typing import Optional, Dict, Any
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_kendall_tau_strength

_logger = logging.getLogger("kronos.bias_override.point_29")

_DEFAULT_CONFIG = {
    "tau_window": 20,
    "exhaustion_threshold": 0.3,
    "min_data_density": 150,
    "fallback_tau": 0.0
}

def _load_point_29_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_29", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_29_override(raw_strength: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_29_config(engine)
        override_val = cfg["fallback_tau"]
        if df is not None and "close" in df.columns:
            try:
                override_val = compute_kendall_tau_strength(df["close"], cfg["tau_window"])
            except Exception:
                pass
        if engine:
            return engine.apply_override(point_id="29", raw_value=raw_strength, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_29] Error: {e}")
        return raw_strength