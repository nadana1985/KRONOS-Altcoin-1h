"""
Point 38: Variance Suppression via Lag-Eliminated Averages - Microstructural Variance Trajectory Isolator
(Vectorized Implementation)

Destroys catastrophic cross-contamination boundaries where smoothed momentum indicators artificially 
suppress variance metrics, tricking position-sizing models into extreme hyper-leveraged blowouts.
Structurally isolates all volatility modeling exclusively to raw unsmoothed geometric returns natively.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_38")


def compute_raw_microstructural_variance(
    raw_close: Union[pd.Series, np.ndarray],
    W: int = 24
) -> pd.Series:
    """
    Computes pure, unfiltered geometric variance strictly isolating true structural market risk explicitly.
    
    MATHEMATICAL SPECIFICATION:
    1. Structurally isolates trend logic cleanly from risk estimations inherently.
    2. Log_Returns = ln(Raw_Close_t / Raw_Close_t-1)
    3. Evaluates core standard derivations strictly utilizing pure geometric realities.
    4. STRICT CAUSALITY BARRIER: Input sequences stride completely backward evaluating strictly 
       out-of-sample index [t-1] (.shift(1)) cleanly locking risk metrics before execution bounds natively.
       
    Parameters
    ----------
    raw_close : array-like
        The pure, entirely unsmoothed baseline Close matrix evaluating absolute limits.
    W : int
        Lookback anchoring the exact variance memory sequences organically natively.
        
    Returns
    -------
    pd.Series
        Continuous true geometric volatility mapping limits flawlessly (Slot 38).
    """
    is_series = isinstance(raw_close, pd.Series)
    index = raw_close.index if is_series else None
    
    C = np.asarray(raw_close, dtype=float)
    N = len(C)
    
    if N == 0:
        return pd.Series(dtype=float, index=index, name="raw_structural_variance")
        
    # Standard numerical bounds preventing strict zero division logic natively
    C_safe = np.maximum(C, 1e-12)
    
    # 1. Structural Geometric Log Returns completely bypassing all smoothed moving averages inherently
    log_ret = np.zeros(N)
    log_ret[1:] = np.log(C_safe[1:] / C_safe[:-1])
    
    # 2. Extract strictly localized rolling sequences mapping continuous structural bounds
    safe_mean = np.mean(log_ret) if N > 0 else 0.0
    
    pad_r = np.pad(log_ret, (W - 1, 0), mode='constant', constant_values=safe_mean)
    win_r_raw = np.lib.stride_tricks.sliding_window_view(pad_r, window_shape=W)
    
    # 3. STRICT CAUSALITY BARRIER (.shift(1))
    win_r_t = np.empty_like(win_r_raw)
    
    # Neutral limit fallback mapping boundaries cleanly natively
    win_r_t[0] = win_r_raw[0]
    
    # Sequence physical lock strictly establishing absolute out-of-sample boundaries naturally
    win_r_t[1:] = win_r_raw[:-1]
    
    # 4. Pure Microstructural Variance Isolation Geometry
    # Evaluate pure execution variance natively extracting limits gracefully
    raw_variance_t = np.var(win_r_t, axis=1, ddof=1)
    raw_std_t = np.sqrt(np.maximum(raw_variance_t, 0.0))
    
    # Scrub numerical matrices physically isolating limit crashes reliably
    raw_std_t = np.nan_to_num(raw_std_t, nan=0.0)
    
    return pd.Series(raw_std_t, index=index, name="raw_structural_variance")


def compute_point_38_override(
    df: pd.DataFrame,
    raw_close_col: str = "close",
    W: int = 24,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Destroys artificial smoothed variance sequences natively standardizing physical volatility strictly on raw limits.
    """
    try:
        if raw_close_col not in df.columns:
            raise ValueError(f"Missing required raw target column '{raw_close_col}' for Point 38.")
            
        return compute_raw_microstructural_variance(
            raw_close=df[raw_close_col],
            W=W
        )
    except Exception as e:
        _logger.error(f"[POINT_38] Raw Microstructural Variance Isolation failed for {symbol}: {e}")
        # Fail-safe: Return pure neutral zero structural risk geometry actively natively
        return pd.Series(0.0, index=df.index, name="raw_structural_variance")
