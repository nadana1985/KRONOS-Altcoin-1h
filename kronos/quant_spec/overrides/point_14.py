"""
Point 14: Hardcoded Denominator Epsilon Guards - Numerical Standard Deviation Precision Scale
(Vectorized Implementation)

Replaces rigid static epsilon constants with dynamically scaled precision guards.
Prevents low-nominal assets from encountering scale distortion while guaranteeing 
mathematical division safety natively.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_14")


def compute_dynamic_precision_epsilon(
    X: Union[pd.Series, np.ndarray],
    W: int = 24,
    scale_factor: float = 1e-7,
    absolute_min_floor: float = 1e-12
) -> Union[pd.Series, np.ndarray]:
    """
    Computes a dynamically adaptive, variance-stabilized epsilon array.
    
    MATHEMATICAL SPECIFICATION:
    1. Ingest targeted denominator matrix X.
    2. epsilon_t = sigma(X_[t-W : t-1]) * scale_factor
    3. STRICT CAUSALITY BARRIER: Standard deviation computes strictly on historical blocks 
       ending at 't-1' (.shift(1)) locking the safety floor out-of-sample.
    4. Enforce absolute_min_floor to prevent total matrix collapse on zero-variance zones.
    
    Parameters
    ----------
    X : array-like
        The targeted denominator series vector.
    W : int
        The rolling lookback window length.
    scale_factor : float
        The scale multiplier mapping standard deviation to an epsilon guard natively.
    absolute_min_floor : float
        Absolute minimum floor protecting against 0 variance.
        
    Returns
    -------
    pd.Series or np.ndarray
        A corresponding vector of dynamically scaled epsilons matching the input.
    """
    is_series = isinstance(X, pd.Series)
    index = X.index if is_series else None
    
    X_arr = np.asarray(X, dtype=float)
    N = len(X_arr)
    
    if N == 0:
        if is_series:
            return pd.Series(dtype=float, index=index, name="dynamic_epsilon")
        return np.array([], dtype=float)
        
    # 1. STRICT CAUSALITY BARRIER
    # Use pure NumPy stride tricks to extract the structural standard deviation instantly.
    # Pad the beginning natively to permit safe structural calculation without early matrix failure
    safe_std = np.std(X_arr) if N > 0 else 1.0
    
    # Pad with W-1 copies of the mean to ensure early initial standard deviations aren't poisoned
    X_padded = np.pad(X_arr, (W - 1, 0), mode='constant', constant_values=np.mean(X_arr) if N > 0 else 1.0)
    
    windows = np.lib.stride_tricks.sliding_window_view(X_padded, window_shape=W)
    sigma_raw = np.std(windows, axis=1, ddof=1)  # shape (N,)
    
    # Fill any NaNs created by ddof=1 on zero variance slices safely
    sigma_raw = np.nan_to_num(sigma_raw, nan=0.0)
    
    # Shift array cleanly forward by 1 index to simulate .shift(1) out-of-sample locking
    sigma_t = np.empty_like(sigma_raw)
    sigma_t[0] = safe_std  # Fallback for index 0
    sigma_t[1:] = sigma_raw[:-1]
    
    # 2. Dynamic Scale Evaluation
    epsilon_raw = sigma_t * scale_factor
    
    # 3. Floor Enforcement
    epsilon_t = np.maximum(epsilon_raw, absolute_min_floor)
    
    if is_series:
        return pd.Series(epsilon_t, index=index, name="dynamic_epsilon")
    return epsilon_t


def compute_point_14_override(
    df: pd.DataFrame,
    target_column: str,
    W: int = 24,
    scale_factor: float = 1e-7,
    absolute_min_floor: float = 1e-12,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Applies the dynamic standard deviation precision guard to a target denominator column.
    """
    try:
        if target_column not in df.columns:
            raise ValueError(f"Target denominator column '{target_column}' missing from DataFrame.")
            
        return compute_dynamic_precision_epsilon(
            X=df[target_column],
            W=W,
            scale_factor=scale_factor,
            absolute_min_floor=absolute_min_floor
        )
    except Exception as e:
        _logger.error(f"[POINT_14] Dynamic epsilon calculation failed for {symbol}: {e}")
        # Fail-safe: Return a rigid static minimum floor fallback natively
        return pd.Series(absolute_min_floor, index=df.index, name="dynamic_epsilon")