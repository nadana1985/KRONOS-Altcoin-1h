"""
Point 15: Symmetric Path-Risk Target Boundaries - Skewness-Weighted Asymmetric Barriers
(Vectorized Implementation)

Replaces identical symmetric stop-loss/take-profit bands with dynamically skewed 
boundaries adapting to asset-specific liquidation asymmetry and directional bias.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any, Tuple

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_15")


def compute_skewness_weighted_asymmetric_barriers(
    close: Union[pd.Series, np.ndarray],
    W: int = 100,
    phi: float = 2.0
) -> Tuple[pd.Series, pd.Series]:
    """
    Computes rolling dynamic Skewness-Weighted Asymmetric Barriers for Risk Management.
    
    MATHEMATICAL SPECIFICATION:
    1. sigma_t = Rolling standard deviation of log returns over W
    2. gamma_skew,t = Rolling Fisher skewness of log returns over W
    3. Barrier_upper = phi * sigma_t * (1.0 + gamma_skew,t)
    4. Barrier_lower = -phi * sigma_t * (1.0 - gamma_skew,t)
    5. STRICT CAUSALITY BARRIER: Rolling parameters are shifted exactly 1 bar forward.
       Upper barriers are strictly bounded to be positive; lower barriers bounded negative.
       
    Parameters
    ----------
    close : array-like
        The raw asset price array.
    W : int
        The rolling lookback window for volatility and skewness metrics.
    phi : float
        The entry baseline multiplier scalar for the risk bands.
        
    Returns
    -------
    Tuple[pd.Series, pd.Series]
        (Barrier_upper, Barrier_lower)
    """
    is_series = isinstance(close, pd.Series)
    index = close.index if is_series else None
    
    # Map to continuous floats to prevent native structural array failures
    C = np.asarray(close, dtype=float)
    N = len(C)
    
    if N == 0:
        empty = pd.Series(dtype=float, index=index)
        return empty, empty
        
    # 1. Compute Realized Log Returns
    log_ret = np.zeros(N, dtype=float)
    C_prev = np.maximum(C[:-1], 1e-12)
    C_curr = np.maximum(C[1:], 1e-12)
    log_ret[1:] = np.log(C_curr / C_prev)
    
    # 2. Extract Rolling Distribution Parameters natively via Pandas structures
    # Using Pandas rolling methods allows explicit and exact Fisher Skewness equations
    log_ret_s = pd.Series(log_ret)
    
    # 3. STRICT CAUSALITY BARRIER (.shift(1))
    # Parameters must never evaluate the current un-settled log return.
    sigma_t = log_ret_s.rolling(window=W, min_periods=W//2).std(ddof=1).shift(1)
    gamma_skew_t = log_ret_s.rolling(window=W, min_periods=W//2).skew().shift(1)
    
    # Safely fill warm-up structures
    sigma_t = sigma_t.fillna(sigma_t.mean() if len(sigma_t.dropna()) > 0 else 0.0).to_numpy()
    gamma_skew_t = gamma_skew_t.fillna(0.0).to_numpy()
    
    # 4. Asymmetric Barrier Output Formulation
    raw_barrier_upper = phi * sigma_t * (1.0 + gamma_skew_t)
    raw_barrier_lower = -phi * sigma_t * (1.0 - gamma_skew_t)
    
    # 5. Safety Floor Extrapolation
    # Prevents total math collapse inside directional flash-crashes (where |skew| > 1.0).
    # Take-profit must be strictly positive; Stop-loss must be strictly negative.
    min_scale = 0.1
    Barrier_upper = np.maximum(raw_barrier_upper, phi * sigma_t * min_scale)
    Barrier_lower = np.minimum(raw_barrier_lower, -phi * sigma_t * min_scale)
    
    # Neutralize any remnant structural data artifacts
    Barrier_upper = np.nan_to_num(Barrier_upper, nan=0.0, posinf=0.0, neginf=0.0)
    Barrier_lower = np.nan_to_num(Barrier_lower, nan=0.0, posinf=0.0, neginf=0.0)
    
    s_upper = pd.Series(Barrier_upper, index=index, name="barrier_upper")
    s_lower = pd.Series(Barrier_lower, index=index, name="barrier_lower")
    
    return s_upper, s_lower


def compute_point_15_override(
    df: pd.DataFrame,
    W: int = 100,
    phi: float = 2.0,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.DataFrame:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Replaces static symmetrical bands by injecting true Skewness-Weighted asymmetric logic.
    """
    try:
        if "close" not in df.columns:
            raise ValueError("DataFrame must contain a 'close' column to compute path-risk boundaries.")
            
        upper, lower = compute_skewness_weighted_asymmetric_barriers(
            close=df["close"],
            W=W,
            phi=phi
        )
        
        return pd.DataFrame({
            "barrier_upper": upper,
            "barrier_lower": lower
        }, index=df.index)
    except Exception as e:
        _logger.error(f"[POINT_15] Asymmetric Barrier calculation failed for {symbol}: {e}")
        # Fail-safe: Returns completely flat boundaries preventing order entry
        return pd.DataFrame({
            "barrier_upper": 0.0,
            "barrier_lower": 0.0
        }, index=df.index)