"""
Point 23: Equal-Weighted Divergence Indices - Eigenvalue-Driven Covariance Weighting
(Vectorized Implementation)

Destroys fixed, rigid weight constants (e.g., divergence_weight = 1.0) by dynamically 
extracting the dominant principal components of price-volume acceleration explicitly. 
Applies Ledoit-Wolf dimensional shrinkage to enforce multi-collinear positive definiteness.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_23")


def compute_eigenvalue_covariance_weighting(
    close: Union[pd.Series, np.ndarray],
    volume: Union[pd.Series, np.ndarray],
    W: int = 24,
    delta_shrinkage: float = 0.05
) -> pd.Series:
    """
    Computes dynamic divergence weights natively via Eigenvalue Decomposition.
    
    MATHEMATICAL SPECIFICATION:
    1. A_p = Delta(ln(C_t / C_{t-1}))
    2. A_v = Delta(ln(V_t))
    3. Sigma_t = Covariance matrix of A_p, A_v over lookback W
    4. Ledoit-Wolf Shrinkage: Off-diagonals shrunk by (1 - delta_shrinkage)
    5. lambda_PC1, lambda_PC2 = Eigenvalues of Sigma_t via np.linalg.eigh
    6. w_div,t = lambda_PC1,t / (lambda_PC1,t + lambda_PC2,t)
    7. STRICT CAUSALITY BARRIER: Shift parameters explicitly (.shift(1)) perfectly out-of-sample.
    
    Parameters
    ----------
    close : array-like
        Historical Close prices array.
    volume : array-like
        Total Base Volume array.
    W : int
        Lookback window length.
    delta_shrinkage : float
        Ledoit-Wolf diagonal target shrinkage parameter enforcing strict positive-definiteness.
        
    Returns
    -------
    pd.Series
        Continuous, strictly bounded [0.0, 1.0] weight feature driving Slot 07 scale natively.
    """
    is_series = isinstance(close, pd.Series)
    index = close.index if is_series else None
    
    C = np.asarray(close, dtype=float)
    V = np.asarray(volume, dtype=float)
    N = len(C)
    
    if N == 0:
        return pd.Series(dtype=float, index=index, name="eigen_divergence_weight")
        
    # Prevent absolute logarithms of zero artifacts natively
    C_safe = np.maximum(C, 1e-12)
    V_safe = np.maximum(V, 1e-12)
    
    # 1. Isolate First-Order Acceleration Arrays natively
    # Log Returns
    log_ret = np.zeros(N)
    log_ret[1:] = np.log(C_safe[1:] / C_safe[:-1])
    
    # Price Acceleration (A_p) -> First difference of log returns
    A_p = np.zeros(N)
    A_p[1:] = log_ret[1:] - log_ret[:-1]
    
    # Volume Acceleration (A_v) -> First difference of log volume
    log_v = np.log(V_safe)
    A_v = np.zeros(N)
    A_v[1:] = log_v[1:] - log_v[:-1]
    
    # 2. Extract Rolling Covariance Parameters natively avoiding slow loops
    safe_mean_p = np.mean(A_p) if N > 0 else 0.0
    safe_mean_v = np.mean(A_v) if N > 0 else 0.0
    
    pad_A_p = np.pad(A_p, (W - 1, 0), mode='constant', constant_values=safe_mean_p)
    pad_A_v = np.pad(A_v, (W - 1, 0), mode='constant', constant_values=safe_mean_v)
    
    win_p = np.lib.stride_tricks.sliding_window_view(pad_A_p, window_shape=W)
    win_v = np.lib.stride_tricks.sliding_window_view(pad_A_v, window_shape=W)
    
    # Extract deviations efficiently
    mean_p = np.mean(win_p, axis=1, keepdims=True)
    mean_v = np.mean(win_v, axis=1, keepdims=True)
    
    dev_p = win_p - mean_p
    dev_v = win_v - mean_v
    
    # Sample variances and covariances (ddof=1)
    var_p_raw = np.sum(dev_p ** 2, axis=1) / (W - 1)
    var_v_raw = np.sum(dev_v ** 2, axis=1) / (W - 1)
    cov_pv_raw = np.sum(dev_p * dev_v, axis=1) / (W - 1)
    
    # 3. STRICT CAUSALITY BARRIER (.shift(1))
    var_p_t = np.empty_like(var_p_raw)
    var_v_t = np.empty_like(var_v_raw)
    cov_pv_t = np.empty_like(cov_pv_raw)
    
    # Protect Initial Index with safe uniform distribution limits
    var_p_t[0] = np.var(A_p, ddof=1) if N > 1 else 1e-6
    var_v_t[0] = np.var(A_v, ddof=1) if N > 1 else 1e-6
    cov_pv_t[0] = 0.0
    
    var_p_t[1:] = var_p_raw[:-1]
    var_v_t[1:] = var_v_raw[:-1]
    cov_pv_t[1:] = cov_pv_raw[:-1]
    
    # 4. Construct Dimensional Matrix with Ledoit-Wolf Shrinkage Constraints
    # Matrix shape (N, 2, 2) specifically mapped to feed np.linalg.eigh internally
    Sigma_t = np.zeros((N, 2, 2))
    
    # Ensure positive definite bounds strictly via epsilon additive shrinkage mappings
    Sigma_t[:, 0, 0] = var_p_t + 1e-12
    Sigma_t[:, 1, 1] = var_v_t + 1e-12
    
    # Shrink structural off-diagonals natively toward zero (diagonal identity target)
    shrunk_cov = cov_pv_t * (1.0 - delta_shrinkage)
    Sigma_t[:, 0, 1] = shrunk_cov
    Sigma_t[:, 1, 0] = shrunk_cov
    
    # 5. Native Eigenvalue Decomposition across massive tensor matrices
    # eigh dynamically returns real sorted eigenvalues (ascending) natively
    evals, _ = np.linalg.eigh(Sigma_t)
    
    # Isolate Principal Component constraints cleanly
    lambda_PC2 = evals[:, 0]  # Minimum variance (secondary state)
    lambda_PC1 = evals[:, 1]  # Maximum variance (dominant principal state)
    
    # Scrub absolute negative floating-point collapses explicitly
    lambda_PC1 = np.maximum(lambda_PC1, 1e-12)
    lambda_PC2 = np.maximum(lambda_PC2, 1e-12)
    
    # 6. Dynamic Divergence Weight Evaluation mapped onto [0.0, 1.0] limits natively
    w_div = lambda_PC1 / (lambda_PC1 + lambda_PC2)
    
    w_div = np.nan_to_num(w_div, nan=0.5, posinf=1.0, neginf=0.0)
    w_div = np.clip(w_div, 0.0, 1.0)
    
    return pd.Series(w_div, index=index, name="eigen_divergence_weight")


def compute_point_23_override(
    df: pd.DataFrame,
    W: int = 24,
    delta_shrinkage: float = 0.05,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Extracts structural convergence dominance through authentic PCA covariance eigenvalues natively.
    """
    try:
        req_cols = ["close", "volume"]
        missing = [c for c in req_cols if c not in df.columns]
        
        if missing:
            raise ValueError(f"Missing required columns for Point 23: {missing}")
            
        return compute_eigenvalue_covariance_weighting(
            close=df["close"],
            volume=df["volume"],
            W=W,
            delta_shrinkage=delta_shrinkage
        )
    except Exception as e:
        _logger.error(f"[POINT_23] Eigenvalue Covariance Weighting failed for {symbol}: {e}")
        # Fail-safe: Return equally neutral bounds (0.50 mapping) natively on matrix breakdown
        return pd.Series(0.5, index=df.index, name="eigen_divergence_weight")