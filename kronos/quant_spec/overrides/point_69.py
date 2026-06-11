"""
Point 69: Rolling Fisher Skewness
"""
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_rolling_skewness

_logger = logging.getLogger("kronos.bias_override.point_69")

_DEFAULT_CONFIG = {
    "skew_window": 50,
    "min_data_density": 40,
    "fallback_skew": 0.0
}

def _load_point_69_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_69", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_69_override(raw_skew: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_69_config(engine)
        override_val = cfg["fallback_skew"]
        if df is not None and "close" in df.columns:
            close = pd.to_numeric(df["close"], errors="coerce")
            returns = np.log((close / close.shift(1).clip(lower=1e-12)).clip(lower=1e-12)).dropna()
            override_val = compute_rolling_skewness(returns, cfg["skew_window"])
        if engine:
            return engine.apply_override(point_id="69", raw_value=raw_skew, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_69] Error: {e}")
        return raw_skew