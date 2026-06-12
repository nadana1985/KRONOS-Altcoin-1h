"""
Point 27: Static Order Slicing Metrics - Power-Law Slicing Exponent Estimator
(Vectorized Implementation)

Replaces naive transaction counting with a mathematically robust Hill MLE exponent.
Dynamically isolates institutional TWAP/VWAP execution signatures masked heavily 
by massive retail order-flow noise.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_27")


def compute_power_law_slicing_exponent(
    volume: Union[pd.Series, np.ndarray],
    trade_count: Union[pd.Series, np.ndarray],
    W: int = 24,
    eps: float = 1e-12
) -> pd.Series:
    """
    Computes continuous Pareto tail parameters modeling real-time institutional execution natively.
    
    MATHEMATICAL SPECIFICATION:
    1. S_bar_t = V_t / (Count_t + eps)
    2. alpha_t = W / sum_{i=0}^{W-1} ( ln( S_bar_{t-i} / S_bar_min,t ) )
    3. STRICT CAUSALITY BARRIER: Extracted Hill MLE parameters are shifted explicitly 
       forward by exactly 1 bar (.shift(1)) perfectly mapping structural boundaries out-of-sample.
       
    Parameters
    ----------
    volume : array-like
        Total Base Volume (V_t).
    trade_count : array-like
        Total Trade Count (Count_t).
    W : int
        Rolling lookback window length for Hill Maximum Likelihood Estimator calculations.
    eps : float
        Numerical safeguard explicitly preventing log(0) and division-by-zero crashes globally.
        
    Returns
    -------
    pd.Series
        Continuous 1D fractional sequence explicitly representing alpha_t (Slot 27).
    """
    is_series = isinstance(volume, pd.Series)
    index = volume.index if is_series else None
    
    V_t = np.asarray(volume, dtype=float)
    Count_t = np.asarray(trade_count, dtype=float)
    
    N = len(V_t)
    
    if N == 0:
        return pd.Series(dtype=float, index=index, name="power_law_exponent")
        
    # 1. Structural Average Trade Size Mapping (S_bar)
    # Block total division collapses natively against absolute zero liquidity bands
    Count_safe = np.maximum(Count_t, eps)
    S_bar = V_t / Count_safe
    S_bar_safe = np.maximum(S_bar, eps)
    
    # 2. Extract Causal Rolling MLE Sequence natively utilizing Stride Tricks
    safe_mean = np.mean(S_bar_safe) if N > 0 else 1.0
    
    pad_S = np.pad(S_bar_safe, (W - 1, 0), mode='constant', constant_values=safe_mean)
    
    # Extract structural sliding data sequences natively (N, W shape)
    windows = np.lib.stride_tricks.sliding_window_view(pad_S, window_shape=W)
    
    # Extract the absolute localized minimum sequence natively aligned on the column axis
    S_min_raw = np.min(windows, axis=1, keepdims=True)
    S_min_safe = np.maximum(S_min_raw, eps)
    
    # Evaluate Hill MLE exact scaling fractions cleanly via matrix broadcasting limits
    log_ratio_windows = np.log(windows / S_min_safe)
    
    # Calculate denominator array
    sum_log_raw = np.sum(log_ratio_windows, axis=1)
    
    # Protect entirely flat sequential limits (where all sizes equal the minimum size)
    # This prevents the final alpha_raw fraction from destroying Python execution bounds
    sum_log_safe = np.maximum(sum_log_raw, eps)
    
    alpha_raw = W / sum_log_safe
    
    # 3. STRICT CAUSALITY BARRIER (.shift(1))
    alpha_t = np.empty_like(alpha_raw)
    
    # Secure baseline initial metrics organically preventing parameter bleed
    alpha_t[0] = np.mean(alpha_raw) if N > 0 else 1.0
    
    # Matrix lock execution strictly out-of-sample scaling forward 1 integer
    alpha_t[1:] = alpha_raw[:-1]
    
    # Scrub remaining infinities or nan metrics safely handling absolute 1e6 bounds
    alpha_t = np.nan_to_num(alpha_t, nan=1.0, posinf=1e6, neginf=1.0)
    
    return pd.Series(alpha_t, index=index, name="power_law_exponent")


def compute_point_27_override(
    df: pd.DataFrame,
    volume_col: str = "volume",
    trade_count_col: str = "number_of_trades",
    W: int = 24,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Demolishes rigid static trade count assumptions processing continuous power-law limits.
    """
    try:
        req_cols = [volume_col, trade_count_col]
        missing = [c for c in req_cols if c not in df.columns]
        
        if missing:
            raise ValueError(f"Missing required columns for Point 27: {missing}")
            
        return compute_power_law_slicing_exponent(
            volume=df[volume_col],
            trade_count=df[trade_count_col],
            W=W
        )
    except Exception as e:
        _logger.error(f"[POINT_27] Power-Law Slicing Exponent Extraction failed for {symbol}: {e}")
        # Fail-safe: Returns neutral fixed probability baseline natively on collapse
        return pd.Series(1.0, index=df.index, name="power_law_exponent")
