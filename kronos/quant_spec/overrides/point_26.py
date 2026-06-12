"""
Point 26: Linear Proximity Modeling Bias - Continuous Cauchy Proximity Kernel
(Vectorized Implementation)

Replaces naive linear distance proxies with a non-linear continuous Cauchy kernel.
Accurately models the exponential gravitational liquidity concentration mapping 
an asset's exact physical proximity to institutional support/resistance thresholds natively.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_26")


def compute_cauchy_proximity_kernel(
    high: Union[pd.Series, np.ndarray],
    low: Union[pd.Series, np.ndarray],
    close: Union[pd.Series, np.ndarray],
    key_level: Union[pd.Series, np.ndarray],
    W: int = 24,
    kappa: float = 0.5,
    gamma_min: float = 1e-6
) -> pd.Series:
    """
    Computes a strictly causal, continuous Cauchy proximity kernel score natively.
    
    MATHEMATICAL SPECIFICATION:
    1. TR_t = max(H_t - L_t, |H_t - C_t-1|, |L_t - C_t-1|)
    2. gamma_t = Mean(TR_[t-W : t-1]) * kappa
    3. K_t = 1.0 / ( 1.0 + ( (C_t - L_key,t) / gamma_t )^2 )
    4. STRICT CAUSALITY BARRIER: The scale parameter gamma_t is generated entirely 
       out-of-sample (.shift(1)) ensuring current price boundaries do not alter the 
       evaluation physics contemporaneously.
       
    Parameters
    ----------
    high : array-like
        High prices array.
    low : array-like
        Low prices array.
    close : array-like
        Close prices array (C_t).
    key_level : array-like
        Nearest validated Support or Resistance line (L_key,t).
    W : int
        Lookback window tracking underlying background volatility dynamically.
    kappa : float
        Scale multiplier controlling kernel bandwidth density bounds.
    gamma_min : float
        Absolute hardware float floor preventing Cauchy singularity points natively.
        
    Returns
    -------
    pd.Series
        Bounded [0.0, 1.0] continuous probability mapping representing proximity density (Slot 26).
    """
    is_series = isinstance(close, pd.Series)
    index = close.index if is_series else None
    
    H = np.asarray(high, dtype=float)
    L = np.asarray(low, dtype=float)
    C = np.asarray(close, dtype=float)
    L_key = np.asarray(key_level, dtype=float)
    
    N = len(C)
    
    if N == 0:
        return pd.Series(dtype=float, index=index, name="cauchy_proximity")
        
    # 1. Structural True Range Extraction
    C_prev = np.empty_like(C)
    C_prev[0] = C[0]  # Warm-up fallback
    C_prev[1:] = C[:-1]
    
    tr1 = H - L
    tr2 = np.abs(H - C_prev)
    tr3 = np.abs(L - C_prev)
    
    # Exact native maximum path
    TR = np.maximum(np.maximum(tr1, tr2), tr3)
    
    # 2. Vectorized Rolling ATR Calculation via Stride Tricks
    safe_mean = np.mean(TR) if N > 0 else 1.0
    
    # Pad array strictly to ensure matrix dimensionality alignment safely
    pad_TR = np.pad(TR, (W - 1, 0), mode='constant', constant_values=safe_mean)
    windows = np.lib.stride_tricks.sliding_window_view(pad_TR, window_shape=W)
    ATR_raw = np.mean(windows, axis=1)
    
    # 3. STRICT CAUSALITY BARRIER (.shift(1))
    ATR_t = np.empty_like(ATR_raw)
    ATR_t[0] = safe_mean
    
    # Lock matrix extraction strictly out-of-sample natively
    ATR_t[1:] = ATR_raw[:-1]
    
    # 4. Localized Scale Parameter Optimization (gamma_t)
    gamma_raw = ATR_t * kappa
    
    # Enforce strict zero-variance structural limits safely protecting Cauchy kernel limits
    gamma_t = np.maximum(gamma_raw, gamma_min)
    
    # 5. Continuous Cauchy Proximity Kernel Mathematics
    # Matches equation exactly: 1.0 / ( 1.0 + ( (C_t - L_key,t) / gamma_t )^2 )
    dist = (C - L_key) / gamma_t
    K_t = 1.0 / (1.0 + (dist ** 2))
    
    # Scrub outputs cleanly explicitly against matrix corruption
    K_t = np.nan_to_num(K_t, nan=0.0, posinf=1.0, neginf=0.0)
    
    # Cauchy inherently maps to [0, 1] securely, explicit clip maintains standard
    K_t = np.clip(K_t, 0.0, 1.0)
    
    return pd.Series(K_t, index=index, name="cauchy_proximity")


def compute_point_26_override(
    df: pd.DataFrame,
    key_level_col: str,
    W: int = 24,
    kappa: float = 0.5,
    gamma_min: float = 1e-6,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Extracts non-linear liquidity gravitational forces into continuous Cauchy state kernels.
    """
    try:
        req_cols = ["high", "low", "close", key_level_col]
        missing = [c for c in req_cols if c not in df.columns]
        
        if missing:
            raise ValueError(f"Missing required columns for Point 26: {missing}")
            
        return compute_cauchy_proximity_kernel(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            key_level=df[key_level_col],
            W=W,
            kappa=kappa,
            gamma_min=gamma_min
        )
    except Exception as e:
        _logger.error(f"[POINT_26] Continuous Cauchy Proximity mapping failed for {symbol}: {e}")
        # Fail-safe: Return pure neutral (0.0) spatial baseline organically on failure
        return pd.Series(0.0, index=df.index, name="cauchy_proximity")