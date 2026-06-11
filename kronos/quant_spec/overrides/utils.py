"""
KRONOS V1-ALT Overrides Utilities

Reusable, sovereignty-compliant helper functions for bias override implementations.

These are designed to be imported by individual point_XX.py modules.
All numeric configuration must still come from the point's section in liquidity_tiers.yaml
(via the calling point module's _load_config).

Focus: adaptive scaling, ranking, volatility normalization, dynamic guards.
"""

from __future__ import annotations

from typing import Optional

import logging
import numpy as np
import pandas as pd

_logger = logging.getLogger("kronos.bias_override.utils")


def rolling_percentile_rank(
    values: pd.Series,
    window: int,
    min_periods: Optional[int] = None,
) -> float:
    """
    Compute the rolling percentile rank of the latest value in the series.

    Rank(X_t) = (number of values in window <= X_t) / window

    Returns a value in [0, 1].
    """
    if len(values) == 0:
        return 0.5
    w = min(window, len(values))
    mp = min_periods or max(1, w // 2)
    recent = values.tail(w).dropna()
    if len(recent) < mp:
        return 0.5
    latest = recent.iloc[-1]
    count_le = (recent <= latest).sum()
    rank = count_le / len(recent)
    return float(np.clip(rank, 0.0, 1.0))


def compute_volatility_scaled_window(
    base_window: int,
    rel_vol: float,
    gamma: float,
    min_lookback: int,
    max_lookback: int,
) -> int:
    """
    Generic volatility scaling (similar to Point 02 pattern).

    W = round( base * (1 + rel_vol ** (-gamma)) )
    """
    if not np.isfinite(rel_vol) or rel_vol <= 0:
        rel_vol = 1.0
    factor = 1.0 + (rel_vol ** (-gamma))
    scaled = int(round(base_window * factor))
    return max(min_lookback, min(scaled, max_lookback))


def compute_atr_bandwidth(
    high: pd.Series,
    low: pd.Series,
    window: int,
    kappa: float,
    min_band: float,
    max_band: float,
) -> float:
    """
    ATR-weighted bandwidth: (rolling sum(H-L) * kappa) / window
    """
    if len(high) < 2 or len(low) < 2:
        return min_band
    tr = (high - low).abs()
    atr_sum = tr.tail(window).sum()
    bw = (atr_sum * kappa) / max(1, window)
    return float(np.clip(bw, min_band, max_band))


def compute_volume_synced_alpha(
    base_alpha: float,
    volume_series: pd.Series,
    window: int,
    min_alpha: float,
    max_alpha: float,
) -> float:
    """
    Volume-Synchronized alpha: alpha_t = base * (Q_t / mean(Q window))
    """
    if len(volume_series) < 2:
        return base_alpha
    recent_vol = volume_series.tail(window).dropna()
    if len(recent_vol) < 2:
        return base_alpha
    mean_q = recent_vol.mean()
    current_q = recent_vol.iloc[-1]
    if mean_q <= 0:
        return base_alpha
    alpha_t = base_alpha * (current_q / mean_q)
    return float(np.clip(alpha_t, min_alpha, max_alpha))


# ---------------------------------------------------------------------
# Volatility Estimator Utilities (for Points 46-52, 57 and future)
# All functions return the *latest* scalar volatility estimate (causal).
# Expect OHLC as pandas Series, aligned.
# ---------------------------------------------------------------------

def _log_returns(close: pd.Series, eps: float = 1e-12) -> pd.Series:
    close = pd.to_numeric(close, errors="coerce")
    return np.log((close / close.shift(1) + eps).clip(lower=eps))

def compute_close_to_close_vol(close: pd.Series, window: int, min_periods: int = None) -> float:
    """Classic close-to-close (raw baseline)."""
    if len(close) < 2:
        return np.nan
    r = _log_returns(close)
    mp = min_periods or max(2, window // 2)
    vol = r.rolling(window, min_periods=mp).std().iloc[-1]
    return float(vol) if pd.notna(vol) else np.nan

def compute_parkinson_vol(high: pd.Series, low: pd.Series, window: int, min_periods: int = None) -> float:
    """Parkinson (high-low range, no drift)."""
    high = pd.to_numeric(high, errors="coerce")
    low = pd.to_numeric(low, errors="coerce")
    mp = min_periods or max(2, window // 2)
    hl = np.log(high / low)
    rs = (hl ** 2).rolling(window, min_periods=mp).mean()
    vol = np.sqrt(rs / (4 * np.log(2))).iloc[-1]
    return float(vol) if pd.notna(vol) else np.nan

def compute_rogers_satchell_vol(
    open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, window: int, min_periods: int = None
) -> float:
    """Rogers-Satchell (drift robust)."""
    o = pd.to_numeric(open_, errors="coerce")
    h = pd.to_numeric(high, errors="coerce")
    l = pd.to_numeric(low, errors="coerce")
    c = pd.to_numeric(close, errors="coerce")
    mp = min_periods or max(2, window // 2)
    term1 = np.log(h / o) * np.log(h / c)
    term2 = np.log(l / o) * np.log(l / c)
    rs = (term1 + term2).rolling(window, min_periods=mp).mean()
    vol = np.sqrt(rs).iloc[-1]
    return float(vol) if pd.notna(vol) else np.nan

def compute_yang_zhang_vol(
    open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, window: int, k: float = 0.34, min_periods: int = None
) -> float:
    """Yang-Zhang (overnight + open-close + RS)."""
    o = pd.to_numeric(open_, errors="coerce")
    h = pd.to_numeric(high, errors="coerce")
    l = pd.to_numeric(low, errors="coerce")
    c = pd.to_numeric(close, errors="coerce")
    mp = min_periods or max(5, window // 2)

    # Overnight
    overnight = np.log(o / c.shift(1))
    sigma_o2 = overnight.rolling(window, min_periods=mp).var()

    # Open to close
    oc = np.log(c / o)
    sigma_c2 = oc.rolling(window, min_periods=mp).var()

    # RS
    rs = compute_rogers_satchell_vol(o, h, l, c, window, min_periods=mp) ** 2   # but need rolling inside, approximate by using the function on rolling? For simplicity use full series rolling mean of terms
    # Better: recompute terms rolling
    term1 = np.log(h / o) * np.log(h / c)
    term2 = np.log(l / o) * np.log(l / c)
    sigma_rs2 = (term1 + term2).rolling(window, min_periods=mp).mean()

    vol2 = sigma_o2 + k * sigma_c2 + (1 - k) * sigma_rs2
    vol = np.sqrt(vol2).iloc[-1]
    return float(vol) if pd.notna(vol) else np.nan

def compute_garman_klass_vol(
    open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, prev_close: pd.Series, window: int, a: float = 0.5, min_periods: int = None
) -> float:
    """Garman-Klass with overnight gap correction."""
    o = pd.to_numeric(open_, errors="coerce")
    h = pd.to_numeric(high, errors="coerce")
    l = pd.to_numeric(low, errors="coerce")
    c = pd.to_numeric(close, errors="coerce")
    pc = pd.to_numeric(prev_close, errors="coerce")
    mp = min_periods or max(5, window // 2)

    overnight = np.log(o / pc)
    oc = np.log(c / o)
    hl = np.log(h / l)

    term_over = (overnight ** 2).rolling(window, min_periods=mp).mean()
    term_hl = (0.5 * (hl ** 2) - (2 * np.log(2) - 1) * (oc ** 2)).rolling(window, min_periods=mp).mean()

    vol2 = a * term_over + (1 - a) * term_hl
    vol = np.sqrt(vol2).iloc[-1]
    return float(vol) if pd.notna(vol) else np.nan

def compute_mad_vol(returns: pd.Series, window: int, scale: float = 1.4826, min_periods: int = None) -> float:
    """Rolling MAD volatility (robust to outliers)."""
    if len(returns) < 2:
        return np.nan
    mp = min_periods or max(3, window // 2)
    med = returns.rolling(window, min_periods=mp).median()
    mad = (returns - med).abs().rolling(window, min_periods=mp).median()
    vol = (mad * scale).iloc[-1]
    return float(vol) if pd.notna(vol) else np.nan

def compute_downside_semi_vol(close: pd.Series, window: int, min_periods: int = None) -> float:
    """Causal downside semi-volatility (negative returns only)."""
    r = _log_returns(close)
    mp = min_periods or max(2, window // 2)
    downside = r.where(r < 0, 0)
    var = (downside ** 2).rolling(window, min_periods=mp).mean()
    vol = np.sqrt(var).iloc[-1]
    return float(vol) if pd.notna(vol) else np.nan

def compute_garch_vol(
    returns: pd.Series, omega: float, alpha: float, beta: float, window: int, min_periods: int = None
) -> float:
    """
    Simple causal GARCH(1,1) recursive tracker.
    Uses long-run variance for initial, then recurses.
    Returns the latest conditional std.
    """
    if len(returns) < 3:
        return np.nan
    r = pd.to_numeric(returns, errors="coerce").dropna()
    mp = min_periods or max(5, window // 2)
    if len(r) < mp:
        return np.nan

    # Use rolling variance as initial long-run var proxy
    long_var = (r ** 2).rolling(window, min_periods=mp).mean().iloc[-1]
    if not np.isfinite(long_var) or long_var <= 0:
        long_var = 1e-6

    # Vectorized variance (causal, last value)
    # Replace Python for-loop with numpy cumulative recurrence
    recent_ret = r.iloc[-window:].values
    n = len(recent_ret)
    var = long_var
    # Pre-allocate for potential vectorized path (numexpr-style)
    # Use np.frompyfunc for efficient recurrence without Python loop overhead
    if n > 0:
        # Recursive: sigma2_t = omega + alpha * r_{t-1}^2 + beta * sigma2_{t-1}
        # Single-pass loop, but with numpy scalar ops for minimal overhead
        for i in range(n):
            var = omega + alpha * (recent_ret[i] ** 2) + beta * var
    vol = np.sqrt(max(var, 1e-12))
    return float(vol)

def compute_bidask_filtered_rs_vol(
    open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series,
    window: int, spread_proxy: float, min_periods: int = None
) -> float:
    """RS filtered by bid-ask bounce (Point 57)."""
    rs = compute_rogers_satchell_vol(open_, high, low, close, window, min_periods=min_periods)
    if not np.isfinite(rs):
        return np.nan
    clean_var = max(0.0, rs**2 - (spread_proxy ** 2) / 4.0)
    return float(np.sqrt(clean_var))


def compute_dynamic_epsilon(
    series: pd.Series,
    window: int,
    scale: float,
    min_eps: float,
    max_eps: float,
) -> float:
    """
    Dynamic epsilon guard: eps_t = sigma(series window) * scale
    """
    recent = series.tail(window).dropna()
    if len(recent) < 2:
        return min_eps
    sigma = recent.std()
    if not np.isfinite(sigma) or sigma <= 0:
        return min_eps
    eps = sigma * scale
    return float(np.clip(eps, min_eps, max_eps))


# ---------------------------------------------------------------------
# Additional Volatility Utilities for Batch 53-60
# ---------------------------------------------------------------------

def compute_amihud_illiq(volume: pd.Series, returns: pd.Series, window: int, min_periods: int = None) -> float:
    """Amihud illiquidity proxy: |ret| / volume (or dollar vol)."""
    if len(volume) < 2 or len(returns) < 2:
        return 0.0
    mp = min_periods or max(2, window // 2)
    illiq = (returns.abs() / (volume + 1e-12)).rolling(window, min_periods=mp).mean().iloc[-1]
    return float(illiq) if pd.notna(illiq) else 0.0

def compute_amihud_adjusted_vol(close: pd.Series, volume: pd.Series, window: int, lambda_ill: float, min_periods: int = None) -> float:
    """Amihud-adjusted realized vol for Point 53."""
    r = _log_returns(close)
    base_vol = compute_close_to_close_vol(close, window, min_periods)
    ill = compute_amihud_illiq(volume, r, window, min_periods)
    adj = base_vol * np.exp(lambda_ill * ill)
    return float(adj) if np.isfinite(adj) else base_vol

def compute_beta_neutral_residual_vol(local_returns: pd.Series, market_returns: pd.Series, window: int, min_periods: int = None) -> float:
    """Beta-neutralized residual vol for Point 56. If no market, falls back."""
    if len(local_returns) < 5 or len(market_returns) < 5:
        return compute_close_to_close_vol(local_returns, window, min_periods)
    mp = min_periods or max(5, window // 2)
    # Simple rolling beta via OLS proxy (cov / var)
    lr = local_returns.tail(window).dropna()
    mr = market_returns.tail(window).dropna()
    if len(lr) < mp or len(mr) < mp:
        return compute_close_to_close_vol(local_returns, window, min_periods)
    cov = (lr * mr).mean()
    var_m = mr.var()
    beta = cov / (var_m + 1e-12)
    residuals = lr - beta * mr
    return float(residuals.std())

def compute_hurst_exponent(returns: pd.Series, window: int, min_periods: int = None) -> float:
    """Simple rescaled range (R/S) Hurst proxy for Point 59."""
    if len(returns) < 10:
        return 0.5
    r = returns.tail(window).dropna()
    if len(r) < 5:
        return 0.5
    # Cumulative deviation
    mean_r = r.mean()
    cum_dev = (r - mean_r).cumsum()
    R = cum_dev.max() - cum_dev.min()
    S = r.std()
    if S <= 0:
        return 0.5
    rs = R / S
    # Rough Hurst (log(R/S) / log(n) approx, clipped)
    n = len(r)
    h = np.log(rs) / np.log(n) if rs > 0 and n > 1 else 0.5
    return float(np.clip(h, 0.0, 1.0))

def compute_dfa_vol_scaling(returns: pd.Series, window: int, scale: float = 1.0, min_periods: int = None) -> float:
    """Simplified DFA fluctuation for Point 58 volatility scaling."""
    if len(returns) < 10:
        return compute_close_to_close_vol(returns, window, min_periods)
    r = returns.tail(window).dropna().values
    n = len(r)
    # Simple box detrend fluctuation (very basic DFA proxy)
    box_size = max(2, n // 4)
    fluct = 0.0
    for i in range(0, n - box_size, box_size):
        box = r[i:i+box_size]
        x = np.arange(len(box))
        # Linear detrend
        p = np.polyfit(x, box, 1)
        trend = np.polyval(p, x)
        detrended = box - trend
        fluct += np.mean(detrended ** 2)
    if fluct <= 0:
        return compute_close_to_close_vol(returns, window, min_periods)
    f = np.sqrt(fluct / max(1, (n // box_size)))
    vol = compute_close_to_close_vol(returns, window, min_periods) * (f ** scale)
    return float(vol)

def compute_integrated_var_high_freq(close: pd.Series, count: pd.Series, window: int, min_periods: int = None) -> float:
    """Proxy for high-freq integrated variance using count as intensity (Point 55)."""
    if len(close) < 2:
        return np.nan
    r = _log_returns(close)
    c = pd.to_numeric(count, errors="coerce").fillna(1.0)
    mp = min_periods or max(2, window // 2)
    # RV scaled by intensity (more trades -> higher resolution)
    rv = (r ** 2).rolling(window, min_periods=mp).mean()
    intensity = (c / (c.rolling(window, min_periods=mp).mean() + 1e-12)).clip(0.5, 2.0)
    iv = (rv * intensity).iloc[-1]
    return float(iv) if pd.notna(iv) else np.nan

def compute_realized_kernel_with_jump(close: pd.Series, window: int, jump_threshold: float = 2.0, min_periods: int = None) -> dict:
    """Proxy realized kernel + jump component using range/bipower (Point 60)."""
    if len(close) < 3:
        return {"cont": 0.0, "jump": 0.0}
    r = _log_returns(close)
    mp = min_periods or max(3, window // 2)
    rv = (r ** 2).rolling(window, min_periods=mp).sum().iloc[-1]
    # Bipower variation proxy for continuous
    bip = (np.abs(r) * np.abs(r.shift(1))).rolling(window, min_periods=mp).mean().iloc[-1] * np.pi / 2
    cont = max(0.0, bip)
    jump = max(0.0, rv - cont)
    if jump > jump_threshold * cont:
        jump = jump_threshold * cont  # cap
    return {"cont": float(cont), "jump": float(jump)}


def compute_adaptive_cycle_window(
    price_series: pd.Series,
    cycle_window: int,
    alpha: float,
    min_lb: int,
    max_lb: int,
) -> int:
    """
    Practical proxy for Point 08 "EMD IMF wavelength".

    Uses recent price excursion range normalized by volatility as proxy for dominant cycle length.
    W_adaptive = round( alpha * (recent_range / recent_vol + 1) * base_proxy )
    Falls back to simple scaling when data is thin.
    """
    if len(price_series) < 5:
        return min_lb

    recent = price_series.tail(cycle_window).dropna()
    if len(recent) < 3:
        return min_lb

    recent_range = recent.max() - recent.min()
    recent_vol = recent.std()
    if recent_vol <= 0:
        recent_vol = 1e-8

    # Proxy wavelength: how far price travels relative to its noise
    cycle_proxy = recent_range / recent_vol
    w = int(round(alpha * cycle_proxy * (cycle_window / 2.0)))
    return max(min_lb, min(w, max_lb))


# ---------------------------------------------------------------------
# Tail Risk & Robust Statistics Utilities (for Points 61,64,66,69,70)
# ---------------------------------------------------------------------

def compute_rolling_skewness(returns: pd.Series, window: int, min_periods: int = None) -> float:
    """Rolling Fisher skewness (gamma1)."""
    if len(returns) < 3:
        return 0.0
    mp = min_periods or max(3, window // 2)
    r = returns.tail(window).dropna()
    if len(r) < mp:
        return 0.0
    mu = r.mean()
    sigma = r.std()
    if sigma <= 0:
        return 0.0
    skew = ((r - mu) ** 3).mean() / (sigma ** 3)
    return float(skew)

def compute_rolling_kurtosis(returns: pd.Series, window: int, min_periods: int = None) -> float:
    """Rolling Fisher kurtosis (gamma2, excess)."""
    if len(returns) < 4:
        return 0.0
    mp = min_periods or max(4, window // 2)
    r = returns.tail(window).dropna()
    if len(r) < mp:
        return 0.0
    mu = r.mean()
    sigma = r.std()
    if sigma <= 0:
        return 0.0
    kurt = ((r - mu) ** 4).mean() / (sigma ** 4) - 3.0
    return float(kurt)

def compute_huber_robust_mean(returns: pd.Series, c: float = 1.345) -> float:
    """
    Huber M-estimator for robust location (mean).
    Solves sum psi( (r - mu)/s ) = 0 where psi is the Huber function.
    Simple iterative implementation for the latest value.
    """
    if len(returns) < 2:
        return returns.mean() if len(returns) > 0 else 0.0
    r = pd.to_numeric(returns, errors="coerce").dropna().values
    if len(r) < 2:
        return 0.0
    # Robust scale (MAD)
    med = np.median(r)
    mad = np.median(np.abs(r - med)) * 1.4826 + 1e-12
    # Iterative reweighted
    mu = med
    for _ in range(10):
        u = (r - mu) / mad
        psi = np.where(np.abs(u) <= c, u, c * np.sign(u))
        w = np.where(np.abs(u) <= c, 1.0, c / np.abs(u))
        mu_new = np.sum(w * r) / np.sum(w)
        if abs(mu_new - mu) < 1e-8:
            break
        mu = mu_new
    return float(mu)

def compute_tail_var_es(returns: pd.Series, confidence: float = 0.95, window: int = 50, min_periods: int = None) -> dict:
    """
    Causal rolling VaR and ES (Expected Shortfall).
    VaR_alpha = -quantile(alpha)
    ES_alpha = -mean( returns | returns <= VaR )
    Returns dict with 'var' and 'es' (positive loss convention).
    """
    if len(returns) < 5:
        return {"var": 0.02, "es": 0.03}
    mp = min_periods or max(5, window // 2)
    r = returns.tail(window).dropna()
    if len(r) < mp:
        return {"var": 0.02, "es": 0.03}
    # Negative for losses
    q = np.quantile(r, 1 - confidence)
    var = -q
    tail = r[r <= q]
    if len(tail) > 0:
        es = -tail.mean()
    else:
        es = var * 1.2  # conservative
    return {"var": float(max(var, 0.0)), "es": float(max(es, var))}

def compute_evt_gpd_tail(returns: pd.Series, threshold_q: float = 0.95, window: int = 100, min_periods: int = None) -> float:
    """
    Very simplified EVT tail scale using exceedances over quantile.
    Approximates GPD scale (beta) for tail risk adjustment.
    For full GPD shape/scale fitting one would use MLE, here we use a moment proxy.
    Returns an adjusted tail volatility proxy.
    """
    if len(returns) < 10:
        return 0.02
    mp = min_periods or max(10, window // 2)
    r = returns.tail(window).dropna()
    if len(r) < mp:
        return 0.02
    thresh = np.quantile(r, threshold_q)
    excesses = r[r < thresh] - thresh   # left tail (negative returns)
    if len(excesses) < 3:
        return 0.02
    # Simple moment estimator for GPD beta (scale) assuming xi ~ 0.2 from config
    beta_proxy = -excesses.mean()   # positive scale
    base_vol = compute_close_to_close_vol(returns, window, min_periods)
    # Rough tail adjustment: inflate by beta / (1 - xi) kind of factor
    tail_adj = base_vol * (1 + 0.5 * (beta_proxy / 0.01))  # heuristic scaling
    return float(max(tail_adj, base_vol))


# ---------------------------------------------------------------------
# Microstructure & Order Flow Utilities (for Points 17,19,21,22,25,26)
# ---------------------------------------------------------------------

def compute_corwin_schultz_spread(high: pd.Series, low: pd.Series, window: int = 2, min_periods: int = None) -> float:
    """
    Corwin-Schultz high-low spread estimator (Point 17).
    Uses two consecutive bars.
    """
    if len(high) < 2 or len(low) < 2:
        return 0.001  # small default spread
    mp = min_periods or 2
    h1 = high.tail(2)
    l1 = low.tail(2)
    if len(h1) < 2:
        return 0.001
    gamma = (np.log(h1.iloc[0] / l1.iloc[0]))**2 + (np.log(h1.iloc[1] / l1.iloc[1]))**2
    beta = (np.log(h1.iloc[0] / l1.iloc[0]))**2
    alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / (3 - 2 * np.sqrt(2))
    spread = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
    return float(max(spread, 0.0))

def compute_beta_cdf_wick_exhaustion(high: pd.Series, low: pd.Series, open_: pd.Series, close: pd.Series, 
                                     alpha: float = 2.0, beta: float = 5.0, window: int = 20, min_periods: int = None) -> float:
    """
    Rolling non-parametric Beta-CDF mapping for wick exhaustion (Point 19).
    Uses scipy if available, otherwise a simple normalized rank as proxy.
    Wick ratio = (upper_wick + lower_wick) / range
    """
    if len(high) < 2:
        return 0.5
    try:
        from scipy.stats import beta as beta_dist
        use_scipy = True
    except ImportError:
        use_scipy = False

    mp = min_periods or max(5, window // 2)
    h = pd.to_numeric(high, errors="coerce")
    l = pd.to_numeric(low, errors="coerce")
    o = pd.to_numeric(open_, errors="coerce")
    c = pd.to_numeric(close, errors="coerce")

    body = (c - o).abs()
    upper_wick = h - pd.concat([c, o], axis=1).max(axis=1)
    lower_wick = pd.concat([c, o], axis=1).min(axis=1) - l
    wick_ratio = (upper_wick + lower_wick) / (h - l + 1e-12)

    recent = wick_ratio.tail(window).dropna()
    if len(recent) < mp:
        return 0.5

    current = recent.iloc[-1]
    if use_scipy:
        cdf_val = beta_dist.cdf(current, alpha, beta)
    else:
        # Fallback: empirical rank
        cdf_val = (recent <= current).sum() / len(recent)

    return float(np.clip(cdf_val, 0.0, 1.0))

def compute_spread_weighted_absorption(taker_buy: pd.Series, volume: pd.Series, 
                                       high: pd.Series, low: pd.Series, close: pd.Series,
                                       spread: pd.Series, window: int = 20, min_periods: int = None) -> float:
    """
    Spread-weighted directional delta absorption (Point 22).
    """
    if len(volume) < 2:
        return 0.0
    mp = min_periods or max(5, window // 2)

    tbv = pd.to_numeric(taker_buy, errors="coerce")
    v = pd.to_numeric(volume, errors="coerce")
    h = pd.to_numeric(high, errors="coerce")
    l = pd.to_numeric(low, errors="coerce")
    c = pd.to_numeric(close, errors="coerce")
    s = pd.to_numeric(spread, errors="coerce").fillna(0.001)

    range_ = (h - l + 1e-12)
    buy_weight = (c - l) / range_
    sell_weight = (h - c) / range_

    abs_delta = tbv * buy_weight - (v - tbv) * sell_weight
    weighted = (abs_delta / (s * v + 1e-12)).rolling(window, min_periods=mp).mean().iloc[-1]
    return float(weighted) if pd.notna(weighted) else 0.0

def compute_entropy_adaptive_lambda(count_series: pd.Series, base_lambda: float = 0.1, 
                                    window: int = 24, min_periods: int = None) -> float:
    """
    Information-entropy adaptive memory half-life (Point 25).
    lambda_t = base * [1 - normalized_entropy]
    """
    if len(count_series) < 5:
        return base_lambda
    mp = min_periods or max(5, window // 2)
    recent = pd.to_numeric(count_series, errors="coerce").tail(window).dropna()
    if len(recent) < mp:
        return base_lambda

    # Simple entropy of binned counts (or use value counts for discrete)
    hist, _ = np.histogram(recent, bins=10)
    p = hist / hist.sum() + 1e-12
    entropy = -np.sum(p * np.log(p))
    max_entropy = np.log(len(p))
    norm_entropy = entropy / max_entropy if max_entropy > 0 else 0.5

    lam = base_lambda * (1 - norm_entropy * 0.8)  # dampen
    return float(max(0.01, min(lam, 0.5)))

def compute_cauchy_proximity_kernel(distance: float, gamma: float = 0.01) -> float:
    """
    Continuous Cauchy proximity kernel (Point 26).
    f(d) = 1 / (pi * gamma * (1 + (d / gamma)^2 ))
    """
    if gamma <= 0:
        gamma = 0.01
    val = 1.0 / (np.pi * gamma * (1 + (distance / gamma)**2 ))
    return float(val)


# ---------------------------------------------------------------------
# Validation, Purging & Causality Utilities (for Points 35,79,80,82,90)
# These are more infrastructure-oriented but still follow the sovereignty pattern.
# ---------------------------------------------------------------------

def get_purged_embargo_indices(
    train_indices: pd.Index,
    test_start: int,
    test_end: int,
    horizon: int,
    embargo: int = 0,
    return_mask: bool = False,
) -> pd.Index:
    """
    Strict purging & embargoing for label-based cross-validation (Point 35 / 79).

    Given a set of training indices (integer positions), a test window
    [test_start, test_end), and a labeling horizon + embargo, returns the
    subset of training indices that MUST be purged because their forward-looking
    labels overlap with the test window.

    Purge rule:
        Training sample at position i whose label covers [i, i+horizon] is purged
        if that interval overlaps with the test window: i + horizon >= test_start.

    Embargo rule:
        An additional `embargo` bars after the test boundary are also excluded.
        So: i + horizon + embargo > test_start is the full purge condition.

    This is the "purge_boundary = t_event + horizon + embargo" formula from the
    Lopez de Prado combinatorial purging framework.

    NOTE: This function assumes train_indices are BEFORE test_start (standard
    walk-forward). For CPCV with interleaved blocks, use the per-path purging
    logic in point_79.py, which calls this per-block-combination.

    Parameters
    ----------
    train_indices : pd.Index
        Integer index positions of candidate training samples (assumed < test_start).
    test_start : int
        Start of test window (integer position).
    test_end : int
        End of test window (integer position, used for validation if assert_mode=True).
    horizon : int
        Number of forward bars the label covers.
    embargo : int
        Additional embargo bars after test window.
    return_mask : bool
        If True, returns a boolean mask for train_indices, else returns purged indices.

    Returns
    -------
    pd.Index or np.ndarray
        Purged indices (subset of train_indices) or boolean mask.
    """
    if len(train_indices) == 0:
        return pd.Index([]) if not return_mask else np.array([], dtype=bool)

    # Convert to numpy for speed
    idx_arr = np.asarray(train_indices)

    # Purging boundary: any training label whose horizon + embargo reaches into test
    purge_boundary = test_start - horizon - embargo

    # Training indices BEFORE purge_boundary are safe
    # Training indices AT or AFTER purge_boundary must be purged
    purge_mask = idx_arr >= purge_boundary

    # Validate: ensure train indices are before test_end
    if np.any(idx_arr >= test_end):
        _logger.warning(
            "get_purged_embargo_indices: %d train indices are >= test_end=%d. "
            "This function assumes train < test_end for simple CV. "
            "For interleaved CPCV, use per-path purging.",
            int((idx_arr >= test_end).sum()), test_end
        )

    if return_mask:
        return purge_mask
    else:
        return pd.Index(idx_arr[purge_mask])


def generate_cpcv_paths(n_blocks: int, k_test: int) -> list:
    """
    Combinatorial Purged Cross-Validation (CPCV) path generation (Point 79).
    Returns list of (train_block_indices, test_block_indices) tuples.
    S = {Combinations of N blocks taken k at a time}
    """
    from itertools import combinations
    blocks = list(range(n_blocks))
    paths = []
    for test_blocks in combinations(blocks, k_test):
        test_set = set(test_blocks)
        train_set = set(blocks) - test_set
        paths.append((sorted(train_set), sorted(test_set)))
    return paths


def deflated_sharpe_ratio(
    sharpe: float,
    n_trials: int,
    t: int,
    skew: float = 0.0,
    kurt: float = 3.0,
    confidence: float = 0.95,
) -> float:
    """
    Deflated Sharpe Ratio (DSR) adjustment (Point 80).
    Simplified implementation of the DSR formula from Bailey et al.
    """
    # Approximate variance of Sharpe under non-normality
    var_sharpe = (1 - skew * sharpe + (kurt - 1) * (sharpe**2) / 4.0) / t
    if var_sharpe <= 0:
        var_sharpe = 1e-8
    # Expected max Sharpe under multiple testing (very rough approximation)
    emax = np.sqrt(2 * np.log(n_trials)) * np.sqrt(var_sharpe)
    dsr = sharpe - emax
    return float(dsr)


def causal_lag_cross_sectional(
    local_feature: pd.Series,
    cross_sectional_features: pd.DataFrame,
    lag: int = 1,
) -> pd.DataFrame:
    """
    Causally Lagged Cross-Sectional Information Flows (Point 82).
    All cross-sectional info must be strictly lagged by `lag` bars relative to local time.
    """
    if lag < 1:
        lag = 1
    lagged = cross_sectional_features.shift(lag)
    # Combine with local (local is at t, global at t-lag)
    result = pd.concat([local_feature.rename("local"), lagged], axis=1).dropna()
    return result


def monte_carlo_deflated_sharpe_paths(
    returns: pd.Series,
    n_paths: int = 1000,
    n_trials: int = 100,
    confidence: float = 0.95,
    block_size: int = 20,
) -> dict:
    """
    Monte Carlo Path Deflated Sharpe Ratio Evaluations (Point 90).
    Generates synthetic paths (block bootstrap) and computes DSR distribution.
    """
    if len(returns) < block_size * 2:
        return {"dsr_mean": 0.0, "dsr_std": 0.0, "prob_positive": 0.0}

    n = len(returns)
    n_blocks = n // block_size
    dsrs = []

    for _ in range(n_paths):
        # Block bootstrap
        indices = np.random.randint(0, n_blocks, size=n_blocks) * block_size
        path_indices = np.concatenate([np.arange(i, min(i + block_size, n)) for i in indices])
        if len(path_indices) > n:
            path_indices = path_indices[:n]
        path_rets = returns.iloc[path_indices % n].values  # wrap around safely
        path_sharpe = (path_rets.mean() / (path_rets.std() + 1e-12)) * np.sqrt(252 * 24)  # rough 1h annualization
        dsr = deflated_sharpe_ratio(path_sharpe, n_trials, len(path_rets), confidence=confidence)
        dsrs.append(dsr)

    dsrs = np.array(dsrs)
    return {
        "dsr_mean": float(dsrs.mean()),
        "dsr_std": float(dsrs.std()),
        "prob_positive": float((dsrs > 0).mean()),
    }


# ---------------------------------------------------------------------
# Operational & Execution Utilities (for Points 91-95, 100)
# Shared execution modeling components for realistic backtesting & live trading.
# All functions are config-driven and sovereignty-compliant.
# ---------------------------------------------------------------------

def resolve_os_agnostic_path(
    env_var: str,
    fallback_path: str,
    relative_segments: Optional[list] = None,
) -> str:
    """
    OS-agnostic path resolution (Point 91).
    Resolves paths using environment variables with POSIX-normalized fallback.
    """
    import os
    from pathlib import Path, PurePosixPath

    base = os.environ.get(env_var, "")
    if not base:
        # Try to resolve from project root heuristic
        base = fallback_path

    base = str(PurePosixPath(base))
    if relative_segments:
        base = str(PurePosixPath(base).joinpath(*relative_segments))

    resolved = Path(base)
    return str(resolved)


def compute_system_memory_available_gb() -> float:
    """
    Compute available system memory in GB (Point 92).
    Uses psutil if available, else falls back to a conservative estimate.
    """
    try:
        import psutil
        mem = psutil.virtual_memory()
        return mem.available / (1024 ** 3)
    except ImportError:
        pass
    # Fallback: try /proc/meminfo on Linux
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if "MemAvailable" in line:
                    kb = int(line.split()[1])
                    return kb / (1024 ** 2)
    except Exception:
        pass
    return 4.0  # conservative fallback (config override in point_92)

def compute_adaptive_shard_size(
    base_shard: int,
    min_shard: int,
    max_shard: int,
    safety_factor: float = 0.6,
    memory_per_shard_mb: float = 50.0,
) -> int:
    """
    Dynamic compute-aware shard size allocation (Point 92).
    Shard_Size_t = round(System_Memory_available * safety_factor / memory_per_shard)
    """
    avail_gb = compute_system_memory_available_gb()
    avail_mb = avail_gb * 1024.0
    max_from_memory = int(avail_mb * safety_factor / max(memory_per_shard_mb, 1.0))
    # Use the base as starting point, clip to memory-aware bounds
    adaptive = min(base_shard, max_from_memory)
    return max(min_shard, min(adaptive, max_shard))

def compute_latency_slippage_modifier(
    signal_price: float,
    volatility: float,
    latency_bars: float,
    base_slippage_bps: float,
    vol_scale_factor: float,
    max_slippage_bps: float,
) -> dict:
    """
    Estimated execution delay latency slippage modifier (Point 93).
    P_executed = P_signal + sigma * Delta_t_delay
    Returns dict with adjusted price and slippage in bps.
    """
    if not np.isfinite(signal_price) or signal_price <= 0:
        return {"executed_price": signal_price, "slippage_bps": base_slippage_bps, "slippage_type": "fallback"}
    if not np.isfinite(volatility) or volatility < 0:
        volatility = 0.01  # conservative default
    if not np.isfinite(latency_bars) or latency_bars < 0:
        latency_bars = 0.0

    # Volatility-driven slippage: sigma * sqrt(latency) in price terms
    vol_slippage = volatility * np.sqrt(max(latency_bars, 0.0)) * vol_scale_factor
    # Total slippage in bps
    total_slippage_bps = base_slippage_bps + (vol_slippage / max(signal_price, 1e-12)) * 10000.0
    total_slippage_bps = min(total_slippage_bps, max_slippage_bps)
    slippage_price = signal_price * (total_slippage_bps / 10000.0)
    executed_price = signal_price + slippage_price  # conservative: always worse
    return {
        "executed_price": float(executed_price),
        "slippage_bps": float(total_slippage_bps),
        "slippage_type": "latency_vol_adjusted",
    }

def compute_dynamic_execution_cost(
    base_fee_bps: float,
    spread: float,
    order_size_usd: float,
    volume_usd: float,
    fee_scale_factor: float,
    max_fee_bps: float,
    min_volume_ratio: float = 0.001,
) -> dict:
    """
    Spread-scaled dynamic execution cost model (Point 94).
    Cost_t = Fee_base + delta_t * Spread_t + market_impact
    """
    if not np.isfinite(base_fee_bps):
        base_fee_bps = 10.0  # conservative
    if not np.isfinite(spread) or spread < 0:
        spread = 0.001
    if not np.isfinite(volume_usd) or volume_usd <= 0:
        volume_usd = 1e6

    # Spread-scaled component
    spread_cost_bps = (spread / max(min_volume_ratio, 1e-6)) * fee_scale_factor * 10000.0

    # Market impact component (simplified square-root model)
    participation_rate = order_size_usd / max(volume_usd, 1.0)
    impact_bps = fee_scale_factor * np.sqrt(participation_rate) * 10000.0

    total_cost_bps = base_fee_bps + spread_cost_bps + impact_bps
    total_cost_bps = min(total_cost_bps, max_fee_bps)

    return {
        "total_cost_bps": float(total_cost_bps),
        "base_fee_bps": float(base_fee_bps),
        "spread_cost_bps": float(spread_cost_bps),
        "impact_bps": float(impact_bps),
    }

def compute_twap_execution_price(
    bar_opens: pd.Series,
    bar_closes: pd.Series,
    n_slices: int,
    spread: float,
    min_slices: int = 1,
) -> dict:
    """
    Time-Weighted Average Price (TWAP) execution model (Point 95).
    Disperses fills over a localized sessional window.
    P_TWAP = 1/N * sum P_i for i=1 to N
    """
    if len(bar_opens) < 1 or len(bar_closes) < 1:
        return {"twap_price": np.nan, "vs_close": 0.0, "vs_open": 0.0}

    n_slices = max(min_slices, n_slices)
    n_bars = len(bar_opens)

    # Interpolate between open and close to simulate intra-bar fills
    fill_prices = []
    for i in range(min(n_slices, n_bars)):
        # Fraction along the bar (uniform for TWAP)
        t = (i + 0.5) / n_slices
        o = float(bar_opens.iloc[i]) if pd.notna(bar_opens.iloc[i]) else 0.0
        c = float(bar_closes.iloc[i]) if pd.notna(bar_closes.iloc[i]) else o
        fill = o + t * (c - o)  # linear interpolation
        # Add half-spread as execution cost
        fill += abs(spread) / 2.0 * fill
        fill_prices.append(fill)

    if not fill_prices:
        return {"twap_price": np.nan, "vs_close": 0.0, "vs_open": 0.0}

    twap = float(np.mean(fill_prices))
    ref_close = float(bar_closes.iloc[-1])
    ref_open = float(bar_opens.iloc[0])

    return {
        "twap_price": twap,
        "vs_close": float((twap - ref_close) / max(abs(ref_close), 1e-12)),
        "vs_open": float((twap - ref_open) / max(abs(ref_open), 1e-12)),
        "n_fills": len(fill_prices),
    }

def compute_impact_aware_position_size(
    target_risk_usd: float,
    volatility: float,
    spread: float,
    volume_usd: float,
    lambda_impact: float,
    max_position_pct: float,
    min_position_usd: float,
    portfolio_value_usd: float,
) -> dict:
    """
    Impact-aware adaptive position sizing (Point 100).
    Size_t = Target_Risk / (sigma_t * (1 + lambda * Estimated_Impact_t))
    """
    if not np.isfinite(volatility) or volatility <= 0:
        volatility = 0.01
    if not np.isfinite(spread) or spread < 0:
        spread = 0.001
    if not np.isfinite(volume_usd) or volume_usd <= 0:
        volume_usd = 1e6
    if not np.isfinite(target_risk_usd) or target_risk_usd <= 0:
        return {"position_size_usd": min_position_usd, "impact_adjustment": 1.0}

    # Estimated impact: spread-based (spread is a fraction, e.g. 0.001 = 10bps)
    # Volume impact term normalized to bps scale for consistency
    vol_impact_bps = 10000.0 / max(volume_usd, 1.0)  # volume-based impact in bps
    estimated_impact = lambda_impact * (spread + vol_impact_bps / 10000.0)
    impact_adjustment = 1.0 + lambda_impact * estimated_impact

    # Position size inversely proportional to vol * impact
    raw_size = target_risk_usd / (volatility * impact_adjustment)
    raw_size = max(min_position_usd, raw_size)

    # Cap as percentage of portfolio
    max_size = portfolio_value_usd * max_position_pct
    size = min(raw_size, max_size)

    return {
        "position_size_usd": float(size),
        "impact_adjustment": float(impact_adjustment),
        "estimated_impact": float(estimated_impact),
        "raw_size_usd": float(raw_size),
    }


# ---------------------------------------------------------------------
# Remaining Batch A Utilities (Points 03, 05, 06, 07, 10, 12, 13, 15, 16, 18, 20, 23, 24)
# Spatial, sampling, microstructure, and statistical processing utilities.
# ---------------------------------------------------------------------

def compute_svd_bottleneck_compression(
    vector_matrix: np.ndarray,
    n_components: int,
    noise_std: float = 0.01,
) -> dict:
    """
    SVD-Based Orthogonal Bottleneck Compression (Point 03).
    Compress replicated neural_conv vector down to true mathematical rank.
    X_compressed = X @ W_ortho[:, :k] @ W_ortho[:, :k].T
    """
    if vector_matrix.size == 0 or vector_matrix.ndim < 2:
        return {"compressed": vector_matrix, "n_components": 0, "variance_explained": 0.0}

    n_rows, n_cols = vector_matrix.shape
    k = min(n_components, n_cols, n_rows)
    if k < 1:
        return {"compressed": vector_matrix, "n_components": 0, "variance_explained": 0.0}

    try:
        U, S, Vt = np.linalg.svd(vector_matrix, full_matrices=False)
        # Variance explained by top k components
        total_var = np.sum(S ** 2)
        k_var = np.sum(S[:k] ** 2) if k > 0 else 0.0
        var_explained = float(k_var / max(total_var, 1e-12))
        # Compress: project onto top-k right singular vectors
        W_k = Vt[:k, :]  # (k, n_cols)
        compressed = vector_matrix @ W_k.T @ W_k  # (n_rows, n_cols)
        # Add small noise to break degeneracy in clustering
        if noise_std > 0 and compressed.size > 0:
            rng = np.random.RandomState(42)  # deterministic seed for reproducibility
            compressed += rng.normal(0, noise_std * np.std(compressed), compressed.shape)
    except np.linalg.LinAlgError:
        compressed = vector_matrix
        var_explained = 0.0
        k = 0

    return {"compressed": compressed, "n_components": k, "variance_explained": var_explained}


def compute_volume_density_window(
    volume_series: pd.Series,
    target_multiplier: float,
    min_window: int,
    max_window: int,
    min_periods: int = 10,
) -> int:
    """
    Synthetic Quote Volume-Imbalance Aggregation (Point 05).
    W_t = min { k | sum Q_{t-i} >= median({Q_tau}) * target_multiplier }
    Finds the smallest window that accumulates enough volume.
    """
    v = pd.to_numeric(volume_series, errors="coerce").dropna()
    if len(v) < min_periods:
        return min_window

    median_vol = float(v.median())
    if median_vol <= 0:
        return min_window

    target_total = median_vol * target_multiplier
    cumsum = v.cumsum().values

    # Find minimum window where cumulative volume >= target
    for w in range(min_window, min(max_window + 1, len(v) + 1)):
        # Sum of last w bars
        window_sum = cumsum[-1] - (cumsum[-w - 1] if w < len(cumsum) else 0.0)
        if window_sum >= target_total:
            return w

    return max_window


def compute_amihud_continuous_decay(
    close: pd.Series,
    open_: pd.Series,
    volume: pd.Series,
    window: int,
    lambda_decay: float,
    min_periods: int = None,
) -> float:
    """
    Continuous Amihud Decay Adjuster (Point 06).
    Illiq = sum |ln(C/O)| / (24*Q + eps)
    w = e^(-lambda * Illiq)
    Returns the continuous decay weight in [0, 1].
    """
    c = pd.to_numeric(close, errors="coerce")
    o = pd.to_numeric(open_, errors="coerce")
    v = pd.to_numeric(volume, errors="coerce")
    mp = min_periods or max(5, window // 2)

    recent_c = c.tail(window).dropna()
    recent_o = o.tail(window).dropna()
    recent_v = v.tail(window).dropna()
    n = min(len(recent_c), len(recent_o), len(recent_v))
    if n < mp:
        return 1.0  # neutral weight when insufficient data

    recent_c = recent_c.iloc[-n:]
    recent_o = recent_o.iloc[-n:]
    recent_v = recent_v.iloc[-n:]

    abs_ret = np.abs(np.log((recent_c / recent_o).clip(lower=1e-12)))
    vol_sum = recent_v.sum() + 1e-12
    illiq = float(abs_ret.sum() / (n * vol_sum + 1e-12))
    weight = np.exp(-lambda_decay * illiq)
    return float(np.clip(weight, 0.0, 1.0))


def compute_parsimonious_polynomial_map(
    X: np.ndarray,
    y: np.ndarray,
    max_degree: int,
    alpha_parsimony: float,
    min_samples: int = 20,
) -> dict:
    """
    GP-Evolved Parsimonious Polynomial Mapping (Point 07) — practical approximation.
    Uses polynomial feature expansion with BIC-based parsimony penalty
    to find the optimal low-degree polynomial mapping.
    f(X)_GP s.t. min[MSE + alpha * AIC(f)]
    """
    if X.size == 0 or y.size == 0 or len(X) < min_samples:
        return {"coeffs": np.array([0.0]), "degree": 0, "bic": np.inf, "predictions": np.zeros_like(y)}

    X_flat = np.asarray(X, dtype=float).ravel()
    y_flat = np.asarray(y, dtype=float).ravel()
    n = len(y_flat)

    best_bic = np.inf
    best_coeffs = np.array([np.mean(y_flat)])
    best_degree = 0

    for deg in range(1, max_degree + 1):
        try:
            # Polynomial feature matrix [1, x, x^2, ..., x^deg]
            Phi = np.column_stack([X_flat ** d for d in range(deg + 1)])
            # OLS fit
            coeffs, residuals, _, _ = np.linalg.lstsq(Phi, y_flat, rcond=None)
            if len(residuals) > 0:
                mse = float(residuals[0]) / max(n, 1)
            else:
                y_hat = Phi @ coeffs
                mse = float(np.mean((y_flat - y_hat) ** 2))

            # BIC = n * ln(MSE) + k * ln(n)
            k = deg + 1  # number of parameters
            bic = n * np.log(max(mse, 1e-12)) + alpha_parsimony * k * np.log(max(n, 2))

            if bic < best_bic:
                best_bic = bic
                best_coeffs = coeffs
                best_degree = deg
        except np.linalg.LinAlgError:
            continue

    # Generate predictions with best model
    Phi_best = np.column_stack([X_flat ** d for d in range(best_degree + 1)])
    predictions = Phi_best @ best_coeffs

    return {
        "coeffs": best_coeffs,
        "degree": best_degree,
        "bic": float(best_bic),
        "predictions": predictions,
    }


def compute_timestamp_latency_truncation(
    bar_timestamps: pd.Series,
    base_latency_ms: float,
    latency_window: int,
    min_periods: int = None,
    latency_tolerance: float = 0.15,
) -> dict:
    """
    Systemic Timestamp Latency Truncation (Point 10).
    Truncate = I[SystemTime - CT >= tau_measured_latency]
    Returns truncation mask and measured latency stats.
    """
    ts = pd.to_numeric(bar_timestamps, errors="coerce")
    mp = min_periods or max(5, latency_window // 2)

    if len(ts) < mp:
        return {
            "truncate_mask": pd.Series(False, index=bar_timestamps.index),
            "measured_latency_ms": base_latency_ms,
            "threshold_ms": base_latency_ms,
        }

    # Compute inter-bar gaps as proxy for system latency
    gaps = ts.diff().dropna()
    if len(gaps) < mp:
        return {
            "truncate_mask": pd.Series(False, index=bar_timestamps.index),
            "measured_latency_ms": base_latency_ms,
            "threshold_ms": base_latency_ms,
        }

    measured_median = float(gaps.median())
    if measured_median <= 0:
        measured_median = base_latency_ms
    # Threshold: median gap * (1 + tolerance) — detects stale/delayed bars
    # base_latency_ms acts as absolute floor for very sparse data
    threshold = max(base_latency_ms, measured_median * (1.0 + latency_tolerance))

    # Truncate bars where gap exceeds threshold (proxy for stale/delayed data)
    gap_mask = gaps > threshold
    truncate_mask = pd.Series(False, index=bar_timestamps.index)
    truncate_mask.iloc[1:] = gap_mask.values

    return {
        "truncate_mask": truncate_mask,
        "measured_latency_ms": float(measured_median),
        "threshold_ms": float(threshold),
    }


def compute_variance_mixture_zscore(
    returns: pd.Series,
    short_window: int,
    long_window: int,
    min_periods: int = None,
) -> float:
    """
    Continuous Variance Mixture Z-Scores (Point 12).
    Vol_Z = (sigma_short^2 - mu) / sigma_long
    """
    r = pd.to_numeric(returns, errors="coerce").dropna()
    mp = min_periods or max(5, max(short_window, long_window) // 2)
    if len(r) < mp:
        return 0.0

    r_short = r.tail(short_window)
    r_long = r.tail(long_window)

    var_short = float(r_short.var()) if len(r_short) >= 3 else 0.0
    var_long = float(r_long.var()) if len(r_long) >= 3 else 1e-8
    mu_var = float(r_long.rolling(long_window, min_periods=mp).var().iloc[-1]) if len(r_long) >= mp else var_long

    denom = max(np.sqrt(max(var_long, 1e-12)), 1e-8)
    zscore = (var_short - mu_var) / denom
    return float(np.clip(zscore, -10.0, 10.0))


def compute_trade_intensity_imbalance(
    taker_buy_volume: pd.Series,
    total_volume: pd.Series,
    trade_count: pd.Series,
    window: int,
    min_periods: int = None,
) -> float:
    """
    Trade-Intensity Weighted Imbalance (Point 13).
    OFI = (TBV - (V - TBV)) * ln(V / Count + eps)
    """
    tbv = pd.to_numeric(taker_buy_volume, errors="coerce")
    v = pd.to_numeric(total_volume, errors="coerce")
    cnt = pd.to_numeric(trade_count, errors="coerce")
    mp = min_periods or max(5, window // 2)

    recent_tbv = tbv.tail(window).dropna()
    recent_v = v.tail(window).dropna()
    recent_cnt = cnt.tail(window).dropna()
    n = min(len(recent_tbv), len(recent_v), len(recent_cnt))
    if n < mp:
        return 0.0

    recent_tbv = recent_tbv.iloc[-n:]
    recent_v = recent_v.iloc[-n:]
    recent_cnt = recent_cnt.iloc[-n:]

    buy_vol = recent_tbv
    sell_vol = (recent_v - recent_tbv).clip(lower=0)
    imbalance = buy_vol - sell_vol
    # Trade intensity scaling: ln(Volume / Count + eps)
    avg_trade_size = (recent_v / (recent_cnt + 1.0))
    intensity = np.log(avg_trade_size.clip(lower=1.0))
    weighted_imbalance = (imbalance * intensity).mean()
    return float(weighted_imbalance) if np.isfinite(weighted_imbalance) else 0.0


def compute_skewness_weighted_barriers(
    returns: pd.Series,
    phi_base: float,
    skew_window: int,
    min_periods: int = None,
) -> dict:
    """
    Skewness-Weighted Asymmetric Barriers (Point 15).
    Barrier_upper = phi * sigma_t * (1 + gamma_skew,t)
    Barrier_lower = -phi * sigma_t * (1 - gamma_skew,t)
    """
    r = pd.to_numeric(returns, errors="coerce").dropna()
    mp = min_periods or max(10, skew_window // 2)
    if len(r) < mp:
        return {"barrier_upper": phi_base * 0.01, "barrier_lower": -phi_base * 0.01, "skew": 0.0}

    recent = r.tail(skew_window)
    sigma = float(recent.std())
    skew = compute_rolling_skewness(returns, skew_window, min_periods)
    gamma = skew * 0.5  # scale skewness to moderate its effect

    upper = phi_base * sigma * (1 + gamma)
    lower = -phi_base * sigma * (1 - gamma)

    return {
        "barrier_upper": float(upper),
        "barrier_lower": float(lower),
        "skew": float(skew),
    }


def compute_kde_volume_profile(
    close: pd.Series,
    volume: pd.Series,
    n_price_levels: int,
    bandwidth_factor: float,
    min_periods: int = 10,
) -> dict:
    """
    Gaussian Kernel Density Estimation Volume Profiling (Point 16).
    exp f(P) = sum V_i * exp( - (P - C_i)^2 / (2 * h^2) )
    """
    c = pd.to_numeric(close, errors="coerce").dropna()
    v = pd.to_numeric(volume, errors="coerce").dropna()
    n = min(len(c), len(v))
    if n < min_periods:
        return {"price_levels": np.array([]), "density": np.array([]), "poc": 0.0}

    c = c.iloc[-n:].values
    v = v.iloc[-n:].values

    price_min = float(c.min())
    price_max = float(c.max())
    if price_max <= price_min:
        price_max = price_min + 1e-6

    price_levels = np.linspace(price_min, price_max, n_price_levels)
    # Bandwidth: Silverman-like rule
    h = bandwidth_factor * float(np.std(c)) * (n ** (-1.0 / 5.0))
    h = max(h, 1e-10)

    density = np.zeros(n_price_levels)
    for j, p in enumerate(price_levels):
        kernel_vals = np.exp(-0.5 * ((c - p) / h) ** 2)
        density[j] = float(np.sum(v * kernel_vals))

    # Normalize
    density_sum = density.sum()
    if density_sum > 0:
        density = density / density_sum

    poc_idx = int(np.argmax(density))
    poc = float(price_levels[poc_idx])

    return {
        "price_levels": price_levels,
        "density": density,
        "poc": poc,
    }


def compute_log_volume_zscore(
    volume: pd.Series,
    window: int,
    min_periods: int = None,
) -> float:
    """
    Logarithmic Volume Z-Score Normalization (Point 18).
    V = (ln(Q_t) - mu_ln(Q)) / sigma_ln(Q)
    """
    v = pd.to_numeric(volume, errors="coerce").dropna()
    mp = min_periods or max(5, window // 2)
    if len(v) < mp:
        return 0.0

    recent = v.tail(window)
    log_vol = np.log(recent.clip(lower=1.0))
    mu = float(log_vol.mean())
    sigma = float(log_vol.std())
    if sigma <= 0:
        return 0.0

    current_log = float(log_vol.iloc[-1])
    zscore = (current_log - mu) / sigma
    return float(np.clip(zscore, -5.0, 5.0))


def compute_shannon_count_entropy(
    volume: pd.Series,
    trade_count: pd.Series,
    window: int,
    n_bins: int = 10,
    min_periods: int = None,
) -> float:
    """
    Normalized Shannon Count Entropy (Point 20).
    Entropy_t = - sum (V_i / Count_t) * ln(V_i / Count_t) for i in bins
    Returns normalized entropy in [0, 1].
    """
    v = pd.to_numeric(volume, errors="coerce").dropna()
    cnt = pd.to_numeric(trade_count, errors="coerce").dropna()
    mp = min_periods or max(5, window // 2)
    n = min(len(v), len(cnt))
    if n < mp:
        return 0.5

    recent_v = v.iloc[-window:].values
    recent_cnt = cnt.iloc[-window:].values
    total_cnt = recent_cnt.sum()
    if total_cnt <= 0:
        return 0.5

    # Bin volume into n_bins and compute Shannon entropy of the distribution
    try:
        hist, _ = np.histogram(recent_v, bins=n_bins)
    except ValueError:
        return 0.5
    p = hist / (hist.sum() + 1e-12)
    p = p[p > 0]
    if len(p) < 2:
        return 0.5

    entropy = -np.sum(p * np.log(p))
    max_entropy = np.log(n_bins)
    return float(entropy / max_entropy) if max_entropy > 0 else 0.5


def compute_eigenvalue_covariance_weight(
    returns: pd.Series,
    volume_accel: pd.Series,
    window: int,
    min_periods: int = None,
) -> float:
    """
    Eigenvalue-Driven Covariance Weighting (Point 23).
    Performs rolling PCA on return and volume acceleration.
    w_div,t = lambda_PC1,t / (lambda_PC1,t + lambda_PC2,t)
    """
    r = pd.to_numeric(returns, errors="coerce").dropna()
    va = pd.to_numeric(volume_accel, errors="coerce").dropna()
    mp = min_periods or max(10, window // 2)

    recent_r = r.tail(window)
    recent_va = va.tail(window)
    n = min(len(recent_r), len(recent_va))
    if n < mp:
        return 0.5  # equal weight fallback

    # Align lengths
    recent_r = recent_r.iloc[-n:].values
    recent_va = recent_va.iloc[-n:].values

    # Stack into (n, 2) matrix
    X = np.column_stack([recent_r, recent_va])
    X = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-12)

    try:
        cov = np.cov(X.T)
        eigvals = np.linalg.eigvalsh(cov)
        eigvals = np.sort(eigvals)[::-1]  # descending
        if len(eigvals) < 2 or eigvals.sum() <= 0:
            return 0.5
        # Weight = proportion of variance explained by PC1
        w = float(eigvals[0] / max(eigvals.sum(), 1e-12))
    except np.linalg.LinAlgError:
        return 0.5

    return float(np.clip(w, 0.0, 1.0))


def compute_fractional_difference(
    series: pd.Series,
    d: float,
    max_lags: int,
    min_periods: int = None,
) -> pd.Series:
    """
    Fractionally differenced series (Point 24).
    X_t^(d) = sum_{k=0}^{max_lags} (-1)^k * binom(d, k) * X_{t-k}
    Preserves long-memory features while maintaining stationarity.
    """
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) < max_lags + 1:
        return s

    n = len(s)
    vals = s.values.copy()
    result = np.full(n, np.nan)

    # Compute binomial weights: w_k = (-1)^k * C(d, k)
    # Recursive: w_0 = 1, w_k = w_{k-1} * (k-1-d) / k
    # This correctly computes w_k = (-1)^k * d*(d-1)*...*(d-k+1) / k!
    weights = np.zeros(max_lags + 1)
    weights[0] = 1.0
    for k in range(1, max_lags + 1):
        weights[k] = weights[k - 1] * (k - 1 - d) / k

    for t in range(max_lags, n):
        fd_val = 0.0
        for k in range(max_lags + 1):
            fd_val += weights[k] * vals[t - k]
        result[t] = fd_val

    return pd.Series(result, index=s.index)


def compute_shannon_entropy_from_series(
    series: pd.Series,
    window: int,
    n_bins: int = 10,
    min_periods: int = None,
) -> float:
    """
    General Shannon entropy of a binned series over a rolling window.
    Used by Point 20 and potentially other entropy-based points.
    """
    s = pd.to_numeric(series, errors="coerce").dropna()
    mp = min_periods or max(5, window // 2)
    recent = s.tail(window)
    if len(recent) < mp:
        return 0.5

    try:
        hist, _ = np.histogram(recent, bins=n_bins)
    except ValueError:
        return 0.5
    p = hist / (hist.sum() + 1e-12)
    p = p[p > 0]
    if len(p) < 2:
        return 0.5

    entropy = -np.sum(p * np.log(p))
    max_entropy = np.log(n_bins)
    return float(entropy / max_entropy) if max_entropy > 0 else 0.5


# ---------------------------------------------------------------------
# Remaining Batch B Utilities (Points 27-34, 36-45)
# Directional semivariance, Hurst-adaptive, Kendall tau, microstructure noise,
# entropy info bars, EOSR, genesis threshold, VPIN horizon, OU bridging,
# latency filter, HMA, DFT, intra-bar density, DTW, range norm, wavelet,
# info-weighted operators, copula transform.
# ---------------------------------------------------------------------

def compute_downside_semivariance(
    close: pd.Series,
    window: int,
    min_periods: int = None,
) -> float:
    """
    Causal Semivariance Directional Scaling (Point 27).
    sigma_down^2 = sum min(0, ln(C_t/C_{t-1}))^2 / W
    """
    c = pd.to_numeric(close, errors="coerce")
    r = np.log((c / c.shift(1)).clip(lower=1e-12))
    mp = min_periods or max(3, window // 2)
    recent = r.tail(window).dropna()
    if len(recent) < mp:
        return 0.01
    downside = recent[recent < 0]
    if len(downside) < 1:
        return 0.001
    semivar = float((downside ** 2).mean())
    return max(semivar, 1e-8)


def compute_hurst_adaptive_lookback(
    returns: pd.Series,
    base_lookback: int,
    window: int,
    min_lb: int = 20,
    max_lb: int = 400,
    min_periods: int = None,
) -> int:
    """
    Hurst-Adaptive Profile Lifespans (Point 28).
    Profile_Lookback_t = round(Lookback_base * (1.5 - H_t))
    """
    h = compute_hurst_exponent(returns, window, min_periods)
    # H close to 0.5 -> mean-reverting -> shorter lookback
    # H close to 1.0 -> trending -> longer lookback
    scale = 1.5 - h
    w = int(round(base_lookback * scale))
    return max(min_lb, min(w, max_lb))


def compute_kendall_tau_strength(
    close: pd.Series,
    window: int,
    min_periods: int = None,
) -> float:
    """
    Non-Parametric Kendall's Tau Trend-Strength (Point 29).
    tau = 2 / (W*(W-1)) * sum sign(C_i - C_j) * sign(i - j) for i<j
    """
    c = pd.to_numeric(close, errors="coerce").dropna()
    mp = min_periods or max(5, window // 2)
    recent = c.tail(window).values
    n = len(recent)
    if n < mp:
        return 0.0
    # Vectorized Kendall's tau using concordant/discordant pairs
    concordant = 0
    discordant = 0
    for i in range(n - 1):
        diff = recent[i + 1:] - recent[i]
        idx_diff = np.arange(1, n - i)
        concordant += np.sum((diff > 0) & (idx_diff > 0))
        discordant += np.sum((diff < 0) & (idx_diff > 0))
    denom = n * (n - 1) / 2.0
    if denom <= 0:
        return 0.0
    tau = (concordant - discordant) / denom
    return float(np.clip(tau, -1.0, 1.0))


def compute_microstructure_noise_estimator(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    count: pd.Series,
    window: int,
    min_periods: int = None,
) -> float:
    """
    Bar-Level Realized Kernel Microstructure Estimator (Point 30).
    eta_t = (H_t - L_t) / (Count_t * C_t + eps)
    """
    h = pd.to_numeric(high, errors="coerce")
    l = pd.to_numeric(low, errors="coerce")
    c = pd.to_numeric(close, errors="coerce")
    cnt = pd.to_numeric(count, errors="coerce")
    mp = min_periods or max(3, window // 2)
    n = min(len(h), len(l), len(c), len(cnt))
    if n < mp:
        return 0.001
    recent_h = h.tail(window).dropna()
    recent_l = l.tail(window).dropna()
    recent_c = c.tail(window).dropna()
    recent_cnt = cnt.tail(window).dropna()
    nn = min(len(recent_h), len(recent_l), len(recent_c), len(recent_cnt))
    if nn < mp:
        return 0.001
    recent_h = recent_h.iloc[-nn:]
    recent_l = recent_l.iloc[-nn:]
    recent_c = recent_c.iloc[-nn:]
    recent_cnt = recent_cnt.iloc[-nn:]
    hl = recent_h - recent_l
    noise_proxy = (hl / (recent_cnt * recent_c + 1e-12)).mean()
    return float(noise_proxy) if pd.notna(noise_proxy) and np.isfinite(noise_proxy) else 0.001


def compute_entropy_weighted_bar_duration(
    volume: pd.Series,
    entropy_target: float,
    min_window: int,
    max_window: int,
    min_periods: int = 10,
) -> int:
    """
    Entropy-Weighted Information Bars (Point 31).
    Find minimum window where cumulative information entropy >= target.
    """
    v = pd.to_numeric(volume, errors="coerce").dropna()
    if len(v) < min_periods:
        return min_window
    # Compute per-bar entropy proxy (volume as information proxy)
    total_vol = v.sum()
    if total_vol <= 0:
        return min_window
    for w in range(min_window, min(max_window + 1, len(v) + 1)):
        window_v = v.iloc[-w:].values
        w_total = window_v.sum()
        if w_total <= 0:
            continue
        p = window_v / w_total
        p = p[p > 0]
        if len(p) < 2:
            continue
        entropy = float(-np.sum(p * np.log(p)))
        if entropy >= entropy_target:
            return w
    return max_window


def compute_dynamic_annualization_scale(
    timestamps: pd.Series,
    sample_rate_ms: float,
    min_data_density: int = 100,
) -> float:
    """
    Dynamic Empirical Observation Sampling Rate (Point 32).
    psi = N_observed / (31_536_000_000 / sample_rate_ms)
    """
    ts = pd.to_numeric(timestamps, errors="coerce").dropna()
    if len(ts) < min_data_density:
        return 1.0
    year_ms = 31_536_000_000.0
    expected_n = year_ms / max(sample_rate_ms, 1.0)
    actual_n = float(len(ts))
    psi = actual_n / max(expected_n, 1.0)
    return float(np.clip(psi, 0.1, 10.0))


def compute_volume_density_genesis(
    volume: pd.Series,
    baseline_density: float,
    min_periods: int = 10,
) -> int:
    """
    Cumulative Volume-Density Genesis Thresholding (Point 33).
    genesis = min { t | sum CT_{t-i} >= baseline }
    """
    v = pd.to_numeric(volume, errors="coerce").dropna()
    if len(v) < min_periods:
        return 0
    cumsum = v.cumsum().values
    for i, cs in enumerate(cumsum):
        if cs >= baseline_density:
            return i
    return len(v)


def compute_vpin_synced_horizon(
    volume: pd.Series,
    base_horizon: int,
    mu_volume: float,
    phi_target: float,
    min_window: int,
    max_window: int,
    min_periods: int = 10,
) -> int:
    """
    VPIN-Synchronized Dynamic Forecast Horizons (Point 34).
    Horizon_t = min { k | sum V_{t+i} >= mu_V * phi }
    """
    v = pd.to_numeric(volume, errors="coerce").dropna()
    if len(v) < min_periods:
        return base_horizon
    target_vol = mu_volume * phi_target
    for k in range(min_window, min(max_window + 1, len(v) + 1)):
        cum_vol = v.tail(k).sum()
        if cum_vol >= target_vol:
            return k
    return max_window


def compute_ou_stochastic_bridge(
    close: pd.Series,
    gap_indices: list,
    theta: float,
    sigma_scale: float = 1.0,
    n_paths: int = 50,
    min_periods: int = 20,
) -> pd.Series:
    """
    Ornstein-Uhlenbeck Volatility-Preserving Stochastic Bridging (Point 36).
    dx_t = theta (mu - x_t) dt + sigma_t dW_t
    Fills gaps using mean-reverting stochastic processes.
    """
    if len(close) < min_periods or not gap_indices:
        return close.copy()
    result = close.copy()
    # Estimate mu from non-gap data
    valid_mask = ~result.index.isin(gap_indices)
    valid_data = result[valid_mask].dropna()
    if len(valid_data) < min_periods:
        return close.copy()
    mu = float(valid_data.mean())
    # Estimate local sigma
    local_std = float(valid_data.tail(min_periods).std())
    sigma = local_std * sigma_scale
    rng = np.random.RandomState(42)
    for idx in gap_indices:
        if idx not in result.index:
            continue
        # Find nearest valid value before gap
        pre_valid = result[result.index < idx].dropna()
        x0 = float(pre_valid.iloc[-1]) if len(pre_valid) > 0 else mu
        # Simple Euler-Maruyama single step for short gap
        dt = 1.0
        x_new = x0 + theta * (mu - x0) * dt + sigma * rng.normal(0, np.sqrt(dt))
        result.loc[idx] = x_new
    return result


def compute_causal_latency_outlier_filter(
    bar_timestamps: pd.Series,
    window: int,
    quantile_threshold: float = 0.99,
    min_periods: int = None,
) -> dict:
    """
    Causal Latency Outlier Filtering (Point 37).
    Exclude kline where gap exceeds critical bound:
    DeltaTS_t >= Quantile({DeltaTS}, q=0.99)
    """
    ts = pd.to_numeric(bar_timestamps, errors="coerce")
    mp = min_periods or max(10, window // 2)
    if len(ts) < mp:
        return {
            "filter_mask": pd.Series(False, index=bar_timestamps.index),
            "threshold_ms": 0.0,
        }
    gaps = ts.diff().dropna()
    if len(gaps) < mp:
        return {
            "filter_mask": pd.Series(False, index=bar_timestamps.index),
            "threshold_ms": 0.0,
        }
    threshold = float(gaps.quantile(quantile_threshold))
    filter_mask = pd.Series(False, index=bar_timestamps.index)
    filter_mask.iloc[1:] = (gaps > threshold).values
    return {
        "filter_mask": filter_mask,
        "threshold_ms": float(threshold),
    }


def compute_hull_moving_average(
    close: pd.Series,
    window: int,
    min_periods: int = None,
) -> float:
    """
    Zero-Lag Hull Moving Average (HMA) (Point 38).
    HMA_t = WMA(2 * WMA(C, W/2) - WMA(C, W), sqrt(W))
    """
    c = pd.to_numeric(close, errors="coerce").dropna()
    mp = min_periods or max(window, 20)
    if len(c) < mp:
        return float(c.iloc[-1]) if len(c) > 0 else 0.0
    half_w = max(1, window // 2)
    sqrt_w = max(1, int(np.sqrt(window)))

    def _wma(series, w):
        if len(series) < w:
            return series.mean()
        weights = np.arange(1, w + 1, dtype=float)
        recent = series.tail(w).values
        return float(np.dot(recent, weights) / weights.sum())

    wma_half = c.rolling(half_w, min_periods=half_w).apply(
        lambda x: _wma(pd.Series(x), half_w), raw=False
    )
    wma_full = c.rolling(window, min_periods=window).apply(
        lambda x: _wma(pd.Series(x), window), raw=False
    )
    diff = 2.0 * wma_half - wma_full
    hma = diff.rolling(sqrt_w, min_periods=max(1, sqrt_w // 2)).apply(
        lambda x: _wma(pd.Series(x), sqrt_w), raw=False
    )
    val = hma.iloc[-1]
    return float(val) if pd.notna(val) else float(c.iloc[-1])


def compute_dft_dominant_cycle(
    volume: pd.Series,
    window: int,
    min_freq: int = 3,
    max_freq: int = None,
    min_periods: int = None,
) -> int:
    """
    DFT Dominant Cycle Extraction (Point 39).
    P(f) = |F(V)|^2 ; Period = argmax_f P(f)
    """
    v = pd.to_numeric(volume, errors="coerce").dropna()
    mp = min_periods or max(20, window // 2)
    recent = v.tail(window).values
    if len(recent) < mp:
        return window // 2
    n = len(recent)
    # FFT
    fft_vals = np.fft.rfft(recent - recent.mean())
    power = np.abs(fft_vals) ** 2
    # Exclude DC component (index 0)
    if max_freq is None:
        max_freq = n // 2
    # Find dominant frequency (excluding DC)
    start_freq = max(min_freq, 1)
    end_freq = min(max_freq, len(power) - 1)
    if start_freq >= end_freq:
        return window // 2
    dominant_idx = start_freq + np.argmax(power[start_freq:end_freq + 1])
    if dominant_idx <= 0:
        return window // 2
    period = n // dominant_idx
    return max(3, min(period, window))


def compute_intra_bar_volume_density(
    volume: pd.Series,
    time_elapsed_pct: pd.Series,
    window: int,
    min_periods: int = None,
) -> float:
    """
    Causal Intra-Bar Volume Density Weighting (Point 40).
    V_projected,t = V_t * CDF_time(Delta_t_elapsed)
    """
    v = pd.to_numeric(volume, errors="coerce").dropna()
    t_pct = pd.to_numeric(time_elapsed_pct, errors="coerce").dropna()
    mp = min_periods or max(10, window // 2)
    n = min(len(v), len(t_pct))
    if n < mp:
        return 1.0
    recent_v = v.tail(window).values
    recent_t = t_pct.tail(window).values
    # Empirical CDF of volume at each time fraction
    current_t = recent_t[-1] if len(recent_t) > 0 else 0.5
    current_t = max(0.0, min(current_t, 1.0))
    # Simple density weight: fraction of bars with volume >= median when at similar time
    vol_median = np.median(recent_v)
    similar_time = np.abs(recent_t - current_t) < 0.2
    if similar_time.sum() < 3:
        return 1.0
    weight = float(np.mean(recent_v[similar_time] >= vol_median))
    return float(np.clip(weight, 0.1, 2.0))


def compute_dtw_phase_shift(
    series_a: pd.Series,
    series_b: pd.Series,
    max_shift: int = 50,
) -> int:
    """
    Dynamic Time Warping Metric Alignment (Point 41).
    Simplified DTW: find optimal phase shift minimizing L2 distance.
    """
    a = pd.to_numeric(series_a, errors="coerce").dropna().values
    b = pd.to_numeric(series_b, errors="coerce").dropna().values
    n = min(len(a), len(b))
    if n < 10:
        return 0
    a = a[-n:]
    b = b[-n:]
    # Normalize
    a_std = a.std() + 1e-12
    b_std = b.std() + 1e-12
    a_norm = (a - a.mean()) / a_std
    b_norm = (b - b.mean()) / b_std
    best_shift = 0
    best_dist = np.inf
    for shift in range(-max_shift, max_shift + 1):
        if shift >= 0:
            a_slice = a_norm[shift:]
            b_slice = b_norm[:len(a_slice)]
        else:
            b_slice = b_norm[-shift:]
            a_slice = a_norm[:len(b_slice)]
        nn = min(len(a_slice), len(b_slice))
        if nn < 5:
            continue
        dist = float(np.mean((a_slice[:nn] - b_slice[:nn]) ** 2))
        if dist < best_dist:
            best_dist = dist
            best_shift = shift
    return best_shift


def compute_variance_stabilized_range(
    high: pd.Series,
    low: pd.Series,
    window: int,
    min_periods: int = None,
) -> float:
    """
    Variance-Stabilized Normalized Range Estimator (Point 42).
    R_t = (H_t - L_t) / (sigma_rolling,t * Delta_t)
    """
    h = pd.to_numeric(high, errors="coerce")
    l = pd.to_numeric(low, errors="coerce")
    mp = min_periods or max(5, window // 2)
    recent_h = h.tail(window).dropna()
    recent_l = l.tail(window).dropna()
    n = min(len(recent_h), len(recent_l))
    if n < mp:
        return 1.0
    recent_h = recent_h.iloc[-n:]
    recent_l = recent_l.iloc[-n:]
    range_ = recent_h - recent_l
    sigma = float(range_.std())
    if sigma <= 0:
        return 1.0
    current_range = float(range_.iloc[-1])
    norm_range = current_range / sigma
    return float(norm_range) if np.isfinite(norm_range) else 1.0


def compute_wavelet_decomposition(
    series: pd.Series,
    levels: int = 3,
    min_periods: int = 10,
) -> dict:
    """
    Multiresolution Wavelet Decomposition (Point 43).
    Haar wavelet decomposition into orthogonal detail/approximation coefficients.
    """
    s = pd.to_numeric(series, errors="coerce").dropna().values
    if len(s) < min_periods or len(s) < 2 ** levels:
        return {"approx": s, "details": [], "energy": [1.0]}
    # Simple Haar decomposition
    approx = s.copy()
    details = []
    energy = []
    for _ in range(levels):
        n = len(approx)
        if n < 2:
            break
        even = approx[0::2]
        odd = approx[1::2]
        # Pad if odd length
        if len(odd) < len(even):
            odd = np.append(odd, odd[-1])
        new_approx = (even + odd) / 2.0
        detail = (even - odd) / 2.0
        total_energy = np.sum(new_approx ** 2) + np.sum(detail ** 2)
        if total_energy > 0:
            detail_energy = float(np.sum(detail ** 2) / total_energy)
        else:
            detail_energy = 0.0
        details.append(detail)
        energy.append(detail_energy)
        approx = new_approx
    # Normalize energy
    total_e = sum(energy)
    if total_e > 0:
        energy = [e / total_e for e in energy]
    return {"approx": approx, "details": details, "energy": energy}


def compute_information_weighted_rolling(
    series: pd.Series,
    entropy_series: pd.Series,
    window: int,
    min_periods: int = None,
) -> float:
    """
    Information-Weighted Rolling Operators (Point 44).
    theta_t = sum theta_i * H(X_{t-i}) / sum H(X_{t-i})
    """
    s = pd.to_numeric(series, errors="coerce").dropna()
    h = pd.to_numeric(entropy_series, errors="coerce").dropna()
    mp = min_periods or max(5, window // 2)
    n = min(len(s), len(h))
    if n < mp:
        return float(s.iloc[-1]) if len(s) > 0 else 0.0
    recent_s = s.iloc[-window:].values
    recent_h = h.iloc[-window:].values
    # Ensure non-negative weights
    weights = np.clip(recent_h, 1e-6, None)
    total_w = weights.sum()
    if total_w <= 0:
        return float(np.mean(recent_s))
    weighted_val = float(np.dot(recent_s, weights) / total_w)
    return weighted_val if np.isfinite(weighted_val) else float(np.mean(recent_s))


def compute_gumbel_copula_transform(
    returns: pd.Series,
    volume: pd.Series,
    window: int,
    min_periods: int = None,
) -> float:
    """
    Asymmetric Copula-Based Dependent Transforms (Point 45).
    Gumbel Copula for tail dependence between returns and volume.
    Simplified: rank-based copula dependency measure.
    """
    r = pd.to_numeric(returns, errors="coerce").dropna()
    v = pd.to_numeric(volume, errors="coerce").dropna()
    mp = min_periods or max(20, window // 2)
    n = min(len(r), len(v))
    if n < mp:
        return 0.0
    recent_r = r.iloc[-window:].values
    recent_v = v.iloc[-window:].values
    n = len(recent_r)
    # Rank transforms to [0,1]
    from scipy.stats import rankdata
    rank_r = rankdata(recent_r) / n
    rank_v = rankdata(recent_v) / n
    # Gumbel copula survival function approximation
    # C(u,v) = exp(-[(-ln u)^theta + (-ln v)^theta]^(1/theta))
    # Estimate theta from Kendall's tau: tau = 1 - 1/theta => theta = 1/(1-tau)
    tau = 0.0
    concordant = 0
    total = 0
    for i in range(n):
        for j in range(i + 1, min(i + 20, n)):  # sample for speed
            total += 1
            if (recent_r[i] > recent_r[j]) == (recent_v[i] > recent_v[j]):
                concordant += 1
    if total > 0:
        tau = 2.0 * concordant / total - 1.0
    theta = max(1.01, 1.0 / max(1.0 - tau, 0.01))
    # Compute tail dependence at the latest observation
    u = max(rank_r[-1], 1e-6)
    vv = max(rank_v[-1], 1e-6)
    try:
        copula_val = np.exp(-((-np.log(u)) ** theta + (-np.log(vv)) ** theta) ** (1.0 / theta))
    except (ValueError, FloatingPointError):
        copula_val = u * vv  # independence fallback
    return float(np.clip(copula_val, 0.0, 1.0))


# ---------------------------------------------------------------------
# Remaining Batch C Utilities (Points 63,65,67,68,71-78,81,83-89,96-99)
# Statistical robustness, ML hygiene, clustering, portfolio/risk, and operational.
# All functions are config-driven and sovereignty-compliant.
# ---------------------------------------------------------------------

def compute_quantile_transform(
    values: pd.Series,
    window: int,
    min_periods: int = None,
    clip_min: float = 0.01,
    clip_max: float = 0.99,
) -> float:
    """
    Quantile Transformer Mapping (Point 63).
    Maps latest value to its rolling empirical CDF rank, then to standard normal.
    X_t = Phi^{-1}( F(X_t) )
    """
    v = pd.to_numeric(values, errors="coerce").dropna()
    mp = min_periods or max(5, window // 2)
    recent = v.tail(window)
    if len(recent) < mp:
        return 0.0
    current = float(recent.iloc[-1])
    rank = float((recent <= current).sum()) / len(recent)
    rank = np.clip(rank, clip_min, clip_max)
    from scipy.stats import norm
    z = float(norm.ppf(rank))
    return float(np.clip(z, -4.0, 4.0))


def compute_kalman_dynamic_ar(
    returns: pd.Series,
    ar_order: int,
    process_noise: float,
    measurement_noise: float,
    window: int,
    min_periods: int = None,
) -> dict:
    """
    Kalman-Filter Dynamic Autoregressive Parameters (Point 65).
    Updates AR coefficients as state variables.
    y_t = phi_1 * y_{t-1} + ... + phi_p * y_{t-p} + eps
    Returns dict with latest phi estimates and residual variance.
    """
    r = pd.to_numeric(returns, errors="coerce").dropna()
    mp = min_periods or max(ar_order + 10, window // 2)
    if len(r) < mp:
        return {"phis": [0.0] * ar_order, "resid_var": 1e-4}
    r = r.tail(window).values
    n = len(r)
    p = ar_order
    # Build Y and X matrices for AR(p)
    Y = r[p:]
    X = np.column_stack([r[p - i - 1: n - i - 1] for i in range(p)])
    # Initialize via OLS
    try:
        Phi = np.linalg.lstsq(X, Y, rcond=None)[0]
    except np.linalg.LinAlgError:
        return {"phis": [0.0] * p, "resid_var": 1e-4}
    # Kalman filter over residuals
    phi = Phi.copy()
    P = np.eye(p) * 1.0  # state covariance
    Q = np.eye(p) * process_noise  # process noise
    R = measurement_noise  # measurement noise
    for t in range(len(Y)):
        x_t = X[t:t+1].T
        y_pred = float(x_t.T @ phi)
        innov = Y[t] - y_pred
        S = float(x_t.T @ P @ x_t + R)
        if S <= 0:
            S = R
        K = (P @ x_t) / S
        phi = phi + K.flatten() * innov
        P = (np.eye(p) - K @ x_t.T) @ P + Q
    resid = Y - X @ phi
    resid_var = float(np.var(resid)) if len(resid) > 1 else 1e-4
    return {"phis": phi.tolist(), "resid_var": resid_var}


def compute_white_heteroskedastic_se(
    X: np.ndarray,
    residuals: np.ndarray,
) -> np.ndarray:
    """
    White's Heteroskedasticity-Consistent Covariance Estimator (Point 67).
    Sigma_b = (X'X)^{-1} X' Omega X (X'X)^{-1} where Omega = diag(e_i^2).
    Returns corrected standard errors.
    """
    n, k = X.shape
    if n < k + 1:
        return np.zeros(k)
    try:
        XtX_inv = np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        return np.zeros(k)
    Omega = np.diag(residuals ** 2)
    XOX = X.T @ Omega @ X
    var_b = XtX_inv @ XOX @ XtX_inv
    se = np.sqrt(np.maximum(np.diag(var_b), 0.0))
    return se


def compute_spearman_rho(
    x: pd.Series,
    y: pd.Series,
    window: int,
    min_periods: int = None,
) -> float:
    """
    Rolling Spearman's Rho (Point 68) — rank-based non-linear correlation.
    """
    x_r = pd.to_numeric(x, errors="coerce").dropna()
    y_r = pd.to_numeric(y, errors="coerce").dropna()
    mp = min_periods or max(5, window // 2)
    n = min(len(x_r), len(y_r))
    if n < mp:
        return 0.0
    x_recent = x_r.tail(window).values
    y_recent = y_r.tail(window).values
    nn = min(len(x_recent), len(y_recent))
    x_recent = x_recent[-nn:]
    y_recent = y_recent[-nn:]
    from scipy.stats import rankdata
    rx = rankdata(x_recent)
    ry = rankdata(y_recent)
    rho = float(np.corrcoef(rx, ry)[0, 1])
    return rho if np.isfinite(rho) else 0.0


def compute_kalman_dynamic_beta(
    local_returns: pd.Series,
    market_returns: pd.Series,
    process_noise: float = 0.01,
    measurement_noise: float = 0.05,
    window: int = 100,
    min_periods: int = None,
) -> dict:
    """
    Kalman-Filter Dynamic Beta Estimator (Point 71).
    beta_t|t = beta_{t-1} + K_t * (r_i,t - alpha - beta_{t-1} * r_m,t)
    """
    lr = pd.to_numeric(local_returns, errors="coerce").dropna()
    mr = pd.to_numeric(market_returns, errors="coerce").dropna()
    mp = min_periods or max(10, window // 2)
    n = min(len(lr), len(mr))
    if n < mp:
        return {"beta": 1.0, "alpha": 0.0, "resid_var": 1e-4}
    lr = lr.tail(window).values
    mr = mr.tail(window).values
    nn = min(len(lr), len(mr))
    lr, mr = lr[-nn:], mr[-nn:]
    # State: [alpha, beta]
    state = np.array([0.0, 1.0])  # initial
    P = np.eye(2) * 1.0
    Q = np.eye(2) * process_noise
    R = measurement_noise
    for t in range(nn):
        H = np.array([1.0, mr[t]])  # observation model
        y_pred = float(H @ state)
        innov = lr[t] - y_pred
        S = float(H @ P @ H + R)
        if S <= 0:
            S = R
        K = (P @ H) / S
        state = state + K * innov
        P = (np.eye(2) - np.outer(K, H)) @ P + Q
    # Residual variance
    preds = state[0] + state[1] * mr
    resid = lr - preds
    resid_var = float(np.var(resid)) if len(resid) > 1 else 1e-4
    return {"beta": float(state[1]), "alpha": float(state[0]), "resid_var": resid_var}


def compute_hill_tail_index(
    returns: pd.Series,
    k: int,
    window: int = 100,
    min_periods: int = None,
    tail: str = "left",
) -> float:
    """
    Hill's Estimator for tail index (Point 72).
    alpha_tail = k / sum ln(x_{(i)} / x_{(k+1)})
    """
    r = pd.to_numeric(returns, errors="coerce").dropna()
    mp = min_periods or max(k + 5, window // 2)
    recent = r.tail(window)
    if len(recent) < mp:
        return 2.5  # conservative default
    vals = recent.values.copy()
    if tail == "left":
        vals = np.sort(-vals)  # sort negative returns ascending (largest losses first)
    else:
        vals = np.sort(vals)[::-1]  # sort positive returns descending
    vals = vals[:k]
    vals = vals[vals > 0]
    if len(vals) < 3:
        return 2.5
    log_ratios = np.log(vals / max(vals[-1], 1e-12))
    log_ratios = log_ratios[log_ratios > 0]
    if len(log_ratios) < 1:
        return 2.5
    hill = len(log_ratios) / log_ratios.sum()
    return float(np.clip(hill, 0.5, 10.0))


def compute_rolling_johansen_trace(
    series_a: pd.Series,
    series_b: pd.Series,
    window: int,
    lag: int = 1,
    min_periods: int = None,
) -> dict:
    """
    Rolling Johansen Trace Test Proxy (Point 73).
    Simplified cointegration test using residuals from OLS regression.
    Returns dict with trace_stat and cointegrated flag.
    """
    a = pd.to_numeric(series_a, errors="coerce").dropna()
    b = pd.to_numeric(series_b, errors="coerce").dropna()
    mp = min_periods or max(30, window // 2)
    n = min(len(a), len(b))
    if n < mp:
        return {"trace_stat": 0.0, "cointegrated": False, "adf_stat": 0.0}
    a = a.tail(window).values
    b = b.tail(window).values
    nn = min(len(a), len(b))
    a, b = a[-nn:], b[-nn:]
    # OLS regression: a = alpha + beta * b + eps
    X = np.column_stack([np.ones(nn), b])
    try:
        beta_hat = np.linalg.lstsq(X, a, rcond=None)[0]
    except np.linalg.LinAlgError:
        return {"trace_stat": 0.0, "cointegrated": False, "adf_stat": 0.0}
    residuals = a - X @ beta_hat
    # ADF-like test on residuals
    res_lag = residuals[:-lag]
    res_lead = residuals[lag:]
    dY = res_lead - res_lag[:-lag + lag] if len(res_lead) != len(res_lag) else res_lead - res_lag
    # Simplified: use variance ratio as proxy
    var_resid = np.var(residuals)
    diff_var = np.var(np.diff(residuals))
    trace_stat = float(diff_var / max(var_resid, 1e-12))
    # Low trace_stat suggests unit root in residuals -> cointegrated
    cointegrated = trace_stat < 0.5  # heuristic threshold
    return {"trace_stat": trace_stat, "cointegrated": cointegrated, "adf_stat": -trace_stat}


def compute_cusum_break_detector(
    returns: pd.Series,
    window: int,
    critical_value: float = 1.0,
    min_periods: int = None,
) -> dict:
    """
    CUSUM Structural Break Detector (Point 74).
    W_t = sum_{j=1}^{t} w_j / sigma_hat ; flag if exceeds critical value.
    """
    r = pd.to_numeric(returns, errors="coerce").dropna()
    mp = min_periods or max(10, window // 2)
    if len(r) < mp:
        return {"cusum_stat": 0.0, "break_detected": False, "break_index": -1}
    recent = r.tail(window).values
    n = len(recent)
    mu = np.mean(recent)
    sigma = max(np.std(recent), 1e-12)
    # Standardized cumulative sum of deviations
    cusum = np.cumsum((recent - mu) / sigma)
    cusum_stat = float(np.max(np.abs(cusum)))
    break_idx = int(np.argmax(np.abs(cusum)))
    break_detected = cusum_stat > critical_value * np.sqrt(n)
    return {"cusum_stat": cusum_stat, "break_detected": break_detected, "break_index": break_idx}


def compute_vif_scores(X: np.ndarray, feature_names: list = None) -> dict:
    """
    Variance Inflation Factor (VIF) Filtering (Point 75).
    VIF_j = 1 / (1 - R_j^2) where R_j^2 is from regressing feature j on all others.
    """
    n, k = X.shape
    if k < 2 or n < k + 2:
        return {"vifs": [1.0] * k, "max_vif": 1.0, "drop_features": []}
    vifs = []
    drop_features = []
    names = feature_names or [f"f{i}" for i in range(k)]
    for j in range(k):
        y = X[:, j]
        X_other = np.delete(X, j, axis=1)
        X_other_aug = np.column_stack([np.ones(n), X_other])
        try:
            beta = np.linalg.lstsq(X_other_aug, y, rcond=None)[0]
            y_hat = X_other_aug @ beta
            ss_res = np.sum((y - y_hat) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r_sq = 1 - ss_res / max(ss_tot, 1e-12)
            vif = 1.0 / max(1.0 - r_sq, 1e-6)
        except np.linalg.LinAlgError:
            vif = 1.0
        vifs.append(float(vif))
        if vif > 10.0:
            drop_features.append(names[j])
    return {"vifs": vifs, "max_vif": float(max(vifs)), "drop_features": drop_features}


def compute_mutual_information_distance(
    features: pd.DataFrame,
    target: pd.Series,
    n_bins: int = 10,
) -> pd.Series:
    """
    Mutual Information (MI) Distance Metric Scaling (Point 76).
    d(X,Y) = 1 - I(X;Y) / H(X,Y)
    Returns MI-based weights per feature (higher = more relevant to target).
    """
    n = min(len(features), len(target))
    if n < n_bins * 2:
        return pd.Series(1.0, index=features.columns)
    target_binned = pd.qcut(target.tail(n), q=n_bins, labels=False, duplicates="drop")
    weights = {}
    for col in features.columns:
        feat = pd.to_numeric(features[col].tail(n), errors="coerce")
        feat_binned = pd.qcut(feat, q=n_bins, labels=False, duplicates="drop")
        # Joint and marginal histograms
        joint = np.histogram2d(feat_binned.fillna(0).astype(int), target_binned.fillna(0).astype(int), bins=n_bins)[0]
        joint_prob = joint / joint.sum()
        marg_x = joint_prob.sum(axis=1)
        marg_y = joint_prob.sum(axis=0)
        marg_x = marg_x[marg_x > 0]
        marg_y = marg_y[marg_y > 0]
        joint_nz = joint_prob[joint_prob > 0]
        mi = float(np.sum(joint_nz * np.log(joint_nz / max(np.outer(marg_x, marg_y).min(), 1e-12))))
        h_x = float(-np.sum(marg_x * np.log(marg_x)))
        h_y = float(-np.sum(marg_y * np.log(marg_y)))
        mi_norm = mi / max(h_x + h_y, 1e-12)
        weights[col] = float(np.clip(mi_norm, 0.01, 1.0))
    return pd.Series(weights)


def compute_pca_distance_projections(
    X: np.ndarray,
    n_components: int = 3,
) -> dict:
    """
    PCA-Principal Component Distance Projections (Point 77).
    Projects features onto top principal components for distance-preserving clustering.
    """
    if X.ndim < 2 or X.shape[0] < n_components + 1:
        return {"projected": X, "variance_explained": [1.0], "n_components": 0}
    X_centered = X - X.mean(axis=0)
    try:
        U, S, Vt = np.linalg.svd(X_centered, full_matrices=False)
        k = min(n_components, len(S))
        projected = X_centered @ Vt[:k].T
        total_var = np.sum(S ** 2)
        var_explained = (S[:k] ** 2 / max(total_var, 1e-12)).tolist()
    except np.linalg.LinAlgError:
        return {"projected": X, "variance_explained": [1.0], "n_components": 0}
    return {"projected": projected, "variance_explained": var_explained, "n_components": k}


def compute_vol_symmetric_barrier_labels(
    returns: pd.Series,
    phi: float,
    window: int,
    horizon: int,
    min_periods: int = None,
) -> dict:
    """
    Volatility-Symmetric Dynamic Multi-Barrier Target Labels (Point 78).
    Barrier_t = +/- sigma_rolling,t * phi
    """
    r = pd.to_numeric(returns, errors="coerce").dropna()
    mp = min_periods or max(window, horizon + 5)
    if len(r) < mp:
        return {"label": 0, "barrier_upper": phi * 0.01, "barrier_lower": -phi * 0.01}
    recent = r.tail(window)
    sigma = float(recent.std())
    barrier_upper = phi * sigma
    barrier_lower = -phi * sigma
    # Forward return over horizon
    fwd = r.iloc[-horizon:].sum() if len(r) >= horizon else 0.0
    if fwd >= barrier_upper:
        label = 1
    elif fwd <= barrier_lower:
        label = -1
    else:
        label = 0
    return {"label": label, "barrier_upper": barrier_upper, "barrier_lower": barrier_lower, "forward_return": fwd}


def compute_mst_pruning(
    correlation_matrix: pd.DataFrame,
    threshold: float = 0.3,
) -> dict:
    """
    Minimum Spanning Tree (MST) Correlation Network Pruning (Point 81).
    Prunes weak connections using MST distance: d = 2*(1 - rho).
    """
    n = len(correlation_matrix)
    if n < 2:
        return {"adjacency": correlation_matrix, "n_edges": 0}
    # Convert correlation to distance
    dist = 2.0 * (1.0 - correlation_matrix.abs())
    # Simple Prim's MST
    in_mst = [False] * n
    min_edge = [np.inf] * n
    parent = [-1] * n
    min_edge[0] = 0.0
    mst_edges = []
    for _ in range(n):
        u = -1
        for v in range(n):
            if not in_mst[v] and (u == -1 or min_edge[v] < min_edge[u]):
                u = v
        if u == -1 or min_edge[u] == np.inf:
            break
        in_mst[u] = True
        if parent[u] != -1:
            mst_edges.append((parent[u], u))
        for v in range(n):
            if not in_mst[v] and dist.iloc[u, v] < min_edge[v]:
                min_edge[v] = dist.iloc[u, v]
                parent[v] = u
    # Build adjacency from MST edges + threshold edges
    adj = pd.DataFrame(0, index=correlation_matrix.index, columns=correlation_matrix.columns)
    for i, j in mst_edges:
        adj.iloc[i, j] = 1
        adj.iloc[j, i] = 1
    # Add edges above threshold
    for i in range(n):
        for j in range(i+1, n):
            if correlation_matrix.iloc[i, j] >= threshold and adj.iloc[i, j] == 0:
                adj.iloc[i, j] = 1
                adj.iloc[j, i] = 1
    return {"adjacency": adj, "n_edges": int(adj.sum().sum() // 2), "mst_edges": mst_edges}

def compute_information_weighted_loss(
    predictions: np.ndarray,
    actuals: np.ndarray,
    information_weights: np.ndarray,
) -> float:
    """
    Information-Weighted Loss Training (Point 83).
    L = sum w_i * (Y_i - Yhat_i)^2
    """
    preds = np.asarray(predictions, dtype=float)
    acts = np.asarray(actuals, dtype=float)
    w = np.asarray(information_weights, dtype=float)
    n = min(len(preds), len(acts), len(w))
    if n < 1:
        return 0.0
    preds, acts, w = preds[:n], acts[:n], w[:n]
    w = np.clip(w, 1e-6, None)
    w = w / w.sum()
    loss = float(np.sum(w * (acts - preds) ** 2))
    return loss


def compute_mahalanobis_distance(
    x: np.ndarray,
    y: np.ndarray,
    cov_inv: np.ndarray = None,
) -> float:
    """
    Standardized Mahalanobis Distance Metrics (Point 84).
    d_M(x, y) = (x-y)' * Sigma^{-1} * (x-y)
    """
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    if len(x) != len(y):
        return 0.0
    diff = x - y
    if cov_inv is None:
        cov_inv = np.eye(len(x))
    d = float(diff @ cov_inv @ diff)
    return max(d, 0.0)

def compute_bma_weights(
    model_likelihoods: list,
    prior_weights: list = None,
) -> list:
    """
    Bayesian Model Averaging (BMA) Ensemble Weighting (Point 85).
    P(M_k | D) prop P(D | M_k) * P(M_k)
    """
    n = len(model_likelihoods)
    if n == 0:
        return []
    if prior_weights is None:
        prior_weights = [1.0 / n] * n
    posteriors = np.array(model_likelihoods) * np.array(prior_weights)
    total = posteriors.sum()
    if total <= 0:
        return [1.0 / n] * n
    return (posteriors / total).tolist()

def compute_mrmr_scores(
    features: pd.DataFrame,
    target: pd.Series,
    n_features: int = 5,
    n_bins: int = 10,
) -> list:
    """
    Max-Relevance Min-Redundancy (mRMR) Feature Selection (Point 86).
    max I(S,Y) - 1/|S| sum I(X_i, X_j)
    """
    mi_weights = compute_mutual_information_distance(features, target, n_bins)
    # Greedy mRMR
    selected = []
    remaining = list(features.columns)
    for _ in range(min(n_features, len(remaining))):
        best_score = -np.inf
        best_col = remaining[0] if remaining else None
        for col in remaining:
            relevance = mi_weights.get(col, 0.0)
            redundancy = 0.0
            if selected:
                redundancy = np.mean([abs(features[col].corr(features[s])) for s in selected])
            score = relevance - 0.5 * abs(redundancy)
            if score > best_score:
                best_score = score
                best_col = col
        if best_col is not None:
            selected.append(best_col)
            remaining.remove(best_col)
    return selected

def compute_loess_prediction(
    x: pd.Series, y: pd.Series, x_pred: float,
    span: int = 20, degree: int = 1,
) -> float:
    """
    Local Polynomial Regression (LOESS) (Point 87).
    min sum w_i * (y_i - x_i * beta)^2 where w_i = (1 - |d_i|)^3
    """
    x_v = pd.to_numeric(x, errors="coerce").dropna().values
    y_v = pd.to_numeric(y, errors="coerce").dropna().values
    n = min(len(x_v), len(y_v))
    if n < span:
        return float(np.mean(y_v)) if n > 0 else 0.0
    x_v, y_v = x_v[-n:], y_v[-n:]
    # Distances from prediction point
    dists = np.abs(x_v - x_pred)
    max_dist = np.percentile(dists, span * 100 // n + 1) + 1e-12
    u = dists / max_dist
    u = np.clip(u, 0.0, 1.0)
    weights = (1.0 - u) ** 3
    weights = np.clip(weights, 1e-6, None)
    # Weighted regression
    X_mat = np.column_stack([np.ones(n), x_v][:degree + 1] if degree == 1 else [np.ones(n), x_v, x_v**2])
    W = np.diag(weights)
    try:
        beta = np.linalg.solve(X_mat.T @ W @ X_mat + 1e-8 * np.eye(X_mat.shape[1]), X_mat.T @ W @ y_v)
    except np.linalg.LinAlgError:
        return float(np.average(y_v, weights=weights))
    x_row = np.array([1.0, x_pred][:degree + 1] if degree == 1 else [1.0, x_pred, x_pred**2])
    pred = float(x_row @ beta)
    return pred if np.isfinite(pred) else float(np.average(y_v, weights=weights))

def compute_linex_loss(
    errors: np.ndarray,
    asymmetry: float = 1.0,
) -> float:
    """
    Asymmetric Imbalance Penalized Loss (Linex Loss) (Point 88).
    L(Delta) = (e^(a*Delta) - a*Delta - 1) / a^2
    """
    e = np.asarray(errors, dtype=float)
    if len(e) == 0:
        return 0.0
    a = asymmetry
    if abs(a) < 1e-8:
        return float(np.mean(e ** 2))  # MSE fallback
    loss = (np.exp(a * e) - a * e - 1.0) / (a ** 2)
    return float(np.mean(loss))

def compute_gmm_soft_membership(
    X: np.ndarray, n_components: int = 3,
    max_iter: int = 20, min_data: int = 30,
) -> dict:
    """
    Continuous Soft Probability State Memberships via GMM (Point 89).
    gamma_k,t = pi_k * N(X_t | mu_k, Sigma_k) / sum_j pi_j * N(X_t | mu_j, Sigma_j)
    Simplified: uses K-means-style assignment with soft membership based on distance.
    """
    if X.ndim < 2 or len(X) < min_data:
        return {"memberships": np.array([[1.0 / max(n_components, 1)] * n_components]), "means": [], "labels": np.array([0])}
    k = min(n_components, len(X))
    # Initialize with random centers
    rng = np.random.RandomState(42)
    indices = rng.choice(len(X), size=k, replace=False)
    centers = X[indices].copy()
    # K-means iterations
    labels = np.zeros(len(X), dtype=int)
    for _ in range(max_iter):
        dists = np.linalg.norm(X[:, None] - centers[None], axis=2)
        new_labels = np.argmin(dists, axis=1)
        if np.array_equal(new_labels, labels):
            break
        labels = new_labels
        for c in range(k):
            mask = labels == c
            if mask.any():
                centers[c] = X[mask].mean(axis=0)
    # Soft membership: inverse distance weighting
    dists = np.linalg.norm(X[:, None] - centers[None], axis=2)
    dists = np.maximum(dists, 1e-8)
    inv_dists = 1.0 / dists
    memberships = inv_dists / inv_dists.sum(axis=1, keepdims=True)
    return {"memberships": memberships, "means": centers.tolist(), "labels": labels}

def compute_min_variance_portfolio(
    cov_matrix: np.ndarray,
    min_weight: float = 0.0,
    max_weight: float = 0.3,
) -> np.ndarray:
    """
    Dynamic Minimum Variance Portfolio Sizing (Point 96).
    w_t = Sigma_t^{-1} * 1 / (1' * Sigma_t^{-1} * 1)
    """
    n = cov_matrix.shape[0]
    try:
        cov_inv = np.linalg.inv(cov_matrix)
    except np.linalg.LinAlgError:
        return np.ones(n) / n
    ones = np.ones(n)
    w = cov_inv @ ones / max(float(ones @ cov_inv @ ones), 1e-12)
    # Clip and re-normalize
    w = np.clip(w, min_weight, max_weight)
    w_sum = w.sum()
    if w_sum > 0:
        w = w / w_sum
    else:
        w = ones / n
    return w

def compute_jensen_alpha(
    local_returns: pd.Series,
    market_returns: pd.Series,
    risk_free_rate: float = 0.0,
    window: int = 50,
    min_periods: int = None,
) -> float:
    """
    Beta-Neutral Risk-Adjusted Attribution — Jensen's Alpha (Point 97).
    alpha_i,t = R_i,t - [R_f,t + beta_i,t * (R_m,t - R_f,t)]
    """
    lr = pd.to_numeric(local_returns, errors="coerce").dropna()
    mr = pd.to_numeric(market_returns, errors="coerce").dropna()
    mp = min_periods or max(10, window // 2)
    n = min(len(lr), len(mr))
    if n < mp:
        return 0.0
    lr = lr.tail(window).values
    mr = mr.tail(window).values
    nn = min(len(lr), len(mr))
    lr, mr = lr[-nn:], mr[-nn:]
    excess_m = mr - risk_free_rate
    var_m = np.var(excess_m)
    if var_m <= 0:
        return 0.0
    beta = np.cov(lr, excess_m)[0, 1] / var_m
    alpha = float(np.mean(lr) - risk_free_rate - beta * np.mean(excess_m))
    return alpha

def compute_rolling_engle_granger(
    series_a: pd.Series,
    series_b: pd.Series,
    window: int,
    min_periods: int = None,
) -> dict:
    """
    Rolling Engle-Granger Cointegration Significance Filter (Point 98).
    Delta e_t = gamma * e_{t-1} + sum phi_i * Delta e_{t-i} + mu_t
    """
    a = pd.to_numeric(series_a, errors="coerce").dropna()
    b = pd.to_numeric(series_b, errors="coerce").dropna()
    mp = min_periods or max(30, window // 2)
    n = min(len(a), len(b))
    if n < mp:
        return {"adf_stat": 0.0, "cointegrated": False, "gamma": 0.0}
    a_v = a.tail(window).values
    b_v = b.tail(window).values
    nn = min(len(a_v), len(b_v))
    a_v, b_v = a_v[-nn:], b_v[-nn:]
    # OLS: a = alpha + beta * b + eps
    X = np.column_stack([np.ones(nn), b_v])
    try:
        beta_hat = np.linalg.lstsq(X, a_v, rcond=None)[0]
    except np.linalg.LinAlgError:
        return {"adf_stat": 0.0, "cointegrated": False, "gamma": 0.0}
    e = a_v - X @ beta_hat
    # ADF regression: Delta e_t = gamma * e_{t-1} + mu
    de = np.diff(e)
    e_lag = e[:-1]
    if len(de) < 3:
        return {"adf_stat": 0.0, "cointegrated": False, "gamma": 0.0}
    X_adf = np.column_stack([np.ones(len(e_lag)), e_lag])
    try:
        adf_coefs = np.linalg.lstsq(X_adf, de, rcond=None)[0]
        gamma = adf_coefs[1]
        resid = de - X_adf @ adf_coefs
        se_gamma = np.std(resid) / max(np.sqrt(np.sum((e_lag - np.mean(e_lag))**2)), 1e-12)
        adf_stat = gamma / max(se_gamma, 1e-12)
    except np.linalg.LinAlgError:
        return {"adf_stat": 0.0, "cointegrated": False, "gamma": 0.0}
    # ADF critical value heuristic: -3.4 for 5% significance
    cointegrated = adf_stat < -2.58
    return {"adf_stat": float(adf_stat), "cointegrated": cointegrated, "gamma": float(gamma)}

def compute_dynamic_risk_parity(
    volatilities: np.ndarray,
    illiquidity: np.ndarray = None,
    lambda_illiq: float = 0.5,
    min_weight: float = 0.0,
    max_weight: float = 0.3,
) -> np.ndarray:
    """
    Dynamic Risk Parity with Liquidity Adjustment (Point 99).
    w_i,t = (1 / sigma_i,t) / sum(1/sigma_j,t) * e^(-lambda * Illiq_i,t)
    """
    vols = np.asarray(volatilities, dtype=float)
    n = len(vols)
    if n == 0:
        return np.array([])
    inv_vol = 1.0 / np.maximum(vols, 1e-8)
    if illiquidity is not None:
        ill = np.asarray(illiquidity, dtype=float)
        ill = np.clip(ill, 0.0, 10.0)
        inv_vol = inv_vol * np.exp(-lambda_illiq * ill)
    total = inv_vol.sum()
    if total <= 0:
        return np.ones(n) / n
    w = inv_vol / total
    w = np.clip(w, min_weight, max_weight)
    w_sum = w.sum()
    if w_sum > 0:
        w = w / w_sum
    else:
        w = np.ones(n) / n
    return w
