"""
Point 10: Sessional Latency Bias - Systemic Timestamp Latency Truncation
(Vectorized Implementation)

Replaces rigid, manual chronological calendar day buffers with a high-speed 
millisecond-precision latency truncation engine. Drops mathematically un-settled 
kline boundaries to prevent real-time dirty data contamination.
"""

from __future__ import annotations

import time
import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_10")


def compute_systemic_timestamp_latency_truncation(
    CT: Union[pd.Series, np.ndarray],
    system_time_ms: Optional[float] = None,
    tau_measured_latency: float = 5000.0
) -> pd.Series:
    """
    Computes a high-speed boolean mask array filter for data settlement.
    
    MATHEMATICAL SPECIFICATION:
    1. CT_t = Binance kline millisecond close timestamp (Field 6).
    2. Truncate_t = I[ SystemTime_ms - CT_t >= tau_measured_latency ]
    3. If Truncate_t == 0, the bar is omitted (un-settled / latency contaminated).
    
    Parameters
    ----------
    CT : array-like
        Array of exact exchange close millisecond timestamps.
    system_time_ms : float, optional
        The true hardware clock time in milliseconds. If None, uses current system time.
    tau_measured_latency : float
        The historical 99th percentile of network transit plus API settlement delays (ms).
        
    Returns
    -------
    pd.Series
        Strict causal boolean mask (True/1 = Settled & Safe, False/0 = Unsettled & Drop).
    """
    is_series = isinstance(CT, pd.Series)
    index = CT.index if is_series else None
    
    # Cast safely to NumPy int64 to prevent float precision loss on Unix millisecond timestamps
    CT_arr = np.asarray(CT, dtype=np.int64)
    
    # Evaluate true hardware clock if no simulation boundary is provided
    if system_time_ms is None:
        system_time_ms = time.time() * 1000.0
        
    # High-speed Boolean Mask Array Filter
    # 1/True evaluates to Safe/Settled. 0/False evaluates to Unsettled/Truncated.
    truncate_mask = (system_time_ms - CT_arr) >= tau_measured_latency
    
    return pd.Series(truncate_mask, index=index, name="latency_truncate_mask")


def compute_point_10_override(
    df: pd.DataFrame,
    tau_measured_latency: float = 5000.0,
    system_time_ms: Optional[float] = None,
    timestamp_col: str = "close_time",
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Ingests the raw DataFrame and isolates un-settled latency artifacts instantly.
    """
    try:
        if timestamp_col not in df.columns:
            # Fallback to general timestamp if exact close_time field 6 is missing
            fallback_col = "timestamp" if "timestamp" in df.columns else None
            if fallback_col:
                CT = df[fallback_col]
            else:
                raise ValueError(f"Required millisecond timestamp column '{timestamp_col}' missing.")
        else:
            CT = df[timestamp_col]
            
        return compute_systemic_timestamp_latency_truncation(
            CT=CT,
            system_time_ms=system_time_ms,
            tau_measured_latency=tau_measured_latency
        )
    except Exception as e:
        _logger.error(f"[POINT_10] Systemic Timestamp Latency Truncation failed for {symbol}: {e}")
        # Fail-safe: assume historical bars are settled to prevent breaking pipelines on error
        return pd.Series(True, index=df.index, name="latency_truncate_mask")
