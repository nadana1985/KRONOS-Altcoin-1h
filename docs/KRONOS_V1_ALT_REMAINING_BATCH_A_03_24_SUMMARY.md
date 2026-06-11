# KRONOS V1-ALT — Remaining Batch A Summary (Points 03, 05, 06, 07, 10, 12, 13, 15, 16, 18, 20, 23, 24)

## Overview

This batch implements **13 bias override points** from the Quant Bias Override Manual v2.0, covering spatial dimension compression, calendar-time flexibility, discrete filtering, formula automation, latency handling, volatility regime boundaries, order flow splits, asymmetric risk, volume profiling, persistence modeling, entropy measures, covariance weighting, and memory regularization.

**Validation:** 39/39 tests passed across all three regimes (normal, low_liquidity, high_liquidity).
**Engine:** 100 total points registered after batch.

---

## Points Implemented

| Point | Title | Complexity | Quant Replacement |
|-------|-------|-----------|-------------------|
| **03** | Spatial Dimension Inflation | Medium | SVD-Based Orthogonal Bottleneck Compression |
| **05** | Calendar-Time Rigidity | Medium | Synthetic Quote Volume-Imbalance Aggregation |
| **06** | Discrete Liquidity Filtering | Low | Continuous Amihud Decay Adjuster |
| **07** | Arbitrary Formula Assembly | High | GP-Evolved Parsimonious Polynomial Mapping |
| **10** | Sessional Latency | Medium | Systemic Timestamp Latency Truncation |
| **12** | Binary Volatility Regime Boundaries | Medium | Continuous Variance Mixture Z-Scores |
| **13** | Fixed Order Flow Proxy Splits | Medium | Trade-Intensity Weighted Imbalance |
| **15** | Symmetric Path-Risk Target Boundaries | Medium | Skewness-Weighted Asymmetric Barriers |
| **16** | Volume-at-Price Fixed Discretization | Medium | Gaussian KDE Volume Profiling |
| **18** | Linear Volume Impact Scaling | Low | Logarithmic Volume Z-Score Normalization |
| **20** | Trade-Count Uniform Weighting | Low | Normalized Shannon Count Entropy |
| **23** | Equal-Weighted Divergence Indices | Medium | Eigenvalue-Driven Covariance Weighting |
| **24** | Linear OFI Persistence | Medium | Fractionally Differenced OFI |

---

## Shared Utilities Created (in utils.py)

| Utility | Points Using | Description |
|---------|-------------|-------------|
| `compute_svd_bottleneck_compression` | 03 | SVD rank reduction with variance explained |
| `compute_volume_density_window` | 05 | Adaptive windowing via cumulative volume |
| `compute_amihud_continuous_decay` | 06 | Continuous exponential decay weight |
| `compute_parsimonious_polynomial_map` | 07 | BIC-penalized polynomial fitting |
| `compute_timestamp_latency_truncation` | 10 | Latency-based bar truncation |
| `compute_variance_mixture_zscore` | 12 | Short/long variance ratio z-score |
| `compute_trade_intensity_imbalance` | 13 | Trade-count-weighted OFI |
| `compute_skewness_weighted_barriers` | 15 | Asymmetric path-risk barriers |
| `compute_kde_volume_profile` | 16 | Gaussian KDE for volume-at-price |
| `compute_log_volume_zscore` | 18 | Log-normalized volume z-score |
| `compute_shannon_count_entropy` | 20 | Normalized Shannon entropy of trade distribution |
| `compute_eigenvalue_covariance_weight` | 23 | PCA-driven return/volume weight |
| `compute_fractional_difference` | 24 | Binomial-weighted fractional differencing |

---

## Key YAML Parameter Decisions

All parameters are in `kronos/config/liquidity_tiers.yaml` under `overrides.point_XX`:

- **Point 03:** `n_components: 3`, `noise_std: 0.01`, `min_data_density: 300`
- **Point 05:** `target_multiplier: 2.0`, `min_window: 5`, `max_window: 200`
- **Point 06:** `lambda_decay: 50.0`, `window: 20`, `min_data_density: 50`
- **Point 07:** `max_degree: 3`, `alpha_parsimony: 1.0`, `min_data_density: 20`
- **Point 10:** `base_latency_ms: 100.0`, `latency_window: 50`, `latency_tolerance: 0.15`
- **Point 12:** `short_window: 20`, `long_window: 100`, `min_data_density: 50`
- **Point 13:** `window: 20`, `min_data_density: 50`
- **Point 15:** `phi_base: 2.0`, `skew_window: 50`, `min_data_density: 50`
- **Point 16:** `n_price_levels: 50`, `bandwidth_factor: 1.0`, `min_data_density: 30`
- **Point 18:** `window: 20`, `min_data_density: 30`
- **Point 20:** `window: 24`, `n_bins: 10`, `min_data_density: 50`
- **Point 23:** `window: 50`, `min_data_density: 30`
- **Point 24:** `d: 0.4`, `max_lags: 20`, `min_data_density: 30`

---

## Critical Fixes Applied During Review

1. **Fractional differencing binomial weights** (utils.py): Original `np.arange(1-k, 1)` always included 0, making all weights after k=0 zero. Fixed to recursive formula: `weights[k] = weights[k-1] * (k-1-d) / k`.

2. **Point 10 latency threshold** (utils.py + point_10.py): `tolerance = 0.15` was hardcoded in Python. Moved to `liquidity_tiers.yaml` as `latency_tolerance: 0.15` and read from config.

3. **Point 03 SVD determinism** (point_03.py): 1D fallback used bare `np.random.normal`. Changed to `np.random.RandomState(42)` for reproducibility.

4. **Point 10 fallback config** (point_10.py): Added `latency_tolerance: 0.15` to fallback dict for consistency.

---

## Integration Recommendations

- **High priority:** Points 03 (SVD compression) and 12 (variance mixture z-scores) should be integrated first — they affect clustering quality and regime detection respectively.
- **Medium priority:** Points 05, 10, 13, 15 — these improve adaptive windowing, latency handling, order flow, and risk targeting.
- **Lower priority:** Points 06, 07, 16, 18, 20, 23, 24 — these are enhancements that provide marginal but compounding gains.

---

## Suggested Next Batch

**Remaining Batch B** covering the following points:
- Points 27-34 (if defined in the manual)
- Points 36-45 (gap between validation and volatility batches)
- Any remaining unimplemented points from the full registry

**Alternative focus:** Integration testing of all implemented points against real shard data to validate cross-point synergy.
