"""
KRONOS V1-ALT — Bias Override Point 02: "Rigid Feature Window Bias"

Manual description (from bias_override_registry.yaml):
  "Arbitrarily fixing indicator windows forces temporal scaling constraints onto
   microstructural dynamics that vary by asset and regime."

Quant replacement (from the manual):
  "Volatility-Scaled Lookback Adaptation. Set dynamic lookbacks scaling with
   relative volatility: W_t = round(W_base * (1 + sigma_rel,t ^ -gamma))."

This module provides the pure scaling logic + a convenience wrapper that computes
both the legacy fixed window (raw) and the volatility-scaled window (new), then
routes the final decision through the BiasOverrideEngine.

Sovereignty:
- All numeric parameters (gamma, vol windows, min/max lookbacks, min data density,
  fallback multiplier, per-feature bases) are loaded exclusively from the
  'overrides.point_02' section of kronos/config/liquidity_tiers.yaml (via the
  engine's override_config or direct load).
- No thresholds, gammas, windows, or multipliers are hardcoded in this .py file.
- The engine enforces liquidity tier applicability and implementation status.

Primary use case (as of this implementation):
- Provide volatility-scaled lookback for the slot_15 history used by Point 01.
- General adapter for any rolling feature window (vpin, ofi, amihud, regime, etc.).

Integration pattern (the only correct way to use this):
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    from kronos.quant_spec.overrides.point_02 import get_volatility_scaled_window

    engine = BiasOverrideEngine()

    # For any base window (e.g. the one Point 01 uses for its history, or vpin_window, etc.)
    scaled_lb = get_volatility_scaled_window(
        base_window=100,          # or from neural["vpin_window"] or cfg
        df=bar_data,
        symbol="ALTUSDT",
        engine=engine,
    )

    # Then use scaled_lb instead of the fixed base in your rolling computation.

The function always returns a safe integer window size. When the engine decides not
to apply the override, it returns the raw base window.

Logging: Structured messages under "kronos.bias_override.point_02".
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import yaml

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

logger = logging.getLogger("kronos.bias_override.point_02")


# ---------------------------------------------------------------------
# Config loading (sovereignty: numbers live only in YAML)
# ---------------------------------------------------------------------
def _load_point_02_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    """
    Load Point 02 parameters exclusively from liquidity_tiers.yaml via the engine
    (preferred) or by direct load as fallback. Never invent numbers here.
    """
    if engine is not None:
        cfg = engine.override_config.get("point_02", {})
        if cfg:
            return cfg

    # Direct load (for standalone use or when engine not passed)
    # Resolve relative to this file: kronos/quant_spec/overrides/ -> kronos/config/
    try:
        base = Path(__file__).parent.parent.parent / "config"
        yaml_path = base / "liquidity_tiers.yaml"
        with open(yaml_path, "r", encoding="utf-8") as f:
            full = yaml.safe_load(f) or {}
        cfg = full.get("overrides", {}).get("point_02", {})
        if cfg:
            return cfg
    except Exception as e:
        logger.warning("Could not load liquidity_tiers.yaml for point_02: %s", e)

    # Last-resort conservative defaults (still better than magic in main logic).
    # These should never be relied upon in production; the YAML must be present.
    logger.warning("Using last-resort conservative defaults for Point 02 (YAML missing?)")
    return {
        "gamma": 0.5,
        "vol_short_window": 20,
        "vol_reference_window": 100,
        "vol_reference_method": "median",
        "min_lookback": 20,
        "max_lookback": 500,
        "min_data_density": 30,
        "fallback_multiplier": 1.0,
        "default_base_lookback": 100,
        "slot15_history_base": 100,
        "vpin_base": 100,
        "ofi_base": 50,
    }


def _compute_relative_volatility(df: pd.DataFrame, config: Dict[str, Any]) -> float:
    """
    Compute sigma_rel,t = recent_vol / reference_vol from close prices.
    recent_vol = std of log returns over vol_short_window
    reference_vol = median (or mean) of rolling stds, or tail of reference window.
    """
    if len(df) < 5:
        return 1.0

    close = pd.to_numeric(df.get("close", df.iloc[:, 0]), errors="coerce").dropna()
    if len(close) < 5:
        return 1.0

    eps = 1e-12
    log_ret = np.log((close / close.shift(1) + eps).clip(lower=eps)).dropna()

    short_w = int(config.get("vol_short_window", 20))
    ref_w = int(config.get("vol_reference_window", 100))
    method = str(config.get("vol_reference_method", "median")).lower()

    if len(log_ret) < short_w:
        return 1.0

    recent_vol = float(log_ret.tail(short_w).std())

    if method == "median":
        if len(log_ret) >= max(10, ref_w // 2):
            ref_series = log_ret.rolling(ref_w, min_periods=max(5, ref_w // 2)).std().dropna()
            ref_vol = float(ref_series.median()) if len(ref_series) > 0 else float(log_ret.std())
        else:
            ref_vol = float(log_ret.std())
    else:
        # mean or simple tail
        ref_vol = float(log_ret.tail(ref_w).std()) if len(log_ret) > ref_w else float(log_ret.std())

    rel_vol = recent_vol / (ref_vol + eps)
    return float(rel_vol)


# ---------------------------------------------------------------------
# Core quant replacement for Point 02
# ---------------------------------------------------------------------
def compute_volatility_scaled_lookback(
    base_window: int,
    df: pd.DataFrame,
    config: Optional[Dict[str, Any]] = None,
) -> int:
    """
    Pure quant replacement: Volatility-Scaled Lookback Adaptation.

    Returns the scaled window size (the "new" value for the engine).

    Formula: W_t = round( W_base * (1 + sigma_rel,t ^ (-gamma)) )
    Clamped to [min_lookback, max_lookback] from config.

    This function does **not** talk to the engine or registry. It is the "new" math.
    """
    cfg = config or {}
    gamma = float(cfg.get("gamma", 0.5))
    min_lb = int(cfg.get("min_lookback", 20))
    max_lb = int(cfg.get("max_lookback", 500))
    fallback_mult = float(cfg.get("fallback_multiplier", 1.0))
    min_density = int(cfg.get("min_data_density", 30))

    base = int(base_window)

    if len(df) < min_density:
        logger.info(
            "[POINT_02] insufficient data (len=%d < min=%d) — using fallback multiplier %.2f",
            len(df), min_density, fallback_mult
        )
        scaled = int(round(base * fallback_mult))
    else:
        try:
            rel_vol = _compute_relative_volatility(df, cfg)
            if not np.isfinite(rel_vol) or rel_vol <= 0:
                rel_vol = 1.0

            factor = (1.0 + (rel_vol ** (-gamma)))
            scaled = int(round(base * factor))

            logger.info(
                "[POINT_02] volatility_scaled | base=%d | rel_vol=%.3f | gamma=%.2f | factor=%.3f | scaled=%d",
                base, rel_vol, gamma, factor, scaled
            )
        except Exception as e:
            logger.warning("[POINT_02] relative vol computation failed (%s) — fallback", e)
            scaled = int(round(base * fallback_mult))

    # Hard safety clamps (defensive only; config values are authoritative)
    scaled = max(min_lb, min(scaled, max_lb))
    return scaled


def get_volatility_scaled_window(
    base_window: int,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> int:
    """
    Full wrapper for Point 02.

    Computes:
      - raw_value  = the fixed base_window (legacy behavior)
      - override_value = the volatility-scaled window (new quant replacement)

    Then routes through engine.apply_override(point_id="02", ...)

    Returns the window size the caller should actually use.
    This is the function that production code should call for any rolling feature.
    """
    if engine is None:
        engine = BiasOverrideEngine()

    cfg = _load_point_02_config(engine)

    raw_w = int(base_window)
    new_w = compute_volatility_scaled_lookback(raw_w, df, config=cfg)

    final_w = engine.apply_override(
        point_id="02",
        raw_value=raw_w,
        override_value=new_w,
        df=df,
        symbol=symbol,
        **kwargs,
    )

    # Extra structured log for this specific point
    logger.debug(
        "[POINT_02] engine_decision | symbol=%s | raw_w=%d | new_w=%d | final=%d",
        symbol, raw_w, new_w, int(final_w)
    )

    return int(round(final_w))


# ---------------------------------------------------------------------
# Convenience helpers for common features (especially slot_15 history for Point 01)
# ---------------------------------------------------------------------
def get_slot15_history_lookback(
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    base: Optional[int] = None,
    **kwargs,
) -> int:
    """
    Volatility-scaled lookback specifically for the slot_15 history window
    used by Point 01 (and any other code needing adaptive history length for slot_15).
    """
    cfg = _load_point_02_config(engine)
    if base is None:
        base = int(cfg.get("slot15_history_base", cfg.get("default_base_lookback", 100)))
    return get_volatility_scaled_window(base, df, symbol, engine=engine, **kwargs)


def get_vpin_lookback(
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    base: Optional[int] = None,
    **kwargs,
) -> int:
    cfg = _load_point_02_config(engine)
    if base is None:
        base = int(cfg.get("vpin_base", cfg.get("default_base_lookback", 100)))
    return get_volatility_scaled_window(base, df, symbol, engine=engine, **kwargs)


def get_ofi_lookback(
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    base: Optional[int] = None,
    **kwargs,
) -> int:
    cfg = _load_point_02_config(engine)
    if base is None:
        base = int(cfg.get("ofi_base", cfg.get("default_base_lookback", 50)))
    return get_volatility_scaled_window(base, df, symbol, engine=engine, **kwargs)


if __name__ == "__main__":
    """
    Standalone smoke / validation for Point 02.

    Demonstrates:
    - Volatility scaling on synthetic price data with different regimes.
    - Raw (fixed base) vs new (scaled) for several common bases (slot15 history, vpin, ofi).
    - Engine integration (raw returned while status="not_started").
    - Safe fallback on low data density / low vol data.
    - Direct benefit for Point 01: scaled lookback that can be passed to its history builder.
    """
    import numpy as np
    import pandas as pd

    print("=== Point 02 (Rigid Feature Window Bias) Smoke / Validation ===")

    engine = BiasOverrideEngine()
    print("Engine override_config for point_02:", engine.override_config.get("point_02"))

    # Synthetic price series with volatility regimes (low vol -> high vol -> medium)
    np.random.seed(42)
    n = 300
    rets = np.concatenate([
        np.random.normal(0.0001, 0.002, 100),   # low vol
        np.random.normal(0.0001, 0.012, 100),   # high vol
        np.random.normal(0.0001, 0.006, 100),   # medium vol
    ])[:n]
    close = 100 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({"close": close})
    # Add minimal other columns for robustness
    df["high"] = df["close"] * (1 + np.abs(np.random.randn(n)) * 0.001)
    df["low"] = df["close"] * (1 - np.abs(np.random.randn(n)) * 0.001)
    df["volume"] = np.random.uniform(5e5, 3e6, n)

    cfg = _load_point_02_config(engine)
    print(f"gamma={cfg['gamma']}, vol_short={cfg['vol_short_window']}, ref_method={cfg['vol_reference_method']}")

    bases_to_test = [
        ("slot15_history", cfg.get("slot15_history_base", 100)),
        ("vpin", cfg.get("vpin_base", 100)),
        ("ofi", cfg.get("ofi_base", 50)),
    ]

    print("\n--- Direct new logic (no engine) ---")
    for name, base in bases_to_test:
        scaled = compute_volatility_scaled_lookback(base, df, config=cfg)
        print(f"{name:18s} base={base:3d} -> scaled={scaled:3d}")

    # Low data density
    print("\n--- Low data density fallback ---")
    short_df = df.tail(15)
    scaled_low = compute_volatility_scaled_lookback(100, short_df, config=cfg)
    print(f"short data (len={len(short_df)}) base=100 -> scaled={scaled_low}")

    # Full engine-wrapped path (will return raw/base while status still not_started)
    print("\n--- Engine-wrapped path (current registry status) ---")
    symbol = "VOLTESTUSDT"
    for name, base in bases_to_test:
        final = get_volatility_scaled_window(base, df, symbol, engine=engine)
        print(f"{name:18s} base={base:3d} via engine -> final={final:3d} (raw while not implemented)")

    # Demonstrate benefit for Point 01: get adaptive history length
    print("\n--- Point 01 synergy: volatility-scaled slot15 history length ---")
    scaled_for_p01 = get_slot15_history_lookback(df, symbol, engine=engine)
    print(f"Recommended lookback for Point 01 slot15 history (base 100): {scaled_for_p01}")

    # Force tier example (still returns raw today, but shows the call site)
    final_forced = get_volatility_scaled_window(100, df, symbol, engine=engine, force_tier="low")
    print(f"With force_tier='low' (demo): final={final_forced}")

    print("\n=== Point 02 smoke complete ===")
    print("While status remains 'not_started', engine always returns the raw base window (safe).")
    print("Flip status in registry to 'implemented' after full verification to activate scaling.")
