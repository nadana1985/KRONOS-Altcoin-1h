"""
Point 02: Rigid Feature Window Bias - Volatility-Scaled Lookback Adaptation
"""
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_volatility_scaled_window

_logger = logging.getLogger("kronos.bias_override.point_02")

_DEFAULT_CONFIG = {
    "gamma": 0.5,
    "vol_short_window": 20,
    "vol_reference_window": 100,
    "vol_reference_method": "median",
    "min_lookback": 20,
    "max_lookback": 500,
    "min_data_density": 30,
    "fallback_multiplier": 1.0,
    "slot15_history_base": 100
}

def _load_point_02_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_02", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def _compute_relative_volatility(df: pd.DataFrame, cfg: Dict[str, Any]) -> float:
    if df is None or len(df) < cfg["vol_reference_window"]:
        return 1.0
    try:
        close = pd.to_numeric(df["close"], errors="coerce")
        ret = np.log((close / close.shift(1).clip(lower=1e-12)).clip(lower=1e-12)).dropna()
        short_vol = ret.tail(cfg["vol_short_window"]).std()
        
        # very simplified reference
        ref_vol = ret.tail(cfg["vol_reference_window"]).std()
        
        if not np.isfinite(short_vol) or not np.isfinite(ref_vol) or ref_vol <= 0:
            return 1.0
        return float(short_vol / ref_vol)
    except Exception as e:
        _logger.debug(f"[POINT_02] Rel vol error: {e}")
        return 1.0

def get_volatility_scaled_window(base_window: int, df: pd.DataFrame, symbol: str, engine: Optional[BiasOverrideEngine] = None) -> int:
    cfg = _load_point_02_config(engine)
    rel_vol = _compute_relative_volatility(df, cfg)
    return compute_volatility_scaled_window(base_window, rel_vol, cfg["gamma"], cfg["min_lookback"], cfg["max_lookback"])

def get_slot15_history_lookback(df: pd.DataFrame, symbol: str, engine: Optional[BiasOverrideEngine] = None) -> int:
    cfg = _load_point_02_config(engine)
    return get_volatility_scaled_window(cfg.get("slot15_history_base", 100), df, symbol, engine)

def compute_point_02_override(current_window: int, base_window: int, rel_volatility: float, gamma: float = 0.5, engine: Optional[BiasOverrideEngine] = None, df: Optional[pd.DataFrame] = None, symbol: str = '') -> int:
    try:
        cfg = _load_point_02_config(engine)
        scaled = compute_volatility_scaled_window(base_window, rel_volatility, cfg["gamma"], cfg["min_lookback"], cfg["max_lookback"])
        if engine:
            return engine.apply_override(point_id="02", raw_value=current_window, override_value=scaled, df=df, symbol=symbol)
        return scaled
    except Exception as e:
        _logger.debug(f"[POINT_02] Error: {e}")
        return current_window