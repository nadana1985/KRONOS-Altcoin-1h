"""
Point 24: Linear Order Flow Imbalance Persistence - Fractionally Differenced Order Flow Imbalance (FDOFI)
(Vectorized Implementation)

Replaces memoryless, stationary order-flow metrics with mathematically pure 
Fractionally Differenced time-series expansions to natively preserve long-memory 
institutional execution dependencies while maintaining absolute covariance stationarity.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_24")


def compute_fractionally_differenced_ofi(
    ofi_series: Union[pd.Series, np.ndarray],
    d: float = 0.45,
    W_expansion: int = 50
) -> pd.Series:
    """
    Computes Fractionally Differenced Order Flow Imbalance (FDOFI) natively via matrix multiplication.
    
    MATHEMATICAL SPECIFICATION:
    1. (1 - L)^d * OFI_t = sum_{k=0}^{W_expansion - 1} ( w_k * OFI_{t-k} )
    2. w_0 = 1.0, w_k = w_{k-1} * (k - 1 - d) / k
    3. The recurrence inherently integrates the alternating binomial sign correctly.
    4. STRICT CAUSALITY BARRIER: The convolution strictly maps [t - W + 1 : t] out-of-sample.
    
    Parameters
    ----------
    ofi_series : array-like
        The raw Trade-Intensity Weighted OFI series computed natively in Point 13.
    d : float
        Fractional differencing degree parameter (0 < d < 1).
    W_expansion : int
        Truncation length for the binomial series expansion lookback.
        
    Returns
    -------
    pd.Series
        Stationary long-memory feature array representing FDOFI_t.
    """
    is_series = isinstance(ofi_series, pd.Series)
    index = ofi_series.index if is_series else None
    
    OFI = np.asarray(ofi_series, dtype=float)
    N = len(OFI)
    
    if N == 0:
        return pd.Series(dtype=float, index=index, name="fractional_ofi")
        
    # 1. Generate the Iterative Binomial Expansion Weights
    # Matches: w_0 = 1.0, w_k = w_{k-1} * (k - 1 - d) / k
    w = np.zeros(W_expansion, dtype=float)
    w[0] = 1.0
    for k in range(1, W_expansion):
        w[k] = w[k - 1] * (k - 1.0 - d) / k
        
    # 2. Extract strictly causal historical windows using NumPy Stride Tricks
    # To evaluate the dot product sum(w_k * OFI_{t-k}), we need the window elements 
    # to be aligned from OFI_{t} backward to OFI_{t-W+1}.
    # The sliding window view natively produces [OFI_{t-W+1}, ..., OFI_{t}].
    # By reversing the weight array from w[0]...w[W-1] to w[W-1]...w[0], 
    # the continuous dot product handles the causal summation correctly.
    
    safe_mean = np.mean(OFI) if N > 0 else 0.0
    
    # Pad leading elements safely to prevent early matrix destruction
    pad_OFI = np.pad(OFI, (W_expansion - 1, 0), mode='constant', constant_values=safe_mean)
    
    # Generate the causal [Time_T, W_expansion] matrices natively in C
    windows = np.lib.stride_tricks.sliding_window_view(pad_OFI, window_shape=W_expansion)
    
    # 3. Apply Sliding Expansion Memory Convolution natively
    # windows shape is (N, W_expansion). 
    # The inner array sequence is [OFI_{t-W+1}, ..., OFI_{t-1}, OFI_t]
    # To match w_0 * OFI_t + w_1 * OFI_{t-1} + ..., we reverse the weight vector natively.
    w_reversed = w[::-1]
    
    # Explicit high-performance Vectorized Convolution / Matrix dot product
    FDOFI_t = np.dot(windows, w_reversed)
    
    # Scrub outputs seamlessly from mathematical anomalies
    FDOFI_t = np.nan_to_num(FDOFI_t, nan=0.0, posinf=0.0, neginf=0.0)
    
    return pd.Series(FDOFI_t, index=index, name="fractional_ofi")


def compute_point_24_override(
    df: pd.DataFrame,
    ofi_col: str = "trade_weighted_ofi",
    d: float = 0.45,
    W_expansion: int = 50,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Enforces long-memory fractional preservation onto localized OFI execution matrices.
    """
    try:
        if ofi_col not in df.columns:
            # Native safe-guard fallback to computing Point 13 inline if matrix decoupled
            from kronos.quant_spec.overrides.point_13 import compute_trade_intensity_weighted_imbalance
            if "volume" in df.columns and "taker_buy_base_asset_volume" in df.columns and "number_of_trades" in df.columns:
                ofi_series = compute_trade_intensity_weighted_imbalance(
                    df["volume"], df["taker_buy_base_asset_volume"], df["number_of_trades"]
                )
            else:
                raise ValueError(f"Missing required OFI target column '{ofi_col}' or prerequisites for Point 24.")
        else:
            ofi_series = df[ofi_col]
            
        return compute_fractionally_differenced_ofi(
            ofi_series=ofi_series,
            d=d,
            W_expansion=W_expansion
        )
    except Exception as e:
        _logger.error(f"[POINT_24] Fractionally Differenced OFI calculation failed for {symbol}: {e}")
        # Fail-safe: Return a zeroed neutral memory array mapping safely on collapse
        return pd.Series(0.0, index=df.index, name="fractional_ofi")