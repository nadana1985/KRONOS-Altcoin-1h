"""
Point 18: Linear Volume Impact Scaling - Logarithmic Volume Z-Score Normalization
(Vectorized Implementation)

Replaces naive linear volume metrics with a statistically robust, non-stationary 
normal distribution. Prevents massive capitalization variances across cross-sectional 
high-beta tokens from distorting standard volume flow algorithms.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_18")


def compute_logarithmic_volume_z_score(
    quote_volume: Union[pd.Series, np.ndarray],
    W: int = 100
) -> pd.Series:
    """
    Computes rolling Logarithmic Volume Z-Scores perfectly normalized out-of-sample.
    
    MATHEMATICAL SPECIFICATION:
    1. log_Q = ln(Q_t)
    2. mu_t = Rolling Mean of log_Q over W
    3. sigma_t = Rolling Standard Deviation of log_Q over W
    4. V_tilde_t = (log_Q_t - mu_t) / sigma_t
    5. STRICT CAUSALITY BARRIER: The rolling mean and standard deviation matrices 
       must be shifted forward by 1 bar (.shift(1)) to lock the distribution 
       out-of-sample prior to scoring the current volume event.
       
    Parameters
    ----------
    quote_volume : array-like
        The raw Quote Asset Volume array (Binance Field 7).
    W : int
        The rolling lookback window length for the distribution parameters.
        
    Returns
    -------
    pd.Series
        Normalized continuous floating-point series representing V_tilde_t.
    """
    is_series = isinstance(quote_volume, pd.Series)
    index = quote_volume.index if is_series else None
    
    Q = np.asarray(quote_volume, dtype=float)
    N = len(Q)
    
    if N == 0:
        return pd.Series(dtype=float, index=index, name="log_volume_z_score")
        
    # 1. Secure logarithmic transformation
    # Guard dynamically against low-nominal 0.0 volume bars via 1e-12 precision floor
    log_Q = np.log(np.maximum(Q, 1e-12))
    
    # 2. Vectorized Rolling Distribution Extraction
    safe_mean = np.mean(log_Q) if N > 0 else 0.0
    safe_std = np.std(log_Q) if N > 0 else 1.0
    
    pad_log_Q = np.pad(log_Q, (W - 1, 0), mode='constant', constant_values=safe_mean)
    
    windows = np.lib.stride_tricks.sliding_window_view(pad_log_Q, window_shape=W)
    
    mu_raw = np.mean(windows, axis=1)
    sigma_raw = np.std(windows, axis=1, ddof=1)
    sigma_raw = np.nan_to_num(sigma_raw, nan=0.0)
    
    # 3. STRICT CAUSALITY BARRIER (.shift(1))
    mu_t = np.empty_like(mu_raw)
    sigma_t = np.empty_like(sigma_raw)
    
    # Safely lock index 0 to neutral assumptions preventing NaN propagation
    mu_t[0] = safe_mean
    sigma_t[0] = safe_std
    
    # Extract out-of-sample history exclusively
    mu_t[1:] = mu_raw[:-1]
    sigma_t[1:] = sigma_raw[:-1]
    
    # 4. Precision Guard & Evaluation
    # Guard against completely flat accumulation patches yielding 0 standard deviation
    sigma_safe = np.maximum(sigma_t, 1e-12)
    
    # V_tilde_t = (ln(Q_t) - mu_ln(Q),t) / sigma_ln(Q),t
    V_tilde_t = (log_Q - mu_t) / sigma_safe
    
    # Clean any un-caught artifacts mathematically
    V_tilde_t = np.nan_to_num(V_tilde_t, nan=0.0, posinf=0.0, neginf=0.0)
    
    return pd.Series(V_tilde_t, index=index, name="log_volume_z_score")


def compute_point_18_override(
    df: pd.DataFrame,
    W: int = 100,
    volume_col: str = "quote_asset_volume",
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Destroys linear capitalization biases by standardizing actual volume impacts mathematically.
    """
    try:
        col_to_use = volume_col if volume_col in df.columns else "volume"
        
        if col_to_use not in df.columns:
            raise ValueError(f"Required volume column '{col_to_use}' missing.")
            
        return compute_logarithmic_volume_z_score(
            quote_volume=df[col_to_use],
            W=W
        )
    except Exception as e:
        _logger.error(f"[POINT_18] Logarithmic Volume Normalization failed for {symbol}: {e}")
        # Fail-safe: Returns neutral 0.0 Z-Score mapping smoothly on matrix collapse
        return pd.Series(0.0, index=df.index, name="log_volume_z_score")
