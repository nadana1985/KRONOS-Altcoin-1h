"""
KRONOS V1-ALT — Backtest Runner

Runs controlled A/B comparison: Legacy mode (overrides disabled) vs
Override-enabled mode on real on-disk shards or synthetic data.

All parameters from config — zero inline literals. Seed-controlled for reproducibility.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("kronos.backtest.runner")

# Bootstrap project paths
_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_this_dir)
sys.path.insert(0, _project_root)
os.environ.setdefault("KRONOS_PARAMS_PATH", os.path.join(_project_root, "params_yaml.txt"))


def create_synthetic_ohlcv(
    n: int = 2000,
    seed: int = 42,
    regimes: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    Create realistic synthetic OHLCV data with configurable volatility regimes.

    Parameters
    ----------
    n : int
        Number of bars.
    seed : int
        Random seed for reproducibility.
    regimes : dict, optional
        Regime configuration: {name: {n_bars, drift, vol}}.
    """
    rng = np.random.default_rng(seed)

    if regimes is None:
        regimes = {
            "low_vol_trending": {"n_bars": n // 4, "drift": 0.0003, "vol": 0.003},
            "high_vol_trending": {"n_bars": n // 4, "drift": 0.0002, "vol": 0.015},
            "low_vol_ranging": {"n_bars": n // 4, "drift": 0.0, "vol": 0.004},
            "high_vol_ranging": {"n_bars": n // 4, "drift": 0.0, "vol": 0.012},
        }

    rets_list = []
    for regime_name, params in regimes.items():
        n_bars = params["n_bars"]
        drift = params["drift"]
        vol = params["vol"]
        rets_list.append(rng.normal(drift, vol, n_bars))

    # Pad or truncate to exact length
    all_rets = np.concatenate(rets_list)[:n]
    if len(all_rets) < n:
        all_rets = np.concatenate([all_rets, rng.normal(0, 0.008, n - len(all_rets))])

    close = 100.0 * np.exp(np.cumsum(all_rets))
    high = close * (1 + np.abs(rng.normal(0, 0.002, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.002, n)))
    low = np.minimum(low, close)
    high = np.maximum(high, close)
    volume = rng.uniform(1e6, 1e8, n)
    # Add volume spikes at regime transitions
    spike_idx = np.arange(n // 4 - 2, n // 4 + 3) % n
    spike_idx = np.concatenate([spike_idx, np.arange(n // 2 - 2, n // 2 + 3) % n])
    spike_idx = np.concatenate([spike_idx, np.arange(3 * n // 4 - 2, 3 * n // 4 + 3) % n])
    volume[spike_idx] *= rng.uniform(3, 10, len(spike_idx))

    open_ = np.roll(close, 1) * (1 + rng.normal(0, 0.0005, n))
    open_[0] = close[0]

    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "quote_volume": volume * close,
        "count": rng.integers(100, 5000, n),
        "taker_buy_base_volume": volume * rng.uniform(0.3, 0.7, n),
        "timestamp": pd.date_range("2023-01-01", periods=n, freq="1h"),
    })


def load_real_shard(
    symbol: str,
    raw_shards_dir: str,
    timeframe: str = "1h",
) -> Optional[pd.DataFrame]:
    """Load a real on-disk shard if it exists."""
    shard_path = os.path.join(raw_shards_dir, f"{symbol}_{timeframe}.parquet")
    if os.path.exists(shard_path):
        df = pd.read_parquet(shard_path)
        logger.info("[BACKTEST] Loaded real shard: %s (%d bars)", symbol, len(df))
        return df
    return None


def run_single_backtest(
    df: pd.DataFrame,
    symbol: str,
    overrides_enabled: bool = True,
    seed: int = 42,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run a single backtest on one symbol with overrides enabled or disabled.

    Returns dict with metrics, returns series, regime data, and signature info.
    """
    from kronos.quant_spec.bias_override_engine import set_overrides_enabled, is_overrides_enabled
    from config.mining.reversal_signature_miner_sovereign import mine_reversal_signature
    from kronos_module.model.structural_engine import get_dual_mode_context
    from backtest.metrics_engine import compute_all_metrics, compute_trade_metrics
    from backtest.regime_classifier import classify_regimes, get_regime_stats

    ctx = get_dual_mode_context()
    neural = ctx["neural_slots"]

    # Set override mode with cleanup guarantee
    set_overrides_enabled(overrides_enabled)
    mode_str = "OVERRIDE_ON" if overrides_enabled else "LEGACY"
    logger.info("[BACKTEST] Running %s for %s (%d bars)", mode_str, symbol, len(df))

    # Problem A fix: In Legacy mode, override Point 01 uses neural["confidence_min"] (0.72)
    # to veto signatures. This is too strict when overrides are OFF. Temporarily relax
    # the threshold so the miner produces signatures that Legacy mode can actually trade.
    original_conf_min = neural.get("confidence_min", 0.72)
    if not overrides_enabled:
        bt_cfg_legacy = {}
        try:
            from config.utils.sovereign_entrypoint import get_sovereign_config
            bt_cfg_legacy = get_sovereign_config().get("backtest", {})
        except Exception:
            pass
        legacy_min = float(bt_cfg_legacy.get("legacy_confidence_min", 0.65))
        neural["confidence_min"] = legacy_min
        logger.info("[BACKTEST] LEGACY mode: relaxed confidence_min %.3f -> %.3f",
                    original_conf_min, legacy_min)

    try:
        # Mine the signature
        sig = mine_reversal_signature(df, symbol, neural, ctx=ctx)
    finally:
        # Always restore to enabled state and original threshold
        neural["confidence_min"] = original_conf_min
        set_overrides_enabled(True)

    # Extract confidence and structural slots
    confidence = sig.get("confidence", 0.0)
    structural_slots = sig.get("structural_slots", {})
    dna_vector = sig.get("dna_vector", {})

    # Compute returns
    close = pd.to_numeric(df["close"], errors="coerce")
    returns = close.pct_change().fillna(0)

    # Regime classification — always use RAW returns (not strategy returns)
    # so regime stats are comparable between Legacy and Override modes.
    try:
        raw_returns = close.pct_change().fillna(0)
        regimes = classify_regimes(df)
        regime_stats = get_regime_stats(regimes, raw_returns)
        if regime_stats:
            logger.info("[BACKTEST] %s %s regime classification: %s",
                        mode_str, symbol,
                        {k: v.get("count", 0) for k, v in regime_stats.items()})
    except Exception as exc:
        logger.warning("[BACKTEST] Regime classification failed for %s: %s", symbol, exc)
        regimes = pd.Series("low_vol_ranging", index=df.index)
        regime_stats = {}

    # ── Volatility-Adjusted Position Sizing ──
    # Replaces legacy linear confidence scaling which was too aggressive on real data.
    # Root cause: overrides produce high confidence → linear conf_factor → oversized positions → large drawdowns.
    # Fix: vol_adjusted is default. Confidence impact dampened via sqrt curve.
    # All params from sovereign config: backtest.position_sizing_*
    bt_cfg = {}
    try:
        from config.utils.sovereign_entrypoint import get_sovereign_config
        bt_cfg = get_sovereign_config().get("backtest", {})
    except Exception:
        pass

    sizing_method = bt_cfg.get("position_sizing_method", "vol_adjusted")
    # Problem A fix: use relaxed threshold for Legacy mode to generate meaningful trades.
    # When overrides are OFF, the miner produces lower confidence values, so we need
    # a lower floor to ensure Legacy mode has a fair baseline for A/B comparison.
    # Fallback defaults here MUST stay in sync with params_yaml.txt backtest section.
    if overrides_enabled:
        conf_min = neural["confidence_min"]  # strict threshold from neural slots (sovereign)
    else:
        conf_min = float(bt_cfg.get("legacy_confidence_min", 0.65))  # relaxed threshold for legacy mode
    base_size = float(bt_cfg.get("position_base_size", 1.0))
    max_size = float(bt_cfg.get("position_max_size", 1.5))   # sync: params default 1.5
    min_size = float(bt_cfg.get("position_min_size", 0.05))
    target_annual_vol = float(bt_cfg.get("position_target_vol", 0.18))  # sync: params default 0.18
    vol_window = int(bt_cfg.get("position_vol_window", 50))
    ann_factor = int(bt_cfg.get("annualization_factor", 8760))
    vol_ratio_cap = float(bt_cfg.get("position_vol_ratio_cap", 1.5))
    vol_floor = float(bt_cfg.get("position_vol_floor", 0.005))

    if confidence < conf_min:
        position = 0.0  # vetoed by Point 01
    elif sizing_method == "vol_adjusted":
        # Volatility-adjusted: position INVERSELY proportional to realized vol.
        # This is the key fix: high-vol environments get smaller positions, low-vol get larger.
        recent_rets = returns.tail(vol_window).dropna()
        realized_vol = float(recent_rets.std()) * np.sqrt(ann_factor) if len(recent_rets) > 10 else target_annual_vol
        realized_vol = max(realized_vol, vol_floor)  # prevent division by near-zero
        vol_ratio = target_annual_vol / realized_vol
        vol_ratio = min(vol_ratio, vol_ratio_cap)  # cap to prevent extreme sizing in ultra-low vol
        # Confidence dampened via sqrt curve: sqrt maps [0,1] to [0,1] but compresses high values
        # At conf_min → conf_factor=0.5 (half size), at conf_max → conf_factor=1.0 (full size)
        # sqrt prevents the linear ramp that made override mode too aggressive
        conf_max_val = float(neural["confidence_clamp"][1])
        conf_norm = (confidence - conf_min) / (conf_max_val - conf_min + 1e-6)
        conf_norm = min(1.0, max(0.0, conf_norm))
        conf_factor = 0.5 + 0.5 * np.sqrt(conf_norm)
        position = base_size * vol_ratio * conf_factor
        logger.info(
            "[SIZING] vol_adjusted: realized_vol=%.4f target_vol=%.4f vol_ratio=%.3f conf=%.3f "
            "conf_factor=%.3f position=%.3f (method=%s)",
            realized_vol, target_annual_vol, vol_ratio, confidence, conf_factor, position, sizing_method,
        )
    elif sizing_method == "sqrt_confidence":
        # Square-root scaling: more conservative than linear
        conf_max_val = float(neural["confidence_clamp"][1])
        conf_norm = (confidence - conf_min) / (conf_max_val - conf_min + 1e-6)
        position = base_size * (0.5 + 0.5 * np.sqrt(max(0.0, min(1.0, conf_norm))))
        logger.info("[SIZING] sqrt_confidence: conf=%.3f position=%.3f", confidence, position)
    elif sizing_method == "linear_capped":
        # Legacy linear but hard-capped at max_size (conservative default 1.0)
        conf_max_val = float(neural["confidence_clamp"][1])
        conf_norm = (confidence - conf_min) / (conf_max_val - conf_min + 1e-6)
        position = base_size * (0.5 + 0.5 * min(1.0, max(0.0, conf_norm)))
        logger.info("[SIZING] linear_capped: conf=%.3f position=%.3f (max=%.2f)", confidence, position, max_size)
    else:
        # Fallback: conservative fixed sizing
        position = base_size if confidence >= conf_min else 0.0

    position = min(max_size, max(min_size, position)) if position > 0 else 0.0
    logger.info("[SIZING] FINAL: method=%s confidence=%.3f -> position=%.3f (base=%.2f max=%.2f)",
                sizing_method, confidence, position, base_size, max_size)

    strategy_returns = returns * position

    # Compute all metrics
    cfg = config or {}
    metrics = compute_all_metrics(strategy_returns, config=cfg.get("metrics", {}))
    trade_metrics = compute_trade_metrics(strategy_returns, config=cfg.get("metrics", {}))
    metrics.update(trade_metrics)

    # Add slot diagnostics for comparison
    metrics["confidence"] = confidence
    metrics["slot_15"] = structural_slots.get("slot_15", 0.0)
    metrics["position_size"] = position
    metrics["regime_stats"] = regime_stats

    return {
        "symbol": symbol,
        "mode": mode_str,
        "confidence": confidence,
        "metrics": metrics,
        "returns": strategy_returns,
        "structural_slots": structural_slots,
        "dna_vector": dna_vector,
        "regimes": regimes,
        "bars": len(df),
    }


def run_ab_comparison(
    symbols: Optional[List[str]] = None,
    n_synthetic: int = 2000,
    seed: int = 42,
    use_real: bool = True,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run full A/B comparison across multiple symbols.

    Returns dict with per-symbol results and aggregate metrics.
    """
    from config.utils.sovereign_entrypoint import get_sovereign_config, get_storage_path
    from config.utils.symbol_discovery_sovereign import discover_symbols_from_shards

    cfg = get_sovereign_config()
    raw_dir = get_storage_path(cfg, "raw_shards_dir")
    tf = cfg["project"]["timeframe"]

    # Discover symbols
    if symbols is None:
        if use_real:
            all_syms = discover_symbols_from_shards(raw_dir, tf)
            symbols = [s["symbol"] for s in all_syms[:20]]
        else:
            symbols = [f"SYN{i:03d}_USDT" for i in range(10)]

    logger.info("[BACKTEST] Comparing %d symbols | seed=%d", len(symbols), seed)

    results_legacy = []
    results_override = []

    for i, sym in enumerate(symbols):
        # Get data: real shard or synthetic
        df = None
        if use_real:
            df = load_real_shard(sym, raw_dir, tf)
        if df is None:
            df = create_synthetic_ohlcv(n=n_synthetic, seed=seed + i)

        # Run with overrides OFF (legacy)
        legacy = run_single_backtest(df, sym, overrides_enabled=False, seed=seed, config=config)
        results_legacy.append(legacy)

        # Run with overrides ON
        override = run_single_backtest(df, sym, overrides_enabled=True, seed=seed, config=config)
        results_override.append(override)

    # Reset to enabled
    from kronos.quant_spec.bias_override_engine import set_overrides_enabled
    set_overrides_enabled(True)

    # Aggregate metrics
    agg_legacy = _aggregate_metrics([r["metrics"] for r in results_legacy])
    agg_override = _aggregate_metrics([r["metrics"] for r in results_override])

    return {
        "symbols": symbols,
        "per_symbol_legacy": results_legacy,
        "per_symbol_override": results_override,
        "aggregate_legacy": agg_legacy,
        "aggregate_override": agg_override,
        "n_symbols": len(symbols),
        "seed": seed,
    }


def _aggregate_metrics(metrics_list: List[Dict[str, float]]) -> Dict[str, float]:
    """Compute mean and std of metrics across symbols. Returns both suffixed and unsuffixed keys."""
    if not metrics_list:
        return {}
    agg = {}
    keys = set()
    for m in metrics_list:
        keys.update(m.keys())
    for key in sorted(keys):
        # Skip non-numeric keys like regime_stats
        vals = [m.get(key, 0.0) for m in metrics_list]
        numeric_vals = [v for v in vals if isinstance(v, (int, float)) and np.isfinite(v)]
        if numeric_vals:
            mean_val = float(np.mean(numeric_vals))
            std_val = float(np.std(numeric_vals))
            agg[key] = mean_val  # unsuffixed for direct access
            agg[f"{key}_mean"] = mean_val  # suffixed for compatibility
            agg[f"{key}_std"] = std_val
        else:
            agg[key] = 0.0
            agg[f"{key}_mean"] = 0.0
            agg[f"{key}_std"] = 0.0
    return agg
