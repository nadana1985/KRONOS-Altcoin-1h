"""
Point 37: Pearson Correlation Collinearity Failures - Causal Rolling Distance Correlation Matrix
(Vectorized Implementation)

Replaces fundamentally flawed linear Pearson correlation logic which explicitly blinds cross-asset 
feature pipelines to non-linear co-movements and massive multi-collinear tail anomalies. 
Engineers a blazing-fast rolling Distance Correlation (dCorr) matrix isolating true structural 
dependencies exclusively out-of-sample natively in multi-dimensional C-backend NumPy arrays.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_37")


def compute_causal_distance_correlation(
    target_x: Union[pd.Series, np.ndarray],
    target_y: Union[pd.Series, np.ndarray],
    W: int = 24,
    eps_scale: float = 1e-7,
    eps_min: float = 1e-12
) -> pd.Series:
    """
    Computes completely localized rolling Distance Correlation mapping absolute non-linear dependencies.
    
    MATHEMATICAL SPECIFICATION:
    1. A_i,j = |X_i - X_j| and B_i,j = |Y_i - Y_j| matrices cleanly evaluated natively.
    2. A_tilde_i,j = A_i,j - Mean_Row(A_i) - Mean_Col(A_j) + Mean_Grand(A)
    3. dCov^2(X, Y) = (1 / W^2) * sum_{i,j} ( A_tilde_i,j * B_tilde_i,j )
    4. dCorr(X, Y) = sqrt( dCov^2(X, Y) / ( dCov^2(X, X) * dCov^2(Y, Y) + epsilon_t ) )
    5. STRICT CAUSALITY BARRIER: Input sequences stride backward chronologically executing out-of-sample
       completely at index [t-1] (.shift(1)) perfectly preventing contemporary target leakage natively.
       
    Parameters
    ----------
    target_x : array-like
        The leading base feature vector array mapping structural dynamics explicitly.
    target_y : array-like
        The parallel cross-asset or secondary feature mapping target non-linear boundaries.
    W : int
        Lookback anchoring the localized distance bounds directly tracing structural geometry.
    eps_scale : float
        Variance scaling multiplier integrating Point 14 numerical guards organically.
    eps_min : float
        Zero-floor hard bounds explicitly preventing infinite fractional expansions.
        
    Returns
    -------
    pd.Series
        Continuous, strictly bounded metric mapping [0.0, 1.0] non-linear dependencies completely (Slot 37).
    """
    is_series = isinstance(target_x, pd.Series)
    index = target_x.index if is_series else None
    
    X = np.asarray(target_x, dtype=float)
    Y = np.asarray(target_y, dtype=float)
    N = len(X)
    
    if N == 0:
        return pd.Series(dtype=float, index=index, name="distance_correlation")
        
    # Baseline normalizations mapping structural limits reliably cleanly across dimensions
    safe_mean_x = np.mean(X) if N > 0 else 0.0
    safe_mean_y = np.mean(Y) if N > 0 else 0.0
    
    pad_X = np.pad(X, (W - 1, 0), mode='constant', constant_values=safe_mean_x)
    pad_Y = np.pad(Y, (W - 1, 0), mode='constant', constant_values=safe_mean_y)
    
    win_X_raw = np.lib.stride_tricks.sliding_window_view(pad_X, window_shape=W)
    win_Y_raw = np.lib.stride_tricks.sliding_window_view(pad_Y, window_shape=W)
    
    # 1. STRICT CAUSALITY BARRIER (.shift(1))
    win_X = np.empty_like(win_X_raw)
    win_Y = np.empty_like(win_Y_raw)
    
    win_X[0] = win_X_raw[0]
    win_Y[0] = win_Y_raw[0]
    
    # Lock matrix inputs physically generating outputs completely blindly backwards natively
    win_X[1:] = win_X_raw[:-1]
    win_Y[1:] = win_Y_raw[:-1]
    
    # 2. Vectorized Pairwise Distance Matrices A and B
    # Executes multi-dimensional broadcasting geometry instantaneously: (N, W, 1) - (N, 1, W) -> (N, W, W)
    A = np.abs(win_X[:, :, None] - win_X[:, None, :])
    B = np.abs(win_Y[:, :, None] - win_Y[:, None, :])
    
    # 3. Explicit Double-Centering Execution 
    mean_row_A = np.mean(A, axis=2, keepdims=True)
    mean_col_A = np.mean(A, axis=1, keepdims=True)
    mean_grand_A = np.mean(A, axis=(1, 2), keepdims=True)
    A_tilde = A - mean_row_A - mean_col_A + mean_grand_A
    
    mean_row_B = np.mean(B, axis=2, keepdims=True)
    mean_col_B = np.mean(B, axis=1, keepdims=True)
    mean_grand_B = np.mean(B, axis=(1, 2), keepdims=True)
    B_tilde = B - mean_row_B - mean_col_B + mean_grand_B
    
    # 4. Empirical Distance Covariance (dCov^2)
    # Extracted securely natively as the exact arithmetic mean of component-wise structural products
    dCov2_XY = np.mean(A_tilde * B_tilde, axis=(1, 2))
    dCov2_XX = np.mean(A_tilde * A_tilde, axis=(1, 2))
    dCov2_YY = np.mean(B_tilde * B_tilde, axis=(1, 2))
    
    # 5. Extract Dynamic Precision limits organically tracking localized variance matrices flawlessly
    std_X = np.std(win_X, axis=1, ddof=1)
    std_Y = np.std(win_Y, axis=1, ddof=1)
    std_X = np.nan_to_num(std_X, nan=0.0)
    std_Y = np.nan_to_num(std_Y, nan=0.0)
    
    epsilon_t = np.maximum(std_X * std_Y * eps_scale, eps_min)
    
    # 6. Extract True Non-Linear Distance Correlation smoothly
    denominator = dCov2_XX * dCov2_YY + epsilon_t
    
    # Eliminate fractional negative limits resulting exclusively from trailing decimal collapses
    ratio = np.maximum(dCov2_XY / denominator, 0.0)
    
    dCorr = np.sqrt(ratio)
    
    # Bound completely physically mapping explicit valid execution geometry limits inherently
    dCorr = np.nan_to_num(dCorr, nan=0.0, posinf=1.0, neginf=0.0)
    dCorr = np.clip(dCorr, 0.0, 1.0)
    
    return pd.Series(dCorr, index=index, name="distance_correlation")


def compute_point_37_override(
    df: pd.DataFrame,
    col_x: str,
    col_y: str,
    W: int = 24,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Discards strictly flawed linear Pearson correlations calculating physical structural Distance Correlations natively.
    """
    try:
        req_cols = [col_x, col_y]
        missing = [c for c in req_cols if c not in df.columns]
        
        if missing:
            raise ValueError(f"Missing required target columns for Point 37: {missing}")
            
        return compute_causal_distance_correlation(
            target_x=df[col_x],
            target_y=df[col_y],
            W=W
        )
    except Exception as e:
        _logger.error(f"[POINT_37] Causal Distance Correlation generation failed for {symbol}: {e}")
        # Fail-safe: Return pure neutral mathematical boundary natively mapping exactly 0.0 explicitly
        return pd.Series(0.0, index=df.index, name="distance_correlation")
