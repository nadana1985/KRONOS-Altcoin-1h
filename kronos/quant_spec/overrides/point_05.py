"""
Point 05: Calendar-Time Rigidity Bias - Synthetic Quote Volume-Imbalance Aggregation
(Vectorized Implementation)

Replaces fixed chronological boundary sampling with a dynamic, density-driven lookback window.
Clears rolling volume targets dynamically to equalize information density across 
volatile liquidations and dead market sessions.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_05")


def compute_dynamic_volume_density_windows(
    Q: Union[pd.Series, np.ndarray],
    M: int = 168,
    W_min: int = 2,
    W_max: int = 72,
    target_multiplier: float = 1.0,
    fallback_window: int = 24
) -> Union[pd.Series, np.ndarray]:
    """
    Computes dynamic window lengths W_t to clear rolling volume density targets.
    
    MATHEMATICAL SPECIFICATION:
    1. Target_t = target_multiplier * median({Q_tau} for tau = t-M to t-1)
    2. W_t = min{ k in N | sum_{i=0}^{k} Q_{t-i} >= Target_t }
    3. STRICT CAUSALITY BARRIER: Median density anchor operates exclusively up to t-1.
    4. BOUNDARY CLIPPING: W_t is explicitly bounded between [W_min, W_max].
    
    Parameters
    ----------
    Q : pd.Series or np.ndarray
        The quote asset volume array (e.g., Binance kline Field 7).
    M : int
        Long-term sessional lookback anchor (e.g., 168 hours) to derive baseline median.
    W_min : int
        Minimum floor for the dynamic window.
    W_max : int
        Maximum ceiling for the dynamic window.
    target_multiplier : float
        Scaling factor for the median target (default 1.0).
    fallback_window : int
        Fallback window length for warm-up phases.
        
    Returns
    -------
    pd.Series or np.ndarray
        Array of integer window lengths enforcing equal-information boundaries.
    """
    is_series = isinstance(Q, pd.Series)
    Q_s = pd.Series(Q) if not is_series else Q
    
    Q_arr = Q_s.to_numpy(dtype=float)
    N = len(Q_arr)
    
    # Output array
    W_t = np.full(N, fallback_window, dtype=int)
    
    if N == 0:
        if is_series:
            return pd.Series(W_t, index=Q_s.index, name="dynamic_window")
        return W_t
        
    # 1. Strict Causality Target Calculation
    # Median is computed exactly from t-M to t-1 via .shift(1)
    median_Q = Q_s.rolling(window=M, min_periods=1).median().shift(1).to_numpy()
    
    # Safe warm-up fill for early indices or absolute missing data
    safe_median = np.nanmedian(Q_arr) if N > 0 and not np.all(np.isnan(Q_arr)) else 1.0
    median_Q = np.nan_to_num(median_Q, nan=safe_median)
    
    Target_t = target_multiplier * median_Q
    Target_t = np.maximum(Target_t, 1e-12)  # Prevent zero or negative volume targets
    
    # 2. Vectorized Cumulative Sum Search
    # We only need to search up to W_max. Pad the left side with zeros to form full W_max windows for all t.
    Q_padded = np.pad(Q_arr, (W_max - 1, 0), mode='constant', constant_values=0)
    
    # Extract sliding windows of size W_max -> shape (N, W_max)
    windows = np.lib.stride_tricks.sliding_window_view(Q_padded, window_shape=W_max)
    
    # Reverse the window axis so index 0 is Q_t, index 1 is Q_{t-1}, ..., up to Q_{t-W_max+1}
    windows_reversed = windows[:, ::-1]
    
    # Compute the rolling accumulation sum_{i=0}^{k} Q_{t-i}
    cumsum_Q = np.cumsum(windows_reversed, axis=1)  # shape (N, W_max)
    
    # Find the smallest k where the cumulative volume clears the dynamic Target_t
    condition = cumsum_Q >= Target_t[:, np.newaxis]
    
    # np.argmax returns the first index 'k' where condition is True
    k_indices = np.argmax(condition, axis=1)
    
    # Handle cases where the target was never reached even at W_max
    target_reached = np.any(condition, axis=1)
    k_indices = np.where(target_reached, k_indices, W_max - 1)
    
    # W_t is the length of the clearance sequence (k + 1)
    W_raw = k_indices + 1
    
    # 3. Apply explicit boundary clipping
    W_t = np.clip(W_raw, W_min, W_max).astype(int)
    
    # Strictly enforce warm-up fallback for t=0 (since shift(1) is NaN)
    W_t[0] = fallback_window
    
    if is_series:
        return pd.Series(W_t, index=Q_s.index, name="dynamic_window")
    return W_t


def compute_point_05_override(
    df: pd.DataFrame,
    W_base: int = 168,
    W_min: int = 2,
    W_max: int = 72,
    target_multiplier: float = 1.0,
    engine: Optional[Any] = None,
    symbol: str = '',
    volume_col: str = 'quote_asset_volume'
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Ingests the Quote Asset Volume and strictly outputs dynamic information-density lookbacks.
    """
    try:
        # Fallback to standard volume if quote_asset_volume is not present
        col_to_use = volume_col if volume_col in df.columns else 'volume'
        
        if col_to_use not in df.columns:
            raise ValueError(f"Volume column '{col_to_use}' missing from DataFrame.")
            
        return compute_dynamic_volume_density_windows(
            Q=df[col_to_use],
            M=W_base,
            W_min=W_min,
            W_max=W_max,
            target_multiplier=target_multiplier
        )
    except Exception as e:
        _logger.error(f"[POINT_05] Synthetic Volume Aggregation failed for {symbol}: {e}")
        # Fail-safe: return static maximum window to prevent OOM or logic failure
        return pd.Series(W_max, index=df.index, name="dynamic_window")
