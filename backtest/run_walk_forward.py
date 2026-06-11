"""
KRONOS V1-ALT — Walk-Forward Execution Script

Runs walk-forward optimization on real on-disk shards or synthetic data.
Usage:
    python backtest/run_walk_forward.py [--real] [--symbols 10] [--seed 42]
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
logger = logging.getLogger("kronos.backtest.walk_forward")


def main():
    parser = argparse.ArgumentParser(description="KRONOS V1-ALT Walk-Forward Optimization")
    parser.add_argument("--real", action="store_true", help="Use real on-disk shards")
    parser.add_argument("--symbols", type=int, default=10, help="Number of symbols to test")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--bars", type=int, default=2000, help="Bars for synthetic fallback")
    parser.add_argument("--output", type=str, default="docs/WALK_FORWARD_REPORT.md", help="Output path")
    parser.add_argument("--train-bars", type=int, default=500, help="Training window size")
    parser.add_argument("--test-bars", type=int, default=200, help="Test window size")
    parser.add_argument("--step-bars", type=int, default=200, help="Step size between folds")
    args = parser.parse_args()

    print("=" * 70)
    print("KRONOS V1-ALT — Walk-Forward Optimization")
    print("=" * 70)
    print(f"Mode: {'Real Shards' if args.real else 'Synthetic Data'}")
    print(f"Symbols: {args.symbols} | Train: {args.train_bars} | Test: {args.test_bars} | Step: {args.step_bars}")
    print(f"Seed: {args.seed}")
    print("=" * 70)

    from backtest.walk_forward import run_walk_forward, generate_wf_report
    from backtest.backtest_runner import load_real_shard, create_synthetic_ohlcv

    # Discover symbols
    symbols = []
    if args.real:
        try:
            from config.utils.sovereign_entrypoint import get_sovereign_config, get_storage_path
            from config.utils.symbol_discovery_sovereign import discover_symbols_from_shards
            cfg = get_sovereign_config()
            raw_dir = get_storage_path(cfg, "raw_shards_dir")
            tf = cfg["project"]["timeframe"]
            all_syms = discover_symbols_from_shards(raw_dir, tf)
            symbols = [s["symbol"] for s in all_syms[:args.symbols]]
        except Exception as e:
            print(f"Symbol discovery failed: {e}, using fallback")
            symbols = [f"SYN{i:03d}_USDT" for i in range(args.symbols)]
    else:
        symbols = [f"SYN{i:03d}_USDT" for i in range(args.symbols)]

    wf_config = {
        "walk_forward": {
            "train_bars": args.train_bars,
            "test_bars": args.test_bars,
            "step_bars": args.step_bars,
            "expanding": True,
        }
    }

    wf_results = []
    for i, sym in enumerate(symbols):
        df = None
        if args.real:
            try:
                from config.utils.sovereign_entrypoint import get_sovereign_config, get_storage_path
                cfg = get_sovereign_config()
                raw_dir = get_storage_path(cfg, "raw_shards_dir")
                tf = cfg["project"]["timeframe"]
                df = load_real_shard(sym, raw_dir, tf)
            except Exception:
                pass
        if df is None:
            df = create_synthetic_ohlcv(n=args.bars, seed=args.seed + i)

        print(f"\n[{i+1}/{len(symbols)}] Running walk-forward for {sym} ({len(df)} bars)...")
        result = run_walk_forward(df, sym, overrides_enabled=True, seed=args.seed, config=wf_config)
        wf_results.append(result)

        agg = result.get("aggregate_oos", {})
        print(f"  Folds: {result.get('n_folds', 0)} | OOS Sharpe: {agg.get('sharpe', 0):.4f} | OOS Ret: {agg.get('total_return', 0):.4f}")

    # Generate report
    report = generate_wf_report(wf_results, output_path=args.output)

    # Print summary
    print("\n" + "=" * 70)
    print("WALK-FORWARD SUMMARY")
    print("=" * 70)
    for res in wf_results:
        agg = res.get("aggregate_oos", {})
        print(f"  {res['symbol']:<25} Folds={res.get('n_folds',0):>2}  Sharpe={agg.get('sharpe',0):>8.4f}  Ret={agg.get('total_return',0):>8.4f}  MDD={agg.get('max_drawdown',0):>8.4f}")
    print("=" * 70)
    print(f"Report saved to: {args.output}")
    print("=" * 70)


if __name__ == "__main__":
    main()
