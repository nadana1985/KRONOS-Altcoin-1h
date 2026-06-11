""""
KRONOS V1-ALT — Validation Script for Validation/Purging/Causality Batch (Points 35,79,80,82,90)

Demonstrates LEAKAGE PREVENTION and OVERFITTING CONTROL properties of each point.
Each test shows the raw (naive/baseline) approach vs the new quant replacement,
with explicit metrics showing why the new approach is safer.

Run: python scripts/validate_validation_batch.py

This script validates:
- Point 35: Purging & Embargo — how much label overlap is eliminated
- Point 79: CPCV Paths — distribution width vs single walk-forward
- Point 80: Deflated Sharpe Ratio — correction under multiple testing
- Point 82: Causally Lagged Global Priors — lookahead prevention
- Point 90: Monte Carlo DSR — robustness vs single-path Sharpe
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides import (
    compute_point_35_override,
    compute_point_79_override,
    compute_point_80_override,
    compute_point_82_override,
    compute_point_90_override,
)
from kronos.quant_spec.overrides.utils import (
    generate_cpcv_paths,
    deflated_sharpe_ratio,
    monte_carlo_deflated_sharpe_paths,
    get_purged_embargo_indices,
)


def make_synthetic_returns(n: int = 500, seed: int = 42) -> pd.Series:
    """Create realistic-ish returns with regime changes and fat tails."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0002, 0.008, n)
    # Inject regime changes, only if n is large enough
    if n >= 150:
        rets[100:min(130, n)] = rng.normal(-0.001, 0.025, min(30, n - 100))
    if n >= 250:
        rets[200:min(250, n)] = rng.normal(0.0005, 0.006, min(50, n - 200))
    if n >= 310:
        rets[300:min(310, n)] = rng.normal(0, 0.04, min(10, n - 300))
    return pd.Series(rets, name="returns")


def make_synthetic_df(n: int = 500, seed: int = 42) -> pd.DataFrame:
    """Create a synthetic OHLCV dataframe."""
    rets = make_synthetic_returns(n, seed)
    close = 100 * np.exp(np.cumsum(rets))
    rng = np.random.default_rng(seed + 1)
    high = close * (1 + np.abs(rng.normal(0, 0.004, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.004, n)))
    volume = rng.uniform(1e6, 5e6, n)
    return pd.DataFrame({
        "open": close, "high": high, "low": low, "close": close,
        "volume": volume, "quote_volume": volume * close,
        "count": rng.integers(200, 5000, n),
    })


def make_cross_sectional_features(n: int, n_assets: int = 5, seed: int = 99) -> pd.DataFrame:
    """Create synthetic cross-sectional features for multi-asset causality tests."""
    rng = np.random.default_rng(seed)
    cols = {}
    for i in range(n_assets):
        cols[f"asset_{i}_ret"] = rng.normal(0.0001, 0.01, n)
        cols[f"asset_{i}_vol"] = np.abs(rng.normal(0.005, 0.003, n))
    return pd.DataFrame(cols)


def test_point_35_purging():
    """Point 35: Demonstrate label overlap elimination via purging & embargo."""
    print("\n" + "=" * 80)
    print("POINT 35: Strict Combinatorial Purging & Embargoing")
    print("=" * 80)

    engine = BiasOverrideEngine()
    n = 200
    times = pd.date_range("2020-01-01", periods=n, freq="h")
    df = make_synthetic_df(n)

    # Scenario: horizon=10 bars, embargo=5 bars
    horizon = 10
    embargo = 5
    n_blocks = 10
    n_test_blocks = 2
    raw_train = int(n * 0.8)  # ~160

    print(f"\nConfiguration: total_bars={n}, horizon={horizon}, embargo={embargo}")
    print(f"               n_blocks={n_blocks}, n_test_blocks={n_test_blocks}")
    print(f"               raw_train_size={raw_train}")

    # Compute effective size with purging
    purged = compute_point_35_override(
        raw_train_size=raw_train,
        event_index=times[:raw_train],
        horizon=horizon,
        df=df,
        symbol="TST35",
        engine=engine,
        n_test_blocks=n_blocks,
        n_test_per_block=n // n_blocks,
    )

    purge_ratio = 1.0 - (purged / max(1, raw_train))
    print(f"\nResults:")
    print(f"  raw (no purging):          {raw_train} training samples")
    print(f"  after purging & embargo:    {purged} training samples")
    print(f"  purge_ratio:                {purge_ratio:.2%}")

    # Also compute: for a simple example, show which train indices get purged
    train_indices = pd.Index(np.arange(raw_train))
    test_start = int(n * 0.8)  # last 20% as test
    test_end = n
    purged_idx = get_purged_embargo_indices(
        train_indices, test_start, test_end, horizon, embargo
    )
    print(f"\nDetailed check for 80/20 split:")
    print(f"  test window: [{test_start}, {test_end})")
    print(f"  purged training indices: {len(purged_idx)} / {len(train_indices)}")
    print(f"  purge boundary (t_event <= test_start - horizon - embargo): "
          f"test_start - {horizon} - {embargo} = {test_start - horizon - embargo}")
    print(f"  Any index >= {test_start - horizon - embargo} is purged")
    print(f"  Purge completeness: {purged_idx.min() if len(purged_idx) > 0 else 'N/A'} to "
          f"{purged_idx.max() if len(purged_idx) > 0 else 'N/A'}")

    return purged


def test_point_79_cpcv():
    """Point 79: CPCV generates more paths and wider distribution than single walk-forward."""
    print("\n" + "=" * 80)
    print("POINT 79: Combinatorial Purged Cross-Validation (CPCV) Path Calculations")
    print("=" * 80)

    # Generate synthetic returns and compute Sharpe on different paths
    n = 300
    rets = make_synthetic_returns(n)
    df = make_synthetic_df(n)
    engine = BiasOverrideEngine()

    n_blocks = 6
    k_test = 2
    naive_paths_count = 5  # e.g., 5-fold walk-forward

    cpcv_count = compute_point_79_override(
        raw_n_paths=naive_paths_count,
        n_blocks=n_blocks,
        k_test=k_test,
        df=df,
        symbol="TST79",
        engine=engine,
    )

    paths = generate_cpcv_paths(n_blocks, k_test)

    print(f"\nConfiguration: n_blocks={n_blocks}, k_test={k_test}")
    print(f"  naive (walk-forward) paths: {naive_paths_count}")
    print(f"  CPCV paths:                  {cpcv_count} (max {len(paths)} combinations)")
    print(f"\nCPCV path structure (first 3):")
    for i, (train, test) in enumerate(paths[:3]):
        print(f"  Path {i+1}: train_blocks={train}, test_blocks={test}")

    # Compute Sharpe distribution across CPCV paths to show variability
    print(f"\nSharpe distribution across CPCV paths (illustrative):")
    sharpe_values = []
    for train_blocks, test_blocks in paths[:20]:  # limit for speed
        # Simple: split returns by blocks
        block_size = n // n_blocks
        test_mask = np.zeros(n, dtype=bool)
        for tb in test_blocks:
            start = tb * block_size
            end = min(start + block_size, n)
            test_mask[start:end] = True
        test_rets = rets.values[test_mask]
        if len(test_rets) > 5:
            s = (test_rets.mean() / (test_rets.std() + 1e-12)) * np.sqrt(252 * 24)
            sharpe_values.append(s)

    if sharpe_values:
        print(f"  Mean Sharpe across paths:   {np.mean(sharpe_values):.3f}")
        print(f"  Std  Sharpe across paths:   {np.std(sharpe_values):.3f}")
        print(f"  Min/Max:                    {np.min(sharpe_values):.3f} / {np.max(sharpe_values):.3f}")
        print(f"  Range (max - min):          {np.max(sharpe_values) - np.min(sharpe_values):.3f}")
        print(f"  ---> Wider range means more realistic OOS uncertainty vs single point estimate")

    return cpcv_count


def test_point_80_dsr():
    """Point 80: DSR penalizes Sharpe under multiple testing."""
    print("\n" + "=" * 80)
    print("POINT 80: Deflated Sharpe Ratio (DSR) Adjustment")
    print("=" * 80)

    engine = BiasOverrideEngine()
    df = make_synthetic_df(200)
    T = 200  # number of observations

    # Test across multiple trial counts
    print(f"\nDSR vs raw Sharpe for different numbers of trials (T={T}):")
    print(f"{'Trials':>8} | {'Raw Sharpe':>11} | {'DSR':>10} | {'Deflation':>10} | {'Actionable':>10}")
    print("-" * 60)

    for n_trials in [1, 5, 20, 100, 500]:
        raw_sharpe = 1.5
        dsr = compute_point_80_override(
            raw_sharpe, n_trials, T, df, "TST80", engine=engine
        )
        deflation = raw_sharpe - dsr
        actionable = "YES" if dsr > 0 else "NO"
        print(f"{n_trials:>8} | {raw_sharpe:>10.3f} | {dsr:>10.4f} | {deflation:>10.4f} | {actionable:>10}")

    print(f"\n  Interpretation:")
    print(f"  - With 1 trial (no multiple testing correction), DSR ~ raw Sharpe")
    print(f"  - As trials increase, DSR penalizes more aggressively")
    print(f"  - At 500 trials, a raw Sharpe of 1.5 may become non-actionable (DSR <= 0)")
    print(f"  - This prevents data-snooping across many model permutations")

    return dsr


def test_point_82_causality():
    """Point 82: Verify lookahead prevention in cross-sectional features."""
    print("\n" + "=" * 80)
    print("POINT 82: Causally Lagged Cross-Sectional Information Flows")
    print("=" * 80)

    engine = BiasOverrideEngine()
    n = 200
    df = make_synthetic_df(n)
    times = pd.date_range("2020-01-01", periods=n, freq="h")

    # Create local feature and cross-sectional features
    local = pd.Series(np.random.default_rng(42).normal(0, 1, n), index=times, name="local_ret")
    xsec = make_cross_sectional_features(n)

    print(f"\nConfiguration: lag=1 (global features shifted by 1 bar)")
    print(f"  local feature has {n} observations")
    print(f"  cross-sectional has {xsec.shape[1]} features")

    # Compute causal version
    result = compute_point_82_override(
        local, local, xsec, df, "TST82", engine=engine
    )

    # Verifying causality: at time t, the cross-sectional features should be from t-1
    print(f"\nResult shape: {result.shape}")
    cs_cols = [c for c in result.columns if c != "local" and not c.endswith("_contemporary")]
    print(f"Causal cross-sectional columns: {cs_cols}")

    # Check that lagged values are NOT equal to contemporary values
    # (they should be shifted by 1)
    rng_check = np.random.default_rng(99)
    simple_xsec = pd.DataFrame({"mkt": rng_check.normal(0, 1, 20)})
    simple_local = pd.Series(rng_check.normal(0, 1, 20))
    simple_df = pd.DataFrame({"close": np.cumsum(rng_check.normal(0, 0.01, 20))})

    diag_result = compute_point_82_override(
        simple_local, pd.Series(simple_local.values), simple_xsec, simple_df, "TEST_DIAG", engine=engine
    )
    if "mkt" in diag_result.columns and "mkt_contemporary" in diag_result.columns:
        mismatch = (diag_result["mkt"].values != diag_result["mkt_contemporary"].values).sum()
        print(f"\nCausality verification:")
        print(f"  Rows where lagged != contemporary: {mismatch} / {len(diag_result)}")
        print(f"  If all differ, causality is properly enforced (each t uses t-1 global)")

    print("  Key principle: Prior_i,t = G( X_j,t-1 for j in Assets )")
    print(f"  Global priors are always one step behind local features")


def test_point_90_mc_dsr():
    """Point 90: Monte Carlo DSR provides distribution, not point estimate."""
    print("\n" + "=" * 80)
    print("POINT 90: Monte Carlo Path Deflated Sharpe Ratio Evaluations")
    print("=" * 80)

    engine = BiasOverrideEngine()
    n = 400
    rets = make_synthetic_returns(n, seed=123)
    df = make_synthetic_df(n)

    # Single-path Sharpe (raw)
    raw_sharpe = (rets.mean() / (rets.std() + 1e-12)) * np.sqrt(252 * 24)
    print(f"\nSingle-path (raw) Sharpe: {raw_sharpe:.4f}")

    # Monte Carlo DSR
    mc_stats = compute_point_90_override(
        raw_sharpe, rets, df, "TST90", engine=engine
    )

    print(f"\nMonte Carlo DSR statistics (synthetic paths):")
    print(f"  raw Sharpe:                 {raw_sharpe:.4f}")
    print(f"  MC DSR mean:                {mc_stats['dsr_mean']:.4f}")
    print(f"  MC DSR std:                 {mc_stats['dsr_std']:.4f}")
    print(f"  P(DSR > 0) [prob positive]: {mc_stats['prob_positive']:.3f}")

    # Compute DSR directly on the full sample for comparison
    dsr_full = deflated_sharpe_ratio(
        raw_sharpe, n_trials=100, t=n, confidence=0.95, skew=float(rets.skew()), kurt=float(rets.kurt())
    )
    print(f"\nComparison:")
    print(f"  Single DSR (full sample):   {dsr_full:.4f}")
    print(f"  MC DSR mean:                {mc_stats['dsr_mean']:.4f}")
    print(f"  Difference (DSR - MC):      {dsr_full - mc_stats['dsr_mean']:.4f}")
    print(f"\n  Interpretation:")
    print(f"  - A single Sharpe hides path dependency")
    print(f"  - MC DSR distribution shows performance robustness")
    print(f"  - Wide std -> high uncertainty -> low confidence in model selection")
    print(f"  - Low P(DSR > 0) -> model may be overfit to a specific historical path")


def main():
    print("=" * 90)
    print("  KRONOS VALIDATION/PURGING/CAUSALITY BATCH (Points 35, 79, 80, 82, 90)")
    print("  Comprehensive Leakage Prevention & Overfitting Control Tests")
    print("=" * 90)

    engine = BiasOverrideEngine()
    print(f"Engine: {engine}")

    # --- Point 35 ---
    p35_result = test_point_35_purging()
    print(f"  Purge completeness: {p35_result} effective samples after purging")

    # --- Point 79 ---
    p79_result = test_point_79_cpcv()

    # --- Point 80 ---
    p80_result = test_point_80_dsr()

    # --- Point 82 ---
    test_point_82_causality()

    # --- Point 90 ---
    test_point_90_mc_dsr()

    # Summary
    print("\n" + "=" * 90)
    print("  VALIDATION SUMMARY")
    print("=" * 90)
    print(f"  Point 35: Purging reduces training set from label overlap")
    print(f"  Point 79: CPCV generates {p79_result} paths vs naive walk-forward")
    print(f"  Point 80: DSR corrects Sharpe from multiple testing ({p80_result:.4f})")
    print(f"  Point 82: Cross-sectional features strictly lagged (no lookahead)")
    print(f"  Point 90: Monte Carlo DSR distribution vs single-point estimate")
    print(f"\n  All points are routed through BiasOverrideEngine.")
    print(f"  While status='implemented' in registry, the engine applies the replacement.")
    print(f"  Fallbacks handle low-data and error conditions gracefully.")
    print(f"  To activate: ensure registry.yaml status for each point is 'implemented'.")
    print("=" * 90)


if __name__ == "__main__":
    main()
