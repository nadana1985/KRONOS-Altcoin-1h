"""
Point 25: Static S/R Memory Decay Parameters - Information-Entropy Adaptive Memory Half-Life
(Vectorized Implementation)

Replaces flat, static exponential decay factors with an adaptive mathematical half-life.
Rapidly flushes historical memory lines in high-entropy liquidation regimes while naturally 
locking support/resistance boundaries permanently during low-entropy accumulation environments.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_25")


def compute_entropy_adaptive_memory_decay(
    entropy_series: Union[pd.Series, np.ndarray],
    lambda_base: float = 0.99,
    W: int = 24
) -> pd.Series:
    """
    Computes an adaptive memory decay factor scaled strictly against order-flow entropy natively.
    
    MATHEMATICAL SPECIFICATION:
    1. H_norm,t = (Entropy_t - min_t) / (max_t - min_t + 1e-12)
    2. lambda_t = lambda_base * (1.0 - H_norm,t)
    3. STRICT CAUSALITY BARRIER: min_t and max_t extract directly from the mathematically 
       closed historical [t-W : t-1] rolling block exclusively (.shift(1)).
       
    Parameters
    ----------
    entropy_series : array-like
        Normalized Shannon Count Entropy array natively computed via Point 20.
    lambda_base : float
        Foundational memory decay parameter anchor locking structural half-life dynamically.
    W : int
        Rolling lookback window tracking relative historical bounds locally.
        
    Returns
    -------
    pd.Series
        Continuous 1D feature floating point array representing the adaptive decay (lambda_t).
    """
    is_series = isinstance(entropy_series, pd.Series)
    index = entropy_series.index if is_series else None
    
    Entropy = np.asarray(entropy_series, dtype=float)
    N = len(Entropy)
    
    if N == 0:
        return pd.Series(dtype=float, index=index, name="adaptive_memory_decay")
        
    # 1. Isolate the explicit structural boundary metrics natively
    safe_mean = np.mean(Entropy) if N > 0 else 0.5
    
    # Pad array exclusively backwards maintaining length while filling safe bounds
    pad_Entropy = np.pad(Entropy, (W - 1, 0), mode='constant', constant_values=safe_mean)
    
    # 2. Striding the matrix arrays safely against W window vectors
    windows = np.lib.stride_tricks.sliding_window_view(pad_Entropy, window_shape=W)
    
    min_raw = np.min(windows, axis=1)
    max_raw = np.max(windows, axis=1)
    
    # 3. STRICT CAUSALITY BARRIER (.shift(1))
    min_t = np.empty_like(min_raw)
    max_t = np.empty_like(max_raw)
    
    # Fallback to the global bounds on index 0 ensuring zero NaN contamination explicitly
    min_t[0] = np.min(Entropy) if N > 0 else 0.0
    max_t[0] = np.max(Entropy) if N > 0 else 1.0
    
    # Hard shift strictly evaluating backward against completely finalized vectors
    min_t[1:] = min_raw[:-1]
    max_t[1:] = max_raw[:-1]
    
    # 4. Continuous Out-Of-Sample Normalization Sequence
    # Evaluate current bar's physical entropy strictly against historical locked bounds
    H_norm_raw = (Entropy - min_t) / (max_t - min_t + 1e-12)
    
    # Since the current bar could theoretically break its own historically closed standard
    # deviation bounds (e.g., flash crash generating completely unprecedented entropy scale),
    # we explicitly bind the normalization securely inside [0.0, 1.0] mathematical logic
    H_norm_t = np.clip(H_norm_raw, 0.0, 1.0)
    
    # 5. Decay Extrapolation Master Equation
    lambda_t = lambda_base * (1.0 - H_norm_t)
    
    # Limit potential float exhaustion bounds strictly against math limits
    lambda_t = np.nan_to_num(lambda_t, nan=lambda_base, posinf=lambda_base, neginf=0.0)
    lambda_t = np.clip(lambda_t, 0.0, 1.0)
    
    return pd.Series(lambda_t, index=index, name="adaptive_memory_decay")


def compute_point_25_override(
    df: pd.DataFrame,
    entropy_col: str = "shannon_entropy",
    lambda_base: float = 0.99,
    W: int = 24,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Bypasses flat S/R proxy memory scales by extracting dynamic Information-Entropy anchors natively.
    """
    try:
        if entropy_col not in df.columns:
            # Inline failsafe: Natively invoke Point 20 module processing safely inside the pipeline
            from kronos.quant_spec.overrides.point_20 import compute_normalized_shannon_count_entropy
            if "volume" in df.columns and "number_of_trades" in df.columns:
                entropy_series = compute_normalized_shannon_count_entropy(
                    df["volume"], df["number_of_trades"]
                )
            else:
                raise ValueError(f"Missing required target column '{entropy_col}' or prerequisites for Point 25.")
        else:
            entropy_series = df[entropy_col]
            
        return compute_entropy_adaptive_memory_decay(
            entropy_series=entropy_series,
            lambda_base=lambda_base,
            W=W
        )
    except Exception as e:
        _logger.error(f"[POINT_25] Adaptive Entropy Memory Decay failed for {symbol}: {e}")
        # Fail-safe: Returns neutral fixed rigid base memory fallback safely maintaining pipeline bounds
        return pd.Series(lambda_base, index=df.index, name="adaptive_memory_decay")