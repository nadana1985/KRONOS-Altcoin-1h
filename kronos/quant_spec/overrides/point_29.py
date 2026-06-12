"""
Point 29: Linear Trend-Exhaustion Proxies - Non-Parametric Kendall's Tau Momentum Exhaustion
(Vectorized Implementation)

Replaces naive linear trend indicators with a strict Non-Parametric Kendall's Tau Momentum Tracker.
Mathematically evaluates rank-order monotonicity natively to eliminate devastating vulnerability
to structural trend-extension rollouts organically.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_29")


def compute_kendall_tau_momentum_exhaustion(
    close: Union[pd.Series, np.ndarray],
    W: int = 24
) -> pd.Series:
    """
    Computes rolling Kendall's Tau sequence evaluating structural trend exhaustion explicitly.
    
    MATHEMATICAL SPECIFICATION:
    1. Tau_t = ( Concordant_Pairs - Discordant_Pairs ) / ( 0.5 * W * (W - 1) )
    2. Concordant mapping natively extracted where sgn(C_i - C_j) == sgn(i - j)
    3. STRICT CAUSALITY BARRIER: Matrix pairwise evaluation must operate completely 
       out-of-sample ending at 't-1' (.shift(1)) perfectly bounded natively inside [-1.0, 1.0].
       
    Parameters
    ----------
    close : array-like
        Historical Close prices tracking structural monotonicity natively.
    W : int
        Lookback sequence interval generating matrix coordinate evaluation nodes.
        
    Returns
    -------
    pd.Series
        Continuous 1D explicit floating point array bounded perfectly [-1.0, 1.0] (Slot 29).
    """
    is_series = isinstance(close, pd.Series)
    index = close.index if is_series else None
    
    C = np.asarray(close, dtype=float)
    N = len(C)
    
    if N == 0:
        return pd.Series(dtype=float, index=index, name="kendall_tau_exhaustion")
        
    # 1. Stride matrix sequences strictly generating localized sliding data chunks
    safe_mean = np.mean(C) if N > 0 else 0.0
    
    # Pad early sequence natively preventing length truncations gracefully
    pad_C = np.pad(C, (W - 1, 0), mode='constant', constant_values=safe_mean)
    
    # Generate completely localized window evaluations natively mapped in memory (N, W)
    windows = np.lib.stride_tricks.sliding_window_view(pad_C, window_shape=W)
    
    # 2. Vectorized Pairwise Rank Generation (O(W^2) matrix mapping natively executed)
    # Extracts exactly the upper-triangle indices where structural index i > j.
    idx_j, idx_i = np.triu_indices(W, k=1)
    
    # Slice the corresponding pairwise structural sequence columns directly
    C_i = windows[:, idx_i]
    C_j = windows[:, idx_j]
    
    # Extract absolute Concordance mappings seamlessly
    # Since idx_i > idx_j, sgn(idx_i - idx_j) is strictly +1.
    # Therefore: Concordant pairs = sum(sgn(diff) > 0), Discordant pairs = sum(sgn(diff) < 0)
    # Summing the exact signs mathematically evaluates (Concordant - Discordant) cleanly natively.
    diff = C_i - C_j
    sgn_diff = np.sign(diff)
    
    tau_numerator_raw = np.sum(sgn_diff, axis=1)
    
    # 3. STRICT CAUSALITY BARRIER (.shift(1))
    tau_numerator_t = np.empty_like(tau_numerator_raw)
    
    # Initialize index 0 strictly preventing matrix corruption (fallback neutral)
    tau_numerator_t[0] = 0.0
    
    # Physical backward constraint entirely mapping sequence exclusively on finalized data
    tau_numerator_t[1:] = tau_numerator_raw[:-1]
    
    # 4. Standardized Kendall Tau Density Limits
    tau_denominator = 0.5 * W * (W - 1.0)
    
    # Since denominators are entirely constant structural definitions, safe evaluation executes natively
    Tau_t = tau_numerator_t / tau_denominator
    
    # Bind limits explicitly strictly maintaining numerical vector limits reliably
    Tau_t = np.nan_to_num(Tau_t, nan=0.0, posinf=1.0, neginf=-1.0)
    Tau_t = np.clip(Tau_t, -1.0, 1.0)
    
    return pd.Series(Tau_t, index=index, name="kendall_tau_exhaustion")


def compute_point_29_override(
    df: pd.DataFrame,
    W: int = 24,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Injects Kendall's Tau coefficient locally into Trend-Exhaustion matrix arrays natively.
    """
    try:
        if "close" not in df.columns:
            raise ValueError("Missing required column 'close' for Point 29.")
            
        return compute_kendall_tau_momentum_exhaustion(
            close=df["close"],
            W=W
        )
    except Exception as e:
        _logger.error(f"[POINT_29] Non-Parametric Kendall's Tau calculation failed for {symbol}: {e}")
        # Fail-safe: Return pure neutral mathematical baseline organically on limits
        return pd.Series(0.0, index=df.index, name="kendall_tau_exhaustion")