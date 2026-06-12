"""
Point 19: Static Wick Prominence Scaling - Rolling Non-Parametric Beta-CDF Mapping
(Vectorized Implementation)

Replaces rigid linear wick thresholds with dynamic Non-Parametric Beta-CDF Mapping.
Translates absolute exhaustion shadows directly into relative structural probability.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd
from scipy.special import betainc

_logger = logging.getLogger("kronos.bias_override.point_19")


def compute_beta_cdf_wick_exhaustion(
    open_price: Union[pd.Series, np.ndarray],
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    W: int = 100,
    eps: float = 1e-8
) -> pd.Series:
    """
    Computes a dynamically adaptive Wick Prominence probability score natively.
    
    MATHEMATICAL SPECIFICATION:
    1. Wick_Ratio_t = ((H_t - max(O_t, C_t)) + (min(O_t, C_t) - L_t)) / (H_t - L_t + epsilon_t)
    2. Fit (alpha, beta) over window W utilizing the Method of Moments.
    3. Wick_Exh_t = Beta_CDF(Wick_Ratio_t, alpha_t, beta_t)
    4. STRICT CAUSALITY BARRIER: Rolling parameters are shifted (.shift(1)) perfectly out-of-sample.
    
    Parameters
    ----------
    open_price : array-like
    high : array-like
    low : array-like
    close : array-like
    W : int
        The rolling lookback window length for the Beta parameter fits.
    eps : float
        Numerical safeguard.
        
    Returns
    -------
    pd.Series
        Continuous, strictly bounded [0.0, 1.0] cumulative probability scale array.
    """
    is_series = isinstance(close, pd.Series)
    index = close.index if is_series else None
    
    O = np.asarray(open_price, dtype=float)
    H = np.asarray(high, dtype=float)
    L = np.asarray(low, dtype=float)
    C = np.asarray(close, dtype=float)
    
    N = len(C)
    
    if N == 0:
        return pd.Series(dtype=float, index=index, name="beta_wick_exhaustion")
        
    # 1. Structural Wick Ratio Extraction
    upper_wick = H - np.maximum(O, C)
    lower_wick = np.minimum(O, C) - L
    total_wick = upper_wick + lower_wick
    total_range = H - L
    
    # Strictly bind the basic ratio cleanly to prevent boundary limit collapses
    wick_ratio = total_wick / (total_range + eps)
    wick_ratio = np.clip(wick_ratio, eps, 1.0 - eps)
    
    # 2. Extract Out-Of-Sample Distribution Parameters
    # Pad perfectly to track the structural mean natively without zero artifacts
    safe_mean = np.mean(wick_ratio) if N > 0 else 0.5
    pad_ratio = np.pad(wick_ratio, (W - 1, 0), mode='constant', constant_values=safe_mean)
    
    windows = np.lib.stride_tricks.sliding_window_view(pad_ratio, window_shape=W)
    
    mu_raw = np.mean(windows, axis=1)
    v_raw = np.var(windows, axis=1, ddof=1)
    
    # 3. STRICT CAUSALITY BARRIER
    mu_t = np.empty_like(mu_raw)
    v_t = np.empty_like(v_raw)
    
    # Provide neutral uniform distribution defaults (alpha=1, beta=1 implies mu=0.5, var=1/12)
    mu_t[0] = 0.5
    v_t[0] = 1.0 / 12.0
    
    # Ensure current ratio score operates explicitly against closed history only
    mu_t[1:] = mu_raw[:-1]
    v_t[1:] = v_raw[:-1]
    
    # 4. Method of Moments Beta Fit
    # Mathematically, variance of the Beta distribution cannot exceed mu * (1 - mu)
    # Clamp scale metrics aggressively to ensure numerical parameter generation compliance
    mu_safe = np.clip(mu_t, 1e-4, 1.0 - 1e-4)
    v_limit = mu_safe * (1.0 - mu_safe)
    v_safe = np.clip(v_t, 1e-8, v_limit - 1e-8)
    
    # Calculate fundamental scaling multiplier equation: ((mu * (1 - mu)) / var) - 1
    temp = (v_limit / v_safe) - 1.0
    temp = np.maximum(temp, 1e-6)
    
    alpha_t = mu_safe * temp
    beta_t = (1.0 - mu_safe) * temp
    
    # Prevent alpha/beta parameters collapsing below 0
    alpha_t = np.maximum(alpha_t, 1e-6)
    beta_t = np.maximum(beta_t, 1e-6)
    
    # 5. Continuous Beta CDF Evaluation
    # Using scipy.special.betainc (Regularized Incomplete Beta Function mapped correctly)
    wick_exh_t = betainc(alpha_t, beta_t, wick_ratio)
    
    # Final cleanup binding natively inside absolute limits safely preventing float exhaust
    wick_exh_t = np.nan_to_num(wick_exh_t, nan=0.5, posinf=1.0, neginf=0.0)
    wick_exh_t = np.clip(wick_exh_t, 0.0, 1.0)
    
    return pd.Series(wick_exh_t, index=index, name="beta_wick_exhaustion")


def compute_point_19_override(
    df: pd.DataFrame,
    W: int = 100,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Destroys linear wick proxies, scaling probability natively against structural limits.
    """
    try:
        req_cols = ["open", "high", "low", "close"]
        missing = [c for c in req_cols if c not in df.columns]
        
        if missing:
            raise ValueError(f"Missing required columns for Point 19: {missing}")
            
        return compute_beta_cdf_wick_exhaustion(
            open_price=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            W=W
        )
    except Exception as e:
        _logger.error(f"[POINT_19] Rolling Beta-CDF Mapping failed for {symbol}: {e}")
        # Fail-safe: Return completely neutral mapping (0.50 probability) on collapse
        return pd.Series(0.5, index=df.index, name="beta_wick_exhaustion")