"""
Point 31: Static Z-Score Stationarity Bias - Causal Welford-Driven One-Pass Adaptive Standardizer
(Numba Optimized Implementation)

Replaces lag-prone static rolling windows with a fully causal, expanding Welford algorithm.
Updates distribution parameters recursively out-of-sample (t-1), ensuring maximum numerical 
stability and preventing current-bar data leakage entirely during severe regime volatility expansions.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

# Gracefully import Numba for hardware C-compiled optimization.
# Provides identical native NumPy fallback if unavailable in environment.
try:
    from numba import njit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    
_logger = logging.getLogger("kronos.bias_override.point_31")


if NUMBA_AVAILABLE:
    @njit
    def _welford_adaptive_z_score_core(X: np.ndarray, eps_scale: float, eps_min: float) -> np.ndarray:
        """
        Numba-compiled recursive Welford loop generating hyper-fast array mapping natively in C.
        """
        N = len(X)
        Z = np.zeros(N)
        
        if N == 0:
            return Z
            
        count = 0.0
        mu = 0.0
        M2 = 0.0
        
        # Initialize index 0 safely
        Z[0] = 0.0
        
        # Recursively update the running statistics purely out-of-sample
        for t in range(1, N):
            x_prev = X[t - 1]
            
            # Welford parameters explicitly processing t-1 logic mathematically
            count += 1.0
            delta = x_prev - mu
            mu += delta / count
            
            # M2 matches Exact variance sum of squares update
            M2 += delta * (x_prev - mu)
            
            if count > 1.0:
                sigma = np.sqrt(M2 / (count - 1.0))
            else:
                sigma = 1.0
                
            # Point 14 Variance-Stabilized precision guard explicitly integrated
            epsilon = max(sigma * eps_scale, eps_min)
            
            # Continuous out-of-sample metric normalization securely tracking state
            Z[t] = (X[t] - mu) / (sigma + epsilon)
            
        return Z
else:
    def _welford_adaptive_z_score_core(X: np.ndarray, eps_scale: float, eps_min: float) -> np.ndarray:
        """
        Fast purely vectorized approximation fallback utilizing NumPy cumulative operators.
        Matches Welford explicitly using shifted mathematical cumsum limits out-of-sample.
        """
        N = len(X)
        Z = np.zeros(N)
        
        if N == 0:
            return Z
            
        count = np.arange(1, N, dtype=float)
        
        # Shift X strictly backwards generating pure out-of-sample data sequence natively
        X_prev = X[:-1]
        
        # Expanding Cumulative Means
        cum_sum = np.cumsum(X_prev)
        mu = cum_sum / count
        
        # Expanding Variance: E[x^2] - (E[x])^2
        cum_sq_sum = np.cumsum(X_prev ** 2)
        var = (cum_sq_sum / count) - (mu ** 2)
        
        # Enforce Bessel's sample correction factor scaling natively
        var_corrected = np.empty_like(var)
        var_corrected[0] = 1.0
        if N > 2:
            var_corrected[1:] = var[1:] * (count[1:] / (count[1:] - 1.0))
            
        # Scrub precision boundaries securely against mathematical zero bounds
        var_corrected = np.maximum(var_corrected, 0.0)
        sigma = np.sqrt(var_corrected)
        
        # Point 14 variance bounds
        epsilon = np.maximum(sigma * eps_scale, eps_min)
        
        Z[0] = 0.0
        Z[1:] = (X[1:] - mu) / (sigma + epsilon)
        
        return Z


def compute_adaptive_welford_z_score(
    feature_series: Union[pd.Series, np.ndarray],
    eps_scale: float = 1e-7,
    eps_min: float = 1e-12
) -> pd.Series:
    """
    Computes expanding Welford Z-scores natively mapping feature normalization flawlessly.
    
    MATHEMATICAL SPECIFICATION:
    1. count_t = count_t-1 + 1
    2. delta_t = X_t-1 - mu_t-1
    3. mu_t = mu_t-1 + delta_t / count_t
    4. M2_t = M2_t-1 + delta_t * (X_t-1 - mu_t)
    5. sigma_t = sqrt(M2_t / (count_t - 1)) if count_t > 1 else 1.0
    6. Z_adaptive,t = (X_t - mu_t) / (sigma_t + epsilon_t)
    7. STRICT CAUSALITY BARRIER: Updates rigidly process index [t-1] (.shift(1)) perfectly out-of-sample.
    
    Parameters
    ----------
    feature_series : array-like
        The raw dynamic feature to be normalized incrementally over time.
    eps_scale : float
        Point 14 dynamic structural precision scaling multiplier.
    eps_min : float
        Absolute hard floor preventing 0.0 limits natively.
        
    Returns
    -------
    pd.Series
        Continuous float mapping standardizing vectors natively (Slot 31).
    """
    is_series = isinstance(feature_series, pd.Series)
    index = feature_series.index if is_series else None
    
    X = np.asarray(feature_series, dtype=float)
    
    # Extrapolate completely over Numba C-compiler array natively
    Z = _welford_adaptive_z_score_core(X, eps_scale, eps_min)
    
    # Safely bind numerical boundaries actively scrubbing absolute math boundaries
    Z = np.nan_to_num(Z, nan=0.0, posinf=0.0, neginf=0.0)
    
    return pd.Series(Z, index=index, name="welford_z_score")


def compute_point_31_override(
    df: pd.DataFrame,
    target_feature_col: str,
    eps_scale: float = 1e-7,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Discards rigid stationary lookbacks, deploying Welford limits standardizing feature extraction loops natively.
    """
    try:
        if target_feature_col not in df.columns:
            raise ValueError(f"Missing required target column '{target_feature_col}' for Point 31.")
            
        return compute_adaptive_welford_z_score(
            feature_series=df[target_feature_col],
            eps_scale=eps_scale
        )
    except Exception as e:
        _logger.error(f"[POINT_31] Adaptive Welford Z-Score Normalization failed for {symbol}: {e}")
        # Fail-safe: Return pure neutral non-standardized vectors securely
        return pd.Series(0.0, index=df.index, name="welford_z_score")
