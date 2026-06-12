"""
Point 15: Symmetric Path-Risk Target Boundaries - Skewness-Weighted Asymmetric Barriers
(Vectorized & Scalar Hardened Implementation)
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any, Tuple, Dict

import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

_logger = logging.getLogger("kronos.bias_override.point_15")


def compute_skewness_weighted_asymmetric_barriers(
    close: Union[pd.Series, np.ndarray],
    W: int = 100,
    phi: float = 2.0
) -> Tuple[pd.Series, pd.Series]:
    """
    Computes rolling dynamic Skewness-Weighted Asymmetric Barriers for Risk Management.
    """
    is_series = isinstance(close, pd.Series)
    index = close.index if is_series else None
    
    C = np.asarray(close, dtype=float)
    N = len(C)
    
    if N == 0:
        empty = pd.Series(dtype=float, index=index)
        return empty, empty
        
    log_ret = np.zeros(N, dtype=float)
    C_prev = np.maximum(C[:-1], 1e-12)
    C_curr = np.maximum(C[1:], 1e-12)
    log_ret[1:] = np.log(C_curr / C_prev)
    
    log_ret_s = pd.Series(log_ret)
    
    sigma_t = log_ret_s.rolling(window=W, min_periods=max(2, W//2)).std(ddof=1).shift(1)
    gamma_skew_t = log_ret_s.rolling(window=W, min_periods=max(2, W//2)).skew().shift(1)
    
    sigma_t = sigma_t.fillna(sigma_t.mean() if len(sigma_t.dropna()) > 0 else 0.0).to_numpy()
    gamma_skew_t = gamma_skew_t.fillna(0.0).to_numpy()
    
    raw_barrier_upper = phi * sigma_t * (1.0 + gamma_skew_t)
    raw_barrier_lower = -phi * sigma_t * (1.0 - gamma_skew_t)
    
    min_scale = 0.1
    Barrier_upper = np.maximum(raw_barrier_upper, phi * sigma_t * min_scale)
    Barrier_lower = np.minimum(raw_barrier_lower, -phi * sigma_t * min_scale)
    
    Barrier_upper = np.nan_to_num(Barrier_upper, nan=0.0, posinf=0.0, neginf=0.0)
    Barrier_lower = np.nan_to_num(Barrier_lower, nan=0.0, posinf=0.0, neginf=0.0)
    
    s_upper = pd.Series(Barrier_upper, index=index, name="barrier_upper")
    s_lower = pd.Series(Barrier_lower, index=index, name="barrier_lower")
    
    return s_upper, s_lower


def compute_point_15_override(
    raw_barrier: Optional[float] = None,
    df: Optional[pd.DataFrame] = None,
    symbol: str = '',
    engine: Optional[Any] = None,
    W: int = 100,
    phi: float = 2.0,
    *args,
    **kwargs
) -> Union[pd.DataFrame, Dict[str, float]]:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Accepts both:
    1. df, W=100, phi=2.0 (standard dataframe return)
    2. raw_barrier=0.02, df=df, symbol=symbol, engine=engine (dict-like return for scalar mining evaluation)
    """
    # Resolve parameters from dual calling conventions
    if len(args) > 0 and isinstance(args[0], pd.DataFrame):
        df_in = args[0]
    elif df is not None:
        df_in = df
    elif isinstance(raw_barrier, pd.DataFrame):
        df_in = raw_barrier
    else:
        df_in = None

    r_bar = raw_barrier if not isinstance(raw_barrier, pd.DataFrame) else 0.02
    if r_bar is None:
        r_bar = 0.02
        
    try:
        if df_in is None:
            return {"barrier_upper": float(r_bar), "barrier_lower": -float(r_bar)}
            
        if "close" not in df_in.columns:
            raise ValueError("DataFrame must contain a 'close' column.")
            
        upper, lower = compute_skewness_weighted_asymmetric_barriers(
            close=df_in["close"],
            W=W,
            phi=phi
        )
        
        # Decide format based on whether raw_barrier was passed (dict of last values expected)
        # If it was a scalar-style override request, return dict of the final values.
        is_scalar_style = raw_barrier is not None and not isinstance(raw_barrier, pd.DataFrame)
        
        if is_scalar_style:
            u_val = float(upper.iloc[-1]) if len(upper) > 0 else float(r_bar)
            l_val = float(lower.iloc[-1]) if len(lower) > 0 else -float(r_bar)
            
            if engine is not None:
                u_val = float(engine.apply_override(
                    point_id="15",
                    raw_value=r_bar,
                    override_value=u_val,
                    df=df_in,
                    symbol=symbol
                ))
                l_val = float(engine.apply_override(
                    point_id="15",
                    raw_value=-r_bar,
                    override_value=l_val,
                    df=df_in,
                    symbol=symbol
                ))
            return {"barrier_upper": u_val, "barrier_lower": l_val}
            
        # Return dataframe for standard feature aggregation pipelines
        return pd.DataFrame({
            "barrier_upper": upper,
            "barrier_lower": lower
        }, index=df_in.index)
        
    except Exception as e:
        _logger.error(f"[POINT_15] Asymmetric Barrier calculation failed for {symbol}: {e}")
        return {"barrier_upper": float(r_bar), "barrier_lower": -float(r_bar)}