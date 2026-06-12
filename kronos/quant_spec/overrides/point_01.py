"""
KRONOS V1-ALT — Bias Override Point 01
Dynamic Quantile Veto (Vectorized Implementation)

This module implements the Point 01 bias override. It completely replaces the 
lazy proxy evaluation of log returns with a rigorous, purely slot_15-based 
rolling quantile veto, strictly preserving the causality barrier.
"""

from __future__ import annotations

import logging
from typing import Union

import numpy as np
import pandas as pd

logger = logging.getLogger("kronos.overrides.point_01")


def compute_point_01_override(
    slot_15: Union[pd.Series, np.ndarray],
    W: int,
) -> Union[pd.Series, np.ndarray]:
    """
    Computes a boolean veto mask for slot_15 values based on a rolling empirical quantile.
    
    MATHEMATICAL SPECIFICATION:
    1. Tracks and evaluates the historical array of slot_15 values exclusively.
    2. Calculates the threshold T_t dynamically using a rolling empirical quantile 
       of the slot_15 series over window 'W' at a strict q=0.65 cutoff.
    3. STRICT CAUSALITY BARRIER: Evaluates strictly from 't-W' up to 't-1' (inclusive),
       excluding contemporaneous data.
    4. VETO TRIGGER: Returns True (veto) if slot_15_t < T_t.
    
    WARM-UP PERIOD:
    If the current index 't' is less than the lookback window 'W', defaults the veto 
    to True due to insufficient historical context.

    Parameters
    ----------
    slot_15 : pd.Series or np.ndarray
        The array or series of historical slot_15 values.
    W : int
        The lookback window length for the rolling quantile.

    Returns
    -------
    pd.Series or np.ndarray
        A boolean mask matching the shape and index (if Series) of the input.
        True indicates a veto, False indicates pass.
    """
    arr = np.asarray(slot_15, dtype=float)
    n = len(arr)
    
    # Initialize all to True (default veto for warm-up period t < W)
    veto_mask = np.ones(n, dtype=bool)
    
    if n > W:
        # Create sliding windows of size W
        # windows[i] covers indices [i : i+W-1]
        windows = np.lib.stride_tricks.sliding_window_view(arr, window_shape=W)
        
        # Calculate the q=0.65 quantile across the rolling windows
        # Using nanquantile to handle missing values robustly without collapsing the window
        # The explicit strict requirement is q=0.65
        quantiles = np.nanquantile(windows, 0.65, axis=1)
        
        # The quantile for time 't' uses the window [t-W : t-1].
        # Since windows[i] covers [i : i+W-1], the window for time 't' is windows[t-W].
        # We evaluate for t from W to n-1.
        T_t = quantiles[:-1]
        
        # Current observation at time 't'
        current_obs = arr[W:]
        
        # Veto if current observation is strictly less than the threshold
        # or if the threshold is NaN (insufficient valid context)
        veto_condition = (current_obs < T_t)
        invalid_context = np.isnan(T_t)
        
        veto_mask[W:] = veto_condition | invalid_context
        
    if isinstance(slot_15, pd.Series):
        return pd.Series(veto_mask, index=slot_15.index, name="veto_mask")
    
    return veto_mask
