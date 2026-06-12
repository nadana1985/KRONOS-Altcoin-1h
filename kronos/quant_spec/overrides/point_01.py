"""
KRONOS V1-ALT — Bias Override Point 01
Dynamic Quantile Veto (Vectorized Implementation)

This module implements the Point 01 bias override. It supports both the vectorized
lookback veto on slot_15 series, and the legacy scalar-return proxy override pattern.
"""

from __future__ import annotations

import logging
from typing import Union, Optional, Dict, Any

import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.overrides.point_01")

_DEFAULTS = {
    "lookback": 100,
    "quantile": 0.30,
    "min_periods": 20,
    "fallback_pass_through": True
}


def _load_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_01", engine)
    if cfg:
        merged = dict(_DEFAULTS)
        merged.update(cfg)
        return merged
    return dict(_DEFAULTS)


def compute_vectorized_quantile_veto(
    slot_15: Union[pd.Series, np.ndarray],
    W: int,
) -> Union[pd.Series, np.ndarray]:
    """
    Computes a boolean veto mask for slot_15 values based on a rolling empirical quantile.
    """
    arr = np.asarray(slot_15, dtype=float)
    n = len(arr)
    veto_mask = np.ones(n, dtype=bool)
    
    if n > W:
        windows = np.lib.stride_tricks.sliding_window_view(arr, window_shape=W)
        quantiles = np.nanquantile(windows, 0.65, axis=1)
        T_t = quantiles[:-1]
        current_obs = arr[W:]
        veto_condition = (current_obs < T_t)
        invalid_context = np.isnan(T_t)
        veto_mask[W:] = veto_condition | invalid_context
        
    if isinstance(slot_15, pd.Series):
        return pd.Series(veto_mask, index=slot_15.index, name="veto_mask")
    return veto_mask


def compute_point_01_override(
    slot_15: Union[pd.Series, np.ndarray, float] = None,
    W: Optional[int] = None,
    current_slot15: Optional[float] = None,
    df: Optional[pd.DataFrame] = None,
    symbol: str = '',
    neural: Optional[Dict[str, Any]] = None,
    engine: Optional[BiasOverrideEngine] = None,
    lookback: Optional[int] = None,
) -> Union[pd.Series, np.ndarray, float]:
    """
    Unified entry point routing to either vectorized series veto or legacy scalar veto.
    """
    # Check if we are running in legacy/scalar mode
    is_scalar_call = (
        current_slot15 is not None or 
        df is not None or 
        (slot_15 is not None and isinstance(slot_15, (int, float, np.number)))
    )
    
    if is_scalar_call:
        val = current_slot15 if current_slot15 is not None else float(slot_15)
        
        # Legacy/scalar logic
        try:
            from kronos.quant_spec.bias_override_engine import OVERRIDES_ENABLED
            if not OVERRIDES_ENABLED:
                return val
        except ImportError:
            pass

        if engine is not None:
            try:
                status = engine.registry.get_point("01").status
                active_statuses = {"implemented", "validated", "active"}
                if status not in active_statuses:
                    return val
            except Exception:
                pass

        cfg = _load_config(engine)
        lb = lookback if lookback is not None else int(cfg.get("lookback", 100))
        quantile = float(cfg.get("quantile", 0.30))
        min_periods = int(cfg.get("min_periods", 20))
        fallback_pass = bool(cfg.get("fallback_pass_through", True))

        if df is None:
            return val if fallback_pass else 0.0
            
        try:
            close = pd.to_numeric(df["close"], errors="coerce").dropna()
            if len(close) < min_periods:
                return val if fallback_pass else 0.0

            recent = close.iloc[-lb:] if len(close) > lb else close
            log_rets = np.abs(np.log(recent / recent.shift(1)).dropna().values)

            if len(log_rets) < min_periods:
                return val if fallback_pass else 0.0

            rolling_q = float(np.quantile(log_rets, quantile))

            if val < rolling_q:
                return 0.0
            return val
        except Exception as exc:
            logger.warning("[P01] Error computing quantile veto for %s: %s", symbol, exc)
            return val
            
    else:
        # Vectorized array/series mode
        window = W if W is not None else lookback
        if window is None:
            cfg = _load_config(engine)
            window = int(cfg.get("lookback", 100))
        return compute_vectorized_quantile_veto(slot_15, window)
