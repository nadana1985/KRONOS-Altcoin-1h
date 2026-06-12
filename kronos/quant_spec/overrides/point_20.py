"""
Point 20: Trade-Count Uniform Weighting - Normalized Shannon Count Entropy
(Vectorized Implementation)

Destroys linear trade-count proxy metrics that ignore internal execution sizing. 
Maps the proportional relationship between base volume and discrete count density 
into a non-stationary Shannon Information Entropy feature vector natively.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_20")


def compute_normalized_shannon_count_entropy(
    volume: Union[pd.Series, np.ndarray],
    trade_count: Union[pd.Series, np.ndarray],
    W_eps: int = 24,
    eps_scale: float = 0.1,
    eps_min: float = 1e-6
) -> pd.Series:
    """
    Computes continuous Information Entropy scaled across average transactional density natively.
    
    MATHEMATICAL SPECIFICATION:
    1. Average Trade Size Equivalent (p) = (V_t / (Count_t + epsilon_t))
    2. Entropy_t = -( p * ln(p) )
    3. epsilon_t is a rolling variance-stabilized numerical floor guarding against zero count boundaries.
    
    Parameters
    ----------
    volume : array-like
        Total Base Volume array (V_t).
    trade_count : array-like
        Total Trade Count array (Count_t).
    W_eps : int
        Lookback window for the dynamic epsilon stabilizer.
    eps_scale : float
        Standard deviation scaling multiplier mapping the numerical density guard.
    eps_min : float
        Absolute minimum hardware float parameter to prevent division collapse.
        
    Returns
    -------
    pd.Series
        Vectorized floating point sequence representing structural Execution Entropy.
    """
    is_series = isinstance(volume, pd.Series)
    index = volume.index if is_series else None
    
    V_t = np.asarray(volume, dtype=float)
    Count_t = np.asarray(trade_count, dtype=float)
    
    N = len(V_t)
    
    if N == 0:
        return pd.Series(dtype=float, index=index, name="shannon_entropy")
        
    # 1. Dynamic Variance-Stabilized Precision Guard (epsilon_t)
    safe_std = np.std(Count_t) if N > 0 else 1.0
    
    # Pad history reliably strictly preventing array truncation or edge-case variance blowouts
    pad_count = np.pad(Count_t, (W_eps - 1, 0), mode='constant', constant_values=np.mean(Count_t))
    
    windows = np.lib.stride_tricks.sliding_window_view(pad_count, window_shape=W_eps)
    std_count = np.std(windows, axis=1, ddof=1)
    
    # Secure structural NaN output from perfectly flat matrices (ddof=1)
    std_count = np.nan_to_num(std_count, nan=safe_std)
    
    # Hard bounds scaling execution precision dynamically per-asset
    epsilon_t = np.maximum(std_count * eps_scale, eps_min)
    
    # 2. Extract Base Transaction Proportionality (p)
    # Prevent the total volume from collapsing into a hard 0 explicitly before the log scale
    V_safe = np.maximum(V_t, 1e-12)
    
    # Represents the fundamental transactional weight structure natively
    p = V_safe / (Count_t + epsilon_t)
    
    # 3. Shannon Entropy Formula
    # Matches exact specification: Entropy_t = -( p * ln(p) )
    Entropy_t = -(p * np.log(p))
    
    # 4. Scrub final outputs effectively from potential logarithm instability
    Entropy_t = np.nan_to_num(Entropy_t, nan=0.0, posinf=0.0, neginf=0.0)
    
    return pd.Series(Entropy_t, index=index, name="shannon_entropy")


def compute_point_20_override(
    df: pd.DataFrame,
    volume_col: str = "volume",
    trade_count_col: str = "number_of_trades",
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Extracts true Information Entropy out of raw trade distributions synchronously.
    """
    try:
        req_cols = [volume_col, trade_count_col]
        missing = [c for c in req_cols if c not in df.columns]
        
        if missing:
            raise ValueError(f"Missing required columns for Point 20: {missing}")
            
        return compute_normalized_shannon_count_entropy(
            volume=df[volume_col],
            trade_count=df[trade_count_col]
        )
    except Exception as e:
        _logger.error(f"[POINT_20] Normalized Shannon Count Entropy failed for {symbol}: {e}")
        # Fail-safe: Return neutralized 0.0 entropy output seamlessly upon pipeline collapse
        return pd.Series(0.0, index=df.index, name="shannon_entropy")
