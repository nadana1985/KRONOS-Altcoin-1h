"""
Point 06: Discrete Liquidity Filtering Bias - Continuous Amihud Decay Adjuster
(Vectorized & Scalar Hardened Implementation)
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any, Tuple, Dict

import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

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
    """
    is_series = isinstance(close, pd.Series)
    
    C = np.asarray(close, dtype=float)
    O = np.asarray(open_price, dtype=float)
    Q = np.asarray(quote_volume, dtype=float)
    
    N = len(C)
    w_t = np.ones(N, dtype=float)
    
    if N >= W:
        price_eps = 1e-12
        O_safe = np.maximum(O, price_eps)
        C_safe = np.maximum(C, price_eps)
        
        abs_log_ret = np.abs(np.log(C_safe / O_safe))
        
        Q_windows = np.lib.stride_tricks.sliding_window_view(Q, window_shape=W)
        num_windows = np.lib.stride_tricks.sliding_window_view(abs_log_ret, window_shape=W)
        
        Q_std = np.std(Q_windows, axis=1)
        eps_t = np.maximum(Q_std * eps_scale, eps_min)
        
        eps_t_expanded = eps_t[:, np.newaxis]
        fractions = num_windows / (Q_windows + eps_t_expanded)
        
        Rliq_t = np.mean(fractions, axis=1)
        decay_weights = np.exp(-lambda_decay * Rliq_t)
        
        w_t[W - 1:] = decay_weights
        
    w_t = np.clip(w_t, 1e-12, 1.0)
    
    if is_series:
        return pd.Series(w_t, index=close.index, name="amihud_decay_weight")
        
    return w_t


def compute_point_06_override(
    raw_weight: Optional[float] = None,
    df: Optional[pd.DataFrame] = None,
    symbol: str = '',
    engine: Optional[Any] = None,
    W: int = 24,
    lambda_decay: float = 2.0,
    *args,
    **kwargs
) -> Union[float, pd.Series]:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Accepts both:
    1. df, W=24, lambda_decay=2.0 (returns full Series)
    2. raw_weight=1.0, df=df, symbol=symbol, engine=engine (returns scalar float weight)
    """
    # Resolve parameters from dual calling conventions
    if len(args) > 0 and isinstance(args[0], pd.DataFrame):
        df_in = args[0]
    elif df is not None:
        df_in = df
    elif isinstance(raw_weight, pd.DataFrame):
        df_in = raw_weight
    else:
        df_in = None

    r_w = raw_weight if not isinstance(raw_weight, pd.DataFrame) else 1.0
    if r_w is None:
        r_w = 1.0

    try:
        if df_in is None:
            return float(r_w)
            
        req_cols = ["close", "open", "quote_asset_volume"]
        actual_vol = "quote_asset_volume" if "quote_asset_volume" in df_in.columns else ("volume" if "volume" in df_in.columns else None)
        
        if "close" not in df_in.columns or "open" not in df_in.columns or actual_vol is None:
            raise ValueError("Missing required OHLCV columns.")
            
        decay_series = compute_continuous_amihud_decay(
            close=df_in["close"],
            open_price=df_in["open"],
            quote_volume=df_in[actual_vol],
            W=W,
            lambda_decay=lambda_decay
        )
        
        # Scalar style override request
        is_scalar_style = raw_weight is not None and not isinstance(raw_weight, pd.DataFrame)
        
        if is_scalar_style:
            new_val = float(decay_series.iloc[-1]) if len(decay_series) > 0 else float(r_w)
            if engine is not None:
                final = engine.apply_override(
                    point_id="06",
                    raw_value=float(r_w),
                    override_value=new_val,
                    df=df_in,
                    symbol=symbol
                )
                return float(final)
            return new_val
            
        # Series style return
        return decay_series
        
    except Exception as e:
        _logger.error(f"[POINT_06] Continuous Amihud Decay failed for {symbol}: {e}")
        return float(r_w)