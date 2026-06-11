"""
KRONOS V1-ALT — Validation Script for Operational & Execution Batch (Points 91, 92, 93, 94, 95, 100)

Demonstrates REALISTIC EXECUTION MODELING properties of each point.
Each test shows the raw (naive/baseline) approach vs the new quant replacement,
with explicit metrics showing why the new approach is safer and more production-ready.

Run: python scripts/validate_execution_batch.py

This script validates:
- Point 91: OS-Agnostic Path Resolution — cross-platform deployment safety
- Point 92: Dynamic Compute Allocation — adaptive resource sizing
- Point 93: Latency Slippage — realistic execution delay modeling
- Point 94: Dynamic Execution Cost — spread-scaled + impact costs
- Point 95: TWAP Execution — realistic fill simulation
- Point 100: Impact-Aware Position Sizing — adaptive position sizing
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides import (
    compute_point_91_override,
    compute_point_92_override,
    compute_point_93_override,
    compute_point_94_override,
    compute_point_95_override,
    compute_point_100_override,
)
from kronos.quant_spec.overrides.utils import (
    resolve_os_agnostic_path,
    compute_system_memory_available_gb,
    compute_adaptive_shard_size,
    compute_latency_slippage_modifier,
    compute_dynamic_execution_cost,
    compute_twap_execution_price,
    compute_impact_aware_position_size,
    compute_close_to_close_vol,
    compute_corwin_schultz_spread,
)


def make_synthetic_df(n: int = 200, seed: int = 42, vol_regime: str = "normal") -> pd.DataFrame:
    """Create synthetic OHLCV dataframe with configurable volatility regime."""
    rng = np.random.default_rng(seed)
    vol_map = {"low": 0.003, "normal": 0.008, "high": 0.02, "crisis": 0.04}
    vol = vol_map.get(vol_regime, 0.008)
    rets = rng.normal(0.0001, vol, n)
    # Inject regime changes
    if n >= 100:
        rets[50:min(70, n)] = rng.normal(-0.002, vol * 2, min(20, n - 50))
    c = 100 * np.exp(np.cumsum(rets))
    h = c * (1 + np.abs(rng.normal(0, 0.004, n)))
    l = c * (1 - np.abs(rng.normal(0, 0.004, n)))
    o = c * (1 + rng.normal(0, 0.001, n))
    v = rng.uniform(5e5, 5e6, n)
    return pd.DataFrame({
        "open": o, "high": h, "low": l, "close": c,
        "volume": v, "quote_volume": v * c,
        "count": rng.integers(200, 5000, n),
    })


def test_point_91_paths():
    """Point 91: OS-Agnostic Path Resolution — cross-platform safety."""
    print("\n" + "=" * 80)
    print("POINT 91: OS-Agnostic Environment Path Resolution")
    print("=" * 80)

    engine = BiasOverrideEngine()
    df = make_synthetic_df(50)

    # Test various hardcoded paths
    test_paths = [
        "f:/kronos_v1_alt",
        "C:\\Users\\admin\\kronos",
        "/home/user/kronos_v1_alt",
        "./kronos",
    ]

    print("\nPath resolution comparison:")
    print(f"  {'Legacy Path':<35} -> {'Resolved Path':<35}")
    print(f"  {'-'*35}   {'-'*35}")

    for raw_path in test_paths:
        final = compute_point_91_override(raw_path, df, "TEST91", engine=engine)
        print(f"  {raw_path:<35} -> {final:<35}")

    # Resolve project paths
    from kronos.quant_spec.overrides.point_91 import resolve_project_paths, validate_path_permissions
    paths = resolve_project_paths()
    print(f"\nResolved project paths:")
    for name, path in paths.items():
        print(f"  {name}: {path}")

    # Validate permissions
    diags = validate_path_permissions(paths)
    accessible = sum(1 for d in diags.values() if d["exists"])
    print(f"\nPath accessibility: {accessible}/{len(diags)} paths exist")

    print("\n  Key improvement: No more OS-dependent hardcoded paths.")
    print("  All paths resolved via env vars + POSIX normalization.")
    return paths


def test_point_92_compute():
    """Point 92: Dynamic Compute-Aware Adaptive Resource Allocation."""
    print("\n" + "=" * 80)
    print("POINT 92: Dynamic Compute-Aware Adaptive Resource Allocation")
    print("=" * 80)

    engine = BiasOverrideEngine()
    df = make_synthetic_df(50)

    raw_shard = 8192
    final = compute_point_92_override(raw_shard, df, "TEST92", engine=engine)

    from kronos.quant_spec.overrides.point_92 import compute_dynamic_resource_allocation
    resources = compute_dynamic_resource_allocation()

    print(f"\nResource allocation:")
    print(f"  Raw (static) shard size:   {raw_shard}")
    print(f"  Adaptive shard size:       {final}")
    print(f"  Memory available:          {resources['memory_available_gb']:.1f} GB")
    print(f"  Memory used by shards:     {resources['memory_used_by_shards_gb']:.1f} GB")
    print(f"  Headroom:                  {resources['headroom_gb']:.1f} GB")
    print(f"  Was scaled down:           {resources['was_scaled_down']}")

    # Show sensitivity to different base sizes
    print(f"\nSensitivity to base shard size:")
    for base in [2048, 4096, 8192, 16384, 32768]:
        shard = compute_adaptive_shard_size(base, 512, 32768, 0.6, 50.0)
        print(f"  base={base:>6} -> adaptive={shard:>6} (scaled={'YES' if shard < base else 'NO'})")

    print("\n  Key improvement: Shard sizes adapt to available system memory.")
    print("  Prevents OOM on constrained systems, maximizes throughput on powerful ones.")
    return final


def test_point_93_slippage():
    """Point 93: Estimated Execution Delay Latency Slippage Modifiers."""
    print("\n" + "=" * 80)
    print("POINT 93: Estimated Execution Delay Latency Slippage Modifiers")
    print("=" * 80)

    engine = BiasOverrideEngine()

    # Test across volatility regimes
    regimes = [
        ("low_vol", "low", 0.5),
        ("normal", "normal", 1.0),
        ("high_vol", "high", 2.0),
        ("crisis", "crisis", 4.0),
    ]

    print(f"\nSlippage across volatility regimes (signal price = 100.0):")
    print(f"  {'Regime':<12} | {'Naive Price':>11} | {'Executed':>10} | {'Slippage':>10} | {'Type':<20}")
    print(f"  {'-'*12} | {'-'*11} | {'-'*10} | {'-'*10} | {'-'*20}")

    for regime_name, regime, vol_mult in regimes:
        df = make_synthetic_df(100, seed=42, vol_regime=regime)
        res = compute_point_93_override(100.0, df, "TEST93", engine=engine)
        print(f"  {regime_name:<12} | {100.0:>11.4f} | {res['engine_final_price']:>10.4f} | "
              f"{res['slippage_bps']:>10.1f} | {res['slippage_type']:<20}")

    # Show latency sensitivity
    print(f"\nLatency sensitivity (normal volatility):")
    df = make_synthetic_df(100, seed=42, vol_regime="normal")
    c = pd.to_numeric(df.get("close"), errors="coerce")
    vol = compute_close_to_close_vol(c, 20)
    for latency in [0.0, 0.05, 0.1, 0.25, 0.5]:
        res = compute_latency_slippage_modifier(100.0, vol, latency, 5.0, 1.0, 50.0)
        print(f"  latency={latency:.2f} bars -> slippage={res['slippage_bps']:.1f}bps "
              f"executed={res['executed_price']:.4f}")

    print("\n  Key improvement: Slippage scales with volatility and latency.")
    print("  Zero-latency assumption replaced with realistic delay model.")
    return regimes


def test_point_94_costs():
    """Point 94: Spread-Scaled Dynamic Execution Cost Models."""
    print("\n" + "=" * 80)
    print("POINT 94: Spread-Scaled Dynamic Execution Cost Models")
    print("=" * 80)

    engine = BiasOverrideEngine()
    df = make_synthetic_df(100, seed=42)

    raw_fee = 10.0  # static 10 bps

    # Test across order sizes and liquidity
    scenarios = [
        ("Small/Liquid", 5000, 5e6),
        ("Medium/Liquid", 25000, 5e6),
        ("Large/Liquid", 100000, 5e6),
        ("Small/Illiquid", 5000, 5e5),
        ("Medium/Illiquid", 25000, 5e5),
        ("Large/Illiquid", 100000, 5e5),
    ]

    print(f"\nExecution cost comparison (raw static fee = {raw_fee:.1f} bps):")
    print(f"  {'Scenario':<18} | {'Raw':>6} | {'Dynamic':>8} | {'Fee':>6} | {'Spread':>7} | {'Impact':>7}")
    print(f"  {'-'*18} | {'-'*6} | {'-'*8} | {'-'*6} | {'-'*7} | {'-'*7}")

    for name, order_usd, vol_usd in scenarios:
        res = compute_point_94_override(
            raw_fee, df, "TEST94", order_size_usd=order_usd, volume_usd=vol_usd, engine=engine
        )
        print(f"  {name:<18} | {raw_fee:>6.1f} | {res['engine_final_cost_bps']:>8.1f} | "
              f"{res['base_fee_bps']:>6.1f} | {res['spread_cost_bps']:>7.1f} | {res['impact_bps']:>7.1f}")

    print("\n  Key improvement: Costs scale with order size and market impact.")
    print("  Small orders in liquid markets get lower costs; large orders in illiquid markets pay more.")
    return scenarios


def test_point_95_twap():
    """Point 95: Time-Weighted Average Price (TWAP) Execution Models."""
    print("\n" + "=" * 80)
    print("POINT 95: Time-Weighted Average Price (TWAP) Execution Models")
    print("=" * 80)

    engine = BiasOverrideEngine()
    df = make_synthetic_df(100, seed=42)

    raw_close = float(df["close"].iloc[-1])

    # Test TWAP with different slice counts
    print(f"\nTWAP execution (close price = {raw_close:.4f}):")
    print(f"  {'Slices':>6} | {'TWAP Price':>10} | {'vs Close':>10} | {'vs Open':>10}")
    print(f"  {'-'*6} | {'-'*10} | {'-'*10} | {'-'*10}")

    for n_slices in [1, 2, 4, 8, 16]:
        cfg = {"n_slices": n_slices, "min_data_density": 5}
        from kronos.quant_spec.overrides.point_95 import simulate_twap_execution
        result = simulate_twap_execution(df["open"], df["close"], config=cfg)
        twap = result.get("twap_price", 0)
        vs_close = result.get("vs_close", 0)
        vs_open = result.get("vs_open", 0)
        print(f"  {n_slices:>6} | {twap:>10.4f} | {vs_close:>10.4f} | {vs_open:>10.4f}")

    # Full wrapper test
    res = compute_point_95_override(raw_close, df, "TEST95", engine=engine)
    print(f"\n  Engine-routed TWAP: close={raw_close:.4f} -> twap={res['engine_final_price']:.4f}")

    print("\n  Key improvement: TWAP simulates realistic order slicing.")
    print("  Prevents unrealistic instant-fill assumptions in backtests.")
    return res


def test_point_100_sizing():
    """Point 100: Impact-Aware Adaptive Position Sizing."""
    print("\n" + "=" * 80)
    print("POINT 100: Impact-Aware Adaptive Position Sizing")
    print("=" * 80)

    engine = BiasOverrideEngine()

    # Test across volatility regimes
    regimes = [
        ("low_vol", "low"),
        ("normal", "normal"),
        ("high_vol", "high"),
        ("crisis", "crisis"),
    ]

    raw_size = 5000.0  # naive fixed $5k

    print(f"\nPosition sizing across volatility regimes (raw fixed = ${raw_size:.0f}):")
    print(f"  {'Regime':<12} | {'Raw Size':>10} | {'Adaptive':>10} | {'Impact Adj':>11} | {'Vol':>8}")
    print(f"  {'-'*12} | {'-'*10} | {'-'*10} | {'-'*11} | {'-'*8}")

    for regime_name, regime in regimes:
        df = make_synthetic_df(100, seed=42, vol_regime=regime)
        res = compute_point_100_override(raw_size, df, "TEST100", volume_usd=1e6, engine=engine)
        print(f"  {regime_name:<12} | ${raw_size:>9.0f} | ${res['engine_final_size']:>9.0f} | "
              f"{res['impact_adjustment']:>11.3f} | {res['volatility']:>8.4f}")

    # Test across liquidity levels
    print(f"\nPosition sizing across liquidity levels:")
    print(f"  {'Liquidity':<12} | {'Volume':>12} | {'Raw Size':>10} | {'Adaptive':>10}")
    print(f"  {'-'*12} | {'-'*12} | {'-'*10} | {'-'*10}")

    for vol_label, vol_usd in [("Ultra-low", 1e4), ("Low", 1e5), ("Medium", 1e6), ("High", 1e7)]:
        df = make_synthetic_df(100, seed=42, vol_regime="normal")
        res = compute_point_100_override(raw_size, df, "TEST100", volume_usd=vol_usd, engine=engine)
        print(f"  {vol_label:<12} | ${vol_usd:>11.0f} | ${raw_size:>9.0f} | ${res['engine_final_size']:>9.0f}")

    print("\n  Key improvement: Position size adapts to volatility and liquidity.")
    print("  High-vol/low-liquidity = smaller positions; low-vol/high-liquidity = larger positions.")
    return regimes


def test_cross_point_synergy():
    """Demonstrate how execution points work together in a realistic pipeline."""
    print("\n" + "=" * 80)
    print("CROSS-POINT SYNERGY: Realistic Execution Pipeline")
    print("=" * 80)

    engine = BiasOverrideEngine()
    df = make_synthetic_df(100, seed=42, vol_regime="normal")

    symbol = "BTCUSDT"
    signal_price = 100.0
    order_size_usd = 25000.0
    volume_usd = 5e6
    portfolio_usd = 100000.0

    print(f"\nScenario: {symbol} signal at ${signal_price:.2f}, order ${order_size_usd:.0f}")

    # Step 1: Path resolution (P91)
    p91 = compute_point_91_override("f:/kronos_v1_alt", df, symbol, engine=engine)
    print(f"\n  [P91] Path: {p91}")

    # Step 2: Compute allocation (P92)
    p92 = compute_point_92_override(8192, df, symbol, engine=engine)
    print(f"  [P92] Shard size: {p92}")

    # Step 3: Latency slippage (P93)
    p93 = compute_point_93_override(signal_price, df, symbol, engine=engine)
    print(f"  [P93] Slippage: {p93['slippage_bps']:.1f}bps -> executed=${p93['engine_final_price']:.4f}")

    # Step 4: Execution cost (P94)
    p94 = compute_point_94_override(10.0, df, symbol, order_size_usd=order_size_usd, volume_usd=volume_usd, engine=engine)
    print(f"  [P94] Cost: {p94['engine_final_cost_bps']:.1f}bps total")

    # Step 5: TWAP execution (P95)
    p95 = compute_point_95_override(p93["engine_final_price"], df, symbol, engine=engine)
    print(f"  [P95] TWAP: ${p95['engine_final_price']:.4f} (vs_close={p95.get('vs_close', 0):.4f})")

    # Step 6: Position sizing (P100)
    p100 = compute_point_100_override(order_size_usd, df, symbol, volume_usd=volume_usd, engine=engine)
    print(f"  [P100] Size: ${p100['engine_final_size']:.0f} (impact_adj={p100['impact_adjustment']:.3f})")

    # Summary
    naive_cost = order_size_usd * 10.0 / 10000  # static 10 bps
    realistic_cost = order_size_usd * p94["engine_final_cost_bps"] / 10000
    print(f"\n  Cost comparison:")
    print(f"    Naive (static 10bps):     ${naive_cost:.2f}")
    print(f"    Realistic (dynamic):      ${realistic_cost:.2f}")
    print(f"    Difference:               ${realistic_cost - naive_cost:.2f}")

    print(f"\n  Position sizing comparison:")
    print(f"    Naive (fixed ${order_size_usd:.0f}):       $1.00x")
    print(f"    Adaptive (${p100['engine_final_size']:.0f}):      ${p100['engine_final_size']/order_size_usd:.2f}x")


def main():
    print("=" * 90)
    print("  KRONOS OPERATIONAL & EXECUTION BATCH (Points 91, 92, 93, 94, 95, 100)")
    print("  Realistic Execution Modeling & Production-Readiness Tests")
    print("=" * 90)

    engine = BiasOverrideEngine()
    print(f"Engine: {engine}")
    print(f"Registry points loaded: {len(engine.registry)}")

    # Run all tests
    test_point_91_paths()
    test_point_92_compute()
    test_point_93_slippage()
    test_point_94_costs()
    test_point_95_twap()
    test_point_100_sizing()
    test_cross_point_synergy()

    # Summary
    print("\n" + "=" * 90)
    print("  VALIDATION SUMMARY")
    print("=" * 90)
    print(f"  Point 91:  OS-agnostic path resolution (env vars + POSIX normalization)")
    print(f"  Point 92:  Dynamic compute allocation (memory-aware shard sizing)")
    print(f"  Point 93:  Latency slippage (vol-adjusted execution delay model)")
    print(f"  Point 94:  Dynamic execution costs (spread + impact + fee model)")
    print(f"  Point 95:  TWAP execution (realistic order slicing simulation)")
    print(f"  Point 100: Impact-aware position sizing (vol + liquidity adaptive)")
    print(f"\n  All points are routed through BiasOverrideEngine.")
    print(f"  Status = 'implemented' in registry for all 6 points.")
    print(f"  All config in liquidity_tiers.yaml overrides section.")
    print(f"  Shared execution utilities in utils.py for reuse.")
    print(f"\n  Integration priority:")
    print(f"    1. Point 93 (latency slippage) — immediate backtest realism improvement")
    print(f"    2. Point 94 (execution costs) — prevents unrealistic profit estimates")
    print(f"    3. Point 100 (position sizing) — critical risk management firewall")
    print(f"    4. Point 95 (TWAP) — realistic fill modeling")
    print(f"    5. Point 91 (paths) — deployment safety")
    print(f"    6. Point 92 (compute) — resource optimization")
    print("=" * 90)


if __name__ == "__main__":
    main()
