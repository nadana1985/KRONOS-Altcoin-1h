"""
Point 03: Spatial Dimension Inflation Bias - SVD-Based Orthogonal Bottleneck Compression
(Vectorized & Scalar Hardened Implementation)
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any, Dict

import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_svd_bottleneck_compression

_logger = logging.getLogger("kronos.bias_override.point_03")

_DEFAULT_CONFIG = {
    "n_components": 3,
    "noise_std": 0.01,
    "min_data_density": 300
}


def _load_point_03_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_03", engine)
    return cfg if cfg else _DEFAULT_CONFIG


def compute_orthogonal_bottleneck_compression(
    X: Union[pd.DataFrame, np.ndarray],
    W: int = 100,
    k: int = 3,
) -> Union[pd.DataFrame, np.ndarray]:
    """
    Computes a strict out-of-sample SVD orthogonal projection to eliminate spatial dimension inflation.
    """
    is_df = isinstance(X, pd.DataFrame)
    X_arr = X.to_numpy() if is_df else np.asarray(X, dtype=float)
    
    N, D = X_arr.shape
    
    if k > D:
        k = D
        
    X_ortho = np.full((N, k), np.nan)
    
    if N <= W:
        if is_df:
            cols = [f"ortho_pc_{i+1}" for i in range(k)]
            return pd.DataFrame(X_ortho, index=X.index, columns=cols)
        return X_ortho
        
    windows_raw = np.lib.stride_tricks.sliding_window_view(X_arr, window_shape=W, axis=0)
    windows = np.swapaxes(windows_raw, 1, 2)
    hist_windows = windows[:-1]
    
    mean_w = np.mean(hist_windows, axis=1, keepdims=True)
    centered_w = hist_windows - mean_w
    
    std_w = np.std(centered_w, axis=1, keepdims=True) + 1e-12
    scaled_w = centered_w / std_w
    
    try:
        U, S, Vh = np.linalg.svd(scaled_w, full_matrices=False)
    except np.linalg.LinAlgError as e:
        _logger.error(f"[POINT_03] Batch SVD failed to converge: {e}.")
        if is_df:
            cols = [f"ortho_pc_{i+1}" for i in range(k)]
            return pd.DataFrame(X_ortho, index=X.index, columns=cols)
        return X_ortho

    V = np.swapaxes(Vh, 1, 2)
    W_L = V[:, :, :k]
    
    X_t = X_arr[W:]
    mean_t = mean_w[:, 0, :]
    std_t = std_w[:, 0, :]
    
    X_t_scaled = (X_t - mean_t) / std_t
    X_ortho_t = np.einsum('md,mdk->mk', X_t_scaled, W_L)
    
    X_ortho[W:] = X_ortho_t
    
    if is_df:
        cols = [f"ortho_pc_{i+1}" for i in range(k)]
        return pd.DataFrame(X_ortho, index=X.index, columns=cols)
        
    return X_ortho


def compute_point_03_override(
    neural_vector: Optional[np.ndarray] = None,
    target_rank: Optional[int] = None,
    engine: Optional[Any] = None,
    df: Optional[pd.DataFrame] = None,
    symbol: str = '',
    X_matrix: Optional[Union[pd.DataFrame, np.ndarray]] = None,
    W: int = 100,
    k: int = 3,
    *args,
    **kwargs
) -> Union[pd.DataFrame, np.ndarray]:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Accepts both:
    1. neural_vector, target_rank, engine, df, symbol (scalar vector compression)
    2. X_matrix, W, k, engine, symbol (vectorized matrix compression)
    """
    X = neural_vector if neural_vector is not None else X_matrix
    rank = target_rank if target_rank is not None else k
    
    if X is None:
        return np.array([])
        
    try:
        if isinstance(X, np.ndarray) and X.ndim <= 2 and not isinstance(X_matrix, pd.DataFrame):
            # Scalar vector compression path
            matrix = X if X.ndim == 2 else X.reshape(1, -1)
            cfg = _load_point_03_config(engine)
            n_comp = rank if rank is not None else cfg.get("n_components", 3)
            
            res = compute_svd_bottleneck_compression(matrix, n_comp, cfg.get("noise_std", 0.01))
            if "compressed" in res:
                compressed = res["compressed"]
                override_val = compressed.flatten() if X.ndim == 1 else compressed
            else:
                override_val = X
                
            if engine is not None:
                return engine.apply_override(point_id="03", raw_value=X, override_value=override_val, df=df, symbol=symbol)
            return override_val
            
        # Matrix vectorized compression path
        return compute_orthogonal_bottleneck_compression(X, W=W, k=rank if rank is not None else 3)
    except Exception as e:
        _logger.error(f"[POINT_03] Orthogonal bottleneck compression failed: {e}")
        return X