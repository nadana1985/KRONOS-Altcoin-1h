# KRONOS V1-ALT — Volatility Estimator Bias Override Batch Summary (Points 46,47,48,49,50,51,52,57)

**Batch:** Advanced Non-Stationary Volatility Estimators (Group 4)  
**Implemented:** 8 points  
**Date:** Post Point 01/02/04/08/09/11/14 foundation  
**Status:** All `"implemented"` + `validation_status: "backtest_only"` after running `scripts/validate_volatility_batch.py`

## Points Implemented

### Point 46: Close-Only Volatility Calculation Bias
- **Replacement:** Yang-Zhang Non-Stationary Volatility Estimator (overnight + open-to-close + RS with weight k).
- **File:** `kronos/quant_spec/overrides/point_46.py`
- **Key Config (liquidity_tiers.yaml):** `vol_window`, `yz_k`, `min_data_density`, `fallback_vol`

### Point 47: Drift-Free Volatility Assumptions (Base for 57)
- **Replacement:** Rogers-Satchell Volatility Estimator (drift-robust range).
- **File:** `kronos/quant_spec/overrides/point_47.py`
- **Key Config:** `vol_window`, `min_data_density`, `fallback_vol`

### Point 48: Linear Volatility Outlier Sensitivity
- **Replacement:** Rolling Median Absolute Deviation (MAD) with scale factor.
- **File:** `kronos/quant_spec/overrides/point_48.py`
- **Key Config:** `mad_window`, `mad_scale`, `min_data_density`, `fallback_vol`

### Point 49: Overnight Gap Blindness
- **Replacement:** Garman-Klass with Overnight Corrections (weighted overnight + intra-bar).
- **File:** `kronos/quant_spec/overrides/point_49.py`
- **Key Config:** `vol_window`, `gk_overnight_weight`, `min_data_density`, `fallback_vol`

### Point 50: Micro-Crash Ignorance
- **Replacement:** High-Low Range Parkinson Estimator.
- **File:** `kronos/quant_spec/overrides/point_50.py`
- **Key Config:** `vol_window`, `min_data_density`, `fallback_vol`

### Point 51: Volatility Clustering Feedback Ignorance
- **Replacement:** Empirical GARCH(1,1) Volatility Tracker (recursive conditional variance).
- **File:** `kronos/quant_spec/overrides/point_51.py`
- **Key Config:** `garch_omega`, `garch_alpha`, `garch_beta`, `garch_window`, `min_data_density`, `fallback_vol`

### Point 52: Real-World Volatility Skewness Blindness
- **Replacement:** Causal Downside Semi-Volatility Estimator (negative returns only).
- **File:** `kronos/quant_spec/overrides/point_52.py`
- **Key Config:** `vol_window`, `min_data_density`, `fallback_vol`

### Point 57: Range-Based Noise Overestimation (Builds on 47)
- **Replacement:** Causal Bid-Ask Bounce Filtered Rogers-Satchell (RS minus spread^2/4).
- **File:** `kronos/quant_spec/overrides/point_57.py`
- **Key Config:** `vol_window`, `spread_proxy`, `min_data_density`, `fallback_vol`
- **Note:** Directly re-uses Point 47 logic + filter utility.

## Shared Utility Functions Created / Extended

Extended `kronos/quant_spec/overrides/utils.py` with a comprehensive volatility toolkit (all causal, pandas/numpy, return latest scalar):

- `compute_close_to_close_vol(close, window)`
- `compute_parkinson_vol(high, low, window)`
- `compute_rogers_satchell_vol(open, high, low, close, window)`
- `compute_yang_zhang_vol(open, high, low, close, window, k)`
- `compute_garman_klass_vol(open, high, low, close, prev_close, window, a)`
- `compute_mad_vol(returns, window, scale=1.4826)`
- `compute_downside_semi_vol(close, window)`
- `compute_garch_vol(returns, omega, alpha, beta, window)`
- `compute_bidask_filtered_rs_vol(...)` (for 57, builds on RS)

These are exported via `overrides/__init__.py` and used heavily to avoid duplication.

Also leveraged existing helpers from prior batches (vol scaling, etc.) where relevant.

## Recommended YAML Parameters (and Rationale)

All pulled from `liquidity_tiers.yaml` → `overrides.point_XX` (chosen for 1h USDT perps altcoin universe, conservative for low-liquidity assets):

- **vol_window / mad_window / etc.:** 20 (short-term responsive for 1h bars; ~ trading day equivalent). Some 50 for GARCH burn-in.
- **min_data_density:** 30-60 (ensures meaningful rolling stats before trusting; triggers fallback otherwise).
- **fallback_vol:** 0.01 (conservative ~1% "daily" scale for 1h context; safe for micro alts).
- **Specifics:**
  - yz_k: 0.34 (classic Yang-Zhang literature value for overnight weight balance).
  - gk_overnight_weight (a): 0.5 (balanced gap vs intra).
  - garch_omega/alpha/beta: 1e-6 / 0.08 / 0.85 (typical persistent clustering without explosion; long-run var ~0.01^2).
  - mad_scale: 1.4826 (standard normal consistency factor).
  - spread_proxy (57): 0.0005 (0.05% realistic for many alts; tunable per-liquidity later).
- **Why these values?** Balance reactivity vs stability for altcoin 1h data. Fallbacks deliberately conservative. All overridable in YAML for different regimes/liquidity tiers.

## Observations on Synergies in the KRONOS System

These 8 estimators are highly complementary and can be wired into existing structures (structural_engine slot_08 regime, slot_07 Amihud/divergence, neural conviction, risk overlays, position sizing, etc.):

- **Robust base (48 MAD + 52 Downside):** Use MAD or semi-vol in place of std for any "vol" input to avoid outlier/ skew distortion (e.g., in regime_vol_short/long, DNA features).
- **Range power (47 RS, 50 Parkinson, 49 GK, 46 YZ):** Switch from close-only in high-liquidity or trending regimes. YZ (46) is often "best" all-rounder for non-stationary 1h data.
- **Clustering (51 GARCH):** Feed into adaptive lookbacks (Point 02) or dynamic windows (Point 08). The recursive state captures memory that simple rolling misses.
- **Microstructure aware (57 Filtered RS):** Critical for low-liquidity alts (micro volume → bid-ask bounce inflates range vols). Combine with liquidity tier from classifier (e.g., heavier filter on "low"/"micro").
- **Combined usage example:**
  - Core "vol" feature: YZ (46) or filtered RS (57) for robustness.
  - Risk / barriers: Downside (52) + MAD (48) for tail-aware sizing.
  - Regime detection (slot_08 style): Blend GARCH persistence + Parkinson extremes.
  - Overall: These replace naive std in many places, directly improving signal quality, Option B priors, and E2E robustness without changing higher-level logic (engine decides per-point activation per liquidity).

They form a "volatility toolkit" that can be selected or blended per-symbol based on the dynamic liquidity tier (via engine) and current regime.

## Suggested Next Batch

High-value follow-ups from Group 4 / related:
- Remaining volatility (53-56, 58-60): relative spread-volume, beta-adjusted, Parkinson gap, DFA detrended, etc.
- Or move to Group 5 (statistical distribution/tail: 61-75) — VaR, CVaR, robust scaling, AR dynamics — which build naturally on better vol inputs from this batch.
- Or Group 2 microstructure (17-30) now that we have solid vol foundations.

Prioritize anything with direct impact on slot_15, regime, or risk (high priority in registry).

**Summary MD file generated as requested.**

All strict rules followed. Clean, reusable code with heavy sharing in utils. Validation passed (with note that engine correctly returns raw pre-status-flip, advanced post-flip). Ready for integration or next batch.