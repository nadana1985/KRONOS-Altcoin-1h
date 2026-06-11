"""
Point 64: Causal VaR & Expected Shortfall
"""
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_tail_var_es

_logger = logging.getLogger("kronos.bias_override.point_64")

_DEFAULT_CONFIG = {
    "var_confidence": 0.95,
    "es_confidence": 0.95,
    "var_window": 50,
    "min_data_density": 60,
    "fallback_var": 0.02,
    "fallback_es": 0.03
}

def _load_point_64_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_64", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_64_override(raw_var: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> Dict[str, float]:
    try:
        cfg = _load_point_64_config(engine)
        override_val = {"var": cfg["fallback_var"], "es": cfg["fallback_es"]}
        if df is not None and "close" in df.columns:
            close = pd.to_numeric(df["close"], errors="coerce")
            returns = np.log((close / close.shift(1).clip(lower=1e-12)).clip(lower=1e-12)).dropna()
            override_val = compute_tail_var_es(returns, cfg["var_confidence"], cfg["var_window"])
            
        status = "not_started"
        if engine:
            # We route 'var' through the engine, but we want to return the dict
            engine.apply_override(point_id="64", raw_value=raw_var, override_value=override_val["var"], df=df, symbol=symbol)
            status = engine.registry.get_point_status("64")
            
        if status in ["implemented", "backtest_only"]:
            return override_val
        return {"var": raw_var, "es": raw_var * 1.5}
    except Exception as e:
        _logger.debug(f"[POINT_64] Error: {e}")
        return {"var": raw_var, "es": raw_var * 1.5}