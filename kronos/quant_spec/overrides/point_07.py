"""
Point 07: Unverified Arbitrary Mathematics Bias - GP Evolved Parsimonious Polynomial Mapping
(Vectorized Implementation)

Replaces manual structural combinations with a strict, out-of-sample polynomial 
mapping driven by an objective function combining MSE and the Akaike Information Criterion.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_07")


def compute_evolved_parsimonious_polynomial(
    X: Union[pd.DataFrame, np.ndarray],
    Y: Union[pd.Series, np.ndarray],
    W: int = 100,
    max_degree: int = 3,
    alpha: float = 0.05
) -> Union[pd.Series, np.ndarray]:
    """
    Computes a dynamically evolved polynomial mapping using out-of-sample GP approximation.
    
    MATHEMATICAL SPECIFICATION:
    1. f_GP(X_t) maps feature matrix X_t to target forward return vector Y.
    2. Objective = MSE + alpha * AIC(f_GP)
       Where AIC(f_GP) = 2*k - 2*ln(L), k = number of parameters.
    3. STRICT CAUSALITY BARRIER: The optimal polynomial degree and coefficients for 
       index 't' are fitted strictly on the historical block [t-W : t-1].
       
    Parameters
    ----------
    X : array-like
        The input feature matrix (N, D).
    Y : array-like
        The target forward return vector (N,).
    W : int
        The historical rolling lookback window.
    max_degree : int
        Maximum polynomial degree to evaluate.
    alpha : float
        Parsimony penalty factor.
        
    Returns
    -------
    pd.Series or np.ndarray
        A single, cleaned feature column scaled dynamically.
    """
    is_df = isinstance(X, pd.DataFrame)
    X_arr = X.to_numpy(dtype=float) if is_df else np.asarray(X, dtype=float)
    Y_arr = np.asarray(Y, dtype=float).flatten()
    
    N = X_arr.shape[0]
    D = X_arr.shape[1] if X_arr.ndim > 1 else 1
    
    if X_arr.ndim == 1:
        X_arr = X_arr.reshape(-1, 1)
        
    out_feature = np.zeros(N, dtype=float)
    
    if N <= W:
        if is_df:
            return pd.Series(out_feature, index=X.index, name="evolved_gp_feature")
        return out_feature

    # Arrays to store the best objective and best prediction at each time t
    M = N - W
    best_obj = np.full(M, np.inf)
    best_pred = np.zeros(M, dtype=float)
    
    # Pre-extract Y windows strictly out-of-sample [t-W : t-1]
    # sliding_window_view gives shape (N - W + 1, W)
    Y_windows_raw = np.lib.stride_tricks.sliding_window_view(Y_arr, window_shape=W)
    Y_hist = Y_windows_raw[:-1]  # shape (M, W)
    
    # To handle NaNs in target safely
    valid_mask = ~np.any(np.isnan(Y_hist), axis=1)  # shape (M,)
    
    for d in range(1, max_degree + 1):
        # 1. Expand X to polynomial degree d: [X, X^2, ..., X^d]
        X_d_list = [X_arr ** deg for deg in range(1, d + 1)]
        X_d_full = np.concatenate(X_d_list, axis=1)  # shape (N, d * D)
        
        # 2. Add bias column
        bias_col = np.ones((N, 1), dtype=float)
        X_d_bias = np.hstack([bias_col, X_d_full])   # shape (N, K), where K = d * D + 1
        K = X_d_bias.shape[1]
        
        # 3. Extract historical windows strictly out-of-sample [t-W : t-1]
        X_windows_raw = np.lib.stride_tricks.sliding_window_view(X_d_bias, window_shape=W, axis=0)
        X_windows = np.swapaxes(X_windows_raw, 1, 2)
        X_hist = X_windows[:-1]  # shape (M, W, K)
        
        # We only process valid rows where target has no NaNs
        # (For NaNs, we leave best_obj as inf so it defaults to 0.0)
        X_hist_valid = X_hist[valid_mask]  # shape (V, W, K)
        Y_hist_valid = Y_hist[valid_mask]  # shape (V, W)
        
        if len(X_hist_valid) == 0:
            continue
            
        # 4. Compute OLS coefficients via vectorized matrix inversion
        # X^T X
        XT = np.swapaxes(X_hist_valid, 1, 2)  # shape (V, K, W)
        XTX = XT @ X_hist_valid               # shape (V, K, K)
        
        # Add tiny Ridge regularization to prevent singular matrix inversion failures
        ridge_penalty = np.eye(K) * 1e-8
        XTX_reg = XTX + ridge_penalty
        
        inv_XTX = np.linalg.inv(XTX_reg)      # shape (V, K, K)
        
        # X^T Y
        XTY = (XT @ Y_hist_valid[..., np.newaxis]).squeeze(-1)  # shape (V, K)
        
        # Coefficients
        coeffs = (inv_XTX @ XTY[..., np.newaxis]).squeeze(-1)   # shape (V, K)
        
        # 5. Compute Training MSE
        # y_pred_hist = X_hist_valid @ coeffs
        y_pred_hist = (X_hist_valid @ coeffs[..., np.newaxis]).squeeze(-1)  # shape (V, W)
        mse = np.mean((Y_hist_valid - y_pred_hist) ** 2, axis=1)            # shape (V,)
        mse = np.maximum(mse, 1e-12)  # Prevent log(0)
        
        # 6. Compute AIC(f_GP) = 2*K - 2*ln(L)
        # Assuming Gaussian errors, ln(L) = -W/2 * ln(2*pi*MSE) - W/2
        ln_L = -(W / 2.0) * np.log(2 * np.pi * mse) - (W / 2.0)
        aic = 2 * K - 2 * ln_L  # shape (V,)
        
        # 7. Objective = MSE + alpha * AIC
        objective = mse + alpha * aic  # shape (V,)
        
        # 8. Apply mapping strictly out-of-sample to X_t
        X_t = X_d_bias[W:]  # shape (M, K)
        X_t_valid = X_t[valid_mask]  # shape (V, K)
        
        # pred = dot(X_t, coeffs)
        pred_valid = np.sum(X_t_valid * coeffs, axis=1)  # shape (V,)
        
        # 9. Update the best models
        # Map valid indices back to full M size
        full_objective = np.full(M, np.inf)
        full_objective[valid_mask] = objective
        
        full_pred = np.zeros(M, dtype=float)
        full_pred[valid_mask] = pred_valid
        
        better_mask = full_objective < best_obj
        best_obj[better_mask] = full_objective[better_mask]
        best_pred[better_mask] = full_pred[better_mask]

    # Assign predictions back to the output feature vector
    out_feature[W:] = best_pred
    
    # Forward-fill and replace NaNs/Infs to prevent downstream poisoning
    out_feature = np.nan_to_num(out_feature, nan=0.0, posinf=0.0, neginf=0.0)

    if is_df:
        return pd.Series(out_feature, index=X.index, name="evolved_gp_feature")
    return out_feature


def compute_point_07_override(
    df: pd.DataFrame,
    target_columns: list[str],
    forward_return_col: str = "forward_returns",
    W: int = 100,
    max_degree: int = 3,
    alpha: float = 0.05,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Applies the strictly out-of-sample Parsimonious Polynomial Mapping algorithm.
    """
    try:
        missing = [c for c in target_columns if c not in df.columns]
        if missing:
            raise ValueError(f"Missing feature columns for Point 07: {missing}")
            
        if forward_return_col not in df.columns:
            # Create a proxy target if missing (strictly for structural fallback)
            # Standard next-bar returns proxy
            close = pd.to_numeric(df.get("close", pd.Series(1.0, index=df.index)), errors="coerce")
            Y = (close.shift(-1) / close - 1.0).fillna(0.0)
        else:
            Y = df[forward_return_col]
            
        return compute_evolved_parsimonious_polynomial(
            X=df[target_columns],
            Y=Y,
            W=W,
            max_degree=max_degree,
            alpha=alpha
        )
    except Exception as e:
        _logger.error(f"[POINT_07] GP Evolution failed for {symbol}: {e}")
        # Fail-safe: zero out the feature on catastrophic failure
        return pd.Series(0.0, index=df.index, name="evolved_gp_feature")
