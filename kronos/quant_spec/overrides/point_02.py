"""
Point 02: Rigid Feature Window Bias - Dynamic Volatility-Scaled Lookback Adaptation
(Vectorized Implementation)

Replaces all hardcoded, rigid lookback spans with a dynamically scaling volatility engine.
W_t = round(W_base * (1 + sigma_rel,t) ** (-gamma))
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any, Dict

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
    "slot15_history_base": 100,
    "vpin_base": 100,
    "ofi_base": 50
}


def _load_point_02_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_02", engine)
    return cfg if cfg else _DEFAULT_CONFIG


def _compute_relative_volatility(df: pd.DataFrame, cfg: Dict[str, Any]) -> float:
    if df is None or len(df) < cfg.get("vol_reference_window", 100):
        return 1.0
    try:
        close = pd.to_numeric(df["close"], errors="coerce")
        ret = np.log((close / close.shift(1).clip(lower=1e-12)).clip(lower=1e-12)).dropna()
        short_vol = ret.tail(cfg.get("vol_short_window", 20)).std()
        ref_vol = ret.tail(cfg.get("vol_reference_window", 100)).std()
        
        if not np.isfinite(short_vol) or not np.isfinite(ref_vol) or ref_vol <= 0:
            return 1.0
        return float(short_vol / ref_vol)
    except Exception as e:
        _logger.debug(f"[POINT_02] Rel vol error: {e}")
        return 1.0


def compute_volatility_scaled_lookback(base_window: int, df: pd.DataFrame, config: Optional[Dict[str, Any]] = None) -> int:
    cfg = config or _DEFAULT_CONFIG
    rel_vol = _compute_relative_volatility(df, cfg)
    return int(compute_volatility_scaled_window(
        base_window,
        rel_vol,
        cfg.get("gamma", 0.5),
        cfg.get("min_lookback", 20),
        cfg.get("max_lookback", 500)
    ))


def get_volatility_scaled_window(base_window: int, df: pd.DataFrame, symbol: str, engine: Optional[BiasOverrideEngine] = None, **kwargs) -> int:
    cfg = _load_point_02_config(engine)
    rel_vol = _compute_relative_volatility(df, cfg)
    return compute_volatility_scaled_window(base_window, rel_vol, cfg.get("gamma", 0.5), cfg.get("min_lookback", 20), cfg.get("max_lookback", 500))


def get_slot15_history_lookback(df: pd.DataFrame, symbol: str, engine: Optional[BiasOverrideEngine] = None, **kwargs) -> int:
    cfg = _load_point_02_config(engine)
    return get_volatility_scaled_window(cfg.get("slot15_history_base", 100), df, symbol, engine, **kwargs)


def get_vpin_lookback(df: pd.DataFrame, symbol: str, engine: Optional[BiasOverrideEngine] = None, **kwargs) -> int:
    cfg = _load_point_02_config(engine)
    return get_volatility_scaled_window(cfg.get("vpin_base", 100), df, symbol, engine, **kwargs)


def get_ofi_lookback(df: pd.DataFrame, symbol: str, engine: Optional[BiasOverrideEngine] = None, **kwargs) -> int:
    cfg = _load_point_02_config(engine)
    return get_volatility_scaled_window(cfg.get("ofi_base", 50), df, symbol, engine, **kwargs)


def compute_dynamic_lookback_windows(
    close: Union[pd.Series, np.ndarray],
    W_base: int = 168,
    gamma: float = 0.5,
    short_window: int = 24,
    long_window: int = 168,
    W_min: int = 24,
    W_max: int = 336
) -> Union[pd.Series, np.ndarray]:
    """
    Computes an array of dynamic lookback windows scaled by relative volatility.
    """
    is_series = isinstance(close, pd.Series)
    s = pd.Series(close) if not is_series else close
    
    # Compute log returns safely
    eps = 1e-12
    s_float = s.astype(float)
    rets = np.log((s_float / s_float.shift(1).clip(lower=eps)).clip(lower=eps))
    
    # Compute rolling standard deviations causal shift(1)
    sigma_short = rets.rolling(window=short_window, min_periods=2).std().shift(1)
    sigma_long = rets.rolling(window=long_window, min_periods=2).std().shift(1)
    
    # Relative volatility
    sigma_long_safe = sigma_long.replace(0.0, np.nan)
    sigma_rel = (sigma_short / sigma_long_safe).fillna(1.0)
    sigma_rel = sigma_rel.replace([np.inf, -np.inf], 1.0)
    
    # Compute dynamic lookback window
    W_t_raw = np.round(W_base * (1.0 + sigma_rel) ** (-gamma))
    W_t = W_t_raw.clip(lower=W_min, upper=W_max).fillna(W_base).astype(int)
    
    if is_series:
        return pd.Series(W_t, index=s.index, name="dynamic_window")
    return W_t.to_numpy()


# Vectorized top-level adapter for BiasOverrideEngine pipeline
def compute_point_02_override(
    df: pd.DataFrame,
    W_base: int = 168,
    gamma: float = 0.5,
    short_window: int = 24,
    long_window: int = 168,
    W_min: int = 24,
    W_max: int = 336,
    engine: Optional[BiasOverrideEngine] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    """
    try:
        if "close" not in df.columns:
            raise ValueError("DataFrame must contain a 'close' column to compute relative volatility.")
            
        new_val = compute_dynamic_lookback_windows(
            close=df["close"],
            W_base=W_base,
            gamma=gamma,
            short_window=short_window,
            long_window=long_window,
            W_min=W_min,
            W_max=W_max
        )
        
        # Legacy scalar value representation for apply_override compatibility
        raw_val = float(W_base)
        
        if engine is not None:
            # We want to map the series through apply_override or apply it directly
            # For simplicity, if engine is present, apply override element-by-element or map.
            # Usually, apply_override returns the final series or single float value depending on target.
            # Here we follow engine routing.
            final = engine.apply_override(
                point_id="02",
                raw_value=raw_val,
                override_value=new_val.iloc[-1] if hasattr(new_val, "iloc") else W_base,
                df=df,
                symbol=symbol
            )
            # return full series matching the decision or matching the output index
            return pd.Series(np.full(len(df), final, dtype=int), index=df.index, name="dynamic_window")
            
        return new_val
    except Exception as e:
        _logger.error(f"[POINT_02] Failed to compute dynamic lookbacks for {symbol}: {e}")
        n = len(df)
        return pd.Series(np.full(n, W_base, dtype=int), index=df.index, name="dynamic_window")