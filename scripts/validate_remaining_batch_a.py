"""
KRONOS V1-ALT — Validation Script: Remaining Batch A
Points 03, 05, 06, 07, 10, 12, 13, 15, 16, 18, 20, 23, 24

Tests all 13 bias override points with synthetic data across different
liquidity regimes. Demonstrates realistic behavior vs. naive assumptions.
"""

import sys
import os
import numpy as np
import pandas as pd

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine


def make_synthetic_data(n=300, seed=42, regime="normal"):
    """Create synthetic OHLCV data with configurable regime."""
    rng = np.random.default_rng(seed)
    if regime == "low_liquidity":
        vol = rng.uniform(10_000, 100_000, n)
        count = rng.integers(50, 500, n)
    elif regime == "high_liquidity":
        vol = rng.uniform(5_000_000, 50_000_000, n)
        count = rng.integers(2000, 20000, n)
    else:  # normal
        vol = rng.uniform(500_000, 5_000_000, n)
        count = rng.integers(500, 5000, n)

    c = 100 + np.cumsum(rng.normal(0, 0.5, n))
    o = c + rng.normal(0, 0.1, n)
    h = np.maximum(c, o) + rng.uniform(0.05, 0.5, n)
    l = np.minimum(c, o) - rng.uniform(0.05, 0.5, n)
    tbv = vol * (0.5 + rng.normal(0, 0.1, n))
    tbv = np.clip(tbv, 0, vol)

    ts = np.arange(n) * 3_600_000.0  # hourly timestamps in ms
    ts[50] += 500_000  # inject a latency spike

    df = pd.DataFrame({
        "open": o, "high": h, "low": l, "close": c,
        "volume": vol, "count": count,
        "taker_buy_volume": tbv,
        "timestamp": ts,
    })
    return df


def test_all_points():
    """Run all 13 points across 3 liquidity regimes."""
    engine = BiasOverrideEngine()
    results = {}
    errors = []

    regimes = {
        "normal": make_synthetic_data(300, seed=42, regime="normal"),
        "low_liquidity": make_synthetic_data(300, seed=43, regime="low_liquidity"),
        "high_liquidity": make_synthetic_data(300, seed=44, regime="high_liquidity"),
    }

    print("=" * 70)
    print("KRONOS V1-ALT — Remaining Batch A Validation")
    print("Points 03, 05, 06, 07, 10, 12, 13, 15, 16, 18, 20, 23, 24")
    print("=" * 70)

    for regime_name, df in regimes.items():
        print(f"\n--- Regime: {regime_name} ({len(df)} bars) ---")
        symbol = f"TEST_{regime_name.upper()}"

        # Point 03: SVD Bottleneck Compression
        try:
            from kronos.quant_spec.overrides import compute_point_03_override
            raw_vec = np.full(8, 0.72)  # replicated scalar
            result = compute_point_03_override(raw_vec, df, symbol, engine=engine)
            print(f"  P03 SVD: n_comp={result['n_components']} var_explained={result['variance_explained']:.3f}")
            results[f"03_{regime_name}"] = result
        except Exception as e:
            errors.append(f"P03_{regime_name}: {e}")
            print(f"  P03 SVD: ERROR — {e}")

        # Point 05: Volume-Density Window
        try:
            from kronos.quant_spec.overrides import compute_point_05_override
            window = compute_point_05_override(24, df, symbol, engine=engine)
            print(f"  P05 VolumeWindow: 24 -> {window}")
            results[f"05_{regime_name}"] = window
        except Exception as e:
            errors.append(f"P05_{regime_name}: {e}")
            print(f"  P05 VolumeWindow: ERROR — {e}")

        # Point 06: Continuous Amihud Decay
        try:
            from kronos.quant_spec.overrides import compute_point_06_override
            weight = compute_point_06_override(0.5, df, symbol, engine=engine)
            print(f"  P06 AmihudDecay: weight={weight:.4f}")
            results[f"06_{regime_name}"] = weight
        except Exception as e:
            errors.append(f"P06_{regime_name}: {e}")
            print(f"  P06 AmihudDecay: ERROR — {e}")

        # Point 07: Parsimonious Polynomial
        try:
            from kronos.quant_spec.overrides import compute_point_07_override
            X = df["close"].values.reshape(-1, 1)
            y = df["volume"].values
            result = compute_point_07_override(0.0, df, symbol, engine=engine, X=X, y=y)
            print(f"  P07 Polynomial: degree={result['degree']} BIC={result['bic']:.1f}")
            results[f"07_{regime_name}"] = result
        except Exception as e:
            errors.append(f"P07_{regime_name}: {e}")
            print(f"  P07 Polynomial: ERROR — {e}")

        # Point 10: Timestamp Latency Truncation
        try:
            from kronos.quant_spec.overrides import compute_point_10_override
            result = compute_point_10_override(1, df, symbol, engine=engine, timestamp_col="timestamp")
            print(f"  P10 Latency: truncated={result['truncated_count']} measured={result['measured_latency_ms']:.0f}ms")
            results[f"10_{regime_name}"] = result
        except Exception as e:
            errors.append(f"P10_{regime_name}: {e}")
            print(f"  P10 Latency: ERROR — {e}")

        # Point 12: Variance Mixture Z-Score
        try:
            from kronos.quant_spec.overrides import compute_point_12_override
            zscore = compute_point_12_override(0.0, df, symbol, engine=engine)
            print(f"  P12 VarZScore: z={zscore:.3f}")
            results[f"12_{regime_name}"] = zscore
        except Exception as e:
            errors.append(f"P12_{regime_name}: {e}")
            print(f"  P12 VarZScore: ERROR — {e}")

        # Point 13: Trade-Intensity Imbalance
        try:
            from kronos.quant_spec.overrides import compute_point_13_override
            imb = compute_point_13_override(0.0, df, symbol, engine=engine)
            print(f"  P13 TradeImbalance: imb={imb:.4f}")
            results[f"13_{regime_name}"] = imb
        except Exception as e:
            errors.append(f"P13_{regime_name}: {e}")
            print(f"  P13 TradeImbalance: ERROR — {e}")

        # Point 15: Asymmetric Barriers
        try:
            from kronos.quant_spec.overrides import compute_point_15_override
            result = compute_point_15_override(0.02, df, symbol, engine=engine)
            print(f"  P15 AsymBarriers: upper={result['barrier_upper']:.4f} lower={result['barrier_lower']:.4f} skew={result['skew']:.3f}")
            results[f"15_{regime_name}"] = result
        except Exception as e:
            errors.append(f"P15_{regime_name}: {e}")
            print(f"  P15 AsymBarriers: ERROR — {e}")

        # Point 16: KDE Volume Profile
        try:
            from kronos.quant_spec.overrides import compute_point_16_override
            result = compute_point_16_override(100.0, df, symbol, engine=engine)
            print(f"  P16 KDEProfile: poc={result['engine_final_poc']:.4f} levels={len(result['price_levels'])}")
            results[f"16_{regime_name}"] = result
        except Exception as e:
            errors.append(f"P16_{regime_name}: {e}")
            print(f"  P16 KDEProfile: ERROR — {e}")

        # Point 18: Log Volume Z-Score
        try:
            from kronos.quant_spec.overrides import compute_point_18_override
            zscore = compute_point_18_override(0.0, df, symbol, engine=engine)
            print(f"  P18 LogVolZ: z={zscore:.3f}")
            results[f"18_{regime_name}"] = zscore
        except Exception as e:
            errors.append(f"P18_{regime_name}: {e}")
            print(f"  P18 LogVolZ: ERROR — {e}")

        # Point 20: Shannon Count Entropy
        try:
            from kronos.quant_spec.overrides import compute_point_20_override
            entropy = compute_point_20_override(0.5, df, symbol, engine=engine)
            print(f"  P20 ShannonEntropy: e={entropy:.4f}")
            results[f"20_{regime_name}"] = entropy
        except Exception as e:
            errors.append(f"P20_{regime_name}: {e}")
            print(f"  P20 ShannonEntropy: ERROR — {e}")

        # Point 23: Eigenvalue Covariance Weight
        try:
            from kronos.quant_spec.overrides import compute_point_23_override
            weight = compute_point_23_override(0.5, df, symbol, engine=engine)
            print(f"  P23 EigenWeight: w={weight:.4f}")
            results[f"23_{regime_name}"] = weight
        except Exception as e:
            errors.append(f"P23_{regime_name}: {e}")
            print(f"  P23 EigenWeight: ERROR — {e}")

        # Point 24: Fractional Differencing OFI
        try:
            from kronos.quant_spec.overrides import compute_point_24_override
            rng = np.random.default_rng(99)
            ofi = pd.Series(np.cumsum(rng.normal(0, 0.5, 300)) + 2.0)  # persistent OFI
            df_ofi = df.copy()
            df_ofi["ofi"] = ofi.values
            result = compute_point_24_override(0.0, df_ofi, symbol, engine=engine)
            print(f"  P24 FDOI: d={result['d']} fdoi={result['fdoi_latest']:.4f}")
            results[f"24_{regime_name}"] = result
        except Exception as e:
            errors.append(f"P24_{regime_name}: {e}")
            print(f"  P24 FDOI: ERROR — {e}")

    # Cross-regime comparison
    print("\n" + "=" * 70)
    print("Cross-Regime Comparison (key diagnostics)")
    print("=" * 70)

    # Point 06: Amihud weight should be lower for low-liquidity
    try:
        w_normal = results.get("06_normal", 0.5)
        w_low = results.get("06_low_liquidity", 0.5)
        w_high = results.get("06_high_liquidity", 0.5)
        print(f"  P06 Decay Weights: high_liq={w_high:.4f} normal={w_normal:.4f} low_liq={w_low:.4f}")
        if w_high >= w_low:
            print("    ✓ High-liquidity weight >= low-liquidity (expected)")
        else:
            print("    ⚠ Weight ordering unexpected")
    except Exception:
        pass

    # Point 18: Log vol z-score should reflect volume scale differences
    try:
        z_normal = results.get("18_normal", 0.0)
        z_low = results.get("18_low_liquidity", 0.0)
        z_high = results.get("18_high_liquidity", 0.0)
        print(f"  P18 LogVol Z-Scores: high_liq={z_high:.3f} normal={z_normal:.3f} low_liq={z_low:.3f}")
    except Exception:
        pass

    # Summary
    print("\n" + "=" * 70)
    n_total = 13 * 3  # 13 points * 3 regimes
    n_passed = n_total - len(errors)
    print(f"Results: {n_passed}/{n_total} passed")
    if errors:
        print(f"Errors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
    else:
        print("All tests passed!")
    print("=" * 70)
    return len(errors) == 0


if __name__ == "__main__":
    success = test_all_points()
    sys.exit(0 if success else 1)
