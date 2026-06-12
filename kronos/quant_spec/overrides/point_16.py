"""
Point 16: Volume-at-Price Fixed Discretization Bias - Gaussian Kernel Density Estimation (KDE)
(Vectorized Implementation)

Replaces rigid linear volume profile buckets with a mathematically convergent 
Gaussian Kernel Density Estimation (KDE) Volume Profiling engine. Safely models 
continuous volume density nodes globally without bin-size scaling distortions.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_16")


def compute_gaussian_kde_volume_profile(
    close: Union[pd.Series, np.ndarray],
    volume: Union[pd.Series, np.ndarray],
    P_target: Optional[Union[pd.Series, np.ndarray]] = None,
    N: int = 100,
    h: float = 0.05
) -> pd.Series:
    """
    Computes continuous Gaussian KDE volume densities natively via multi-dimensional broadcasting.
    
    MATHEMATICAL SPECIFICATION:
    1. f(P) = (1 / (N * h)) * sum_{i=1}^{N} ( V_i * exp(-0.5 * ((P - C_i) / h)^2) )
    2. N represents the sliding sample size count (lookback window).
    3. Fully vectorized [Time_T, Lookback_N] array broadcasting avoids procedural loops.
    
    Parameters
    ----------
    close : array-like
        Historical Close prices array (C_i).
    volume : array-like
        Historical Base Volumes array (V_i).
    P_target : array-like, optional
        Target price levels to evaluate the density surface. Defaults to evaluating 
        the density precisely at the current close price (C_t).
    N : int
        Lookback window length / sample size constraint.
    h : float
        Localized smoothing bandwidth parameter.
        
    Returns
    -------
    pd.Series
        Continuous 1D feature vector representing the volume node density at P_target.
    """
    is_series = isinstance(close, pd.Series)
    index = close.index if is_series else None
    
    C = np.asarray(close, dtype=float)
    V = np.asarray(volume, dtype=float)
    T = len(C)
    
    # Default target evaluation plane is the current bar's close price
    if P_target is None:
        P = C.copy()
    else:
        P = np.asarray(P_target, dtype=float)
        
    if T == 0:
        return pd.Series(dtype=float, index=index, name="kde_volume_density")
        
    # 1. Isolate the Historical Matrix [Time_T, Lookback_N] natively
    # To evaluate rolling N-period KDE surfaces for each time t, we pad the leading edge
    # to maintain strict array alignment and stride the historical arrays.
    
    # Prevent division-by-zero or negative bandwidth collapses
    h_safe = max(h, 1e-8)
    
    # Initial warm-up padding (fallback to the first element to lock scale)
    C_padded = np.pad(C, (N - 1, 0), mode='edge')
    V_padded = np.pad(V, (N - 1, 0), mode='constant', constant_values=0.0)
    
    # Extract sliding [Time_T, Lookback_N] contiguous memory blocks directly in C
    C_hist = np.lib.stride_tricks.sliding_window_view(C_padded, window_shape=N)
    V_hist = np.lib.stride_tricks.sliding_window_view(V_padded, window_shape=N)
    
    # 2. Vectorized Gaussian Kernel Evaluation
    # Align P vector to broadcast against the Lookback_N axis: shape transforms to (T, 1)
    P_expanded = P[:, np.newaxis]
    
    # Z-Score the distance offset natively across the continuous surface
    z_dist = (P_expanded - C_hist) / h_safe
    
    # Gaussian kernel weight mapping (exponential decay)
    kernel_weights = np.exp(-0.5 * (z_dist ** 2))
    
    # 3. Apply the Base Volume Density Scaling
    # Matches: V_i * exp(...)
    weighted_volumes = V_hist * kernel_weights
    
    # 4. Collapse the Surface via Exact Mathematical Architecture
    # f(P) = (1 / (N * h)) * sum_{i=1}^{N} (...)
    kde_density_surface = (1.0 / (N * h_safe)) * np.sum(weighted_volumes, axis=1)
    
    # Scrub outputs securely for safety
    kde_density_surface = np.nan_to_num(kde_density_surface, nan=0.0, posinf=0.0, neginf=0.0)
    
    return pd.Series(kde_density_surface, index=index, name="kde_volume_density")


def compute_point_16_override(
    df: pd.DataFrame,
    N_lookback: int = 100,
    bandwidth_h: float = 0.05,
    volume_col: str = "volume",
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Erases fixed discretization proxies and models the true KDE profile density.
    """
    try:
        req_cols = ["close", volume_col]
        missing = [c for c in req_cols if c not in df.columns]
        
        if missing:
            raise ValueError(f"Missing required columns for Point 16: {missing}")
            
        return compute_gaussian_kde_volume_profile(
            close=df["close"],
            volume=df[volume_col],
            N=N_lookback,
            h=bandwidth_h
        )
    except Exception as e:
        _logger.error(f"[POINT_16] Gaussian KDE Profiling failed for {symbol}: {e}")
        # Fail-safe: Return a zeroed density curve
        return pd.Series(0.0, index=df.index, name="kde_volume_density")
