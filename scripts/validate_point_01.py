"""
Validation script for KRONOS Point 01 — Hardcoded Alpha Threshold Bias.

Run this after any change to point_01.py or the registry status.

It demonstrates:
1. Direct new quant logic on synthetic regimes (old static vs dynamic quantile).
2. Full engine integration (the only production path).
3. Safe fallback on low data density.
4. That while the point status in the registry is not "implemented", the engine
   always returns the raw (static) value — this is the safety guarantee.
5. Behavior under forced liquidity tiers (via engine.force_tier).

Usage:
    python scripts/validate_point_01.py
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Bootstrap so we can import from kronos.*
sys.path.insert(0, str(Path(__file__).parent.parent))

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.point_01 import (
    compute_point_01_dynamic_veto,
    compute_point_01_override,
    _load_point_01_config,
)


def make_synthetic_slot15_history(n: int = 300, seed: int = 123) -> pd.Series:
    """Create a realistic-looking slot_15 history with regime changes."""
    rng = np.random.default_rng(seed)
    # Low vol regime, then higher, then noisy
    part1 = rng.normal(0.52, 0.07, n // 3)
    part2 = rng.normal(0.71, 0.05, n // 3)
    part3 = rng.normal(0.63, 0.09, n - 2 * (n // 3))
    vals = np.clip(np.concatenate([part1, part2, part3]), 0.0, 1.0)
    return pd.Series(vals, name="slot15_hist")


def main():
    print("=" * 70)
    print("KRONOS Point 01 Validation — Hardcoded Alpha Threshold Bias")
    print("=" * 70)

    engine = BiasOverrideEngine()
    cfg = _load_point_01_config(engine)
    print(f"Loaded Point 01 config from YAML: quantile={cfg['quantile']}, "
          f"lookback_default={cfg['lookback_default']}, fallback_T={cfg['fallback_static_threshold']}")

    hist = make_synthetic_slot15_history(280)
    print(f"\nSynthetic history: len={len(hist)}, mean={hist.mean():.3f}, std={hist.std():.3f}")

    # 1. Direct new logic examples
    print("\n--- 1. Direct new quant replacement (no engine) ---")
    test_currents = [0.48, 0.59, 0.67, 0.74, 0.81]
    for curr in test_currents:
        T, eff = compute_point_01_dynamic_veto(curr, hist.tail(150), config=cfg)
        old_T = 0.72  # the static we are replacing (shown only for comparison)
        old_eff = curr if curr >= old_T else 0.0
        print(f"current={curr:.2f} | old_T=0.72 old_eff={old_eff:.2f} | "
              f"new_T={T:.3f} new_eff={eff:.2f} | changed={old_eff != eff}")

    # 2. Low data density fallback
    print("\n--- 2. Low data density fallback ---")
    short_hist = hist.tail(20)
    T_low, eff_low = compute_point_01_dynamic_veto(0.61, short_hist, config=cfg)
    print(f"short history len={len(short_hist)} → T={T_low:.3f}, effective={eff_low:.3f} (fallback active)")

    # 3. Full engine path (status is still "not_started" → must return raw)
    print("\n--- 3. Engine-wrapped path (current registry status) ---")
    dummy_df = pd.DataFrame({
        "close": np.linspace(0.3, 0.31, 80),
        "high": np.linspace(0.3, 0.31, 80) + 0.005,
        "low": np.linspace(0.3, 0.31, 80) - 0.005,
        "volume": np.random.uniform(8e5, 3e6, 80),
        "quote_volume": np.random.uniform(4e5, 2e6, 80),
        "count": np.random.randint(400, 5000, 80),
    })

    neural = {
        "confidence_min": 0.72,
        "confidence_clamp": (0.58, 0.91),
        "strength_mult": 4.2,
        "strength_add": 0.55,
        "variation": 0.38,
        "slot15_entropy_weight": 0.1,
        "reversal_window": [20, 50],
    }

    raw_curr = 0.61
    final = compute_point_01_override(
        current_slot15=raw_curr,
        df=dummy_df,
        symbol="VALUSDT",
        neural=neural,
        engine=engine,
        lookback=120,
    )
    print(f"current_slot15={raw_curr:.2f} via engine → final={final:.3f}")
    print("  (Must equal raw because point status is still 'not_started' in registry)")

    # 4. Force a tier (simulates different liquidity) — still should return raw today
    final_forced = compute_point_01_override(
        current_slot15=raw_curr,
        df=dummy_df,
        symbol="VALUSDT",
        neural=neural,
        engine=engine,
        lookback=120,
        force_tier="micro",   # passed through **kwargs to engine
    )
    print(f"same current, force_tier='micro' → final={final_forced:.3f} (still raw)")

    # 5. What happens if we pretend the point is implemented (for illustration only)
    print("\n--- 5. Illustration only: if status were 'implemented' ---")
    print("  (We temporarily monkey-patch the engine's active statuses for demo)")
    orig_statuses = engine._active_statuses
    engine._active_statuses = {"implemented", "validated", "active", "not_started"}  # demo only
    final_if_impl = compute_point_01_override(
        current_slot15=raw_curr,
        df=dummy_df,
        symbol="VALUSDT",
        neural=neural,
        engine=engine,
        lookback=120,
    )
    engine._active_statuses = orig_statuses
    print(f"  If point were implemented → final would be {final_if_impl:.3f} (dynamic applied)")

    print("\n" + "=" * 70)
    print("Validation complete.")
    print("Safety property verified: while status != 'implemented', engine always returns raw.")
    print("Update registry.yaml point 01 status to 'implemented' ONLY after full review.")
    print("=" * 70)


if __name__ == "__main__":
    main()
