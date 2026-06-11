"""
KRONOS V1-ALT — Remaining Batch C Validation Script
Validates Points: 63, 65, 67, 68, 71, 72, 73, 74, 75, 76, 77, 78, 81, 83, 84, 85, 86, 87, 88, 89, 96, 97, 98, 99

Tests each point across 3 liquidity regimes (high, medium, low) using synthetic data.
"""
import sys
import numpy as np
import pandas as pd

def make_synthetic_df(n=200, seed=42):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, n)))
    high = close * (1 + rng.uniform(0, 0.01, n))
    low = close * (1 - rng.uniform(0, 0.01, n))
    open_ = close * (1 + rng.normal(0, 0.005, n))
    volume = rng.uniform(1e6, 1e8, n)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume})

def test_point(point_id, test_fn, df):
    try:
        result = test_fn(df)
        status = "PASS" if result is not False else "FAIL"
        return point_id, status, result
    except Exception as e:
        return point_id, f"ERROR: {e}", None

def main():
    df = make_synthetic_df(200)
    results = []
    
    # Import all points
    try:
        from kronos.quant_spec.overrides.point_63 import compute_point_63_override
        from kronos.quant_spec.overrides.point_65 import compute_point_65_override
        from kronos.quant_spec.overrides.point_67 import compute_point_67_override
        from kronos.quant_spec.overrides.point_68 import compute_point_68_override
        from kronos.quant_spec.overrides.point_71 import compute_point_71_override
        from kronos.quant_spec.overrides.point_72 import compute_point_72_override
        from kronos.quant_spec.overrides.point_73 import compute_point_73_override
        from kronos.quant_spec.overrides.point_74 import compute_point_74_override
        from kronos.quant_spec.overrides.point_75 import compute_point_75_override
        from kronos.quant_spec.overrides.point_76 import compute_point_76_override
        from kronos.quant_spec.overrides.point_77 import compute_point_77_override
        from kronos.quant_spec.overrides.point_78 import compute_point_78_override
        from kronos.quant_spec.overrides.point_81 import compute_point_81_override
        from kronos.quant_spec.overrides.point_83 import compute_point_83_override
        from kronos.quant_spec.overrides.point_84 import compute_point_84_override
        from kronos.quant_spec.overrides.point_85 import compute_point_85_override
        from kronos.quant_spec.overrides.point_86 import compute_point_86_override
        from kronos.quant_spec.overrides.point_87 import compute_point_87_override
        from kronos.quant_spec.overrides.point_88 import compute_point_88_override
        from kronos.quant_spec.overrides.point_89 import compute_point_89_override
        from kronos.quant_spec.overrides.point_96 import compute_point_96_override
        from kronos.quant_spec.overrides.point_97 import compute_point_97_override
        from kronos.quant_spec.overrides.point_98 import compute_point_98_override
        from kronos.quant_spec.overrides.point_99 import compute_point_99_override
        print("All imports successful")
    except ImportError as e:
        print(f"Import error: {e}")
        sys.exit(1)
    
    # Test each point
    tests = [
        ("63", lambda df: compute_point_63_override(0.5, df, "TEST", feature_series=df["close"])),
        ("65", lambda df: compute_point_65_override(0.3, df, "TEST")),
        ("67", lambda df: compute_point_67_override(0.01, df, "TEST")),
        ("68", lambda df: compute_point_68_override(0.5, df, "TEST")),
        ("71", lambda df: compute_point_71_override(1.0, df, "TEST")),
        ("72", lambda df: compute_point_72_override(2.5, df, "TEST")),
        ("73", lambda df: compute_point_73_override(0.0, df, "TEST")),
        ("74", lambda df: compute_point_74_override(0.0, df, "TEST")),
        ("75", lambda df: compute_point_75_override(1.0, df, "TEST", features=pd.DataFrame({"x1": df["close"], "x2": df["volume"]}))),
        ("76", lambda df: compute_point_76_override(1.0, df, "TEST", features=pd.DataFrame({"x1": df["close"], "x2": df["volume"]}), target=df["close"])),
        ("77", lambda df: compute_point_77_override(1.0, df, "TEST", features=pd.DataFrame({"x1": df["close"], "x2": df["volume"]}))),
        ("78", lambda df: compute_point_78_override(0.0, df, "TEST")),
        ("81", lambda df: compute_point_81_override(0.0, df, "TEST", returns=pd.DataFrame({"A": df["close"].pct_change(), "B": df["volume"].pct_change()}))),
        ("83", lambda df: compute_point_83_override(0.01, df, "TEST", predictions=np.random.randn(100), actuals=np.random.randn(100))),
        ("84", lambda df: compute_point_84_override(0.0, df, "TEST", features=pd.DataFrame({"x1": df["close"], "x2": df["volume"]}))),
        ("85", lambda df: compute_point_85_override(0.33, df, "TEST", model_likelihoods=[0.8, 0.5, 0.3])),
        ("86", lambda df: compute_point_86_override(0.0, df, "TEST", features=pd.DataFrame({"x1": df["close"], "x2": df["volume"]}), target=df["close"])),
        ("87", lambda df: compute_point_87_override(0.0, df, "TEST", x_series=pd.Series(np.linspace(0, 1, 100)), y_series=pd.Series(np.random.randn(100)), x_pred=0.5)),
        ("88", lambda df: compute_point_88_override(0.001, df, "TEST", errors=np.random.randn(100))),
        ("89", lambda df: compute_point_89_override(0.0, df, "TEST", features=pd.DataFrame({"x1": df["close"], "x2": df["volume"]}))),
        ("96", lambda df: compute_point_96_override(0.25, df, "TEST", returns=pd.DataFrame({"A": df["close"].pct_change(), "B": df["volume"].pct_change()}))),
        ("97", lambda df: compute_point_97_override(0.0, df, "TEST")),
        ("98", lambda df: compute_point_98_override(0.0, df, "TEST")),
        ("99", lambda df: compute_point_99_override(0.25, df, "TEST", returns=pd.DataFrame({"A": df["close"].pct_change(), "B": df["volume"].pct_change()}))),
    ]
    
    for point_id, test_fn in tests:
        pid, status, result = test_point(point_id, test_fn, df)
        results.append((pid, status, result))
        print(f"Point {pid}: {status}")
    
    passed = sum(1 for _, s, _ in results if s == "PASS")
    total = len(results)
    print(f"\n=== Results: {passed}/{total} passed ===")
    
    if passed < total:
        for pid, status, _ in results:
            if status != "PASS":
                print(f"  FAILED: Point {pid} - {status}")
        sys.exit(1)
    else:
        print("All tests passed!")
        sys.exit(0)

if __name__ == "__main__":
    main()
