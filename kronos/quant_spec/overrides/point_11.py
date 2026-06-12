"""
Point 11: Arbitrary EWM Smoothing Span Bias - Volume-Synchronized Exponential Smoothing (VSES)
(Numba Optimized Implementation)
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any, Dict

import numpy as np
import pandas as pd
import numba

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

_logger = logging.getLogger("kronos.bias_override.point_11")


@numba.njit(cache=True)
def _compute_vses_recursive(X: np.ndarray, alpha_t: np.ndarray) -> np.ndarray:
    """
    Highly optimized Numba C-compiled loop to evaluate the recursive state equation.
    S_t = alpha_t * X_t + (1 - alpha_t) * S_{t-1}
    """
    N = len(X)
    S = np.empty(N, dtype=np.float64)
    if N == 0:
        return S
        
    if np.isnan(X[0]):
        S[0] = 0.0
    else:
        S[0] = X[0]
        
    for t in range(1, N):
        a = alpha_t[t]
        x_val = X[t]
        
        if np.isnan(x_val):
            S[t] = S[t - 1]
        else:
            S[t] = a * x_val + (1.0 - a) * S[t - 1]
            
    return S


def compute_volume_synchronized_exponential_smoothing(
    X: Union[pd.Series, np.ndarray],
    Q: Union[pd.Series, np.ndarray],
    alpha_base: float = 0.1,
    W: int = 24
) -> Union[pd.Series, np.ndarray]:
    """
    Computes a strictly causal, dynamic Volume-Synchronized Exponential Smoothing (VSES) filter.
    """
    is_series = isinstance(X, pd.Series)
    index = X.index if is_series else None
    
    X_arr = np.asarray(X, dtype=float)
    Q_arr = np.asarray(Q, dtype=float)
    
    N = len(X_arr)
    if N == 0:
        return pd.Series(dtype=float, index=index, name="vses_smoothed_feature")
    
    safe_mean = np.mean(Q_arr) if N > 0 else 1.0
    Q_padded = np.pad(Q_arr, (W - 1, 0), mode='constant', constant_values=safe_mean)
    
    windows = np.lib.stride_tricks.sliding_window_view(Q_padded, window_shape=W)
    rolling_mean_raw = np.mean(windows, axis=1)
    
    rolling_mean_Q = np.empty_like(rolling_mean_raw)
    rolling_mean_Q[0] = safe_mean
    rolling_mean_Q[1:] = rolling_mean_raw[:-1]
    rolling_mean_Q = np.maximum(rolling_mean_Q, 1e-12)
    
    alpha_raw = alpha_base * (Q_arr / rolling_mean_Q)
    alpha_t = np.clip(alpha_raw, 0.0, 1.0)
    
    S_t = _compute_vses_recursive(X_arr, alpha_t)
    
    if is_series:
        return pd.Series(S_t, index=index, name="vses_smoothed_feature")
    return S_t


def compute_point_11_override(
    raw_alpha: Optional[float] = None,
    df: Optional[pd.DataFrame] = None,
    symbol: str = '',
    engine: Optional[Any] = None,
    target_column: Optional[str] = None,
    alpha_base: float = 0.1,
    W: int = 24,
    volume_col: str = "quote_asset_volume",
    *args,
    **kwargs
) -> Union[float, pd.Series]:
    """
    Unified Point 11 override supporting:
    1. Standard target column smoothing: compute_point_11_override(df, target_column, ...)
    2. Raw alpha dynamics query: compute_point_11_override(raw_alpha, df, symbol, engine)
    """
    # Resolve parameters from dual calling conventions
    if len(args) > 0 and isinstance(args[0], pd.DataFrame):
        df_in = args[0]
        t_col = target_column if target_column is not None else (args[1] if len(args) > 1 else None)
    elif df is not None:
        df_in = df
        t_col = target_column
    else:
        df_in = None
        t_col = target_column

    a_base = raw_alpha if raw_alpha is not None else alpha_base
    
    try:
        if df_in is None:
            return float(a_base)
            
        vol_col = volume_col if volume_col in df_in.columns else "volume"
        if vol_col not in df_in.columns:
            vol_col = "volume" if "volume" in df_in.columns else None
            
        if vol_col is None:
            return float(a_base) if t_col is None else pd.Series(df_in[t_col], index=df_in.index)

        # Compute dynamic alphas
        Q_arr = df_in[vol_col].astype(float).values
        safe_mean = np.mean(Q_arr) if len(Q_arr) > 0 else 1.0
        Q_padded = np.pad(Q_arr, (W - 1, 0), mode='constant', constant_values=safe_mean)
        windows = np.lib.stride_tricks.sliding_window_view(Q_padded, window_shape=W)
        rolling_mean_raw = np.mean(windows, axis=1)
        
        rolling_mean_Q = np.empty_like(rolling_mean_raw)
        rolling_mean_Q[0] = safe_mean
        rolling_mean_Q[1:] = rolling_mean_raw[:-1]
        rolling_mean_Q = np.maximum(rolling_mean_Q, 1e-12)
        
        alpha_t = np.clip(a_base * (Q_arr / rolling_mean_Q), 0.0, 1.0)
        
        if t_col is None:
            # Direct raw alpha dynamic calculation mode: return the final scalar dynamic alpha
            new_val = float(alpha_t[-1]) if len(alpha_t) > 0 else float(a_base)
            if engine is not None:
                final = engine.apply_override(
                    point_id="11",
                    raw_value=float(a_base),
                    override_value=new_val,
                    df=df_in,
                    symbol=symbol
                )
                return float(final)
            return new_val
        else:
            # Target column smoothing mode: returns Series of smoothed values
            new_val = compute_volume_synchronized_exponential_smoothing(
                X=df_in[t_col],
                Q=df_in[vol_col],
                alpha_base=a_base,
                W=W
            )
            if engine is not None:
                final_series = engine.apply_override(
                    point_id="11",
                    raw_value=df_in[t_col],
                    override_value=new_val,
                    df=df_in,
                    symbol=symbol
                )
                return final_series
            return new_val
            
    except Exception as e:
        _logger.error(f"[POINT_11] VSES computation failed for {symbol}: {e}")
        if t_col is not None and df_in is not None:
            return pd.Series(df_in[t_col], index=df_in.index, name="vses_smoothed_feature")
        return float(a_base)