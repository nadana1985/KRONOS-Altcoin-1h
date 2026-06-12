"""
Point 17: Constant Spread Assumptions - Corwin-Schultz High-Low Range Spread Estimator
(Vectorized Implementation)

Replaces rigid, static spread assumptions by continuously extracting implied 
bid-ask execution frictions natively from high-low price extremes. Eradicates 
cheap, single-period technical proxies to enforce exact mathematical compliance.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_17")


def compute_corwin_schultz_spread(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray]
) -> pd.Series:
    """
    Computes a continuous Corwin-Schultz (2012) implied spread natively across arrays.
    
    MATHEMATICAL SPECIFICATION:
    1. beta = [ln(H_t / L_t)]^2 + [ln(H_{t-1} / L_{t-1})]^2
    2. joint_high = max(H_t, H_{t-1}), joint_low = min(L_t, L_{t-1})
    3. gamma_joint = [ln(joint_high / joint_low)]^2
    4. alpha = (sqrt(2 * beta) - sqrt(beta)) / (3 - 2 * sqrt(2)) - sqrt(gamma_joint / (3 - 2 * sqrt(2)))
    5. Spread_t = (2 * (exp(alpha) - 1)) / (1 + exp(alpha))
    
    Parameters
    ----------
    high : array-like
        High prices array.
    low : array-like
        Low prices array.
        
    Returns
    -------
    pd.Series
        Continuous floating-point array of implied bid-ask spreads.
    """
    is_series = isinstance(high, pd.Series)
    index = high.index if is_series else None
    
    # Cast to raw float array to leverage low-level C-backend speeds
    H = np.asarray(high, dtype=float)
    L = np.asarray(low, dtype=float)
    
    N = len(H)
    
    if N == 0:
        return pd.Series(dtype=float, index=index, name="corwin_schultz_spread")
        
    # Prevent division by zero and log(0) native crashes
    H_safe = np.maximum(H, 1e-12)
    L_safe = np.maximum(L, 1e-12)
    
    # 1. Single-bar local variances
    # Matches: [ln(H_t / L_t)]^2
    local_var = np.log(H_safe / L_safe) ** 2
    
    # Generate t-1 arrays looking backward exactly 1 step out-of-sample
    local_var_prev = np.empty_like(local_var)
    local_var_prev[0] = local_var[0]  # Warm-up fallback
    local_var_prev[1:] = local_var[:-1]
    
    H_prev = np.empty_like(H_safe)
    H_prev[0] = H_safe[0]
    H_prev[1:] = H_safe[:-1]
    
    L_prev = np.empty_like(L_safe)
    L_prev[0] = L_safe[0]
    L_prev[1:] = L_safe[:-1]
    
    # 2. Corwin-Schultz Beta (Sum of adjacent local variances)
    beta = local_var + local_var_prev
    
    # 3. Corwin-Schultz Gamma (Joint high-low variance across the 2-bar block)
    joint_high = np.maximum(H_safe, H_prev)
    joint_low = np.minimum(L_safe, L_prev)
    
    gamma_joint = np.log(joint_high / joint_low) ** 2
    
    # 4. Compute Alpha
    # Extract the foundational denominator scaling constant natively
    k_denom = 3.0 - 2.0 * np.sqrt(2.0)
    
    # Guard natively against micro-scale negative roots (floating point exhaustion artifacts)
    beta_safe = np.maximum(beta, 0.0)
    gamma_safe = np.maximum(gamma_joint, 0.0)
    
    alpha = ((np.sqrt(2.0 * beta_safe) - np.sqrt(beta_safe)) / k_denom) - np.sqrt(gamma_safe / k_denom)
    
    # 5. Implied Bid-Ask Spread Output
    # Matches: Spread_t = (2 * (exp(alpha) - 1)) / (1 + exp(alpha))
    exp_alpha = np.exp(alpha)
    Spread_t = (2.0 * (exp_alpha - 1.0)) / (1.0 + exp_alpha)
    
    # Clamp final spread calculations securely to a strict mathematical floor of 0.0
    Spread_t = np.maximum(Spread_t, 0.0)
    
    # Neutralize any remnant structural data artifacts (NaN, inf) 
    # to protect downstream matrix signatures
    Spread_t = np.nan_to_num(Spread_t, nan=0.0, posinf=0.0, neginf=0.0)
    
    return pd.Series(Spread_t, index=index, name="corwin_schultz_spread")


def compute_point_17_override(
    df: pd.DataFrame,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Extracts explicit, mathematically exact implied frictions directly from exchange data streams.
    """
    try:
        req_cols = ["high", "low"]
        missing = [c for c in req_cols if c not in df.columns]
        
        if missing:
            raise ValueError(f"Missing required columns for Point 17: {missing}")
            
        return compute_corwin_schultz_spread(
            high=df["high"],
            low=df["low"]
        )
    except Exception as e:
        _logger.error(f"[POINT_17] Corwin-Schultz Implied Spread failed for {symbol}: {e}")
        # Fail-safe: Returns neutral 0.0 implied spread natively
        return pd.Series(0.0, index=df.index, name="corwin_schultz_spread")