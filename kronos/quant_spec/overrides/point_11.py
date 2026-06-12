"""
Point 11: Arbitrary EWM Smoothing Span Bias - Volume-Synchronized Exponential Smoothing (VSES)
(Numba Optimized Implementation)

Eliminates static time-span EMAs. Adapts the exponential decay factor synchronously 
to real-time quote volume, preventing liquidation distortions while preserving 
structural causality.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd
import numba

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
        
    # Initialization fallback
    if np.isnan(X[0]):
        S[0] = 0.0
    else:
        S[0] = X[0]
        
    for t in range(1, N):
        a = alpha_t[t]
        x_val = X[t]
        
        # Handle NaN values elegantly without breaking the recursive state
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
    
    MATHEMATICAL SPECIFICATION:
    1. alpha_t = alpha_base * ( Q_t / Mean(Q_[t-W:t-1]) )
    2. S_t = alpha_t * X_t + (1 - alpha_t) * S_{t-1}
    3. STRICT CAUSALITY BARRIER: Rolling Mean operates strictly on the closed 
       window ending at 't-1'.
    4. BOUNDS: alpha_t is clipped via np.clip to a hard maximum of 1.0.
    
    Parameters
    ----------
    X : array-like
        The input feature matrix/series to be smoothed.
    Q : array-like
        Quote Asset Volume array.
    alpha_base : float
        Foundational smoothing scalar.
    W : int
        Rolling lookback window to calculate the baseline volume mean.
        
    Returns
    -------
    pd.Series or np.ndarray
        A continuous, dynamically smoothed feature array.
    """
    is_series = isinstance(X, pd.Series)
    index = X.index if is_series else None
    
    X_arr = np.asarray(X, dtype=float)
    Q_arr = np.asarray(Q, dtype=float)
    
    N = len(X_arr)
    if N == 0:
        return pd.Series(dtype=float, index=index, name="vses_smoothed_feature")
    
    # 1. STRICT CAUSALITY BARRIER - Historical Rolling Mean Volume
    # We use stride tricks for speed to compute the rolling mean of Q
    safe_mean = np.mean(Q_arr) if N > 0 else 1.0
    Q_padded = np.pad(Q_arr, (W - 1, 0), mode='constant', constant_values=safe_mean)
    
    windows = np.lib.stride_tricks.sliding_window_view(Q_padded, window_shape=W)
    rolling_mean_raw = np.mean(windows, axis=1)  # shape (N,)
    
    # Apply strict out-of-sample shift ending at 't-1'
    rolling_mean_Q = np.empty_like(rolling_mean_raw)
    rolling_mean_Q[0] = safe_mean
    rolling_mean_Q[1:] = rolling_mean_raw[:-1]
    
    # Prevent division by zero
    rolling_mean_Q = np.maximum(rolling_mean_Q, 1e-12)
    
    # 2. Dynamic Smoothing Factor Calculation
    # alpha_t = alpha_base * ( Q_t / Mean(Q_[t-W:t-1]) )
    alpha_raw = alpha_base * (Q_arr / rolling_mean_Q)
    
    # Explicitly bound to max 1.0 and min 0.0
    alpha_t = np.clip(alpha_raw, 0.0, 1.0)
    
    # 3. High-Performance Recursive State Evaluation
    S_t = _compute_vses_recursive(X_arr, alpha_t)
    
    if is_series:
        return pd.Series(S_t, index=index, name="vses_smoothed_feature")
    return S_t


def compute_point_11_override(
    df: pd.DataFrame,
    target_column: str,
    alpha_base: float = 0.1,
    W: int = 24,
    volume_col: str = "quote_asset_volume",
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Applies the strictly causal Volume-Synchronized Exponential Smoothing mapping.
    """
    try:
        if target_column not in df.columns:
            raise ValueError(f"Missing target feature column: {target_column}")
            
        vol_col = volume_col if volume_col in df.columns else "volume"
        if vol_col not in df.columns:
            raise ValueError(f"Missing required volume column '{vol_col}' for VSES.")
            
        return compute_volume_synchronized_exponential_smoothing(
            X=df[target_column],
            Q=df[vol_col],
            alpha_base=alpha_base,
            W=W
        )
    except Exception as e:
        _logger.error(f"[POINT_11] VSES computation failed for {symbol}: {e}")
        # Fail-safe: Return raw target column completely un-smoothed on failure
        return pd.Series(df.get(target_column, 0.0), index=df.index, name="vses_smoothed_feature")