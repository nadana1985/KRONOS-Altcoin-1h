"""
Point 06: Discrete Liquidity Filtering Bias - Continuous Amihud Decay Adjuster
(Vectorized Implementation)

Replaces naive binary volume thresholding with a continuous, 
regime-adaptive liquidity penalty weight.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_06")


def compute_continuous_amihud_decay(
    close: Union[pd.Series, np.ndarray],
    open_price: Union[pd.Series, np.ndarray],
    quote_volume: Union[pd.Series, np.ndarray],
    W: int = 24,
    lambda_decay: float = 2.0,
    eps_scale: float = 0.1,
    eps_min: float = 1e-6
) -> Union[pd.Series, np.ndarray]:
    """
    Computes the Continuous Amihud Decay weight for each bar.
    
    MATHEMATICAL SPECIFICATION:
    1. Rliq_t = (1 / W) * sum_{i=0}^{W-1} ( |ln(C_{t-i} / O_{t-i})| / (Q_{t-i} + epsilon_t) )
    2. epsilon_t dynamically scales with rolling standard deviation of volume.
    3. w_t = exp(-lambda * Rliq_t) -> bounds cleanly into (0.0, 1.0].
    
    Parameters
    ----------
    close : array-like
        Close prices.
    open_price : array-like
        Open prices.
    quote_volume : array-like
        Quote asset volumes.
    W : int
        Lookback window (e.g., 24 hours).
    lambda_decay : float
        Sensitivity parameter for the exponential decay penalty.
    eps_scale : float
        Scaling factor for the dynamic epsilon variance stabilizer.
    eps_min : float
        Absolute minimum floor for epsilon to prevent division by zero.
        
    Returns
    -------
    pd.Series or np.ndarray
        Continuous confidence weight penalty strictly in (0.0, 1.0].
    """
    is_series = isinstance(close, pd.Series)
    
    # Cast to float numpy arrays
    C = np.asarray(close, dtype=float)
    O = np.asarray(open_price, dtype=float)
    Q = np.asarray(quote_volume, dtype=float)
    
    N = len(C)
    
    # Default to 1.0 (no penalty) for warm-up phase
    w_t = np.ones(N, dtype=float)
    
    if N >= W:
        # 1. Compute the instantaneous Amihud ratio numerator: |ln(C_t / O_t)|
        # Add tiny eps to prices to prevent log(0) or division issues
        price_eps = 1e-12
        O_safe = np.maximum(O, price_eps)
        C_safe = np.maximum(C, price_eps)
        
        abs_log_ret = np.abs(np.log(C_safe / O_safe))
        
        # 2. Extract strictly rolling windows of size W for Q and the numerator
        # Using stride tricks: shape (N - W + 1, W)
        Q_windows = np.lib.stride_tricks.sliding_window_view(Q, window_shape=W)
        num_windows = np.lib.stride_tricks.sliding_window_view(abs_log_ret, window_shape=W)
        
        # 3. Dynamic variance-stabilized precision guard (epsilon_t)
        # Computed per window to adapt to shifting volume regimes
        Q_std = np.std(Q_windows, axis=1)  # shape (N - W + 1,)
        eps_t = np.maximum(Q_std * eps_scale, eps_min)  # shape (N - W + 1,)
        
        # 4. Compute Rliq_t = (1 / W) * sum( numerator / (Q + eps_t) )
        # To broadcast eps_t across the window, we add a dimension: eps_t[:, np.newaxis]
        eps_t_expanded = eps_t[:, np.newaxis]
        
        # The element-wise fraction across the window
        fractions = num_windows / (Q_windows + eps_t_expanded)
        
        # Mean across the window axis (equivalent to 1/W * sum)
        Rliq_t = np.mean(fractions, axis=1)  # shape (N - W + 1,)
        
        # 5. Continuous signal penalty weight w_t = exp(-lambda * Rliq_t)
        decay_weights = np.exp(-lambda_decay * Rliq_t)
        
        # Assign to output array
        w_t[W - 1:] = decay_weights
        
    # Strictly bound outputs between an epsilon above zero and exactly 1.0
    w_t = np.clip(w_t, 1e-12, 1.0)
    
    if is_series:
        return pd.Series(w_t, index=close.index, name="amihud_decay_weight")
        
    return w_t


def compute_point_06_override(
    df: pd.DataFrame,
    W: int = 24,
    lambda_decay: float = 2.0,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Processes the DataFrame sequentially to compute continuous liquidity penalty scaling.
    """
    try:
        req_cols = ["close", "open", "quote_asset_volume"]
        missing = [c for c in req_cols if c not in df.columns]
        
        # Fallback to standard volume if quote_asset_volume is missing
        if "quote_asset_volume" not in df.columns and "volume" in df.columns:
            q_col = "volume"
            req_cols[2] = "volume"
            missing = [c for c in req_cols if c not in df.columns]
        else:
            q_col = "quote_asset_volume"
            
        if missing:
            raise ValueError(f"Missing required columns for Point 06: {missing}")
            
        return compute_continuous_amihud_decay(
            close=df["close"],
            open_price=df["open"],
            quote_volume=df[q_col],
            W=W,
            lambda_decay=lambda_decay
        )
    except Exception as e:
        _logger.error(f"[POINT_06] Continuous Amihud Decay failed for {symbol}: {e}")
        # Fail-safe: neutral 1.0 weight (no penalty)
        return pd.Series(1.0, index=df.index, name="amihud_decay_weight")