"""
Point 09: Discrete Key Level Bandwidths - ATR-Weighted Volatility Bandwidths
(Vectorized Implementation)

Replaces flat, static percentage boundaries with a dynamic Average True Range (ATR)
scaling algorithm. Seamlessly adjusts to shifting volatility profiles and high-beta
structural divergence across distinct market regimes.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_09")


def compute_dynamic_atr_bandwidths(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    W: int = 24,
    kappa: float = 0.25,
) -> pd.Series:
    """
    Computes a strictly causal, dynamic floating-point series of ATR-scaled bandwidths.
    
    MATHEMATICAL SPECIFICATION:
    1. True_Range_t = max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|)
    2. ATR_t = (1 / W) * sum_{i=0}^{W-1} True_Range_{t-i}
    3. Bandwidth_t = ATR_t * kappa
    4. STRICT CAUSALITY BARRIER: The ATR evaluated at time 't' strictly operates on
       the closed window ending at 't-1' (.shift(1)), locking the boundaries prior 
       to the current bar's price action.
       
    Parameters
    ----------
    high : array-like
        High prices array.
    low : array-like
        Low prices array.
    close : array-like
        Close prices array.
    W : int
        The rolling historical lookback window for the ATR metric.
    kappa : float
        The scale multiplier constant determining the proportion of the ATR used.
        
    Returns
    -------
    pd.Series
        Dynamic Bandwidth_t as a floating-point series.
    """
    is_series = isinstance(close, pd.Series)
    index = close.index if is_series else None
    
    # Cast safely to float arrays for backend NumPy matrix operations
    H = np.asarray(high, dtype=float)
    L = np.asarray(low, dtype=float)
    C = np.asarray(close, dtype=float)
    
    N = len(C)
    
    if N == 0:
        return pd.Series(dtype=float, index=index, name="atr_bandwidth")
        
    # 1. Compute True Range components natively
    # Generate C_{t-1} array, guarding the 0-index with the current open or close to prevent NaN bleed
    C_prev = np.empty_like(C)
    C_prev[0] = C[0] 
    C_prev[1:] = C[:-1]
    
    tr1 = H - L
    tr2 = np.abs(H - C_prev)
    tr3 = np.abs(L - C_prev)
    
    # 2. Vectorized True_Range_t calculation
    TR = np.maximum(np.maximum(tr1, tr2), tr3)
    
    # 3. Fast NumPy Rolling ATR Extraction
    # Calculate a safe warm-up mean for initial padding
    safe_mean = np.mean(TR) if N > 0 else 1.0
    
    # Pad TR array to easily stride windows of size W identically mapping output length to N
    TR_padded = np.pad(TR, (W - 1, 0), mode='constant', constant_values=safe_mean)
    
    # Generate batched windows: shape (N, W)
    windows = np.lib.stride_tricks.sliding_window_view(TR_padded, window_shape=W)
    
    # Calculate rolling mean across all windows instantly
    ATR_raw = np.mean(windows, axis=1)  # shape (N,)
    
    # 4. STRICT CAUSALITY BARRIER (.shift(1) emulation)
    # The ATR assigned to time 't' must only incorporate [t-W : t-1].
    # By shifting ATR_raw exactly 1 slot forward, we lock out current-bar contamination.
    ATR_t = np.empty_like(ATR_raw)
    ATR_t[0] = safe_mean  # Initialize index 0 with the fallback density
    ATR_t[1:] = ATR_raw[:-1]
    
    # 5. Dynamic Bandwidth Scaling
    Bandwidth_t = ATR_t * kappa
    
    # Return directly as a pandas Series for downstream engine compatibility
    return pd.Series(Bandwidth_t, index=index, name="atr_bandwidth")


def compute_point_09_override(
    df: pd.DataFrame,
    W: int = 24,
    kappa: float = 0.25,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Processes the DataFrame securely without slow loops, returning the dynamic
    ATR-scaled floating-point boundaries.
    """
    try:
        req_cols = ["high", "low", "close"]
        missing = [c for c in req_cols if c not in df.columns]
        
        if missing:
            raise ValueError(f"Missing required price columns for Point 09: {missing}")
            
        return compute_dynamic_atr_bandwidths(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            W=W,
            kappa=kappa
        )
    except Exception as e:
        _logger.error(f"[POINT_09] Dynamic ATR Bandwidth calculation failed for {symbol}: {e}")
        # Fail-safe: Returns an ultra-tight default bandwidth on catastrophic failure
        return pd.Series(0.005, index=df.index, name="atr_bandwidth")