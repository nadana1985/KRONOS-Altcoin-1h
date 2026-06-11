"""
Validation script for KRONOS Volatility Batch 2 (Points 53,54,55,56,58,59,60)

Compares legacy close-to-close vs new advanced estimators across regimes:
- Normal, trending, high-vol, low-vol, jump, gappy.

Tests:
- Raw vs new differences
- Low data fallback
- Engine gating (via liquidity tiers)
- Reusable utilities

Run this before flipping registry statuses.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides import (
    compute_point_53_override,
    compute_point_54_override,
    compute_point_55_override,
    compute_point_56_override,
    compute_point_58_override,
    compute_point_59_override,
    compute_point_60_override,
)
from kronos.quant_spec.overrides.utils import compute_close_to_close_vol


def make_regime_df(n: int = 200, seed: int = 123) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0002, 0.007, n)
    # Add regimes
    rets[30:50] *= 3.0  # high vol
    rets[80] = -0.07    # jump
    rets[120:140] += 0.001  # trend
    rets[160:] *= 0.3   # low vol

    c = 100 * np.exp(np.cumsum(rets))
    o = c * (1 + rng.normal(0, 0.001, n))
    h = np.maximum(c, o) * (1 + rng.uniform(0, 0.004, n))
    l = np.minimum(c, o) * (1 - rng.uniform(0, 0.004, n))
    v = rng.uniform(2e5, 4e6, n)
    cnt = rng.integers(200, 4000, n)

    return pd.DataFrame({
        "open": o, "high": h, "low": l, "close": c,
        "volume": v, "count": cnt
    })


def main():
    print("=" * 80)
    print("KRONOS Volatility Batch 2 Validation (53,54,55,56,58,59,60)")
    print("=" * 80)

    engine = BiasOverrideEngine()
    df = make_regime_df()
    symbol = "VOLBATCH2USDT"

    raw_vol = compute_close_to_close_vol(df["close"], 20)
    print(f"\nBaseline raw C2C vol: {raw_vol:.5f}")

    points = [
        ("53", compute_point_53_override, "Amihud-Adj"),
        ("54", compute_point_54_override, "DCC-GARCH (simpl)"),
        ("55", compute_point_55_override, "High-Freq Int Var"),
        ("56", compute_point_56_override, "Beta-Neutral"),
        ("58", compute_point_58_override, "DFA Scaling"),
        ("59", compute_point_59_override, "Hurst-Adaptive"),
        ("60", compute_point_60_override, "Kernel + Jump"),
    ]

    print("\nEstimator comparison (via engine):")
    for pid, func, name in points:
        try:
            # For points needing extra (market for 54/56), pass dummy
            if pid in ["54", "56"]:
                mkt = df["close"] * 0.8 + np.random.normal(0, 0.1, len(df))
                val = func(raw_vol, df, symbol, market_close=mkt, engine=engine)
            else:
                val = func(raw_vol, df, symbol, engine=engine)
            delta = (val - raw_vol) / max(raw_vol, 1e-8) * 100
            print(f"  P{pid} ({name:18s}): {val:.5f} (raw {raw_vol:.5f}, {delta:+.1f}%)")
        except Exception as e:
            print(f"  P{pid} error: {e}")

    # Low data test
    print("\nLow-data fallback (P58 on n=15):")
    short = df.iloc[:15]
    sraw = compute_close_to_close_vol(short["close"], 10)
    sval = compute_point_58_override(sraw, short, symbol, engine=engine)
    print(f"  short raw={sraw:.5f} -> P58={sval:.5f}")

    print("\n" + "=" * 80)
    print("Validation script completed. Check diffs and fallbacks above.")
    print("Run with real shards for deeper regime analysis.")
    print("=" * 80)


if __name__ == "__main__":
    main()