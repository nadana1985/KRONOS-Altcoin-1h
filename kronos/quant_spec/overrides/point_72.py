"""
Point 72: Hill's Tail Index Estimation
"""
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

_logger = logging.getLogger("kronos.bias_override.point_72")

_DEFAULT_CONFIG = {
    "hill_k": 10,
    "window": 100,
    "min_data_density": 50,
    "fallback_tail_index": 2.5
}

def _load_point_72_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_72", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_72_override(raw_tail_index: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_72_config(engine)
        override_val = cfg["fallback_tail_index"]
        if df is not None and "close" in df.columns:
            close = pd.to_numeric(df["close"], errors="coerce")
            returns = np.log((close / close.shift(1).clip(lower=1e-12)).clip(lower=1e-12)).dropna()
            recent_ret = returns.tail(cfg["window"]).dropna()
            
            # Use negative returns for tail index
            losses = recent_ret[recent_ret < 0].abs()
            if len(losses) > cfg["hill_k"]:
                sorted_losses = np.sort(losses.values)[::-1] # descending
                k = cfg["hill_k"]
                log_ratio = np.log(sorted_losses[:k] / sorted_losses[k])
                xi = np.mean(log_ratio)
                if xi > 0:
                    override_val = 1.0 / xi
        
        if engine:
            return engine.apply_override(point_id="72", raw_value=raw_tail_index, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_72] Error: {e}")
        return raw_tail_index