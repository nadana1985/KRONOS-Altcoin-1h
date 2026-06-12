"""
Point 02: Rigid Feature Window Bias - Dynamic Volatility-Scaled Lookback Adaptation
(Vectorized Implementation)

Replaces all hardcoded, rigid lookback spans with a dynamically scaling volatility engine.
W_t = round(W_base * (1 + sigma_rel,t) ** (-gamma))
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_02")


def compute_dynamic_lookback_windows(
    close: Union[pd.Series, np.ndarray],
    W_base: int = 168,
    gamma: float = 0.5,
    short_window: int = 24,
    long_window: int = 168,
    W_min: int = 24,
    W_max: int = 336
) -> Union[pd.Series, np.ndarray]:
    """
    Computes an array of dynamic lookback windows scaled by relative volatility.
    
    MATHEMATICAL SPECIFICATION:
    1. W_t = round(W_base * (1 + sigma_rel,t) ** (-gamma))
    2. sigma_rel,t = sigma_short,t / sigma_long,t
    3. STRICT CAUSALITY BARRIER: Volatility metrics at time 't' are computed strictly
       using data up to 't-1' via .shift(1).
    4. BOUNDARY CLIPPING: Results are strictly clipped between [W_min, W_max].
    
    Parameters
    ----------
    close : pd.Series or np.ndarray
        Array or Series of close prices.
    W_base : int
        The foundational anchor window (e.g., 168 hours).
    gamma : float
        Volatility sensitivity dampener (e.g., 0.5).
    short_window : int
        Lookback for short-term rolling volatility metric (sigma_short).
    long_window : int
        Lookback for long-term rolling volatility metric (sigma_long).
    W_min : int
        Absolute minimum allowed lookback window.
    W_max : int
        Absolute maximum allowed lookback window.

    Returns
    -------
    pd.Series or np.ndarray
        A sequence of integer window assignments representing the exact adaptive window length.
    """
    is_series = isinstance(close, pd.Series)
    s = pd.Series(close) if not is_series else close
    
    # 1. Compute log returns safely
    eps = 1e-12
    s_float = s.astype(float)
    rets = np.log((s_float / s_float.shift(1).clip(lower=eps)).clip(lower=eps))
    
    # 2. Compute strictly causal rolling standard deviations
    # The .shift(1) explicitly enforces the strict causality barrier (t-1).
    sigma_short = rets.rolling(window=short_window, min_periods=2).std().shift(1)
    sigma_long = rets.rolling(window=long_window, min_periods=2).std().shift(1)
    
    # 3. Compute relative volatility (sigma_rel,t = sigma_short,t / sigma_long,t)
    # Safe division: map div-by-zero to NaN, then fill invalid bounds with 1.0 (neutral fallback)
    sigma_long_safe = sigma_long.replace(0.0, np.nan)
    sigma_rel = (sigma_short / sigma_long_safe).fillna(1.0)
    sigma_rel = sigma_rel.replace([np.inf, -np.inf], 1.0)
    
    # 4. Compute dynamic lookback window W_t
    W_t_raw = np.round(W_base * (1.0 + sigma_rel) ** (-gamma))
    
    # 5. Boundary Clipping & integer casting
    W_t = W_t_raw.clip(lower=W_min, upper=W_max).fillna(W_base).astype(int)
    
    if is_series:
        return pd.Series(W_t, index=s.index, name="dynamic_window")
    return W_t.to_numpy()


# Top-level adapter for the BiasOverrideEngine pipeline
def compute_point_02_override(
    df: pd.DataFrame,
    W_base: int = 168,
    gamma: float = 0.5,
    short_window: int = 24,
    long_window: int = 168,
    W_min: int = 24,
    W_max: int = 336,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Processes the entire DataFrame in a single, highly optimized vectorized pass.
    Output Series matches the original DataFrame index and contains the assigned window bounds.
    """
    try:
        if "close" not in df.columns:
            raise ValueError("DataFrame must contain a 'close' column to compute relative volatility.")
            
        return compute_dynamic_lookback_windows(
            close=df["close"],
            W_base=W_base,
            gamma=gamma,
            short_window=short_window,
            long_window=long_window,
            W_min=W_min,
            W_max=W_max
        )
    except Exception as e:
        _logger.error(f"[POINT_02] Failed to compute dynamic lookbacks for {symbol}: {e}")
        # Fail-safe: return static base window array on catastrophic failure
        n = len(df)
        return pd.Series(np.full(n, W_base, dtype=int), index=df.index, name="dynamic_window")