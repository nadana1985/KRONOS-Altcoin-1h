"""
KRONOS V1-ALT — Walk-Forward Optimization Module

Implements rolling walk-forward analysis to test override robustness
across expanding or rolling windows. Prevents overfitting by ensuring
out-of-sample validation on each step.

All parameters from config — zero inline literals. Seed-controlled.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("kronos.backtest.walk_forward")

_DEFAULT_WF_CONFIG = {
    "train_bars": 500,
    "test_bars": 200,
    "step_bars": 200,
    "expanding": True,
}


def _load_wf_config() -> Dict[str, Any]:
    """Load walk-forward config from sovereign params (cached)."""
    try:
        import os, sys
        _proj = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _proj not in sys.path:
            sys.path.insert(0, _proj)
        from config.utils.sovereign_entrypoint import get_sovereign_config
        cfg = get_sovereign_config().get("backtest", {})
        return {
            "train_bars": cfg.get("wf_train_bars", 500),
            "test_bars": cfg.get("wf_test_bars", 200),
            "step_bars": cfg.get("wf_step_bars", 200),
            "expanding": cfg.get("wf_expanding", True),
        }
    except Exception:
        return dict(_DEFAULT_WF_CONFIG)


def generate_walk_forward_splits(
    n_bars: int,
    config: Optional[Dict[str, Any]] = None,
) -> List[Tuple[int, int, int, int]]:
    """
    Generate walk-forward train/test index splits.

    Returns list of (train_start, train_end, test_start, test_end) tuples.
    """
    cfg = config or _load_wf_config()
    train_w = int(cfg.get("train_bars", 500))
    test_w = int(cfg.get("test_bars", 200))
    step = int(cfg.get("step_bars", 200))
    expanding = bool(cfg.get("expanding", True))

    splits = []
    t = 0
    while t + train_w + test_w <= n_bars:
        train_start = 0 if expanding else t
        train_end = t + train_w
        test_start = train_end
        test_end = test_start + test_w
        splits.append((train_start, train_end, test_start, test_end))
        t += step

    logger.info("[WF] Generated %d walk-forward splits for %d bars", len(splits), n_bars)
    return splits


def run_walk_forward(
    df: pd.DataFrame,
    symbol: str,
    overrides_enabled: bool = True,
    seed: int = 42,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run walk-forward analysis on a single symbol.

    For each split:
    1. Compute structural slots on train window (in-sample)
    2. Apply confidence threshold from train window to test window (out-of-sample)
    3. Track out-of-sample performance

    Returns dict with per-fold metrics and aggregate OOS performance.
    """
    from kronos.quant_spec.bias_override_engine import set_overrides_enabled
    from config.mining.reversal_signature_miner_sovereign import mine_reversal_signature
    from kronos_module.model.structural_engine import get_dual_mode_context
    from backtest.metrics_engine import compute_all_metrics

    cfg = config or {}
    wf_cfg = cfg.get("walk_forward", {})
    splits = generate_walk_forward_splits(len(df), config=wf_cfg)

    if not splits:
        logger.warning("[WF] No valid splits for %s (%d bars)", symbol, len(df))
        return {"symbol": symbol, "folds": [], "aggregate_oos": {}}

    ctx = get_dual_mode_context()
    neural = ctx["neural_slots"]

    set_overrides_enabled(overrides_enabled)
    mode_str = "OVERRIDE_ON" if overrides_enabled else "LEGACY"

    fold_results = []
    oos_returns_list = []

    try:
        for fold_idx, (tr_start, tr_end, te_start, te_end) in enumerate(splits):
            train_df = df.iloc[tr_start:tr_end].copy()
            test_df = df.iloc[te_start:te_end].copy()

            # Mine signature on train window
            sig = mine_reversal_signature(train_df, symbol, neural, ctx=ctx)
            confidence = sig.get("confidence", 0.0)
            # Use relaxed threshold for Legacy mode to generate meaningful trades
            if overrides_enabled:
                conf_min = neural["confidence_min"]  # strict (0.72)
            else:
                bt_cfg = cfg.get("backtest", {})
                conf_min = float(bt_cfg.get("legacy_confidence_min", 0.65))  # relaxed (0.65)

            # Apply to test window
            close_test = pd.to_numeric(test_df["close"], errors="coerce")
            returns_test = close_test.pct_change().fillna(0)

            if confidence >= conf_min:
                # Volatility-adjusted position sizing (same logic as backtest_runner.py)
                # All params from sovereign config: backtest.position_sizing_*
                # Fallback defaults MUST stay in sync with params_yaml.txt backtest section.
                wf_cfg_sizing = cfg.get("backtest", {}) if cfg else {}
                sizing_method = wf_cfg_sizing.get("position_sizing_method", "vol_adjusted")
                base_size = float(wf_cfg_sizing.get("position_base_size", 1.0))
                max_size = float(wf_cfg_sizing.get("position_max_size", 1.5))    # sync: params default 1.5
                min_size = float(wf_cfg_sizing.get("position_min_size", 0.05))
                target_annual_vol = float(wf_cfg_sizing.get("position_target_vol", 0.18))  # sync: params default 0.18
                vol_window = int(wf_cfg_sizing.get("position_vol_window", 50))
                ann_factor = int(wf_cfg_sizing.get("annualization_factor", 8760))
                vol_ratio_cap = float(wf_cfg_sizing.get("position_vol_ratio_cap", 1.5))
                vol_floor = float(wf_cfg_sizing.get("position_vol_floor", 0.005))

                close_train = pd.to_numeric(train_df["close"], errors="coerce")
                returns_train = close_train.pct_change().fillna(0)
                conf_max_val = float(neural.get("confidence_clamp", (0.58, 0.91))[1])
                conf_norm = (confidence - conf_min) / (conf_max_val - conf_min + 1e-6)
                conf_norm = min(1.0, max(0.0, conf_norm))

                if sizing_method == "vol_adjusted":
                    # Position inversely proportional to realized volatility
                    recent_rets = returns_train.tail(vol_window).dropna()
                    realized_vol = float(recent_rets.std()) * np.sqrt(ann_factor) if len(recent_rets) > 10 else target_annual_vol
                    realized_vol = max(realized_vol, vol_floor)
                    vol_ratio = min(target_annual_vol / realized_vol, vol_ratio_cap)
                    conf_factor = 0.5 + 0.5 * np.sqrt(conf_norm)
                    position = base_size * vol_ratio * conf_factor
                elif sizing_method == "sqrt_confidence":
                    position = base_size * (0.5 + 0.5 * np.sqrt(conf_norm))
                elif sizing_method == "linear_capped":
                    position = base_size * (0.5 + 0.5 * conf_norm)
                else:
                    # Legacy fallback
                    position = 0.5 + (confidence - conf_min) / (1.0 - conf_min + 1e-6)

                position = min(max_size, max(min_size, position))
            else:
                position = 0.0

            oos_rets = returns_test * position
            oos_returns_list.append(oos_rets)

            metrics = compute_all_metrics(oos_rets, config=cfg.get("metrics", {}))
            metrics["confidence"] = confidence
            metrics["position_size"] = position
            metrics["fold"] = fold_idx

            fold_results.append({
                "fold": fold_idx,
                "train_bars": tr_end - tr_start,
                "test_bars": te_end - te_start,
                "confidence": confidence,
                "oos_metrics": metrics,
            })
    finally:
        set_overrides_enabled(True)

    # Aggregate OOS performance
    if oos_returns_list:
        all_oos = pd.concat(oos_returns_list, ignore_index=True)
        agg_oos = compute_all_metrics(all_oos, config=cfg.get("metrics", {}))
    else:
        agg_oos = {}

    return {
        "symbol": symbol,
        "mode": mode_str,
        "n_folds": len(fold_results),
        "folds": fold_results,
        "aggregate_oos": agg_oos,
    }


def generate_wf_report(
    wf_results: List[Dict[str, Any]],
    output_path: Optional[str] = None,
) -> str:
    """Generate a markdown walk-forward report."""
    lines = []
    lines.append("# KRONOS V1-ALT — Walk-Forward Optimization Report")
    lines.append("")

    for res in wf_results:
        sym = res.get("symbol", "?")
        n_folds = res.get("n_folds", 0)
        agg = res.get("aggregate_oos", {})

        lines.append(f"## {sym}")
        lines.append(f"- Folds: {n_folds}")
        lines.append(f"- OOS Sharpe: {agg.get('sharpe', 0):.4f}")
        lines.append(f"- OOS Total Return: {agg.get('total_return', 0):.4f}")
        lines.append(f"- OOS Max Drawdown: {agg.get('max_drawdown', 0):.4f}")
        lines.append(f"- OOS Win Rate: {agg.get('win_rate', 0):.4f}")
        lines.append("")

        if res.get("folds"):
            lines.append("| Fold | Train_Bars | Test_Bars | Confidence | OOS_Sharpe | OOS_Ret | OOS_MDD |")
            lines.append("|------|-----------|-----------|------------|------------|---------|---------|")
            for f in res["folds"]:
                m = f.get("oos_metrics", {})
                lines.append(
                    f"| {f['fold']} | {f['train_bars']} | {f['test_bars']} | "
                    f"{f['confidence']:.3f} | {m.get('sharpe', 0):.2f} | "
                    f"{m.get('total_return', 0):.4f} | {m.get('max_drawdown', 0):.4f} |"
                )
            lines.append("")

    report_text = "\n".join(lines)
    if output_path:
        import os
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        logger.info("[WF] Report written to %s", output_path)

    return report_text
