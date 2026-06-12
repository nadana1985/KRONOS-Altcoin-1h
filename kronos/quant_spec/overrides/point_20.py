"""
Point 20: Trade-Count Uniform Weighting - Normalized Shannon Count Entropy
(Vectorized & Numba-Compiled Hardened Implementation)
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any, Dict
import numpy as np
import pandas as pd
import numba

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

_logger = logging.getLogger("kronos.bias_override.point_20")


@numba.njit(cache=True)
def _rolling_shannon_entropy_numba(V: np.ndarray, W: int, n_bins: int) -> np.ndarray:
    """
    Numba-compiled rolling histogram-based Shannon Entropy calculator.
    Guarantees a mathematically sound PMF (simplex constraints) for every window.
    """
    n = len(V)
    out = np.zeros(n, dtype=np.float64)
    if n < W:
        return out
        
    for t in range(W - 1, n):
        window_data = V[t - W + 1 : t + 1]
        
        # Determine range for localized quantile state bins
        v_min = window_data[0]
        v_max = window_data[0]
        for val in window_data:
            if val < v_min:
                v_min = val
            if val > v_max:
                v_max = val
                
        # Handle zero-variance window
        if v_max == v_min or np.isnan(v_min) or np.isnan(v_max):
            out[t] = 0.0
            continue
            
        counts = np.zeros(n_bins, dtype=np.float64)
        bin_width = (v_max - v_min) / n_bins
        if bin_width <= 0:
            out[t] = 0.0
            continue
            
        for val in window_data:
            if np.isnan(val):
                continue
            bin_idx = int((val - v_min) / bin_width)
            if bin_idx >= n_bins:
                bin_idx = n_bins - 1
            elif bin_idx < 0:
                bin_idx = 0
            counts[bin_idx] += 1.0
            
        total = np.sum(counts)
        if total <= 0:
            out[t] = 0.0
            continue
            
        # PMF normalization: satisfies sum(p) == 1.0
        p = counts / total
        
        entropy = 0.0
        for pi in p:
            if pi > 0.0:
                entropy -= pi * np.log(pi)
                
        max_entropy = np.log(n_bins)
        out[t] = entropy / max_entropy if max_entropy > 0.0 else 0.0
        
    # Backfill warm-up period
    for t in range(W - 1):
        out[t] = out[W - 1]
        
    return out


def compute_normalized_shannon_count_entropy(
    volume: Union[pd.Series, np.ndarray],
    trade_count: Union[pd.Series, np.ndarray],
    W_eps: int = 24,
    n_bins: int = 10
) -> pd.Series:
    """
    Computes Shannon Count Entropy based on trade sizes normalized to a valid PMF rolling window.
    """
    is_series = isinstance(volume, pd.Series)
    index = volume.index if is_series else None
    
    V_t = np.asarray(volume, dtype=float)
    Count_t = np.asarray(trade_count, dtype=float)
    
    # Calculate trade sizes equivalent (V_t / Count_t)
    trade_sizes = V_t / np.maximum(Count_t, 1e-12)
    trade_sizes = np.nan_to_num(trade_sizes, nan=0.0, posinf=0.0, neginf=0.0)
    
    entropy_arr = _rolling_shannon_entropy_numba(trade_sizes, W_eps, n_bins)
    
    # Scrub outputs from potential floating point irregularities
    entropy_arr = np.nan_to_num(entropy_arr, nan=0.0, posinf=0.0, neginf=0.0)
    entropy_arr = np.clip(entropy_arr, 0.0, 1.0)
    
    return pd.Series(entropy_arr, index=index, name="shannon_entropy")


def compute_point_20_override(
    df: pd.DataFrame,
    volume_col: str = "volume",
    trade_count_col: str = "number_of_trades",
    engine: Optional[BiasOverrideEngine] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    """
    try:
        req_cols = [volume_col, trade_count_col]
        
        # Map fields if standard columns are missing but alternative exists
        actual_vol = volume_col if volume_col in df.columns else ("volume" if "volume" in df.columns else None)
        actual_cnt = trade_count_col if trade_count_col in df.columns else ("number_of_trades" if "number_of_trades" in df.columns else None)
        
        if actual_vol is None or actual_cnt is None:
            raise ValueError(f"Missing required columns for Point 20: volume_col={volume_col}, trade_count_col={trade_count_col}")
            
        new_val = compute_normalized_shannon_count_entropy(
            volume=df[actual_vol],
            trade_count=df[actual_cnt]
        )
        
        if engine is not None:
            # We can override the output series if active
            status = engine.registry.get_point_status("20")
            if status in ["implemented", "validated", "active", "backtest_only"]:
                # Simply return our mathematically sound PMF entropy series
                return new_val
                
        return new_val
    except Exception as e:
        _logger.error(f"[POINT_20] Normalized Shannon Count Entropy failed for {symbol}: {e}")
        return pd.Series(0.0, index=df.index, name="shannon_entropy")
