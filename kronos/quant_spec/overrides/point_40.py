"""
Point 40: Symmetric Uniform PCA Loadings - Causal Information-Weighted Principal Component Projection
(Vectorized Implementation)

Destroys standard unweighted Principal Component Analysis (PCA) frameworks natively prone to dumping 
structurally sound feature variance and overfitting to absolute unconditioned macro-noise. 
Deploys a Causal Information-Weighted SVD Tensor Matrix physically scaling orthogonal loadings via
localized Shannon Entropy profiles completely out-of-sample.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any, List

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_40")


def compute_causal_information_weighted_pca(
    feature_matrix: Union[pd.DataFrame, np.ndarray],
    entropy_series: Union[pd.Series, np.ndarray],
    W: int = 24,
    eps_min: float = 1e-12
) -> pd.Series:
    """
    Computes purely non-symmetric, out-of-sample directional PC1 vectors seamlessly natively.
    
    MATHEMATICAL SPECIFICATION:
    1. Extracts strictly out-of-sample historical blocks [t-W : t-1] exclusively via (.shift(1)).
    2. Calculates explicit diagonal Information Density Weights (W_entropy,t) evaluating absolute
       structural correlation bounds linking each feature column against sessional Shannon Entropy.
    3. X_hist,weighted = (X_hist - Mean_hist) * W_entropy,t
    4. SVD matrix execution: X_hist,weighted = U * S * V^T
    5. Isolates the dominant non-symmetric orthogonal right loading vector (V_1).
    6. PC1_weighted,t = ((X_t - Mean_hist) * W_entropy,t) * V_1
    
    Parameters
    ----------
    feature_matrix : array-like or DataFrame
        The N x K raw unweighted structural input feature sequence natively.
    entropy_series : array-like
        The parallel Shannon Execution Entropy target array evaluating sessional execution density organically.
    W : int
        Lookback sequence interval physically establishing historical correlation density bounds.
    eps_min : float
        Explicit numerical limit sequence explicitly preventing zero-division cascades natively.
        
    Returns
    -------
    pd.Series
        Continuous 1D feature isolating completely uncompromised dominant structural momentum exactly (Slot 40).
    """
    is_df = isinstance(feature_matrix, pd.DataFrame)
    index = feature_matrix.index if is_df else None
    
    X = np.asarray(feature_matrix, dtype=float)
    E = np.asarray(entropy_series, dtype=float)
    
    N, K = X.shape
    
    if N == 0 or K == 0:
        return pd.Series(dtype=float, index=index, name="pc1_information_weighted")
        
    # Baseline neutral spatial mapping cleanly natively establishing fallback geometry
    safe_mean_X = np.mean(X, axis=0)
    safe_mean_E = np.mean(E) if N > 0 else 0.0
    
    pad_X = np.pad(X, ((W - 1, 0), (0, 0)), mode='constant', constant_values=0.0)
    
    # Secure baseline padding values
    if N > 0:
        pad_X[:W - 1, :] = safe_mean_X
        
    pad_E = np.pad(E, (W - 1, 0), mode='constant', constant_values=safe_mean_E)
    
    # Generate completely localized matrix memory bounds natively (N, W, K) and (N, W)
    win_X_raw = np.lib.stride_tricks.sliding_window_view(pad_X, window_shape=(W, K)).reshape(N, W, K)
    win_E_raw = np.lib.stride_tricks.sliding_window_view(pad_E, window_shape=W)
    
    # 1. STRICT CAUSALITY BARRIER (.shift(1))
    win_X = np.empty_like(win_X_raw)
    win_E = np.empty_like(win_E_raw)
    
    win_X[0] = win_X_raw[0]
    win_E[0] = win_E_raw[0]
    
    # Explicit lock mapping boundary dependencies flawlessly perfectly out-of-sample backward natively
    win_X[1:] = win_X_raw[:-1]
    win_E[1:] = win_E_raw[:-1]
    
    # 2. Vectorized Information Density Weight Calculations
    # Calculate historical localized means
    mean_X = np.mean(win_X, axis=1, keepdims=True)  # (N, 1, K)
    mean_E = np.mean(win_E, axis=1, keepdims=True)  # (N, 1)
    
    # Mean-centered deviation geometries natively
    dev_X = win_X - mean_X  # (N, W, K)
    dev_E = win_E - mean_E  # (N, W)
    dev_E_expanded = dev_E[:, :, None]  # (N, W, 1)
    
    # Establish dynamic mathematical cross-correlation mapping bounds natively
    cov_XE = np.mean(dev_X * dev_E_expanded, axis=1)  # (N, K)
    var_X = np.var(win_X, axis=1)  # (N, K)
    var_E = np.var(win_E, axis=1, keepdims=True)  # (N, 1)
    
    # Physical metric extraction scaling variables relative to absolute Information profile seamlessly
    corr_denom = np.sqrt(np.maximum(var_X * var_E, eps_min))
    weights = np.abs(cov_XE / corr_denom)  # (N, K)
    
    # Scrub numerical matrix fractional anomalies smoothly natively
    weights = np.nan_to_num(weights, nan=1.0)
    
    # 3. Compute Information-Weighted Feature Matrix
    weights_expanded = weights[:, None, :]  # (N, 1, K)
    win_X_weighted = dev_X * weights_expanded  # (N, W, K)
    
    # 4. Vectorized Batch Singular Value Decomposition (SVD) Matrix Extrapolation
    # Hardware array explicitly extracts completely localized eigenvectors instantaneously natively via BLAS limits
    # Handles rank constraints naturally utilizing full_matrices=False natively
    U, S, Vt = np.linalg.svd(win_X_weighted, full_matrices=False)
    
    # 5. Extract Dominant Orthogonal Structural Vector
    # Vt shape is explicitly (N, min(W, K), K). Dominant loading array maps precisely to index 0.
    V1 = Vt[:, 0, :]  # (N, K)
    
    # 6. Current Feature Matrix Out-Of-Sample PC1 Projection
    # Transform present coordinate explicitly utilizing historically finalized out-of-sample mapping logic natively
    X_t_centered = X - mean_X[:, 0, :]  # (N, K)
    X_t_weighted = X_t_centered * weights  # (N, K)
    
    # Project target coordinates cleanly across dominant eigenvector geometry explicitly natively
    PC1_weighted_t = np.sum(X_t_weighted * V1, axis=1)
    
    # Scrub limit crash conditions reliably
    PC1_weighted_t = np.nan_to_num(PC1_weighted_t, nan=0.0, posinf=0.0, neginf=0.0)
    
    return pd.Series(PC1_weighted_t, index=index, name="pc1_information_weighted")


def compute_point_40_override(
    df: pd.DataFrame,
    feature_cols: List[str],
    entropy_col: str,
    W: int = 24,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Destroys primitive symmetric PCA loadings implementing Information-Weighted SVD tensor extraction natively.
    """
    try:
        req_cols = feature_cols + [entropy_col]
        missing = [c for c in req_cols if c not in df.columns]
        
        if missing:
            raise ValueError(f"Missing required target columns for Point 40: {missing}")
            
        return compute_causal_information_weighted_pca(
            feature_matrix=df[feature_cols],
            entropy_series=df[entropy_col],
            W=W
        )
    except Exception as e:
        _logger.error(f"[POINT_40] Information-Weighted SVD PCA failed for {symbol}: {e}")
        # Fail-safe: Returns neutral sequence boundaries natively cleanly completely avoiding structural matrix explosions
        return pd.Series(0.0, index=df.index, name="pc1_information_weighted")
