"""
Point 06: Discrete Liquidity Filtering - Continuous Amihud Decay Adjuster
"""
import logging
from typing import Optional, Dict, Any
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_amihud_continuous_decay

_logger = logging.getLogger("kronos.bias_override.point_06")

_DEFAULT_CONFIG = {
    "amihud_window": 20,
    "lambda_decay": 50.0,
    "window": 20,
    "min_data_density": 50,
    "fallback_weight": 0.5
}

def _load_point_06_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_06", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_06_override(raw_weight: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_06_config(engine)
        override_val = cfg.get("fallback_weight", 0.5)
        if df is not None and all(c in df.columns for c in ["close", "open", "volume"]):
            override_val = compute_amihud_continuous_decay(
                df["close"], df["open"], df["volume"],
                cfg.get("window", cfg.get("amihud_window", 20)),
                cfg["lambda_decay"]
            )
        if engine:
            return engine.apply_override(point_id="06", raw_value=raw_weight, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_06] Error: {e}")
        return raw_weight