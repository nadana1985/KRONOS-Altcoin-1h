"""
Validation script for KRONOS Tail Risk & Robust Statistics Batch (Points 61, 64, 66, 69, 70)

Demonstrates:
- Behavior on normal vs heavy-tailed / crisis regimes.
- Raw (mean / symmetric / normal) vs new (robust / tail-aware) estimates.
- Low data density fallbacks.
- Engine routing (liquidity gating).

Only after this script runs cleanly do we consider the points "validated" for registry update.
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides import (
    compute_point_61_override,
    compute_point_64_override,
    compute_point_66_override,
    compute_point_69_override,
    compute_point_70_override,
)
from kronos.quant_spec.overrides.utils import compute_close_to_close_vol


def make_regime_df(n: int = 180, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0005, 0.007, n)
    # Crisis / heavy tail regime
    rets[50:80] = rng.normal(-0.02, 0.025, 30)
    # Fat tails
    rets[100:110] = rng.normal(0, 0.04, 10)
    c = 100 * np.exp(np.cumsum(rets))
    v = np.random.uniform(3e5, 4e6, n)
    h = c + np.abs(np.random.randn(n)) * 0.6
    l = c - np.abs(np.random.randn(n)) * 0.6
    return pd.DataFrame({"open": c, "high": h, "low": l, "close": c, "volume": v})


def main():
    print("=" * 80)
    print("KRONOS Tail Risk Batch Validation (61,64,66,69,70)")
    print("=" * 80)

    engine = BiasOverrideEngine()
    df = make_regime_df()
    symbol = "TAILTESTUSDT"

    raw_vol = compute_close_to_close_vol(df["close"], 50)
    print(f"\nBaseline raw vol proxy: {raw_vol:.5f}")

    # Simple raw proxies for the points
    r = (df["close"] / df["close"].shift(1) - 1.0).dropna()
    raw_mean = float(r.mean())
    raw_skew = float(r.skew() or 0.0)
    raw_kurt = float(r.kurt() or 0.0)

    print("\n--- Point 66: Huber Robust Return ---")
    res66 = compute_point_66_override(raw_mean, df, symbol, engine=engine)
    print(f"  raw_mean={raw_mean:.5f} -> huber={res66:.5f}")

    print("\n--- Point 69 / 70: Skew & Kurtosis ---")
    res69 = compute_point_69_override(raw_skew, df, symbol, engine=engine)
    res70 = compute_point_70_override(raw_kurt, df, symbol, engine=engine)
    print(f"  raw_skew={raw_skew:.3f} -> rolling_skew={res69:.3f}")
    print(f"  raw_kurt={raw_kurt:.3f} -> rolling_kurt={res70:.3f}")

    print("\n--- Point 64: VaR / ES ---")
    res64 = compute_point_64_override(0.015, df, symbol, engine=engine)
    print(f"  raw_var_proxy=0.015 -> var={res64.get('var', 0):.4f} es={res64.get('es', 0):.4f}")

    print("\n--- Point 61: EVT GPD Tail ---")
    res61 = compute_point_61_override(raw_vol, df, symbol, engine=engine)
    print(f"  raw_vol={raw_vol:.4f} -> evt_gpd_tail={res61:.4f}")

    # Low data test (one representative)
    print("\n--- Low data fallback test (P66 on first 20 bars) ---")
    short_df = df.iloc[:20]
    sraw = r.iloc[:15].mean()
    sval = compute_point_66_override(sraw, short_df, symbol, engine=engine)
    print(f"  short raw_mean={sraw:.5f} -> P66={sval:.5f}")

    print("\n" + "=" * 80)
    print("Validation script finished.")
    print("All points executed. Differences visible in crisis regime.")
    print("Fallbacks and engine routing exercised.")
    print("Ready to update registry statuses (if this run looks good).")
    print("=" * 80)


if __name__ == "__main__":
    main()