"""
Point 04: Manual Linear Multiplier Bias - Strict Rolling Percentile Rank Transform
(Vectorized Implementation)

Eliminates arbitrary manual linear multipliers. Maps feature signals into a dynamic
non-parametric percentile space bound in [0.0, 1.0], using a strict causality barrier.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_04")


def compute_strict_rolling_percentile_rank(
    X: Union[pd.Series, np.ndarray],
    W: int = 100,
) -> Union[pd.Series, np.ndarray]:
    """
    Computes a strictly causal rolling percentile rank.
    
    MATHEMATICAL SPECIFICATION:
    1. Rank(X_t) = (1 / W) * sum( I[X_tau <= X_t] ) for tau = t-W to t-1
    2. STRICT CAUSALITY BARRIER: The current observation 'X_t' is evaluated strictly 
       against the closed historical slice [X_t-W, ..., X_t-1]. It is absolutely 
       prevented from being included in its own reference pool.
    3. BOUNDS: Output is explicitly a floating-point value bounded uniformly in [0.0, 1.0].
    4. WARM-UP PERIOD: For 't' < W, the rank defaults to 0.5 to prevent NaNs.
    
    Parameters
    ----------
    X : pd.Series or np.ndarray
        The input array or series representing the feature or multiplier proxy to be ranked.
    W : int
        The historical lookback window length.
        
    Returns
    -------
    pd.Series or np.ndarray
        An array/series of strictly causal rank values bounded in [0.0, 1.0].
    """
    is_series = isinstance(X, pd.Series)
    X_arr = np.asarray(X, dtype=float)
    
    N = len(X_arr)
    
    # Initialize output array with the neutral 0.5 baseline for warm-up index 't' < W
    R = np.full(N, 0.5, dtype=float)
    
    if N > W:
        # 1. Create vectorized historical windows using stride tricks
        # sliding_window_view(X_arr, W) returns shape (N - W + 1, W)
        windows = np.lib.stride_tricks.sliding_window_view(X_arr, window_shape=W)
        
        # 2. Enforce Strict Causality Barrier
        # X_hist spans indices [t-W : t-1].
        # windows[0] covers [0 : W-1], which is the exact history for predicting at t=W.
        # windows[:-1] correctly maps to t from W to N-1.
        X_hist = windows[:-1]  # shape: (N - W, W)
        
        # Current observation X_t at timestamp 't' (from W to N-1)
        X_t = X_arr[W:]  # shape: (N - W,)
        
        # Expand X_t for broadcasting against X_hist
        X_t_expanded = X_t[:, np.newaxis]  # shape: (N - W, 1)
        
        # 3. Compute the rank using boolean indicators
        # Ignore NaNs in historical comparisons
        # I[X_tau <= X_t]
        indicators = (X_hist <= X_t_expanded)
        
        # Handle cases where historical data contains NaNs
        valid_hist = ~np.isnan(X_hist)
        indicators = indicators & valid_hist
        valid_counts = valid_hist.sum(axis=1)
        
        # Fallback to 1 if all are NaN to prevent div by zero
        valid_counts = np.maximum(valid_counts, 1)
        
        # Rank(X_t) = sum / valid_W
        rank_t = indicators.sum(axis=1) / valid_counts
        
        # If X_t itself is NaN, rank defaults to 0.5
        rank_t = np.where(np.isnan(X_t), 0.5, rank_t)
        
        R[W:] = rank_t
        
    # 4. Strict bounding to [0.0, 1.0] to guarantee uniform constraint
    R = np.clip(R, 0.0, 1.0)
        
    if is_series:
        return pd.Series(R, index=X.index, name="rank_transform")
        
    return R


def compute_point_04_override(
    df: pd.DataFrame,
    target_column: str,
    W: int = 100,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Processes the entire DataFrame sequentially via stride tricks without procedural loops.
    Strips away all arbitrary linear scaling multipliers and replaces them with 
    the dynamic, causality-safe empirical rank transformation.
    """
    try:
        if target_column not in df.columns:
            raise ValueError(f"Target feature column '{target_column}' missing from DataFrame.")
            
        return compute_strict_rolling_percentile_rank(df[target_column], W=W)
    except Exception as e:
        _logger.error(f"[POINT_04] Rolling Rank Transform failed for {symbol}: {e}")
        # Fail-safe: neutral 0.5 propagation
        return pd.Series(0.5, index=df.index, name="rank_transform")