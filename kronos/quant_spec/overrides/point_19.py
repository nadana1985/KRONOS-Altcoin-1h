"""
Point 19: Beta-CDF Wick Mapping
"""
import logging
from typing import Optional, Dict, Any
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_beta_cdf_wick_exhaustion

_logger = logging.getLogger("kronos.bias_override.point_19")

_DEFAULT_CONFIG = {
    "beta_alpha": 2.0,
    "beta_beta": 5.0,
    "wick_window": 20,
    "min_data_density": 60,
    "fallback_wick": 0.5
}

def _load_point_19_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_19", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_19_override(raw_wick: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_19_config(engine)
        override_val = cfg["fallback_wick"]
        if df is not None and all(col in df.columns for col in ["high", "low", "open", "close"]):
            override_val = compute_beta_cdf_wick_exhaustion(df["high"], df["low"], df["open"], df["close"], cfg["beta_alpha"], cfg["beta_beta"], cfg["wick_window"])
        if engine:
            return engine.apply_override(point_id="19", raw_value=raw_wick, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_19] Error: {e}")
        return raw_wick