"""
KRONOS V5.1 — Individual Override Points Ablation Study

Systematically tests each logical group of override points to measure
marginal contribution to key risk/return metrics.

Usage:
    python backtest/run_ablation_study.py [--real] [--symbols 10] [--seed 42]

Config-driven via params_yaml.txt -> neural.point_XX_enabled flags.
"""
import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

_project_root = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, _project_root)
os.environ.setdefault("KRONOS_PARAMS_PATH", os.path.join(_project_root, "params_yaml.txt"))

logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger("kronos.ablation")
logging.getLogger("kronos").setLevel(logging.WARNING)

# ── Group Definitions ─────────────────────────────────────────────
# Each group has: label, point_numbers (the XX from point_XX_enabled), category
OVERRIDE_GROUPS = {
    "core_dynamic": {
        "label": "Core Dynamic (01-03)",
        "points": [1, 2, 3],
        "category": "High",
        "description": "Dynamic gating, volatility-scaled lookback, SVD compression",
    },
    "risk_tail": {
        "label": "Risk & Tail (15,64,72)",
        "points": [15, 64, 72],
        "category": "High",
        "description": "Asymmetric barriers, VaR/ES, Hill tail index",
    },
    "volatility": {
        "label": "Volatility (48,52,56,57)",
        "points": [48, 52, 56, 57],
        "category": "High",
        "description": "MAD vol, downside semi-vol, beta-neutral, bounce-corrected RS",
    },
    "order_flow": {
        "label": "Order Flow (11,24)",
        "points": [11, 24],
        "category": "Medium",
        "description": "Volume-sync EWMA, fractional diff OFI",
    },
    "microstructure": {
        "label": "Microstructure (06,19,23,25,29)",
        "points": [6, 19, 23, 25, 29],
        "category": "Medium",
        "description": "Amihud decay, wick mapping, eigenvalue weight, S/R entropy, Kendall trend",
    },
    "robust_stats": {
        "label": "Robust Stats (66,69)",
        "points": [66, 69],
        "category": "Medium",
        "description": "Huber return, Fisher skewness",
    },
    "validation": {
        "label": "Validation (35,36,82)",
        "points": [35, 36, 82],
        "category": "Medium",
        "description": "Purging/embargo, OU bridge imputation, causal lag",
    },
    "vol_batch2": {
        "label": "Vol Batch2 (46,47)",
        "points": [46, 47],
        "category": "Medium",
        "description": "Yang-Zhang vol, Parkins vol",
    },
    "misc_b5": {
        "label": "Batch5 Misc (28,44)",
        "points": [28, 44],
        "category": "Low",
        "description": "Hurst-adaptive profile, info-weighted operators",
    },
}

# All enabled point numbers (26 total from params_yaml.txt neural section)
ALL_ENABLED_POINTS = [1, 2, 3, 6, 11, 15, 19, 23, 24, 25, 28, 29, 35, 36, 44, 46, 47, 48, 52, 56, 57, 64, 66, 69, 72, 82]

# Point numbers that DON'T have enabled flags but ARE implemented (always on if overrides_enabled=True)
# These are points that exist in the override system but aren't in our enabled/disable list
# They will always be active when overrides_enabled=True regardless of our group selection.
# We need to handle this: we'll use the OVERRIDES_ENABLED=False approach instead to truly isolate groups.
# Actually, the cleanest approach is to use the override_config_cache and set enabled=False for non-group points.


def set_group_enabled(group_points: List[int]) -> None:
    """
    Enable ONLY the specified group of override points and disable all others.
    Uses the module-level disable_override_points / enable_all_override_points
    from bias_override_engine to suppress non-group points at runtime.
    """
    from kronos.quant_spec.bias_override_engine import disable_override_points, enable_all_override_points

    points_to_disable = set(ALL_ENABLED_POINTS) - set(group_points)
    if len(points_to_disable) == len(ALL_ENABLED_POINTS):
        # No group points enabled — this would disable ALL, which is same as legacy
        disable_override_points(set(ALL_ENABLED_POINTS))
    else:
        # Disable all non-group points
        disable_override_points(points_to_disable)

    logger.info("[ABLATION] Enabled points: %s | Disabled: %s", group_points, list(points_to_disable))


def reset_all_points_enabled() -> None:
    """Reset all override points to enabled=True."""
    from kronos.quant_spec.bias_override_engine import enable_all_override_points
    enable_all_override_points()


def run_ablation_group(
    group_key: str,
    group_cfg: Dict[str, Any],
    df: pd.DataFrame,
    symbol: str,
    seed: int = 42,
) -> Dict[str, float]:
    """Run backtest with ONLY one group of overrides enabled."""
    group_points = group_cfg["points"]

    # Enable only this group
    set_group_enabled(group_points)

    # Run backtest with overrides ON but only our group's points active
    from backtest.backtest_runner import run_single_backtest

    result = run_single_backtest(df, symbol, overrides_enabled=True, seed=seed)
    metrics = result.get("metrics", {})

    return {
        "confidence": result.get("confidence", 0),
        "position_size": metrics.get("position_size", 0),
        "total_return": metrics.get("total_return", 0),
        "sharpe": metrics.get("sharpe", 0),
        "sortino": metrics.get("sortino", 0),
        "max_drawdown": metrics.get("max_drawdown", 0),
        "calmar": metrics.get("calmar", 0),
        "var_95": metrics.get("var_95", 0),
        "expected_shortfall": metrics.get("expected_shortfall", 0),
        "profit_factor": metrics.get("profit_factor", 0),
        "win_rate": metrics.get("win_rate", 0),
        "tail_ratio": metrics.get("tail_ratio", 0),
        "skewness": metrics.get("skewness", 0),
        "kurtosis": metrics.get("kurtosis", 0),
    }


def run_full_ablation_study(
    symbols: List[str],
    n_synthetic: int = 2000,
    seed: int = 42,
    use_real: bool = False,
) -> Dict[str, Any]:
    """
    Run ablation study across all groups + baseline modes.
    """
    from backtest.backtest_runner import create_synthetic_ohlcv, load_real_shard, run_single_backtest
    from config.utils.sovereign_entrypoint import get_sovereign_config, get_storage_path

    cfg = get_sovereign_config()
    raw_dir = get_storage_path(cfg, "raw_shards_dir")
    tf = cfg["project"]["timeframe"]

    # ── Baseline: Legacy mode (no overrides) ──
    all_results: Dict[str, List[Dict[str, float]]] = {"legacy_baseline": [], "full_override": []}

    print("\n" + "=" * 80)
    print("  KRONOS V5.1 — Override Ablation Study")
    print("=" * 80)
    print(f"\n  Running {len(symbols)} symbols | seed={seed}")
    if use_real:
        print(f"  Mode: REAL SHARDS from {raw_dir}")
    else:
        print(f"  Mode: SYNTHETIC ({n_synthetic} bars)")

    for i, sym in enumerate(symbols):
        # Get data
        df = None
        if use_real:
            df = load_real_shard(sym, raw_dir, tf)
        if df is None:
            df = create_synthetic_ohlcv(n=n_synthetic, seed=seed + i)

        print(f"\n  [{i+1}/{len(symbols)}] {sym} ({len(df)} bars)")

        # Legacy baseline
        reset_all_points_enabled()
        leg = run_single_backtest(df, sym, overrides_enabled=False, seed=seed)
        all_results["legacy_baseline"].append(leg.get("metrics", {}))

        # Full override (all points enabled)
        reset_all_points_enabled()
        full = run_single_backtest(df, sym, overrides_enabled=True, seed=seed)
        all_results["full_override"].append(full.get("metrics", {}))

        # Each group
        for gkey, gcfg in OVERRIDE_GROUPS.items():
            if gkey not in all_results:
                all_results[gkey] = []

            grp = run_ablation_group(gkey, gcfg, df, sym, seed=seed)
            all_results[gkey].append(grp)
            print(f"         Group {gcfg['label']}: Sharpe={grp.get('sharpe', 0):.3f} "
                  f"MDD={grp.get('max_drawdown', 0):.4f} "
                  f"PF={grp.get('profit_factor', 0):.3f}")

    # Reset
    reset_all_points_enabled()

    # ── Aggregate ──
    aggregated = {}
    print("\n" + "=" * 80)
    print("  AGGREGATE RESULTS (mean across symbols)")
    print("=" * 80)

    # Key metrics table header
    key_metrics = [
        ("sharpe", "Sharpe"),
        ("sortino", "Sortino"),
        ("max_drawdown", "Max DD"),
        ("calmar", "Calmar"),
        ("profit_factor", "PF"),
        ("win_rate", "WinRate"),
        ("tail_ratio", "TailR"),
        ("expected_shortfall", "ES"),
    ]

    header = f"{'Mode':<30} {'Sharpe':>8} {'Sortino':>8} {'Max DD':>8} {'Calmar':>8} {'PF':>7} {'WinRate':>8} {'TailR':>7} {'ES':>8}"
    print("\n" + header)
    print("-" * len(header))

    for mode_key in ["legacy_baseline", "full_override"] + list(OVERRIDE_GROUPS.keys()):
        results_list = all_results[mode_key]
        if not results_list:
            continue

        agg = {}
        for mk, ml in key_metrics:
            vals = [r.get(mk, 0) for r in results_list if isinstance(r.get(mk, 0), (int, float))]
            agg[mk] = np.mean(vals) if vals else 0.0

        mode_label = mode_key
        if mode_key == "legacy_baseline":
            mode_label = "LEGACY (no overrides)"
        elif mode_key == "full_override":
            mode_label = "FULL OVERRIDE (all 26 points)"

        print(
            f"{mode_label:<30} {agg.get('sharpe', 0):>8.3f} {agg.get('sortino', 0):>8.3f} "
            f"{agg.get('max_drawdown', 0):>8.4f} {agg.get('calmar', 0):>8.3f} "
            f"{agg.get('profit_factor', 0):>7.3f} {agg.get('win_rate', 0):>8.3f} "
            f"{agg.get('tail_ratio', 0):>7.3f} {agg.get('expected_shortfall', 0):>8.4f}"
        )

    return aggregated


def main():
    parser = argparse.ArgumentParser(description="KRONOS V5.1 Override Points Ablation Study")
    parser.add_argument("--real", action="store_true", help="Use real on-disk shards")
    parser.add_argument("--symbols", type=int, default=10, help="Number of symbols")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--bars", type=int, default=2000, help="Synthetic bars per symbol")
    parser.add_argument("--output", type=str, default="docs/KRONOS_V5_1_ABLATION_STUDY.md", help="Output report path")
    args = parser.parse_args()

    # Discover symbols
    from config.utils.sovereign_entrypoint import get_sovereign_config, get_storage_path
    from config.utils.symbol_discovery_sovereign import discover_symbols_from_shards

    cfg = get_sovereign_config()
    raw_dir = get_storage_path(cfg, "raw_shards_dir")
    tf = cfg["project"]["timeframe"]

    if args.real:
        all_syms = discover_symbols_from_shards(raw_dir, tf)
        symbols = [s["symbol"] for s in all_syms[:args.symbols]]
    else:
        symbols = [f"SYN{i:03d}_USDT" for i in range(args.symbols)]

    run_full_ablation_study(symbols, n_synthetic=args.bars, seed=args.seed, use_real=args.real)


if __name__ == "__main__":
    main()