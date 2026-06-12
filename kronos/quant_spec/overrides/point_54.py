"""
KRONOS V1-ALT — Bias Override Point 54: "Homoskedastic Multi-Asset Volatility Matrices"
(Dynamic Conditional Correlation GARCH + Analytical OAS Hardened Implementation)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_garch_vol, compute_close_to_close_vol
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

_logger = logging.getLogger("kronos.bias_override.point_54")

_DEFAULT_POINT_54_CONFIG = {
    "garch_window": 50,
    "dcc_alpha": 0.05,
    "dcc_beta": 0.9,
    "min_data_density": 100,
    "fallback_vol": 0.01,
}


def _load_point_54_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_54", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_54_CONFIG


def compute_oas_shrinkage(S: np.ndarray, n: int) -> float:
    """
    Computes the analytical Oracle Approximating Shrinkage (OAS) coefficient
    based on empirical Frobenius matrix norms.
    """
    p = S.shape[0]
    if p <= 1 or n <= 1:
        return 0.0
        
    tr_S = np.trace(S)
    tr_S2 = np.trace(S @ S)
    
    num = (1.0 - 2.0 / p) * tr_S2 + tr_S**2
    den = (n + 1.0 - 2.0 / p) * (tr_S2 - (tr_S**2) / p)
    
    if den <= 0:
        return 1.0
    rho = num / den
    return float(np.clip(rho, 0.0, 1.0))


def compute_dcc_garch_adjusted_vol(
    local_returns: pd.Series,
    market_returns: Optional[pd.Series] = None,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """
    DCC-GARCH adjusted volatility using dynamic correlation updates and OAS regularization.
    """
    cfg = config or _DEFAULT_POINT_54_CONFIG
    w = int(cfg.get("garch_window", 50))
    dcc_a = float(cfg.get("dcc_alpha", 0.05))
    dcc_b = float(cfg.get("dcc_beta", 0.9))
    min_d = int(cfg.get("min_data_density", 100))
    fb = float(cfg.get("fallback_vol", 0.01))

    if len(local_returns) < min_d:
        return fb

    # Local GARCH vol
    local_vol = compute_garch_vol(local_returns, 1e-6, 0.08, 0.85, w)
    if not np.isfinite(local_vol) or local_vol <= 0:
        local_vol = fb

    if market_returns is None or len(market_returns) < min_d:
        return float(local_vol)

    # Convert to tail arrays for DCC
    lr = local_returns.tail(w).dropna().values
    mr = market_returns.tail(w).dropna().values
    n = min(len(lr), len(mr))
    if n < 10:
        return local_vol

    lr = lr[-n:]
    mr = mr[-n:]

    # Standardized innovation vectors
    lr_std = (lr - lr.mean()) / (lr.std() + 1e-12)
    mr_std = (mr - mr.mean()) / (mr.std() + 1e-12)

    # Unconditional correlation R_bar
    R_bar = float(np.corrcoef(lr_std, mr_std)[0, 1])
    R_bar = np.clip(R_bar, -0.9, 0.9)

    # DCC Temporal Recursion
    R_bar_mat = np.array([[1.0, R_bar], [R_bar, 1.0]])
    Q = R_bar_mat.copy()
    for t in range(1, n):
        eps_t = np.array([lr_std[t-1], mr_std[t-1]])
        innovation = np.outer(eps_t, eps_t)
        Q = (1.0 - dcc_a - dcc_b) * R_bar_mat + dcc_a * innovation + dcc_b * Q

    # Analytical OAS Shrinkage Regularization
    rho = compute_oas_shrinkage(Q, n)
    Q = (1.0 - rho) * Q + rho * np.eye(2)

    # Ensure positive definite matrix properties safely
    eigvals = np.linalg.eigvalsh(Q)
    if eigvals[0] <= 0:
        Q += (abs(eigvals[0]) + 1e-8) * np.eye(2)

    # Dynamic correlation from recursion output
    dyn_corr = Q[0, 1] / np.sqrt(Q[0, 0] * Q[1, 1] + 1e-12)
    dyn_corr = np.clip(dyn_corr, -0.9, 0.9)

    # Adjust local vol by dyn corr effect (spillover)
    adj_vol = local_vol * (1 + abs(dyn_corr) * 0.2)
    return float(max(adj_vol, fb * 0.5))


def compute_point_54_override(
    raw_vol: float,
    df: pd.DataFrame,
    symbol: str,
    market_returns: Optional[pd.Series] = None,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    """
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_54_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    r = (c / c.shift(1) - 1.0).dropna()

    raw_val = float(raw_vol) if np.isfinite(raw_vol) else compute_close_to_close_vol(c, int(cfg.get("garch_window", 50)))
    new_val = compute_dcc_garch_adjusted_vol(r, market_returns, config=cfg)

    final = engine.apply_override(
        point_id="54",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    return float(final)
