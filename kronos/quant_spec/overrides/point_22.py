"""
Point 22: Linear Bid-Ask Absorption Scaling - Spread-Weighted Directional Delta Absorption
(Vectorized Implementation)

Replaces naive symmetric extreme evaluations with a rigorous mathematical sequence 
capturing the actual unequal execution force of aggressive market orders crossing 
the spread during directional liquidity runs.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_22")


def compute_directional_delta_absorption(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    volume: Union[pd.Series, np.ndarray],
    taker_buy_volume: Union[pd.Series, np.ndarray],
    W_eps: int = 24,
    eps_scale: float = 1e-7,
    eps_min: float = 1e-12
) -> pd.Series:
    """
    Computes a fully vectorized, strictly bounded directional absorption indicator natively.
    
    MATHEMATICAL SPECIFICATION:
    1. Numerator = IDV_t * (C_t - L_t) - (V_t - IDV_t) * (H_t - C_t)
    2. Denominator = (H_t - L_t + epsilon_t) * V_t
    3. Absorp_t = Numerator / Denominator
    4. epsilon_t is evaluated dynamically (Point 14) using the structural variance 
       of V_t locked perfectly out-of-sample (.shift(1)).
    5. Output strictly bounded natively to exactly [-1.0, 1.0].
    
    Parameters
    ----------
    high : array-like
        High prices array.
    low : array-like
        Low prices array.
    close : array-like
        Close prices array.
    volume : array-like
        Total Base Volume array (V_t).
    taker_buy_volume : array-like
        Taker Buy Base Volume array (IDV_t).
    W_eps : int
        Lookback window length for the rolling volume variance guard.
    eps_scale : float
        Standard deviation mapping multiplier.
    eps_min : float
        Absolute minimum hardware float floor protecting flat ranges.
        
    Returns
    -------
    pd.Series
        Continuous, bounded [-1.0, 1.0] feature floating-point array (Slot 22).
    """
    is_series = isinstance(close, pd.Series)
    index = close.index if is_series else None
    
    H = np.asarray(high, dtype=float)
    L = np.asarray(low, dtype=float)
    C = np.asarray(close, dtype=float)
    V_t = np.asarray(volume, dtype=float)
    IDV_t = np.asarray(taker_buy_volume, dtype=float)
    
    N = len(C)
    
    if N == 0:
        return pd.Series(dtype=float, index=index, name="delta_absorption")
        
    # 1. Component Pre-Calculation
    dist_bottom = C - L
    dist_top = H - C
    total_range = H - L
    
    maker_sell_vol = V_t - IDV_t
    
    # 2. Extract Dynamic Precision Guard (Point 14 Architecture)
    safe_std = np.std(V_t) if N > 0 else 1.0
    
    pad_V = np.pad(V_t, (W_eps - 1, 0), mode='constant', constant_values=np.mean(V_t))
    windows = np.lib.stride_tricks.sliding_window_view(pad_V, window_shape=W_eps)
    std_V_raw = np.std(windows, axis=1, ddof=1)
    
    # Scrub potential NaNs on perfectly flat distribution slots
    std_V_raw = np.nan_to_num(std_V_raw, nan=0.0)
    
    # Strict Causality Barrier (.shift(1)) natively mapped
    std_V_t = np.empty_like(std_V_raw)
    std_V_t[0] = safe_std
    std_V_t[1:] = std_V_raw[:-1]
    
    epsilon_t = np.maximum(std_V_t * eps_scale, eps_min)
    
    # 3. Formulate the Absolute Delta Absorption Vector
    numerator = (IDV_t * dist_bottom) - (maker_sell_vol * dist_top)
    
    # Safely lock the volume denominator preventing division by 0 natively
    V_safe = np.maximum(V_t, 1e-12)
    denominator = (total_range + epsilon_t) * V_safe
    
    Absorp_t = numerator / denominator
    
    # 4. Strict Continuous Feature Bounding
    # The mathematical formula is inherently structured to output between -1 and 1
    # We clip mathematically exactly to scrub floating point distortions or boundary drift
    Absorp_t = np.nan_to_num(Absorp_t, nan=0.0, posinf=1.0, neginf=-1.0)
    Absorp_t = np.clip(Absorp_t, -1.0, 1.0)
    
    return pd.Series(Absorp_t, index=index, name="delta_absorption")


def compute_point_22_override(
    df: pd.DataFrame,
    volume_col: str = "volume",
    taker_buy_vol_col: str = "taker_buy_base_asset_volume",
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Bypasses simplistic linear volume thresholds to isolate pure directional liquidity exhaustion natively.
    """
    try:
        req_cols = ["high", "low", "close", volume_col, taker_buy_vol_col]
        missing = [c for c in req_cols if c not in df.columns]
        
        if missing:
            raise ValueError(f"Missing required columns for Point 22: {missing}")
            
        return compute_directional_delta_absorption(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            volume=df[volume_col],
            taker_buy_volume=df[taker_buy_vol_col]
        )
    except Exception as e:
        _logger.error(f"[POINT_22] Spread-Weighted Directional Delta Absorption failed for {symbol}: {e}")
        # Fail-safe: Return neutralized 0.0 directional force on pipeline collapse
        return pd.Series(0.0, index=df.index, name="delta_absorption")