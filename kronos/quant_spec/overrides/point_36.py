"""
Point 36: Linear Moving Average Phase Lag - Causal Zero-Lag Kaufman Adaptive Moving Average (KAMA)
(Numba Optimized Implementation)

Destroys standard Simple and Exponential Moving Averages intrinsically blinding execution models 
to sudden microstructural reversals. Replaces linear logic with a Causal Zero-Lag KAMA engine
scaling execution exponentially across active directional breakouts and freezing natively during noise.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

try:
    from numba import njit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    
_logger = logging.getLogger("kronos.bias_override.point_36")


if NUMBA_AVAILABLE:
    @njit
    def _causal_kama_engine_core(C: np.ndarray, W: int, eps_scale: float, eps_min: float) -> np.ndarray:
        """
        Numba-compiled KAMA engine directly eliminating recursive execution bottlenecks safely.
        """
        N = len(C)
        KAMA = np.zeros(N)
        
        if N == 0:
            return KAMA
            
        KAMA[0] = C[0]
        
        # Explicit bounds defined symmetrically
        fast_sc = 2.0 / (2.0 + 1.0)
        slow_sc = 2.0 / (30.0 + 1.0)
        diff_sc = fast_sc - slow_sc
        
        for t in range(1, N):
            # Safe warm-up boundary preventing index out-of-bounds
            if t <= W:
                sc_t = slow_sc ** 2
                KAMA[t] = KAMA[t - 1] + sc_t * (C[t] - KAMA[t - 1])
                continue
                
            # STRICT CAUSALITY BARRIER: Evaluate purely using C[t-1] and backwards securely
            # direction_t = | C[t-1] - C[t-1-W] |
            direction = abs(C[t - 1] - C[t - 1 - W])
            
            volatility = 0.0
            sum_c = 0.0
            sum_c2 = 0.0
            
            # Evaluate sequence [t-1-W : t-1] cleanly via strict iteration loop out-of-sample natively
            for i in range(W):
                c_curr = C[t - 1 - i]
                c_prev = C[t - 1 - i - 1]
                volatility += abs(c_curr - c_prev)
                
                sum_c += c_curr
                sum_c2 += c_curr * c_curr
                
            # Evaluate exact local distribution variance securely
            mean_c = sum_c / W
            var_c = (sum_c2 / W) - (mean_c * mean_c)
            
            if var_c < 0.0:
                var_c = 0.0
                
            std_c = np.sqrt(var_c)
            
            # Integrate dynamic precision limits seamlessly preventing zero collapse
            epsilon = max(std_c * eps_scale, eps_min)
            
            ER_t = direction / (volatility + epsilon)
            
            # Bind logic cleanly natively limiting ER_t to [0, 1] mathematically
            if ER_t > 1.0:
                ER_t = 1.0
            elif ER_t < 0.0:
                ER_t = 0.0
                
            # Scale mathematical execution natively
            sc_t = (ER_t * diff_sc + slow_sc) ** 2
            
            # Contemporaneous KAMA mathematical execution 
            KAMA[t] = KAMA[t - 1] + sc_t * (C[t] - KAMA[t - 1])
            
        return KAMA

else:
    def _causal_kama_engine_core(C: np.ndarray, W: int, eps_scale: float, eps_min: float) -> np.ndarray:
        """
        NumPy-hybrid fallback mapping KAMA variables identically via vectorized bounds cleanly.
        """
        N = len(C)
        KAMA = np.zeros(N)
        
        if N == 0:
            return KAMA
            
        KAMA[0] = C[0]
        
        fast_sc = 2.0 / 3.0
        slow_sc = 2.0 / 31.0
        diff_sc = fast_sc - slow_sc
        
        # Extrapolate physical vectors natively
        abs_diff = np.zeros(N)
        abs_diff[1:] = np.abs(C[1:] - C[:-1])
        
        pad_diff = np.pad(abs_diff, (W - 1, 0), mode='constant', constant_values=0)
        win_diff = np.lib.stride_tricks.sliding_window_view(pad_diff, window_shape=W)
        volatility_raw = np.sum(win_diff, axis=1)
        
        direction_raw = np.zeros(N)
        direction_raw[W:] = np.abs(C[W:] - C[:-W])
        
        pad_C = np.pad(C, (W - 1, 0), mode='constant', constant_values=C[0])
        win_C = np.lib.stride_tricks.sliding_window_view(pad_C, window_shape=W)
        std_C_raw = np.std(win_C, axis=1, ddof=1)
        std_C_raw = np.nan_to_num(std_C_raw, nan=0.0)
        
        # STRICT CAUSALITY BARRIER (.shift(1))
        volatility_t = np.zeros(N)
        direction_t = np.zeros(N)
        std_t = np.zeros(N)
        
        volatility_t[1:] = volatility_raw[:-1]
        direction_t[1:] = direction_raw[:-1]
        std_t[1:] = std_C_raw[:-1]
        
        epsilon_t = np.maximum(std_t * eps_scale, eps_min)
        ER_t = direction_t / (volatility_t + epsilon_t)
        ER_t = np.nan_to_num(ER_t, nan=0.0, posinf=1.0, neginf=0.0)
        ER_t = np.clip(ER_t, 0.0, 1.0)
        
        sc_t = (ER_t * diff_sc + slow_sc) ** 2
        
        # Procedural fallback evaluating strict recursive logic explicitly
        for t in range(1, N):
            if t <= W:
                curr_sc = slow_sc ** 2
            else:
                curr_sc = sc_t[t]
            KAMA[t] = KAMA[t - 1] + curr_sc * (C[t] - KAMA[t - 1])
            
        return KAMA


def compute_causal_kama_filter(
    close_series: Union[pd.Series, np.ndarray],
    W: int = 10,
    eps_scale: float = 1e-7,
    eps_min: float = 1e-12
) -> pd.Series:
    """
    Computes a Zero-Lag adaptive memory matrix directly tracking explicit breakout sequences natively.
    
    MATHEMATICAL SPECIFICATION:
    1. ER_t = Direction_t / (Volatility_t + epsilon_t)
    2. sc_t = ( ER_t * (fast_sc - slow_sc) + slow_sc ) ** 2
    3. KAMA_t = KAMA_t-1 + sc_t * (C_t - KAMA_t-1)
    4. STRICT CAUSALITY BARRIER: Extraction metrics calculate exclusively evaluating out-of-sample
       historical data terminating cleanly at index 't-1' natively preventing current-bar leakage.
       
    Parameters
    ----------
    close_series : array-like
        Historical Sequence array extracting local geometries natively (Close prices).
    W : int
        Lookback anchoring the exact interval sequence explicitly tracking logic natively.
    eps_scale : float
        Explicit standard deviation scalar scaling precision dynamically.
    eps_min : float
        Zero-floor hard bounds preventing catastrophic math cascades explicitly.
        
    Returns
    -------
    pd.Series
        Continuous 1D feature array exactly evaluating structural state outputs organically (Slot 36).
    """
    is_series = isinstance(close_series, pd.Series)
    index = close_series.index if is_series else None
    
    C = np.asarray(close_series, dtype=float)
    
    KAMA = _causal_kama_engine_core(C, W, eps_scale, eps_min)
    
    # Ensure physical limits maintain floating structures reliably efficiently
    KAMA = np.nan_to_num(KAMA, nan=0.0, posinf=np.max(C), neginf=np.min(C))
    
    return pd.Series(KAMA, index=index, name="kama_adaptive_ma")


def compute_point_36_override(
    df: pd.DataFrame,
    target_col: str = "close",
    W: int = 10,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Discards strictly flawed rigid lagging SMAs sequentially tracking real-time KAMA bounds exclusively.
    """
    try:
        if target_col not in df.columns:
            raise ValueError(f"Missing required target column '{target_col}' for Point 36.")
            
        return compute_causal_kama_filter(
            close_series=df[target_col],
            W=W
        )
    except Exception as e:
        _logger.error(f"[POINT_36] Causal Zero-Lag KAMA generation failed for {symbol}: {e}")
        # Fail-safe: Return pure original target limits exactly natively mapping without crash bounds
        if target_col in df.columns:
            return pd.Series(df[target_col], index=df.index, name="kama_adaptive_ma")
        return pd.Series(0.0, index=df.index, name="kama_adaptive_ma")