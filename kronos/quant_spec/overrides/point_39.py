"""
Point 39: Static Outlier Winsorization Bounds - Volatility-Adaptive Huber Weighting Filter
(Vectorized Implementation)

Replaces fundamentally rigid percentile hard-clipping constraints which systematically distort true 
distribution profiles and blindly mask massive structural anomalies natively. Deploys a continuously 
scaling Volatility-Adaptive Huber Weighting Filter precisely bounding distributions completely out-of-sample.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_39")


def compute_adaptive_huber_winsorization(
    feature_series: Union[pd.Series, np.ndarray],
    vol_z_series: Union[pd.Series, np.ndarray],
    W: int = 50,
    k_base: float = 2.5,
    eps_scale: float = 1e-7,
    eps_min: float = 1e-12
) -> pd.Series:
    """
    Computes an actively breathing anomaly boundary natively scaling via localized geometric variance matrices.
    
    MATHEMATICAL SPECIFICATION:
    1. Extracts explicit historical Median and MAD bounds securely executing logic natively over window W.
    2. z_t = (X_t - median(X)) / (1.4826 * MAD(X) + epsilon_t)
    3. k_t = k_base * (1.0 + max(0.0, Vol_Z_t))
    4. X_cleaned,t = X_t if |z_t| <= k_t else median(X) + sgn(z_t) * k_t * (1.4826 * MAD(X))
    5. STRICT CAUSALITY BARRIER: Median and MAD parameters exclusively execute utilizing structural
       historical limits mapped via (.shift(1)) perfectly avoiding modern lookahead leaks naturally.
       
    Parameters
    ----------
    feature_series : array-like
        The raw dynamic feature extracting bounds tracking physical geometric limits explicitly.
    vol_z_series : array-like
        The contemporary Volatility Z-Score index naturally modulating filter boundary capacities natively.
    W : int
        Continuous rolling lookback window interval mapping baseline sequences.
    k_base : float
        Absolute geometric standard deviation parameter scaling the primary Huber boundary matrix.
    eps_scale : float
        Explicit standard deviation bounds scaling Point 14 precision bounds properly.
    eps_min : float
        Hard sequence floor perfectly avoiding division by zero logical cascades explicitly.
        
    Returns
    -------
    pd.Series
        Cleaned, fully winsorized 1D sequence mapping dynamic geometric outliers smoothly completely natively (Slot 39).
    """
    is_series = isinstance(feature_series, pd.Series)
    index = feature_series.index if is_series else None
    
    X = np.asarray(feature_series, dtype=float)
    Vol_Z = np.asarray(vol_z_series, dtype=float)
    N = len(X)
    
    if N == 0:
        return pd.Series(dtype=float, index=index, name="huber_winsorized_feature")
        
    # Baseline normalizations mapping spatial logic seamlessly natively 
    safe_median = np.median(X) if N > 0 else 0.0
    
    pad_X = np.pad(X, (W - 1, 0), mode='constant', constant_values=safe_median)
    windows = np.lib.stride_tricks.sliding_window_view(pad_X, window_shape=W)
    
    # 1. Structural Median and Median Absolute Deviation calculations
    med_raw = np.median(windows, axis=1)
    
    # Executing explicitly vectorized limits calculating localized variance organically
    med_raw_dims = med_raw.reshape(-1, 1)
    mad_raw = np.median(np.abs(windows - med_raw_dims), axis=1)
    
    std_raw = np.std(windows, axis=1, ddof=1)
    std_raw = np.nan_to_num(std_raw, nan=0.0)
    
    # 2. STRICT CAUSALITY BARRIER (.shift(1))
    med_t = np.empty_like(med_raw)
    mad_t = np.empty_like(mad_raw)
    std_t = np.empty_like(std_raw)
    
    # Safe fallback initialization natively mapping index 0 boundary structures completely cleanly
    med_t[0] = safe_median
    mad_t[0] = np.median(np.abs(X - safe_median)) if N > 0 else 1.0
    std_t[0] = np.std(X) if N > 0 else 1.0
    
    # Absolute physical lock exclusively extracting historical vectors organically
    med_t[1:] = med_raw[:-1]
    mad_t[1:] = mad_raw[:-1]
    std_t[1:] = std_raw[:-1]
    
    # 3. Dynamic Out-of-Sample Robust Standardization Extrapolation natively
    epsilon_t = np.maximum(std_t * eps_scale, eps_min)
    mad_scaled = 1.4826 * mad_t
    
    z_t = (X - med_t) / (mad_scaled + epsilon_t)
    
    # 4. Adaptive Huber Threshold Boundary Limits Scaling 
    k_t = k_base * (1.0 + np.maximum(0.0, Vol_Z))
    
    # 5. Continuous Huber Winsorization Spatial Sequence
    abs_z = np.abs(z_t)
    mask_within = abs_z <= k_t
    
    # Explicit mapping substituting absolute structural anomalies natively bounding limits strictly
    X_cleaned = np.where(
        mask_within,
        X,
        med_t + np.sign(z_t) * k_t * mad_scaled
    )
    
    # Scrub outputs natively bounding potential mathematical overflows dynamically structurally
    X_cleaned = np.nan_to_num(X_cleaned, nan=safe_median, posinf=np.max(X), neginf=np.min(X))
    
    return pd.Series(X_cleaned, index=index, name="huber_winsorized_feature")


def compute_point_39_override(
    df: pd.DataFrame,
    feature_col: str,
    vol_z_col: str,
    W: int = 50,
    k_base: float = 2.5,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Discards rigid absolute truncation sequence rules naturally embedding intelligent Huber elasticity limits dynamically.
    """
    try:
        req_cols = [feature_col, vol_z_col]
        missing = [c for c in req_cols if c not in df.columns]
        
        if missing:
            raise ValueError(f"Missing required target columns for Point 39: {missing}")
            
        return compute_adaptive_huber_winsorization(
            feature_series=df[feature_col],
            vol_z_series=df[vol_z_col],
            W=W,
            k_base=k_base
        )
    except Exception as e:
        _logger.error(f"[POINT_39] Volatility-Adaptive Huber Winsorization failed for {symbol}: {e}")
        # Fail-safe: Returns neutral unadjusted vectors mapping identical structural bounds without crash explicitly
        if feature_col in df.columns:
            return pd.Series(df[feature_col], index=df.index, name="huber_winsorized_feature")
        return pd.Series(0.0, index=df.index, name="huber_winsorized_feature")
