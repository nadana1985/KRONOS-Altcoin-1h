"""
Batch validation script for Points 36, 11, 06, 48.
Tests engine routing and basic numerical correctness for each point.
Run: python scripts/validate_batch_36_11_06_48.py
"""
import sys
import os
from pathlib import Path

# Resolve project root
_here = Path(__file__).resolve()
proj_root = _here.parent.parent
sys.path.insert(0, str(proj_root))

import numpy as np
import pandas as pd

os.environ.setdefault("KRONOS_PARAMS_PATH", str(proj_root / "params_yaml.txt"))

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

engine = BiasOverrideEngine()

rng = np.random.default_rng(42)
N = 200
c = 100.0 + np.cumsum(rng.normal(0, 0.5, N))
o = c + rng.normal(0, 0.1, N)
h = c + rng.uniform(0, 1.0, N)
l = c - rng.uniform(0, 1.0, N)
v_high = rng.uniform(5_000_000, 20_000_000, N)
v_low = rng.uniform(10_000, 100_000, N)
df_high = pd.DataFrame({"close": c, "open": o, "high": h, "low": l, "volume": v_high})
df_low = pd.DataFrame({"close": c, "open": o, "high": h, "low": l, "volume": v_low})
df_norm = df_high.copy()

failures = []

# ── Point 36: OU Gap Imputation ────────────────────────────────────────────
print("\n=== Point 36: OU Gap Imputation ===")
from kronos.quant_spec.overrides.point_36 import compute_point_36_override, compute_ou_bridge_imputation, _load_point_36_config

p36_cfg = _load_point_36_config(engine)
close_s = pd.Series(c)
result36 = compute_ou_bridge_imputation(close_s, [50, 100, 150], p36_cfg)
print(f"  imputed_count={result36['imputed_count']}  quality_proxy={result36['quality_proxy']:.4f}")

final36_gap = compute_point_36_override(0.0, close_s, [50, 100], df=df_norm, symbol="P36_GAP", engine=engine)
final36_none = compute_point_36_override(0.0, close_s, [], df=df_norm, symbol="P36_NOGAP", engine=engine)
print(f"  with gaps:    {final36_gap:.4f}  | without gaps: {final36_none:.4f}")
if not (0.0 <= final36_gap <= 2.0 and 0.0 <= final36_none <= 2.0):
    failures.append("P36: values out of expected range")
print("  Point 36 OK")

# ── Point 11: Volume-Synchronized EWM Alpha ────────────────────────────────
print("\n=== Point 11: Volume-Synchronized EWM Alpha ===")
from kronos.quant_spec.overrides.point_11 import compute_point_11_override, compute_volume_synced_ewm_alpha, _load_point_11_config

p11_cfg = _load_point_11_config(engine)
alpha_high = compute_volume_synced_ewm_alpha(0.1, pd.Series(v_high), config=p11_cfg)
alpha_low = compute_volume_synced_ewm_alpha(0.1, pd.Series(v_low), config=p11_cfg)
print(f"  high_vol_alpha={alpha_high:.4f}  low_vol_alpha={alpha_low:.4f}")

final11 = compute_point_11_override(0.1, df_high, "P11_TEST", engine=engine)
print(f"  engine_routed: base=0.1 -> final={final11:.4f}")
if not (0.0 < final11 <= 1.0):
    failures.append(f"P11: final alpha {final11} out of (0,1]")
print("  Point 11 OK")

# ── Point 06: Continuous Amihud Decay ──────────────────────────────────────
print("\n=== Point 06: Continuous Amihud Decay ===")
from kronos.quant_spec.overrides.point_06 import compute_point_06_override, compute_continuous_decay_weight, _load_point_06_config

p06_cfg = _load_point_06_config(engine)
w_high = compute_continuous_decay_weight(pd.Series(c), pd.Series(o), pd.Series(v_high), config=p06_cfg)
w_low = compute_continuous_decay_weight(pd.Series(c), pd.Series(o), pd.Series(v_low), config=p06_cfg)
print(f"  high_liq_weight={w_high:.4f}  low_liq_weight={w_low:.4f}")

if not (w_high >= w_low):
    failures.append(f"P06: high_liq ({w_high:.4f}) should >= low_liq ({w_low:.4f})")

final06 = compute_point_06_override(0.5, df_high, "P06_HIGH", engine=engine)
print(f"  engine_routed: raw=0.5 -> final={final06:.4f}")
if not (0.0 <= final06 <= 1.0):
    failures.append(f"P06: weight {final06} out of [0,1]")
print("  Point 06 OK")

# ── Point 48: Rolling MAD Volatility ───────────────────────────────────────
print("\n=== Point 48: Rolling MAD Volatility ===")
from kronos.quant_spec.overrides.point_48 import compute_point_48_override, compute_mad_volatility, _load_point_48_config

p48_cfg = _load_point_48_config(engine)
# Introduce an outlier spike
c_spike = c.copy()
c_spike[100] += 25.0
vol_mad = compute_mad_volatility(pd.Series(c_spike), config=p48_cfg)
vol_std = float(pd.Series(c_spike).pct_change().std())
print(f"  MAD_vol={vol_mad:.5f}  std_vol={vol_std:.5f}  (MAD should be more robust)")

df48_spike = pd.DataFrame({"close": c_spike, "open": o, "high": h, "low": l, "volume": v_high})
final48 = compute_point_48_override(vol_std, df48_spike, "P48_SPIKE", engine=engine)
print(f"  engine_routed: raw_std={vol_std:.5f} -> final_mad={final48:.5f}")
if not (vol_mad > 0.0 and vol_std > 0.0):
    failures.append(f"P48: invalid vol values: mad={vol_mad}, std={vol_std}")
print("  Point 48 OK")

# ── Final result ────────────────────────────────────────────────────────────
print("\n" + "="*60)
if failures:
    print(f"FAILURES ({len(failures)}):")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("ALL POINTS (36, 11, 06, 48) VALIDATED SUCCESSFULLY [OK]")
    sys.exit(0)
