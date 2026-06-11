"""
KRONOS V1-ALT — Remaining Batch B Validation Script
Points 27, 28, 29, 30, 31, 32, 33, 34, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45
"""
from __future__ import annotations

import sys
import traceback

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

passed = 0
failed = 0
errors = []

def run_test(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  [PASS] {name}")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        print(f"  [FAIL] {name}: {e}")


def make_data(n=300, regime="normal"):
    rng = np.random.RandomState(42)
    if regime == "low_liquidity":
        close = pd.Series(10 + np.cumsum(rng.randn(n) * 0.02))
        vol = pd.Series(rng.uniform(1000, 10000, n))
        count = pd.Series(rng.randint(50, 500, n).astype(float))
    elif regime == "high_liquidity":
        close = pd.Series(50 + np.cumsum(rng.randn(n) * 0.005))
        vol = pd.Series(rng.uniform(5e6, 5e7, n))
        count = pd.Series(rng.randint(2000, 20000, n).astype(float))
    else:
        close = pd.Series(100 + np.cumsum(rng.randn(n) * 0.01))
        vol = pd.Series(rng.uniform(1e5, 1e6, n))
        count = pd.Series(rng.randint(200, 2000, n).astype(float))
    h = close + rng.uniform(0, 2, n)
    l = close - rng.uniform(0, 2, n)
    o = close + rng.randn(n) * 0.5
    return h, l, o, close, vol, count


print("=" * 60)
print("KRONOS V1-ALT - Remaining Batch B Validation")
print("=" * 60)

for regime in ["low_liquidity", "normal", "high_liquidity"]:
    print(f"\n--- Regime: {regime} ---")
    h, l, o, close, vol, count = make_data(regime=regime)
    rng = np.random.RandomState(42)
    returns = pd.Series(rng.randn(300) * 0.01)
    volume_accel = pd.Series(rng.randn(300) * 1e4)
    timestamps = pd.Series(range(0, 300 * 3600000, 3600000))

    def test_p27():
        from kronos.quant_spec.overrides.point_27 import compute_semivariance_directional_scaling
        result = compute_semivariance_directional_scaling(close, 20, 0.5, 100)
        assert "directional_weight" in result
        assert 0 <= result["directional_weight"] <= 1
    run_test("Point 27: Semivariance Directional Scaling", test_p27)

    def test_p28():
        from kronos.quant_spec.overrides.point_28 import compute_hurst_adaptive_profile
        result = compute_hurst_adaptive_profile(close, 288, 50, 20, 400, 100)
        assert "profile_lookback" in result
        assert 20 <= result["profile_lookback"] <= 400
    run_test("Point 28: Hurst-Adaptive Profile", test_p28)

    def test_p29():
        from kronos.quant_spec.overrides.point_29 import compute_kendall_trend_strength
        result = compute_kendall_trend_strength(close, 20, 100)
        assert "tau" in result
        assert -1 <= result["tau"] <= 1
    run_test("Point 29: Kendall's Tau Trend-Strength", test_p29)

    def test_p30():
        from kronos.quant_spec.overrides.point_30 import compute_microstructure_noise
        result = compute_microstructure_noise(h, l, close, count, 20, 1.0, 100)
        assert "noise_eta" in result
        assert result["noise_eta"] >= 0
    run_test("Point 30: Microstructure Noise", test_p30)

    def test_p31():
        from kronos.quant_spec.overrides.point_31 import compute_entropy_info_bars
        cfg = {"entropy_target": 2.0, "min_window": 1, "max_window": 12, "min_data_density": 100, "fallback_window": 1}
        result = compute_entropy_info_bars(vol, cfg)
        assert "bar_duration" in result
        assert 1 <= result["bar_duration"] <= 12
    run_test("Point 31: Entropy Info Bars", test_p31)

    def test_p32():
        from kronos.quant_spec.overrides.point_32 import compute_dynamic_annualization
        cfg = {"sample_rate_ms": 3600000.0, "min_data_density": 100, "fallback_scale": 1.0}
        result = compute_dynamic_annualization(timestamps, cfg)
        assert "annualization_scale" in result
        assert 0.1 <= result["annualization_scale"] <= 10.0
    run_test("Point 32: Dynamic Annualization", test_p32)

    def test_p33():
        from kronos.quant_spec.overrides.point_33 import compute_volume_genesis
        cfg = {"baseline_density": 1000000.0, "min_data_density": 100, "fallback_genesis": 0}
        result = compute_volume_genesis(vol, cfg)
        assert "genesis_index" in result
        assert result["genesis_index"] >= 0
    run_test("Point 33: Volume Genesis Threshold", test_p33)

    def test_p34():
        from kronos.quant_spec.overrides.point_34 import compute_vpin_synced_horizon
        cfg = {"base_horizon": 4, "phi_target": 1.5, "min_window": 1, "max_window": 12, "min_data_density": 100}
        result = compute_vpin_synced_horizon(vol, cfg)
        assert "dynamic_horizon" in result
        assert 1 <= result["dynamic_horizon"] <= 12
    run_test("Point 34: VPIN Synced Horizon", test_p34)

    def test_p36():
        from kronos.quant_spec.overrides.point_36 import compute_ou_bridge_imputation
        cfg = {"theta": 0.1, "sigma_scale": 1.0, "n_paths": 50, "min_data_density": 100, "fallback_fill": 0.0}
        result = compute_ou_bridge_imputation(close, [100, 150], cfg)
        assert "imputed_count" in result
        assert result["imputed_count"] == 2
    run_test("Point 36: OU Bridge Imputation", test_p36)

    def test_p37():
        from kronos.quant_spec.overrides.point_37 import compute_latency_outlier_filter
        cfg = {"window": 50, "quantile_threshold": 0.99, "min_data_density": 100, "fallback_filtered_pct": 0.0}
        result = compute_latency_outlier_filter(timestamps, cfg)
        assert "filtered_count" in result
        assert result["filtered_count"] >= 0
    run_test("Point 37: Latency Outlier Filter", test_p37)

    def test_p38():
        from kronos.quant_spec.overrides.point_38 import compute_hma_override
        result = compute_hma_override(close, 20, 100)
        assert "hma_value" in result
        assert np.isfinite(result["hma_value"])
    run_test("Point 38: Hull Moving Average", test_p38)

    def test_p39():
        from kronos.quant_spec.overrides.point_39 import compute_dft_dominant_cycle
        cfg = {"window": 288, "min_freq": 3, "min_data_density": 100, "fallback_period": 24}
        result = compute_dft_dominant_cycle(vol, cfg)
        assert "dominant_period" in result
        assert result["dominant_period"] >= 3
    run_test("Point 39: DFT Dominant Cycle", test_p39)

    def test_p40():
        from kronos.quant_spec.overrides.point_40 import compute_intra_bar_density
        cfg = {"window": 50, "min_data_density": 100, "fallback_weight": 1.0}
        t_pct = pd.Series(np.linspace(0, 1, 300))
        result = compute_intra_bar_density(vol, t_pct, cfg)
        assert "density_weight" in result
        assert result["density_weight"] > 0
    run_test("Point 40: Intra-Bar Density", test_p40)

    def test_p41():
        from kronos.quant_spec.overrides.point_41 import compute_dtw_alignment
        cfg = {"max_shift": 50, "min_data_density": 100, "fallback_shift": 0}
        result = compute_dtw_alignment(close, vol, cfg)
        assert "optimal_shift" in result
    run_test("Point 41: DTW Alignment", test_p41)

    def test_p42():
        from kronos.quant_spec.overrides.point_42 import compute_range_normalization
        cfg = {"window": 20, "min_data_density": 100, "fallback_norm_range": 1.0}
        result = compute_range_normalization(h, l, cfg)
        assert "normalized_range" in result
        assert result["normalized_range"] > 0
    run_test("Point 42: Range Normalization", test_p42)

    def test_p43():
        from kronos.quant_spec.overrides.point_43 import compute_wavelet_decomp
        cfg = {"levels": 3, "min_data_density": 100, "fallback_orthogonality": 0.5}
        result = compute_wavelet_decomp(close, cfg)
        assert "energy_distribution" in result
        assert len(result["energy_distribution"]) > 0
    run_test("Point 43: Wavelet Decomposition", test_p43)

    def test_p44():
        from kronos.quant_spec.overrides.point_44 import compute_info_weighted_rolling
        cfg = {"window": 50, "min_data_density": 100, "fallback_weighted": 0.0}
        entropy_s = pd.Series(rng.uniform(0.1, 1.0, 300))
        result = compute_info_weighted_rolling(returns, entropy_s, cfg)
        assert "weighted_value" in result
        assert np.isfinite(result["weighted_value"])
    run_test("Point 44: Info-Weighted Rolling", test_p44)

    def test_p45():
        from kronos.quant_spec.overrides.point_45 import compute_copula_transform
        cfg = {"window": 100, "min_data_density": 100, "fallback_copula": 0.5}
        result = compute_copula_transform(returns, vol, cfg)
        assert "copula_value" in result
        assert 0 <= result["copula_value"] <= 1
    run_test("Point 45: Copula Transform", test_p45)


print("\n--- Engine Integration ---")
def test_engine_integration():
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    engine = BiasOverrideEngine()
    for pid in ["27", "28", "29", "30", "31", "32", "33", "34", "36", "37", "38", "39", "40", "41", "42", "43", "44", "45"]:
        assert pid in engine.registry, f"Point {pid} not in registry"
    print(f"  All 18 Batch B points registered (total: {len(engine.registry)})")

run_test("Engine Integration", test_engine_integration)


print("\n" + "=" * 60)
print(f"Results: {passed} passed, {failed} failed")
if errors:
    print("\nFailures:")
    for name, err in errors:
        print(f"  - {name}: {err}")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
