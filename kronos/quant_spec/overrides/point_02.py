"""
Point 02: Rigid Feature Window Bias - Dynamic Volatility-Scaled Lookback Adaptation
(Vectorized & Scalar Hardened Implementation)
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


def get_volatility_scaled_window(base_window: int, df: pd.DataFrame, symbol: str, engine: Optional[BiasOverrideEngine] = None, **kwargs) -> int:
    cfg = _load_point_02_config(engine)
    rel_vol = _compute_relative_volatility(df, cfg)
    return int(compute_volatility_scaled_window(base_window, rel_vol, cfg.get("gamma", 0.5), cfg.get("min_lookback", 20), cfg.get("max_lookback", 500)))


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
    is_series = isinstance(close, pd.Series)
    s = pd.Series(close) if not is_series else close
    
    eps = 1e-12
    s_float = s.astype(float)
    rets = np.log((s_float / s_float.shift(1).clip(lower=eps)).clip(lower=eps))
    
    sigma_short = rets.rolling(window=short_window, min_periods=2).std().shift(1)
    sigma_long = rets.rolling(window=long_window, min_periods=2).std().shift(1)
    
    sigma_long_safe = sigma_long.replace(0.0, np.nan)
    sigma_rel = (sigma_short / sigma_long_safe).fillna(1.0)
    sigma_rel = sigma_rel.replace([np.inf, -np.inf], 1.0)
    
    W_t_raw = np.round(W_base * (1.0 + sigma_rel) ** (-gamma))
    W_t = W_t_raw.clip(lower=W_min, upper=W_max).fillna(W_base).astype(int)
    
    if is_series:
        return pd.Series(W_t, index=s.index, name="dynamic_window")
    return W_t.to_numpy()


def compute_point_02_override(
    current_window: Optional[int] = None,
    base_window: Optional[int] = None,
    rel_volatility: Optional[float] = None,
    gamma: Optional[float] = None,
    engine: Optional[BiasOverrideEngine] = None,
    df: Optional[pd.DataFrame] = None,
    symbol: str = '',
    *args,
    **kwargs
) -> Union[int, pd.Series]:
    """
    Hardened multi-signature override adapter. Supporting both:
    1. Scalar lookback query: compute_point_02_override(current_window, base_window, rel_volatility, gamma, engine, df, symbol)
    2. Vectorized series query: compute_point_02_override(df, W_base, gamma, ...)
    """
    is_vectorized_call = False
    
    if len(args) > 0 and isinstance(args[0], pd.DataFrame):
        df_in = args[0]
        is_vectorized_call = True
    elif isinstance(current_window, pd.DataFrame):
        df_in = current_window
        is_vectorized_call = True
    else:
        df_in = df
        
    if is_vectorized_call and df_in is not None:
        W_base = base_window if base_window is not None else (current_window if isinstance(current_window, int) else 168)
        cfg = _load_point_02_config(engine)
        g = gamma if gamma is not None else cfg.get("gamma", 0.5)
        
        try:
            if "close" not in df_in.columns:
                raise ValueError("DataFrame must contain a 'close' column.")
            
            new_val = compute_dynamic_lookback_windows(
                close=df_in["close"],
                W_base=W_base,
                gamma=g,
                short_window=kwargs.get("short_window", 24),
                long_window=kwargs.get("long_window", 168),
                W_min=kwargs.get("W_min", 24),
                W_max=kwargs.get("W_max", 336)
            )
            
            if engine is not None:
                raw_val = float(W_base)
                final = engine.apply_override(
                    point_id="02",
                    raw_value=raw_val,
                    override_value=new_val.iloc[-1] if hasattr(new_val, "iloc") else W_base,
                    df=df_in,
                    symbol=symbol
                )
                return pd.Series(np.full(len(df_in), final, dtype=int), index=df_in.index, name="dynamic_window")
                
            return new_val
        except Exception as e:
            _logger.error(f"[POINT_02] Vectorized failure: {e}")
            n = len(df_in)
            return pd.Series(np.full(n, W_base, dtype=int), index=df_in.index, name="dynamic_window")
            
    else:
        try:
            cfg = _load_point_02_config(engine)
            target_base = base_window if base_window is not None else (current_window if current_window is not None else 100)
            g = gamma if gamma is not None else cfg.get("gamma", 0.5)
            
            if rel_volatility is None and df_in is not None:
                rel_vol = _compute_relative_volatility(df_in, cfg)
            else:
                rel_vol = rel_volatility if rel_volatility is not None else 1.0
                
            scaled = int(round(compute_volatility_scaled_window(
                target_base,
                rel_vol,
                g,
                cfg.get("min_lookback", 20),
                cfg.get("max_lookback", 500)
            )))
            
            if engine is not None:
                raw_val = current_window if current_window is not None else target_base
                final = engine.apply_override(
                    point_id="02",
                    raw_value=raw_val,
                    override_value=scaled,
                    df=df_in,
                    symbol=symbol
                )
                return int(final)
            return scaled
        except Exception as e:
            _logger.error(f"[POINT_02] Scalar failure: {e}")
            return current_window if current_window is not None else 100