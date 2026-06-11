"""
KRONOS V1-ALT — Bias Override Point 01
Dynamic Quantile Veto (replaces static reversal_confidence_min threshold).

Point 01 computes an effective slot_15 value using a rolling quantile of recent
slot_15 history. When overrides are ENABLED, the engine applies a dynamic veto:
signals that fall below the rolling quantile of historical slot_15 values are
suppressed. This replaces the static 0.72 threshold from params_yaml.txt.

When overrides are DISABLED (legacy mode), the function returns current_slot15
unchanged — the static threshold in backtest_runner.py controls the veto.

All numeric parameters are loaded from the engine's override_config
(liquidity_tiers.yaml, 'overrides.point_01') with safe fallbacks.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("kronos.overrides.point_01")

# ── Default config (used if engine / YAML not available) ──────────────
_DEFAULTS: Dict[str, Any] = {
    "quantile": 0.30,          # rolling quantile for dynamic veto (30th pct)
    "lookback": 100,           # bars to compute rolling quantile over
    "min_periods": 20,         # minimum bars before quantile is meaningful
    "fallback_pass_through": True,  # if history too short, pass slot_15 through
}


def _load_config(engine=None) -> Dict[str, Any]:
    """Load Point 01 config from override engine, falling back to defaults."""
    if engine is not None:
        try:
            cfg = engine.override_config.get("point_01", {})
            if cfg:
                merged = dict(_DEFAULTS)
                merged.update(cfg)
                return merged
        except Exception:
            pass
    # Try sovereign config directly
    try:
        import os, sys
        _proj = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        if _proj not in sys.path:
            sys.path.insert(0, _proj)
        from config.utils.sovereign_entrypoint import get_sovereign_config
        ov_cfg = (
            get_sovereign_config()
            .get("backtest", {})
            .get("overrides", {})
            .get("point_01", {})
        )
        if ov_cfg:
            merged = dict(_DEFAULTS)
            merged.update(ov_cfg)
            return merged
    except Exception:
        pass
    return dict(_DEFAULTS)


def compute_point_01_override(
    current_slot15: float,
    df: pd.DataFrame,
    symbol: str,
    neural: Optional[Dict[str, Any]] = None,
    engine=None,
    lookback: Optional[int] = None,
) -> float:
    """
    Compute the effective slot_15 value after applying the dynamic quantile veto.

    When the master override switch is OFF (legacy mode), returns current_slot15
    unchanged so the static threshold in backtest_runner.py takes effect.

    When override switch is ON:
    - Computes a rolling historical quantile of close-price returns as a proxy
      for slot_15 activity levels.
    - If current_slot15 < rolling_quantile, returns 0.0 (veto signal).
    - Otherwise returns current_slot15 (pass through).

    Parameters
    ----------
    current_slot15 : float
        Slot_15 value computed by compute_slots_sovereign().
    df : pd.DataFrame
        Recent OHLCV data for the symbol.
    symbol : str
        Symbol identifier (for logging).
    neural : dict, optional
        Neural slots dict from get_dual_mode_context() (for confidence_min fallback).
    engine : BiasOverrideEngine, optional
        Override engine for config loading and status gating.
    lookback : int, optional
        Override the config lookback. If None, uses config default.

    Returns
    -------
    float
        Effective slot_15: 0.0 (veto) or current_slot15 (pass through).
    """
    # ── Master switch gate ────────────────────────────────────────────
    try:
        from kronos.quant_spec.bias_override_engine import OVERRIDES_ENABLED
        if not OVERRIDES_ENABLED:
            # Legacy mode: return current_slot15 as-is; static threshold in runner controls veto
            logger.debug("[P01] LEGACY mode — pass through slot_15=%.4f for %s", current_slot15, symbol)
            return current_slot15
    except ImportError:
        pass

    # ── Status gate (engine decides if P01 is implemented) ───────────
    if engine is not None:
        try:
            status = engine.registry.get_point("01").status
            active_statuses = {"implemented", "validated", "active"}
            if status not in active_statuses:
                logger.debug("[P01] status=%s — pass through for %s", status, symbol)
                return current_slot15
        except Exception:
            pass

    # ── Load config ───────────────────────────────────────────────────
    cfg = _load_config(engine)
    lb = lookback if lookback is not None else int(cfg.get("lookback", 100))
    quantile = float(cfg.get("quantile", 0.30))
    min_periods = int(cfg.get("min_periods", 20))
    fallback_pass = bool(cfg.get("fallback_pass_through", True))

    # ── Compute rolling quantile proxy from recent returns ───────────
    # We use absolute log returns as a proxy for slot_15 activity level.
    # A low quantile veto means: only pass signals when slot_15 is above
    # the bottom (quantile)% of recent activity — filters out flat noise.
    try:
        close = pd.to_numeric(df["close"], errors="coerce").dropna()
        if len(close) < min_periods:
            logger.debug("[P01] Insufficient history (%d bars) for %s — %s",
                         len(close), symbol, "pass through" if fallback_pass else "veto")
            return current_slot15 if fallback_pass else 0.0

        recent = close.iloc[-lb:] if len(close) > lb else close
        log_rets = np.abs(np.log(recent / recent.shift(1)).dropna().values)

        if len(log_rets) < min_periods:
            return current_slot15 if fallback_pass else 0.0

        rolling_q = float(np.quantile(log_rets, quantile))

        # Veto: if current slot_15 is below the dynamic quantile threshold, suppress
        if current_slot15 < rolling_q:
            logger.info(
                "[P01] VETO: slot_15=%.4f < rolling_q%.0f=%.4f for %s — suppressing signal",
                current_slot15, quantile * 100, rolling_q, symbol,
            )
            return 0.0

        logger.debug(
            "[P01] PASS: slot_15=%.4f >= rolling_q%.0f=%.4f for %s",
            current_slot15, quantile * 100, rolling_q, symbol,
        )
        return current_slot15

    except Exception as exc:
        logger.warning("[P01] Error computing quantile veto for %s: %s — pass through", symbol, exc)
        return current_slot1
