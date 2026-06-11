"""
KRONOS V1-ALT -- Backtest Execution Script

Main entry point for running the full A/B comparison.
Usage:
    cd F:/kronos_v1_alt
    python backtest/run_backtest.py [--real] [--symbols 10] [--seed 42]
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Bootstrap project paths
_project_root = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, _project_root)
os.environ.setdefault("KRONOS_PARAMS_PATH", os.path.join(_project_root, "params_yaml.txt"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("kronos.backtest")


def main():
    parser = argparse.ArgumentParser(description="KRONOS V1-ALT Bias Override Impact Analysis")
    parser.add_argument("--real", action="store_true", help="Use real on-disk shards instead of synthetic data")
    parser.add_argument("--symbols", type=int, default=10, help="Number of symbols to test")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--bars", type=int, default=2000, help="Number of bars for synthetic data")
    parser.add_argument("--output", type=str, default="docs/BACKTEST_IMPACT_ANALYSIS.md", help="Output report path")
    args = parser.parse_args()

    print("=" * 70)
    print("KRONOS V1-ALT -- Bias Override Impact Analysis")
    print("=" * 70)
    print(f"Mode: {'Real Shards' if args.real else 'Synthetic Data'}")
    print(f"Symbols: {args.symbols} | Bars: {args.bars} | Seed: {args.seed}")
    print(f"Output: {args.output}")
    print("=" * 70)

    # Run the A/B comparison
    from backtest.backtest_runner import run_ab_comparison

    results = run_ab_comparison(
        n_synthetic=args.bars,
        seed=args.seed,
        use_real=args.real,
        config={
            "metrics": {
                "risk_free_rate": 0.0,
                "annualization_factor": 8760,
                "var_confidence": 0.95,
            }
        },
    )

    # Generate and save report
    from backtest.report_generator import generate_comparison_report

    report = generate_comparison_report(results, output_path=args.output)

    # Print summary to console
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    agg_leg = results["aggregate_legacy"]
    agg_ovr = results["aggregate_override"]

    key_metrics = [
        ("total_return_mean", "Total Return"),
        ("sharpe_mean", "Sharpe Ratio"),
        ("sortino_mean", "Sortino Ratio"),
        ("max_drawdown_mean", "Max Drawdown"),
        ("calmar_mean", "Calmar Ratio"),
        ("var_mean", "VaR (95%)"),
        ("expected_shortfall_mean", "Expected Shortfall"),
        ("profit_factor_mean", "Profit Factor"),
        ("win_rate_mean", "Win Rate"),
    ]

    print(f"\n{'Metric':<25} {'Legacy':>12} {'Override':>12} {'Delta':>12}")
    print("-" * 61)
    for key, label in key_metrics:
        v_l = agg_leg.get(key, 0.0)
        v_o = agg_ovr.get(key, 0.0)
        d = v_o - v_l
        print(f"  {label:<23} {v_l:>12.4f} {v_o:>12.4f} {d:>+12.4f}")

    print("\n" + "=" * 70)
    print(f"Full report saved to: {args.output}")
    print("=" * 70)


if __name__ == "__main__":
    main()
