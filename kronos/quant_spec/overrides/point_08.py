"""
Point 08: Hardcoded Lookback Scaling Ratios - Empirical Mode Decomposition Wavelet Alignment
(Vectorized Implementation)

Replaces rigid, hardcoded scalar constant multipliers with a dynamic, spectral DFT 
Wavelet Alignment engine. Automatically extracts the dominant cyclical frequency to 
resize downstream indicators synchronously with actual high-beta altcoin cycle scales.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Any

import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.point_08")


def compute_adaptive_cycle_lookbacks(
    price_series: Union[pd.Series, np.ndarray],
    W_anchor: int = 400,
    alpha: float = 0.5,
    W_min: int = 12,
    W_max: int = 168
) -> Union[pd.Series, np.ndarray]:
    """
    Computes an array of dynamic integer window lengths targeting the dominant spectral cycle.
    
    MATHEMATICAL SPECIFICATION:
    1. Computes localized Power Spectrum via rolling Discrete Fourier Transform (DFT).
    2. Lambda_t = 1 / argmax_f( Power_Spectrum(f) ) isolating the dominant wavelength.
    3. W_adaptive,t = round(alpha * Lambda_t)
    4. STRICT CAUSALITY BARRIER: Computes rolling window strictly off [t-W_anchor : t-1].
    5. BOUNDS: Safely clips output between [12, 168] to prevent structural frequency collapse.
    
    Parameters
    ----------
    price_series : array-like
        The raw asset price array.
    W_anchor : int
        The foundational DFT lookback window to evaluate. Must be large enough to 
        capture low-frequency cycles (W_anchor >= W_max / alpha).
    alpha : float
        Adjustment scalar factor mapping wavelength to indicator lookback.
    W_min : int
        Absolute minimum allowed lookback window.
    W_max : int
        Absolute maximum allowed lookback window.

    Returns
    -------
    pd.Series or np.ndarray
        Array of adaptive integer window lengths aligned perfectly to cycle regimes.
    """
    is_series = isinstance(price_series, pd.Series)
    X = np.asarray(price_series, dtype=float)
    N = len(X)
    
    # Initialize safe bounded output for warm-up phases
    W_t = np.full(N, W_max, dtype=int)
    
    if N <= W_anchor:
        if is_series:
            return pd.Series(W_t, index=price_series.index, name="adaptive_window")
        return W_t
        
    # 1. Strictly Causal Rolling Window Extraction
    # sliding_window_view provides shape (N - W_anchor + 1, W_anchor)
    windows_raw = np.lib.stride_tricks.sliding_window_view(X, window_shape=W_anchor)
    
    # Exclude the last window to lock causality out-of-sample ending at t-1
    hist_windows = windows_raw[:-1]  # shape: (N - W_anchor, W_anchor)
    
    # 2. Signal Pre-processing
    # Center the time-series blocks to strip the zero-frequency (DC) offset,
    # preventing massive DC power leakage from overwhelming actual cycles
    mean_w = np.mean(hist_windows, axis=1, keepdims=True)
    centered_w = hist_windows - mean_w
    
    # Apply a Hanning window to suppress spectral leakage / ringing artifacts
    hanning = np.hanning(W_anchor)
    windowed_data = centered_w * hanning
    
    # 3. Matrix Batched Discrete Fourier Transform
    # Executes FFT entirely in C-backend natively across all rows
    fft_vals = np.fft.rfft(windowed_data, axis=1)
    
    # Extract structural Power Spectrum (Amplitude squared)
    power = np.abs(fft_vals) ** 2
    
    # Generate spatial frequency bins
    freqs = np.fft.rfftfreq(W_anchor)
    
    # 4. Wavelength (Lambda_t) Extraction
    # Ignore DC component bin (f=0) entirely by searching [:, 1:]
    dominant_idx = np.argmax(power[:, 1:], axis=1) + 1  # Add 1 to align with original freqs array
    dominant_f = freqs[dominant_idx]
    
    # Invert dominant frequency to resolve spatial wavelength in bars
    Lambda_t = 1.0 / dominant_f
    
    # 5. Adaptive Formulation
    W_raw = np.round(alpha * Lambda_t)
    
    # Explicit Boundary Clipping
    W_clipped = np.clip(W_raw, W_min, W_max).astype(int)
    
    W_t[W_anchor:] = W_clipped
    
    if is_series:
        return pd.Series(W_t, index=price_series.index, name="adaptive_window")
        
    return W_t


def compute_point_08_override(
    df: pd.DataFrame,
    W_anchor: int = 400,
    alpha: float = 0.5,
    W_min: int = 12,
    W_max: int = 168,
    engine: Optional[Any] = None,
    symbol: str = ''
) -> pd.Series:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    Processes the entire DataFrame in a single, highly optimized rolling DFT pass.
    """
    try:
        if "close" not in df.columns:
            raise ValueError("DataFrame must contain a 'close' column to compute spectral cycles.")
            
        return compute_adaptive_cycle_lookbacks(
            price_series=df["close"],
            W_anchor=W_anchor,
            alpha=alpha,
            W_min=W_min,
            W_max=W_max
        )
    except Exception as e:
        _logger.error(f"[POINT_08] Spectral Wavelet Alignment failed for {symbol}: {e}")
        # Fail-safe: return static maximum window on catastrophic failure
        return pd.Series(W_max, index=df.index, name="adaptive_window")