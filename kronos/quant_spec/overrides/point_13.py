"""
Point 13: Fixed Order Flow Proxy Splits - Trade-Intensity Weighted Imbalance (OFI)
(Vectorized Implementation)

Replaces crude symmetrical volume assumptions with a dynamic order flow intensity 
model. Scales net aggressor imbalances synchronously to log-transformed transaction density.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_13")


def compute_trade_intensity_weighted_imbalance(
    volume: Union[pd.Series, np.ndarray],
    taker_buy_volume: Union[pd.Series, np.ndarray],
    trade_count: Union[pd.Series, np.ndarray],
    W_eps: int = 24,
    eps_scale: float = 0.1,
    eps_min: float = 1e-6
) -> pd.Series:
    """
    Computes the Trade-Intensity Weighted Imbalance (OFI) metric natively across the matrix.
    
    MATHEMATICAL SPECIFICATION:
    1. Net Taker Volume = TBV_t - (V_t - TBV_t)
    2. OFI_t = Net_Taker_Volume * ln( V_t / (Count_t + epsilon_t) )
    3. epsilon_t is a dynamic variance-stabilized precision guard (Point 14 formulation)
       preventing division-by-zero or log(0) collapse during zero-trade blocks.
       
    Parameters
    ----------
    volume : array-like
        Total Base Volume (Binance Field 5).
    taker_buy_volume : array-like
        Taker Buy Base Volume (Binance Field 9).
    trade_count : array-like
        Total Trade Count (Binance Field 8).
    W_eps : int
        Lookback window for the dynamic epsilon stabilizer.
    eps_scale : float
        Scaling factor for the standard deviation.
    eps_min : float
        Absolute minimum floor for epsilon.
        
    Returns
    -------
    pd.Series
        Continuous, fully scaled Order Flow Imbalance metric.
    """
    is_series = isinstance(volume, pd.Series)
    index = volume.index if is_series else None
    
    # Cast cleanly to float NumPy arrays for structural speed
    V_t = np.asarray(volume, dtype=float)
    TBV_t = np.asarray(taker_buy_volume, dtype=float)
    Count_t = np.asarray(trade_count, dtype=float)
    
    N = len(V_t)
    if N == 0:
        return pd.Series(dtype=float, index=index, name="trade_weighted_ofi")
        
    # 1. Net Taker Volume
    # Net Taker Volume = TBV_t - (V_t - TBV_t) = 2 * TBV_t - V_t
    net_taker_volume = 2.0 * TBV_t - V_t
    
    # 2. Dynamic Variance-Stabilized Precision Guard (epsilon_t)
    # Compute the rolling standard deviation of trade counts using stride tricks
    safe_std = np.std(Count_t) if N > 0 else 1.0
    pad_count = np.pad(Count_t, (W_eps - 1, 0), mode='constant', constant_values=np.mean(Count_t))
    
    windows = np.lib.stride_tricks.sliding_window_view(pad_count, window_shape=W_eps)
    std_count = np.std(windows, axis=1, ddof=1)
    
    # Guard against NaN/div-zero inside the variance calculation itself
    std_count = np.nan_to_num(std_count, nan=safe_std)
    
    eps_t = np.maximum(std_count * eps_scale, eps_min)
    
    # 3. Density Ratio
    # Guard the numerator volume natively to prevent log(0) explicitly
    V_safe = np.maximum(V_t, 1e-12)
    density_ratio = V_safe / (Count_t + eps_t)
    
    # 4. Final Trade-Intensity Weighted Imbalance Evaluation
    OFI_t = net_taker_volume * np.log(density_ratio)
    
    # Scrub outputs perfectly clean from any float infinity artifacts
    OFI_t = np.nan_to_num(OFI_t, nan=0.0, posinf=0.0, neginf=0.0)
    
    return pd.Series(OFI_t, index=index, name="trade_weighted_ofi")


def compute_point_13_override(
    df: pd.DataFrame,
    volume_col: str = "volume",
    taker_buy_vol_col: str = "taker_buy_base_asset_volume",
    trade_count_col: str = "number_of_trades",
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Destroys the old static proxy split assumptions and returns true continuous OFI density.
    """
    try:
        req_cols = [volume_col, taker_buy_vol_col, trade_count_col]
        missing = [c for c in req_cols if c not in df.columns]
        
        if missing:
            raise ValueError(f"Missing required execution flow columns for Point 13: {missing}")
            
        return compute_trade_intensity_weighted_imbalance(
            volume=df[volume_col],
            taker_buy_volume=df[taker_buy_vol_col],
            trade_count=df[trade_count_col]
        )
    except Exception as e:
        _logger.error(f"[POINT_13] Trade-Intensity Weighted Imbalance calculation failed for {symbol}: {e}")
        # Fail-safe: Return a zeroed series to lock the module open neutrally
        return pd.Series(0.0, index=df.index, name="trade_weighted_ofi")
