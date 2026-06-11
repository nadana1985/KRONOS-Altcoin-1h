"""
Point 44: Information-Weighted Rolling Operators
"""
import logging
from typing import Optional, Dict, Any
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_information_weighted_rolling

_logger = logging.getLogger("kronos.bias_override.point_44")

_DEFAULT_CONFIG = {
    "window": 50,
    "min_data_density": 150,
    "fallback_weighted": 0.0
}

def _load_point_44_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_44", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_44_override(raw_value: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_44_config(engine)
        override_val = cfg["fallback_weighted"]
        if df is not None and "close" in df.columns:
            try:
                # Need an entropy series; we use returns as proxy to run function
                override_val = compute_information_weighted_rolling(df["close"], df["close"].pct_change(), cfg["window"])
            except Exception:
                pass
        if engine:
            return engine.apply_override(point_id="44", raw_value=raw_value, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_44] Error: {e}")
        return raw_value