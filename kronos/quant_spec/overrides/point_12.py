"""
Point 12: Binary Volatility Regime Boundaries - Continuous Variance Mixture Z-Scores
(Vectorized Implementation)

Replaces rigid binary state partitioning (e.g., ADX > 50) with continuous normalized
volatility Z-scores. Identifies and scales structural regime shifts probabilistically
without forcing continuous variance data into artificial categorical bins.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_12")


def compute_continuous_volatility_z_scores(
    close: Union[pd.Series, np.ndarray],
    W_short: int = 12,
    W_long: int = 72,
    W_anchor: int = 168
) -> pd.Series:
    """
    Computes a strictly causal, normalized continuous Volatility Z-score using Variance Ratios.
    
    MATHEMATICAL SPECIFICATION:
    1. sigma_short,t^2 = Variance(log_returns) over W_short
    2. sigma_long,t^2  = Variance(log_returns) over W_long
    3. R_t = sigma_short,t^2 / sigma_long,t^2
    4. Vol_Z_t = (R_t - mu) / sigma
    5. STRICT CAUSALITY BARRIER: Rolling mean (mu) and standard deviation (sigma) of R_t 
       are shifted by 1 bar to score the current ratio exclusively out-of-sample.
    
    Parameters
    ----------
    close : array-like
        The raw asset price array.
    W_short : int
        Short-term variance lookback window.
    W_long : int
        Long-term variance lookback window.
    W_anchor : int
        Anchor window for the rolling variance ratio distribution.
        
    Returns
    -------
    pd.Series
        Normalized continuous indicator series representing Vol_Z_t.
    """
    is_series = isinstance(close, pd.Series)
    index = close.index if is_series else None
    
    # Cast to raw float array to leverage low-level C-backend matrix speeds
    C = np.asarray(close, dtype=float)
    N = len(C)
    
    if N == 0:
        return pd.Series(dtype=float, index=index, name="vol_z_score")
        
    # 1. Compute Raw Log Returns
    log_ret = np.zeros(N, dtype=float)
    # Handle the division by zero natively with 1e-12 safeguards
    C_prev = np.maximum(C[:-1], 1e-12)
    C_curr = np.maximum(C[1:], 1e-12)
    log_ret[1:] = np.log(C_curr / C_prev)
    
    # 2. NumPy Vectorized Rolling Variance Extraction
    # Short-Term Variance
    pad_short = np.pad(log_ret, (W_short - 1, 0), mode='constant', constant_values=0.0)
    windows_short = np.lib.stride_tricks.sliding_window_view(pad_short, window_shape=W_short)
    sigma2_short = np.var(windows_short, axis=1, ddof=1)  # shape (N,)
    
    # Long-Term Variance
    pad_long = np.pad(log_ret, (W_long - 1, 0), mode='constant', constant_values=0.0)
    windows_long = np.lib.stride_tricks.sliding_window_view(pad_long, window_shape=W_long)
    sigma2_long = np.var(windows_long, axis=1, ddof=1)  # shape (N,)
    
    # Protect against div by zero on absolutely flat accumulation ranges
    sigma2_long = np.maximum(sigma2_long, 1e-12)
    
    # 3. Compute Realized Variance Ratios
    R_t = sigma2_short / sigma2_long
    
    # 4. Track Continuous Rolling Distributions natively in NumPy
    pad_anchor = np.pad(R_t, (W_anchor - 1, 0), mode='constant', constant_values=1.0)
    windows_anchor = np.lib.stride_tricks.sliding_window_view(pad_anchor, window_shape=W_anchor)
    
    # Raw unshifted population parameters
    mu_raw = np.mean(windows_anchor, axis=1)
    sigma_raw = np.std(windows_anchor, axis=1, ddof=1)
    
    # 5. STRICT CAUSALITY BARRIER
    # Shift parameters exactly 1 bar forward. This ensures that the variance ratio evaluated
    # currently at index 't' is scored against the distribution explicitly locking at 't-1'.
    mu_shifted = np.empty_like(mu_raw)
    sigma_shifted = np.empty_like(sigma_raw)
    
    # Initial fallback states
    mu_shifted[0] = 1.0
    sigma_shifted[0] = 1.0
    
    # Apply strict out-of-sample forward shift
    mu_shifted[1:] = mu_raw[:-1]
    sigma_shifted[1:] = sigma_raw[:-1]
    
    # Safely lock minimum standard deviation 
    sigma_shifted = np.maximum(sigma_shifted, 1e-12)
    
    # 6. Output Continuous Volatility Z-score
    Vol_Z_t = (R_t - mu_shifted) / sigma_shifted
    
    # Scrub outputs from potential warm-up NaN artifacts safely
    Vol_Z_t = np.nan_to_num(Vol_Z_t, nan=0.0, posinf=0.0, neginf=0.0)
    
    return pd.Series(Vol_Z_t, index=index, name="vol_z_score")


def compute_point_12_override(
    df: pd.DataFrame,
    W_short: int = 12,
    W_long: int = 72,
    W_anchor: int = 168,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Erases binary volatility logic and maps structural states probabilistically.
    """
    try:
        if "close" not in df.columns:
            raise ValueError("DataFrame must contain a 'close' column to compute Volatility Z-Scores.")
            
        return compute_continuous_volatility_z_scores(
            close=df["close"],
            W_short=W_short,
            W_long=W_long,
            W_anchor=W_anchor
        )
    except Exception as e:
        _logger.error(f"[POINT_12] Variance Mixture Z-Score failed for {symbol}: {e}")
        # Fail-safe: Return flat neutral series on matrix collapse
        return pd.Series(0.0, index=df.index, name="vol_z_score")
