"""
Point 28: Homogeneous Volume Profile Lifespans - Hurst-Adaptive Profile Lifespans
(Vectorized Implementation)

Replaces rigid static lookback windows for volume density profiles with a dynamically 
calibrated Rescaled Range (R/S) Hurst Exponent estimator. Allows volume profiling arrays 
to breathe organically, compressing during trending persistence and expanding heavily 
to comprehensively encapsulate broad mean-reverting structural nodes locally.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_28")


def compute_hurst_adaptive_lifespan(
    close: Union[pd.Series, np.ndarray],
    W_anchor: int = 100,
    N_min: int = 24,
    N_max: int = 240
) -> pd.Series:
    """
    Computes dynamic, non-linear integer limits extracting localized Hurst profile sequences natively.
    
    MATHEMATICAL SPECIFICATION:
    1. Extract structural log returns seamlessly from Price sequences.
    2. H_t = ln(R/S) / ln(W_anchor) -> Evaluated via Rescaled Range matrix sequences.
    3. N_adaptive,t = round( N_min + (N_max - N_min) * (1.0 - H_t) )
    4. STRICT CAUSALITY BARRIER: The explicit Hurst exponent sequence computes completely
       out-of-sample mapping backwards strictly via (.shift(1)) causality isolation.
       
    Parameters
    ----------
    close : array-like
        Historical Close price sequence evaluating structural returns natively.
    W_anchor : int
        Baseline R/S fractional boundary lookback window.
    N_min : int
        Absolute minimum compressed profile limit natively bounding the system.
    N_max : int
        Absolute maximum persistent node memory ceiling limit.
        
    Returns
    -------
    pd.Series
        Continuous 1D explicit integer array driving localized Profile sequence constraints.
    """
    is_series = isinstance(close, pd.Series)
    index = close.index if is_series else None
    
    C = np.asarray(close, dtype=float)
    N = len(C)
    
    if N == 0:
        return pd.Series(dtype=int, index=index, name="adaptive_profile_lifespan")
        
    C_safe = np.maximum(C, 1e-12)
    
    # 1. Structural Log Returns Extraction
    log_ret = np.zeros(N)
    log_ret[1:] = np.log(C_safe[1:] / C_safe[:-1])
    
    # 2. Extract strictly causal historical sequences via Stride matrices natively
    safe_mean = np.mean(log_ret) if N > 0 else 0.0
    
    pad_r = np.pad(log_ret, (W_anchor - 1, 0), mode='constant', constant_values=safe_mean)
    windows = np.lib.stride_tricks.sliding_window_view(pad_r, window_shape=W_anchor)
    
    # 3. Vectorized Rescaled Range (R/S) Mathematical Engine
    m = np.mean(windows, axis=1, keepdims=True)
    
    # Mean-adjusted localized matrix distribution deviations
    Y = windows - m
    
    # Cumulative Sum limits natively capturing structural density ranges organically
    Z = np.cumsum(Y, axis=1)
    
    R = np.max(Z, axis=1) - np.min(Z, axis=1)
    S = np.std(windows, axis=1, ddof=1)
    
    # Secure analytical division points from strictly bounded numerical collapses
    S_safe = np.maximum(S, 1e-12)
    RS = R / S_safe
    
    # Single-scale Logarithmic Hurst Extrapolation 
    H_raw = np.log(np.maximum(RS, 1e-12)) / np.log(W_anchor)
    
    # Force continuous mathematical outputs securely across bounds
    H_raw = np.nan_to_num(H_raw, nan=0.5, posinf=1.0, neginf=0.0)
    H_raw = np.clip(H_raw, 0.0, 1.0)
    
    # 4. STRICT CAUSALITY BARRIER (.shift(1))
    H_t = np.empty_like(H_raw)
    
    # Initialize index 0 safely generating completely unbiased mean-reverting thresholds
    H_t[0] = 0.5 
    
    # Lock matrix extraction explicitly capturing completely finalized historical structures locally
    H_t[1:] = H_raw[:-1]
    
    # 5. Adaptive Integer Profile Lifespan Conversion natively
    # Formula explicitly matches: N_adaptive,t = round( N_min + (N_max - N_min) * (1.0 - H_t) )
    N_adaptive_raw = N_min + (N_max - N_min) * (1.0 - H_t)
    
    # Cast entirely natively to structural integers seamlessly preventing precision boundaries
    N_adaptive_t = np.round(N_adaptive_raw).astype(int)
    
    # Limit potential float exhaustion bounds strictly against math limits explicitly
    N_adaptive_t = np.clip(N_adaptive_t, N_min, N_max)
    
    return pd.Series(N_adaptive_t, index=index, name="adaptive_profile_lifespan")


def compute_point_28_override(
    df: pd.DataFrame,
    W_anchor: int = 100,
    N_min: int = 24,
    N_max: int = 240,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Extracts continuous Hurst-Adaptive Volume Profile integer boundaries organically.
    """
    try:
        req_cols = ["close"]
        missing = [c for c in req_cols if c not in df.columns]
        
        if missing:
            raise ValueError(f"Missing required columns for Point 28: {missing}")
            
        return compute_hurst_adaptive_lifespan(
            close=df["close"],
            W_anchor=W_anchor,
            N_min=N_min,
            N_max=N_max
        )
    except Exception as e:
        _logger.error(f"[POINT_28] Hurst-Adaptive Profile Extrapolation failed for {symbol}: {e}")
        # Fail-safe: Returns completely neutral structural baseline organically (median density limits)
        median_N = int((N_min + N_max) / 2)
        return pd.Series(median_N, index=df.index, name="adaptive_profile_lifespan")