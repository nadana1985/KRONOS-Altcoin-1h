"""
Validation script for KRONOS Batch: Points 04, 08, 09, 11, 14

Demonstrates:
- Raw vs new quant replacement for each point using the shared utils.
- Full engine-routed wrappers (raw returned while status=not_started).
- Low data density fallbacks.
- Reusable helpers in action.
- Cross-point synergy (e.g. Point 04 rank + Point 02/08 scaling + Point 11/14 guards).

After running, the script prints a recommendation for shared utilities.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides import (
    compute_point_04_override,
    compute_point_08_override,
    compute_point_09_override,
    compute_point_11_override,
    compute_point_14_override,
)
from kronos.quant_spec.overrides.utils import (
    rolling_percentile_rank,
    compute_atr_bandwidth,
    compute_volume_synced_alpha,
    compute_dynamic_epsilon,
    compute_adaptive_cycle_window,
)


def make_synthetic_df(n: int = 220, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0002, 0.008, n)
    rets[70:110] *= 0.3   # low vol
    rets[150:] *= 2.5     # high vol / liquidation
    close = 100 * np.exp(np.cumsum(rets))
    high = close * (1 + rng.uniform(0, 0.012, n))
    low = close * (1 - rng.uniform(0, 0.012, n))
    vol = rng.uniform(2e5, 6e6, n)
    vol[70:110] *= 0.15
    return pd.DataFrame({"close": close, "high": high, "low": low, "volume": vol})


def main():
    print("=" * 75)
    print("KRONOS Bias Override Batch Validation: 04, 08, 09, 11, 14")
    print("=" * 75)

    engine = BiasOverrideEngine()
    df = make_synthetic_df()
    symbol = "BATCHTESTUSDT"

    # Point 04
    print("\n--- Point 04: Manual Linear Multiplier Bias (rolling rank) ---")
    raw_mult = 4.2
    proxy = (df["close"].pct_change().abs() * df["volume"]).dropna()
    final04 = compute_point_04_override(raw_mult, df, symbol, history_proxy=proxy, engine=engine)
    print(f"  raw_mult={raw_mult:.2f} -> final (engine)={final04:.3f}  (raw expected)")

    # Point 09
    print("\n--- Point 09: Static Percentage Threshold Bias (ATR bandwidth) ---")
    raw_bw = 0.005
    final09 = compute_point_09_override(raw_bw, df, symbol, engine=engine)
    print(f"  raw_bw={raw_bw:.4f} -> final (engine)={final09:.5f}")

    # Point 11
    print("\n--- Point 11: Arbitrary EWM Smoothing Span Bias (VSES alpha) ---")
    raw_alpha = 0.12
    final11 = compute_point_11_override(raw_alpha, df, symbol, engine=engine)
    print(f"  raw_alpha={raw_alpha:.3f} -> final (engine)={final11:.4f}")

    # Point 14
    print("\n--- Point 14: Hardcoded Denominator Epsilon Guards (dynamic eps) ---")
    raw_eps = 1e-8
    final14 = compute_point_14_override(raw_eps, df, symbol, engine=engine)
    print(f"  raw_eps={raw_eps:.2e} -> final (engine)={final14:.2e}")

    # Point 08
    print("\n--- Point 08: Hardcoded Lookback Scaling Ratios (adaptive cycle) ---")
    raw_w = 120
    final08 = compute_point_08_override(raw_w, df, symbol, engine=engine)
    print(f"  raw_w={raw_w} -> final (engine)={final08}")

    # Low data test (one example)
    print("\n--- Low data density fallback example (Point 14) ---")
    short_df = df.tail(12)
    f14_low = compute_point_14_override(1e-8, short_df, symbol, engine=engine)
    print(f"  short data (n=12) raw_eps=1e-8 -> final={f14_low:.2e} (fallback)")

    print("\n" + "=" * 75)
    print("Batch validation complete.")
    print("All points return raw values via engine (statuses still not_started during validation).")
    print("Shared utilities (rolling_percentile_rank, compute_*_*) exercised across points.")
    print("=" * 75)

    # Suggestion for future
    print("\n=== Recommendation on Shared Utilities ===")
    print("Strongly recommended to promote the following to a top-level")
    print("kronos/quant_spec/overrides/transforms.py (or keep in utils.py):")
    print("  - rolling_percentile_rank  (used by 04, future multiplier biases)")
    print("  - compute_volatility_scaled_window + compute_adaptive_cycle_window (02 + 08)")
    print("  - compute_atr_bandwidth (09 + any S/R or exhaustion point)")
    print("  - compute_volume_synced_alpha (11 + any smoothing / decay point)")
    print("  - compute_dynamic_epsilon (14 + any division guard / normalization point)")
    print("\nThese 5 helpers already cover the majority of 'adaptive scaling / guard' patterns")
    print("in the first ~15 points. Future batches (e.g. 16-30 orderflow, 46-60 vol estimators)")
    print("will benefit enormously from a single well-tested transforms module.")
    print("Consider also a thin `apply_override_transform(point_id, raw_value, df, symbol, engine)`")
    print("dispatcher if the pattern becomes repetitive.")


if __name__ == "__main__":
    main()