"""
KRONOS V1-ALT -- A/B Test: Overrides ON vs OFF

Compares mining results with bias overrides enabled vs disabled
on synthetic data for controlled comparison.

Usage:
    cd F:/kronos_v1_alt
    python scripts/ab_test_overrides.py
"""
import sys
import os

# Set up project root and ensure env var is set for orchestrator_engine path setup
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)
os.environ.setdefault("KRONOS_PARAMS_PATH", os.path.join(_project_root, "params_yaml.txt"))

import numpy as np
import pandas as pd
from config.mining.reversal_signature_miner_sovereign import mine_reversal_signature
from kronos.quant_spec.bias_override_engine import set_overrides_enabled, is_overrides_enabled
from kronos_module.model.structural_engine import get_dual_mode_context


def create_synthetic_data(n=500, seed=42):
    """Create realistic synthetic OHLCV data with volatility regimes."""
    rng = np.random.default_rng(seed)
    # Three regimes: low vol, high vol, mixed
    rets = np.concatenate([
        np.random.normal(0.0001, 0.003, n // 3),   # low vol
        np.random.normal(0.0001, 0.015, n // 3),   # high vol
        np.random.normal(0.0001, 0.008, n - 2 * (n // 3)),  # mixed
    ])
    close = 100 * np.exp(np.cumsum(rets))
    high = close * (1 + np.abs(rng.normal(0, 0.002, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.002, n)))
    volume = rng.uniform(1e6, 1e8, n)
    # Add some volume spikes
    spike_idx = rng.choice(n, size=n // 10, replace=False)
    volume[spike_idx] *= rng.uniform(3, 10, len(spike_idx))

    return pd.DataFrame({
        "open": close * (1 + rng.normal(0, 0.001, n)),
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "quote_volume": volume * close,
        "count": rng.integers(100, 5000, n),
        "taker_buy_base_volume": volume * rng.uniform(0.3, 0.7, n),
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="1h"),
    })


def run_ab_test():
    """Run A/B test comparing overrides ON vs OFF."""
    ctx = get_dual_mode_context()
    neural = ctx["neural_slots"]

    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT", "ADAUSDT",
                "XRPUSDT", "AVAXUSDT", "LINKUSDT", "MATICUSDT", "ATOMUSDT"]

    results_on = []
    results_off = []

    print("=" * 70)
    print("KRONOS V1-ALT -- A/B Test: Overrides ON vs OFF")
    print("=" * 70)

    for symbol in symbols:
        df = create_synthetic_data(n=500, seed=hash(symbol) % 10000)

        # Run with overrides ON
        set_overrides_enabled(True)
        assert is_overrides_enabled() is True
        sig_on = mine_reversal_signature(df, symbol, neural, ctx=ctx)
        results_on.append(sig_on)

        # Run with overrides OFF
        set_overrides_enabled(False)
        assert is_overrides_enabled() is False
        sig_off = mine_reversal_signature(df, symbol, neural, ctx=ctx)
        results_off.append(sig_off)

        # Reset
        set_overrides_enabled(True)

    # Print comparison table
    print(f"\n{'Symbol':<14} {'Conf_ON':>8} {'Conf_OFF':>8} {'Delta':>8} {'ExecCost':>10} {'Spread':>10} {'IlliqW':>8}")
    print("-" * 72)

    for i, symbol in enumerate(symbols):
        on = results_on[i]
        off = results_off[i]
        conf_on = on.get("confidence", 0)
        conf_off = off.get("confidence", 0)
        delta = conf_on - conf_off
        exec_cost = on.get("execution_sim", {}).get("total_cost_bps", 0) if on.get("execution_sim") else 0
        spread = on.get("dna_vector", {}).get("slot_32_spread", 0)
        illiq = on.get("dna_vector", {}).get("slot_33_illiq_weight", 0)
        print(f"{symbol:<14} {conf_on:>8.3f} {conf_off:>8.3f} {delta:>+8.3f} {exec_cost:>10.1f} {spread:>10.5f} {illiq:>8.4f}")

    # Summary statistics
    confs_on = [r.get("confidence", 0) for r in results_on]
    confs_off = [r.get("confidence", 0) for r in results_off]
    exec_costs = [r.get("execution_sim", {}).get("total_cost_bps", 0)
                  for r in results_on if r.get("execution_sim")]
    spreads = [r.get("dna_vector", {}).get("slot_32_spread", 0)
               for r in results_on if r.get("dna_vector", {}).get("slot_32_spread")]

    print("\n" + "=" * 70)
    print("Summary Statistics")
    print("=" * 70)
    print(f"  Avg confidence ON:  {np.mean(confs_on):.3f}")
    print(f"  Avg confidence OFF: {np.mean(confs_off):.3f}")
    print(f"  Avg delta:          {np.mean(confs_on) - np.mean(confs_off):+.3f}")
    print(f"  Veto rate ON:       {sum(1 for c in confs_on if c < 0.01)}/{len(symbols)}")
    print(f"  Veto rate OFF:      {sum(1 for c in confs_off if c < 0.01)}/{len(symbols)}")
    if exec_costs:
        print(f"  Avg exec cost:      {np.mean(exec_costs):.1f} bps")
    if spreads:
        print(f"  Avg spread est:     {np.mean(spreads):.5f}")

    # Check overrides_active flag
    active_count = sum(1 for r in results_on if r.get("overrides_active"))
    print(f"\n  Overrides active:   {active_count}/{len(symbols)} (ON)")

    # Check execution_sim presence
    exec_count = sum(1 for r in results_on if r.get("execution_sim"))
    print(f"  Execution simulated:{exec_count}/{len(symbols)} (ON)")

    print("\n" + "=" * 70)
    print("A/B Test Complete")
    print("=" * 70)

    # Sanity checks -- vetoed symbols return early without overrides_active/exec fields
    vetoed_count = sum(1 for c in confs_on if c < 0.01)
    min_expected = len(symbols) - vetoed_count
    assert active_count >= min_expected, f"Expected at least {min_expected} overrides active, got {active_count}/{len(symbols)}"
    assert exec_count >= min_expected, f"Expected at least {min_expected} executions simulated, got {exec_count}/{len(symbols)}"
    print(f"\nAll assertions passed (vetoed={vetoed_count}, active={active_count}, exec={exec_count}).")

    return results_on, results_off


if __name__ == "__main__":
    run_ab_test()
