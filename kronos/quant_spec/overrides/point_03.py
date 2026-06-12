"""
Point 03: Spatial Dimension Inflation Bias - SVD-Based Orthogonal Bottleneck Compression
(Vectorized Implementation)

Replaces naive dimension replication with rigorous SVD orthogonal projection.
Compresses the collinear spatial features down to their true mathematical rank
prior to clustering, enforcing a strict causality barrier.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_03")


def compute_orthogonal_bottleneck_compression(
    X: Union[pd.DataFrame, np.ndarray],
    W: int = 100,
    k: int = 3,
) -> Union[pd.DataFrame, np.ndarray]:
    """
    Computes a strict out-of-sample SVD orthogonal projection to eliminate spatial dimension inflation.
    
    MATHEMATICAL SPECIFICATION:
    1. Extracts strictly historical lookback windows from 't-W' to 't-1' to prevent lookahead leakage.
    2. Centers and scales the window matrix to prevent singular/static row failures.
    3. Computes the batch SVD: X_hist = U * S * V^T
    4. Isolates the right singular vectors (V) and truncates to rank 'k' to form the loading matrix W_L.
    5. Applies the projection exactly at time 't': X_ortho_t = X_t * W_L
    
    Parameters
    ----------
    X : pd.DataFrame or np.ndarray
        The highly correlated, artificially inflated spatial feature matrix (e.g., duplicate slots).
    W : int
        The rolling lookback window used to fit the SVD transformation.
    k : int
        The strict mathematical bottleneck rank to truncate the features down to.
        
    Returns
    -------
    pd.DataFrame or np.ndarray
        The compressed, strictly orthogonal feature matrix X_ortho of shape (N, k).
    """
    is_df = isinstance(X, pd.DataFrame)
    X_arr = X.to_numpy() if is_df else np.asarray(X, dtype=float)
    
    N, D = X_arr.shape
    
    # Cap bottleneck rank to available dimensions
    if k > D:
        k = D
        
    # Output array initialized with NaNs for warm-up period
    X_ortho = np.full((N, k), np.nan)
    
    if N <= W:
        if is_df:
            cols = [f"ortho_pc_{i+1}" for i in range(k)]
            return pd.DataFrame(X_ortho, index=X.index, columns=cols)
        return X_ortho
        
    # 1. Create fully vectorized rolling windows [t-W : t-1]
    # np.lib.stride_tricks.sliding_window_view gives shape (N - W + 1, D, W) when axis=0
    # We swap axes to get shape (N - W + 1, W, D) representing each historical window.
    windows_raw = np.lib.stride_tricks.sliding_window_view(X_arr, window_shape=W, axis=0)
    windows = np.swapaxes(windows_raw, 1, 2)
    
    # Isolate windows specifically ending at t-1.
    # windows[0] spans [0 : W-1] which is used to project X at t=W.
    # We omit the last window, since it would be used to project t=N (out of bounds).
    hist_windows = windows[:-1]  # shape: (N - W, W, D)
    
    # 2. Centering and low-variance numerical stabilization (precision scale)
    mean_w = np.mean(hist_windows, axis=1, keepdims=True)  # (N - W, 1, D)
    centered_w = hist_windows - mean_w
    
    std_w = np.std(centered_w, axis=1, keepdims=True) + 1e-12  # (N - W, 1, D)
    scaled_w = centered_w / std_w
    
    # 3. Compute Batch SVD over the historical matrices
    # X_hist = U * S * Vh (where Vh is V^T)
    # scaled_w shape is (M, W, D) -> U: (M, W, K), S: (M, K), Vh: (M, K, D) where K = min(W,D)
    try:
        U, S, Vh = np.linalg.svd(scaled_w, full_matrices=False)
    except np.linalg.LinAlgError as e:
        _logger.error(f"[POINT_03] Batch SVD failed to converge: {e}. Returning NaN projections.")
        if is_df:
            cols = [f"ortho_pc_{i+1}" for i in range(k)]
            return pd.DataFrame(X_ortho, index=X.index, columns=cols)
        return X_ortho

    # 4. Isolate the right singular vectors matrix V and establish loading matrix W_L
    # Vh is shape (M, min(W,D), D). Transposing the last two axes gives V shape (M, D, min(W,D)).
    V = np.swapaxes(Vh, 1, 2)
    
    # Truncate to the true mathematical rank 'k'
    W_L = V[:, :, :k]  # shape: (M, D, k)
    
    # 5. Compress the feature matrix at the current timestamp 't'
    X_t = X_arr[W:]  # shape: (N - W, D)
    
    # Apply the exact historical fit parameters to the out-of-sample vector 't'
    mean_t = mean_w[:, 0, :]  # shape: (N - W, D)
    std_t = std_w[:, 0, :]    # shape: (N - W, D)
    
    X_t_scaled = (X_t - mean_t) / std_t  # shape: (N - W, D)
    
    # X_ortho_t = X_t_scaled * W_L
    # Utilizing Einstein summation for optimized batch matrix multiplication
    X_ortho_t = np.einsum('md,mdk->mk', X_t_scaled, W_L)  # shape: (N - W, k)
    
    X_ortho[W:] = X_ortho_t
    
    if is_df:
        cols = [f"ortho_pc_{i+1}" for i in range(k)]
        return pd.DataFrame(X_ortho, index=X.index, columns=cols)
        
    return X_ortho


def compute_point_03_override(
    X_matrix: Union[pd.DataFrame, np.ndarray],
    W: int = 100,
    k: int = 3,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> Union[pd.DataFrame, np.ndarray]:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Ingests the high-dimensional spatial feature matrix and outputs its strictly orthogonal projection.
    """
    try:
        return compute_orthogonal_bottleneck_compression(X_matrix, W=W, k=k)
    except Exception as e:
        _logger.error(f"[POINT_03] Orthogonal bottleneck compression failed for {symbol}: {e}")
        
        # Return empty matrix on failure to prevent collinear poison
        is_df = isinstance(X_matrix, pd.DataFrame)
        N = len(X_matrix)
        X_fail = np.full((N, k), np.nan)
        if is_df:
            return pd.DataFrame(X_fail, index=X_matrix.index, columns=[f"ortho_pc_{i+1}" for i in range(k)])
        return X_fail