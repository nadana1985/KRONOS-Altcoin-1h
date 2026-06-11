"""
kronos.quant_spec.overrides

Implementations of individual bias override points from the 100-point manual.

Each point module:
- Is self-contained or imports shared helpers.
- Computes both raw (legacy) and new quant replacement.
- Is intended to be called, with the result passed through BiasOverrideEngine.apply_override().
- Loads all numeric parameters from the overrides section of liquidity_tiers.yaml (via engine or direct load).

Current points:
- point_01: Hardcoded Alpha Threshold Bias (dynamic quantile veto on slot_15)
- point_02: Rigid Feature Window Bias (volatility-scaled lookbacks)
- point_04: Manual Linear Multiplier Bias (rolling percentile rank)
- point_08: Hardcoded Lookback Scaling Ratios (adaptive cycle scaling)
- point_09: Static Percentage Threshold Bias (ATR-weighted bandwidths)
- point_11: Arbitrary EWM Smoothing Span Bias (volume-synchronized EWM)
- point_14: Hardcoded Denominator Epsilon Guards (dynamic sigma-scaled eps)
- point_46: Close-Only Volatility Calculation Bias (Yang-Zhang)
- point_47: Drift-Free Volatility Assumptions (Rogers-Satchell)
- point_48: Linear Volatility Outlier Sensitivity (MAD)
- point_49: Overnight Gap Blindness (Garman-Klass w/ overnight)
- point_50: Micro-Crash Ignorance (Parkinson)
- point_51: Volatility Clustering Feedback Ignorance (GARCH(1,1))
- point_52: Real-World Volatility Skewness Blindness (Downside Semi-Vol)
- point_57: Range-Based Noise Overestimation (Bid-Ask Filtered RS)

Shared utilities live in .utils (many volatility estimators added for this batch).
"""

from .point_01 import compute_point_01_override  # noqa: F401
from .point_02 import get_volatility_scaled_window, compute_point_02_override  # noqa: F401
from .point_04 import compute_point_04_override  # noqa: F401
from .point_08 import compute_point_08_override  # noqa: F401
from .point_09 import compute_point_09_override  # noqa: F401
from .point_11 import compute_point_11_override  # noqa: F401
from .point_14 import compute_point_14_override  # noqa: F401

# Volatility batch
from .point_46 import compute_point_46_override  # noqa: F401
from .point_47 import compute_point_47_override  # noqa: F401
from .point_48 import compute_point_48_override  # noqa: F401
from .point_49 import compute_point_49_override  # noqa: F401
from .point_50 import compute_point_50_override  # noqa: F401
from .point_51 import compute_point_51_override  # noqa: F401
from .point_52 import compute_point_52_override  # noqa: F401
from .point_57 import compute_point_57_override  # noqa: F401

# New volatility batch 2
from .point_53 import compute_point_53_override  # noqa: F401
from .point_54 import compute_point_54_override  # noqa: F401
from .point_55 import compute_point_55_override  # noqa: F401
from .point_56 import compute_point_56_override  # noqa: F401
from .point_58 import compute_point_58_override  # noqa: F401
from .point_59 import compute_point_59_override  # noqa: F401
from .point_60 import compute_point_60_override  # noqa: F401

# Tail risk batch
from .point_61 import compute_point_61_override  # noqa: F401
from .point_64 import compute_point_64_override  # noqa: F401
from .point_66 import compute_point_66_override  # noqa: F401
from .point_69 import compute_point_69_override  # noqa: F401
from .point_70 import compute_point_70_override  # noqa: F401

# Microstructure & Order Flow batch
from .point_17 import compute_point_17_override  # noqa: F401
from .point_19 import compute_point_19_override  # noqa: F401
from .point_21 import compute_point_21_override  # noqa: F401
from .point_22 import compute_point_22_override  # noqa: F401
from .point_25 import compute_point_25_override  # noqa: F401
from .point_26 import compute_point_26_override  # noqa: F401

# Validation, Purging & Causality batch
from .point_35 import compute_point_35_override  # noqa: F401
from .point_79 import compute_point_79_override  # noqa: F401
from .point_80 import compute_point_80_override  # noqa: F401
from .point_82 import compute_point_82_override  # noqa: F401
from .point_90 import compute_point_90_override  # noqa: F401

# Operational & Execution batch (91-95, 100)
from .point_91 import compute_point_91_override  # noqa: F401
from .point_92 import compute_point_92_override  # noqa: F401
from .point_93 import compute_point_93_override  # noqa: F401
from .point_94 import compute_point_94_override  # noqa: F401
from .point_95 import compute_point_95_override  # noqa: F401
from .point_100 import compute_point_100_override  # noqa: F401

# Remaining Batch A (Points 03, 05, 06, 07, 10, 12, 13, 15, 16, 18, 20, 23, 24)
from .point_03 import compute_point_03_override  # noqa: F401
from .point_05 import compute_point_05_override  # noqa: F401
from .point_06 import compute_point_06_override  # noqa: F401
from .point_07 import compute_point_07_override  # noqa: F401
from .point_10 import compute_point_10_override  # noqa: F401
from .point_12 import compute_point_12_override  # noqa: F401
from .point_13 import compute_point_13_override  # noqa: F401
from .point_15 import compute_point_15_override  # noqa: F401
from .point_16 import compute_point_16_override  # noqa: F401
from .point_18 import compute_point_18_override  # noqa: F401
from .point_20 import compute_point_20_override  # noqa: F401
from .point_23 import compute_point_23_override  # noqa: F401
from .point_24 import compute_point_24_override  # noqa: F401

# Remaining Batch B (Points 27-34, 36-45)
from .point_27 import compute_point_27_override  # noqa: F401
from .point_28 import compute_point_28_override  # noqa: F401
from .point_29 import compute_point_29_override  # noqa: F401
from .point_30 import compute_point_30_override  # noqa: F401
from .point_31 import compute_point_31_override  # noqa: F401
from .point_32 import compute_point_32_override  # noqa: F401
from .point_33 import compute_point_33_override  # noqa: F401
from .point_34 import compute_point_34_override  # noqa: F401
from .point_36 import compute_point_36_override  # noqa: F401
from .point_37 import compute_point_37_override  # noqa: F401
from .point_38 import compute_point_38_override  # noqa: F401
from .point_39 import compute_point_39_override  # noqa: F401
from .point_40 import compute_point_40_override  # noqa: F401
from .point_41 import compute_point_41_override  # noqa: F401
from .point_42 import compute_point_42_override  # noqa: F401
from .point_43 import compute_point_43_override  # noqa: F401
from .point_44 import compute_point_44_override  # noqa: F401
from .point_45 import compute_point_45_override  # noqa: F401

# Remaining Batch C (Points 63,65,67,68,71-78,81,83-89,96-99)
from .point_63 import compute_point_63_override  # noqa: F401
from .point_65 import compute_point_65_override  # noqa: F401
from .point_67 import compute_point_67_override  # noqa: F401
from .point_68 import compute_point_68_override  # noqa: F401
from .point_71 import compute_point_71_override  # noqa: F401
from .point_72 import compute_point_72_override  # noqa: F401
from .point_73 import compute_point_73_override  # noqa: F401
from .point_74 import compute_point_74_override  # noqa: F401
from .point_75 import compute_point_75_override  # noqa: F401
from .point_76 import compute_point_76_override  # noqa: F401
from .point_77 import compute_point_77_override  # noqa: F401
from .point_78 import compute_point_78_override  # noqa: F401
from .point_81 import compute_point_81_override  # noqa: F401
from .point_83 import compute_point_83_override  # noqa: F401
from .point_84 import compute_point_84_override  # noqa: F401
from .point_85 import compute_point_85_override  # noqa: F401
from .point_86 import compute_point_86_override  # noqa: F401
from .point_87 import compute_point_87_override  # noqa: F401
from .point_88 import compute_point_88_override  # noqa: F401
from .point_89 import compute_point_89_override  # noqa: F401
from .point_96 import compute_point_96_override  # noqa: F401
from .point_97 import compute_point_97_override  # noqa: F401
from .point_98 import compute_point_98_override  # noqa: F401
from .point_99 import compute_point_99_override  # noqa: F401

from .utils import (  # noqa: F401
    rolling_percentile_rank,
    compute_volatility_scaled_window,
    compute_atr_bandwidth,
    compute_volume_synced_alpha,
    compute_dynamic_epsilon,
    compute_adaptive_cycle_window,
    # Execution utilities
    resolve_os_agnostic_path,
    compute_system_memory_available_gb,
    compute_adaptive_shard_size,
    compute_latency_slippage_modifier,
    compute_dynamic_execution_cost,
    compute_twap_execution_price,
    compute_impact_aware_position_size,
    # Previous vol estimators
    compute_close_to_close_vol,
    compute_parkinson_vol,
    compute_rogers_satchell_vol,
    compute_yang_zhang_vol,
    compute_garman_klass_vol,
    compute_mad_vol,
    compute_downside_semi_vol,
    compute_garch_vol,
    compute_bidask_filtered_rs_vol,
    # New for previous batch
    compute_amihud_illiq,
    compute_amihud_adjusted_vol,
    compute_beta_neutral_residual_vol,
    compute_hurst_exponent,
    compute_dfa_vol_scaling,
    compute_integrated_var_high_freq,
    compute_realized_kernel_with_jump,
    # New for tail risk batch
    compute_rolling_skewness,
    compute_rolling_kurtosis,
    compute_huber_robust_mean,
    compute_tail_var_es,
    compute_evt_gpd_tail,
    # New for microstructure batch
    compute_corwin_schultz_spread,
    compute_beta_cdf_wick_exhaustion,
    compute_spread_weighted_absorption,
    compute_entropy_adaptive_lambda,
    compute_cauchy_proximity_kernel,
    # New for validation/purging/causality batch
    get_purged_embargo_indices,
    generate_cpcv_paths,
    deflated_sharpe_ratio,
    causal_lag_cross_sectional,
    monte_carlo_deflated_sharpe_paths,
    # New for Remaining Batch A
    compute_svd_bottleneck_compression,
    compute_volume_density_window,
    compute_amihud_continuous_decay,
    compute_parsimonious_polynomial_map,
    compute_timestamp_latency_truncation,
    compute_variance_mixture_zscore,
    compute_trade_intensity_imbalance,
    compute_skewness_weighted_barriers,
    compute_kde_volume_profile,
    compute_log_volume_zscore,
    compute_shannon_count_entropy,
    compute_eigenvalue_covariance_weight,
    compute_fractional_difference,
    # Remaining Batch B utilities
    compute_downside_semivariance,
    compute_hurst_adaptive_lookback,
    compute_kendall_tau_strength,
    compute_microstructure_noise_estimator,
    compute_entropy_weighted_bar_duration,
    compute_dynamic_annualization_scale,
    compute_volume_density_genesis,
    compute_vpin_synced_horizon,
    compute_ou_stochastic_bridge,
    compute_causal_latency_outlier_filter,
    compute_hull_moving_average,
    compute_dft_dominant_cycle,
    compute_intra_bar_volume_density,
    compute_dtw_phase_shift,
    compute_variance_stabilized_range,
    compute_wavelet_decomposition,
    compute_information_weighted_rolling,
    compute_gumbel_copula_transform,
    # Remaining Batch C utilities
    compute_quantile_transform,
    compute_kalman_dynamic_ar,
    compute_white_heteroskedastic_se,
    compute_spearman_rho,
    compute_kalman_dynamic_beta,
    compute_hill_tail_index,
    compute_rolling_johansen_trace,
    compute_cusum_break_detector,
    compute_vif_scores,
    compute_mutual_information_distance,
    compute_pca_distance_projections,
    compute_vol_symmetric_barrier_labels,
    compute_mst_pruning,
    compute_information_weighted_loss,
    compute_mahalanobis_distance,
    compute_bma_weights,
    compute_mrmr_scores,
    compute_loess_prediction,
    compute_linex_loss,
    compute_gmm_soft_membership,
    compute_min_variance_portfolio,
    compute_jensen_alpha,
    compute_rolling_engle_granger,
    compute_dynamic_risk_parity,
)
