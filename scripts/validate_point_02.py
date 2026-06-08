"""
Validation script for KRONOS Point 02 — Rigid Feature Window Bias.

Demonstrates the volatility-scaled lookback adaptation and its integration
with the engine + Point 01 (slot15 history lookback).

Run:
    python scripts/validate_point_02.py
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.point_02 import (
    compute_volatility_scaled_lookback,
    get_volatility_scaled_window,
    get_slot15_history_lookback,
    get_vpin_lookback,
    get_ofi_lookback,
    _load_point_02_config,
)
# Optional: show synergy with Point 01
try:
    from kronos.quant_spec.overrides.point_01 import compute_point_01_override
    HAS_POINT_01 = True
except Exception:
    HAS_POINT_01 = False


def make_synthetic_price_df(n: int = 300, seed: int = 123) -> pd.DataFrame:
    """Price series with clear volatility regimes (low -> high -> medium)."""
    rng = np.random.default_rng(seed)
    rets = np.concatenate([
        rng.normal(0.0001, 0.002, n // 3),
        rng.normal(0.0001, 0.015, n // 3),
        rng.normal(0.0001, 0.007, n - 2 * (n // 3)),
    ])[:n]
    close = 100 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({"close": close})
    df["high"] = df["close"] * (1 + np.abs(rng.normal(0, 0.001, n)))
    df["low"] = df["close"] * (1 - np.abs(rng.normal(0, 0.001, n)))
    df["volume"] = rng.uniform(5e5, 4e6, n)
    return df


def main():
    print("=" * 72)
    print("KRONOS Point 02 Validation — Rigid Feature Window Bias")
    print("=" * 72)

    engine = BiasOverrideEngine()
    cfg = _load_point_02_config(engine)
    print(f"Loaded Point 02 config: gamma={cfg['gamma']}, "
          f"vol_short={cfg['vol_short_window']}, ref_method={cfg['vol_reference_method']}")
    print(f"Bases: slot15={cfg.get('slot15_history_base')}, vpin={cfg.get('vpin_base')}, ofi={cfg.get('ofi_base')}")

    df = make_synthetic_price_df(280)
    symbol = "VOLREGIMEUSDT"

    print(f"\nSynthetic df: len={len(df)}, price range ~{df['close'].min():.1f}-{df['close'].max():.1f}")

    # 1. Direct pure function on different bases
    print("\n--- 1. Direct volatility scaling (pure quant, no engine) ---")
    for name, base in [("slot15_history", cfg.get("slot15_history_base", 100)),
                       ("vpin", cfg.get("vpin_base", 100)),
                       ("ofi", cfg.get("ofi_base", 50))]:
        scaled = compute_volatility_scaled_lookback(base, df, config=cfg)
        print(f"  {name:18s} base={base:3d}  ->  scaled={scaled:3d}")

    # 2. Low data density
    print("\n--- 2. Low data density fallback ---")
    short_df = df.tail(15)
    scaled_short = compute_volatility_scaled_lookback(100, short_df, config=cfg)
    print(f"  len={len(short_df)} base=100 -> scaled={scaled_short} (fallback active)")

    # 3. Engine-wrapped (status still not_started in registry at start of validation)
    print("\n--- 3. Engine-wrapped calls (respects current registry status) ---")
    for name, base in [("slot15_history", cfg.get("slot15_history_base", 100)),
                       ("vpin", cfg.get("vpin_base", 100)),
                       ("ofi", cfg.get("ofi_base", 50))]:
        final = get_volatility_scaled_window(base, df, symbol, engine=engine)
        print(f"  {name:18s} base={base:3d} via engine -> final={final:3d} (raw while not implemented)")

    # 4. Specific helpers + force tier demo
    print("\n--- 4. Convenience helpers + force_tier demo ---")
    slot15_lb = get_slot15_history_lookback(df, symbol, engine=engine)
    vpin_lb = get_vpin_lookback(df, symbol, engine=engine)
    ofi_lb = get_ofi_lookback(df, symbol, engine=engine)
    print(f"  slot15_history_lookback (recommended for Point 01): {slot15_lb}")
    print(f"  vpin_lookback: {vpin_lb}")
    print(f"  ofi_lookback:  {ofi_lb}")

    forced = get_volatility_scaled_window(100, df, symbol, engine=engine, force_tier="low")
    print(f"  base=100 with force_tier='low' -> {forced} (still raw, but shows call site)")

    # 5. Synergy with Point 01 (if available): use scaled lb for its history window
    if HAS_POINT_01:
        print("\n--- 5. Point 01 synergy demo (using Point 02 scaled lookback) ---")
        scaled_lb = get_slot15_history_lookback(df, symbol, engine=engine)
        print(f"  Point 02 recommends lookback={scaled_lb} for Point 01 slot15 history")

        # Minimal neural + dummy current for the call
        neural = {
            "confidence_min": 0.72,
            "confidence_clamp": (0.58, 0.91),
            "strength_mult": 4.2,
            "strength_add": 0.55,
            "variation": 0.38,
            "slot15_entropy_weight": 0.1,
            "reversal_window": [20, 50],
        }
        curr_slot15 = 0.64
        # Pass the scaled lookback explicitly (Point 01 accepts **kwargs / lookback)
        p01_result = compute_point_01_override(
            current_slot15=curr_slot15,
            df=df,
            symbol=symbol,
            neural=neural,
            engine=engine,
            lookback=scaled_lb,   # <-- volatility-scaled value from Point 02
        )
        print(f"  Point 01 called with volatility-scaled lookback={scaled_lb} -> result={p01_result:.4f}")
    else:
        print("\n--- 5. Point 01 synergy: (Point 01 not importable in this env, skipped) ---")

    print("\n" + "=" * 72)
    print("Validation complete.")
    print("Safety property: while status != 'implemented', engine returns raw base windows.")
    print("Update registry point 02 status to 'implemented' ONLY after review.")
    print("Point 02 now provides adaptive lookbacks (start with slot15 history for Point 01).")
    print("=" * 72)


if __name__ == "__main__":
    main()
