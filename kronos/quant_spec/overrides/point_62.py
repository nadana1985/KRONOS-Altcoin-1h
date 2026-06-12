"""
Point 62: Stationary Covariance Matrices - Ledoit-Wolf Shrinkage Covariance Estimation
(Sovereign Hardened Implementation)
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any, Union
import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

_logger = logging.getLogger("kronos.bias_override.point_62")

_DEFAULT_CONFIG = {
    "min_data_density": 50,
    "fallback_shrinkage": 0.1
}


def _load_point_62_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_62", engine)
    return cfg if cfg else _DEFAULT_CONFIG


def compute_ledoit_wolf_shrinkage(X: np.ndarray) -> np.ndarray:
    """
    Sovereign manual implementation of Ledoit-Wolf shrinkage covariance estimation.
    """
    n, p = X.shape
    if n <= 1 or p == 0:
        return np.eye(p)
        
    X_centered = X - np.mean(X, axis=0)
    S = (X_centered.T @ X_centered) / (n - 1)
    
    mean_var = np.mean(np.diag(S))
    F = mean_var * np.eye(p)
    
    tr_S = np.trace(S)
    tr_S2 = np.trace(S @ S)
    
    num = (1.0 - 2.0 / p) * tr_S2 + tr_S**2
    den = (n + 1.0 - 2.0 / p) * (tr_S2 - (tr_S**2) / p)
    
    if den <= 0:
        delta = 1.0
    else:
        delta = float(np.clip(num / den, 0.0, 1.0))
        
    Sigma_shrunk = delta * F + (1.0 - delta) * S
    return Sigma_shrunk


def compute_point_62_override(
    sample_cov: np.ndarray,
    returns_matrix: Optional[np.ndarray] = None,
    engine: Optional[BiasOverrideEngine] = None,
    df: Optional[pd.DataFrame] = None,
    symbol: str = ''
) -> np.ndarray:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    """
    try:
        cfg = _load_point_62_config(engine)
        
        override_val = sample_cov
        if returns_matrix is not None and len(returns_matrix) >= cfg.get("min_data_density", 50):
            override_val = compute_ledoit_wolf_shrinkage(returns_matrix)
        else:
            p = sample_cov.shape[0]
            mean_var = np.mean(np.diag(sample_cov)) if p > 0 else 1.0
            F = mean_var * np.eye(p)
            fb_s = float(cfg.get("fallback_shrinkage", 0.1))
            override_val = fb_s * F + (1.0 - fb_s) * sample_cov
            
        if engine is not None:
            status = engine.registry.get_point_status("62")
            if status in ["implemented", "validated", "active", "backtest_only"]:
                return engine.apply_override(
                    point_id="62",
                    raw_value=sample_cov,
                    override_value=override_val,
                    df=df,
                    symbol=symbol
                )
        return override_val
    except Exception as e:
        _logger.error(f"[POINT_62] Ledoit-Wolf Shrinkage Covariance failed: {e}")
        return sample_cov
