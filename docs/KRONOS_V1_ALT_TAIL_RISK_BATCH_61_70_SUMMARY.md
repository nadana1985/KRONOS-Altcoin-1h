# KRONOS V1-ALT — Tail Risk & Robust Statistics Batch Summary (Points 61, 64, 66, 69, 70)

**Batch:** Tail Risk & Robust Statistics (Group 5)  
**Implemented:** 5 points  
**Validation:** `scripts/validate_tail_risk_batch.py` (regime tests + fallbacks + engine gating)  
**Status:** All points set to `"implemented"` / `validation_status="backtest_only"` after validation passed.

## Short Implementation Summary per Point

- **Point 61: Normal Distribution Assumptions**  
  Extreme Value Theory (EVT) Generalized Pareto Distribution (GPD) tail modeling.  
  Practical causal tail scale adjustment on base volatility using exceedance proxy.  
  File: `point_61.py`. Uses `compute_evt_gpd_tail`.

- **Point 64: Symmetric Tail Risk Bounds**  
  Causal Value at Risk (VaR) & Expected Shortfall (ES).  
  Proper one-sided tail loss measures (ES is the key output).  
  File: `point_64.py`. Uses `compute_tail_var_es`.

- **Point 66: Outlier Sensitivity in Return Estimations**  
  Huber Loss Robust Return Estimator (M-estimator that down-weights outliers).  
  File: `point_66.py`. Uses `compute_huber_robust_mean`.

- **Point 69: Tail Skewness Ignorance**  
  Rolling Fisher Skewness Estimator (gamma1).  
  File: `point_69.py`. Uses `compute_rolling_skewness`.

- **Point 70: Heavy-Tail Excess Kurtosis Ignorance**  
  Rolling Fisher Kurtosis Estimator (gamma2, excess).  
  File: `point_70.py`. Uses `compute_rolling_kurtosis`.

All points strictly follow the established wrapper + engine pattern, load all params from YAML, have structured logging, and implement proper fallbacks.

## Shared Statistical / Tail Risk Utilities Created

Extended `kronos/quant_spec/overrides/utils.py`:

- `compute_rolling_skewness`
- `compute_rolling_kurtosis`
- `compute_huber_robust_mean`
- `compute_tail_var_es` (returns dict with 'var' and 'es')
- `compute_evt_gpd_tail` (simplified GPD-scale proxy for tail adjustment)

These are now available for reuse across the system and future batches. They complement the volatility utilities from previous work.

## Key Parameter Decisions in `liquidity_tiers.yaml` + Reasoning

New sections appended for the batch with conservative, practical values suitable for 1h altcoin perps:

- **Point 61 (EVT):** `threshold_quantile: 0.95`, `gpd_xi: 0.2`, `gpd_beta: 0.01`, `min_data_density: 100`, `fallback_tail_vol: 0.02`  
  Reason: Standard 95% threshold for tails; modest xi (shape) for altcoins; sufficient data for stable exceedance stats.

- **Point 64 (VaR/ES):** `var_confidence: 0.95`, `es_confidence: 0.95`, `var_window: 50`, `min_data_density: 60`, `fallback_var: 0.02`, `fallback_es: 0.03`  
  Reason: Common 95% level; 50-bar window balances responsiveness and stability; conservative fallbacks.

- **Point 66 (Huber):** `huber_c: 1.345`, `huber_window: 50`, `min_data_density: 40`, `fallback_return: 0.0`  
  Reason: Classic Huber tuning constant (95% efficiency); reasonable window for return estimation.

- **Point 69 (Skew) / 70 (Kurt):** `*_window: 50`, `min_data_density: 40`, `fallback_* : 0.0`  
  Reason: Consistent with other moment-based points; sufficient observations for stable higher moments in 1h data.

All values are deliberately conservative for low-liquidity alts and fully configurable.

## Observations on KRONOS Improvements

These tail-risk and robust tools significantly strengthen several areas:

- **Risk Management & Position Sizing:** Proper VaR/ES (64) + EVT tail adjustment (61) give much better downside risk numbers than symmetric variance. Huber (66) provides outlier-resistant expected returns for sizing.
- **Regime Detection & Signal Filtering:** Skew (69) and Kurt (70) are excellent regime indicators (fat tails + negative skew often precede crises). Can feed into or replace parts of existing regime features.
- **Complement to Previous Volatility Work:** The prior batches gave better "scale" (vol estimators). This batch adds "shape" (tails, asymmetry, robustness). Together they enable far more accurate risk overlays, conviction adjustments, and Option B components.
- **Liquidity Awareness:** Because everything routes through the BiasOverrideEngine + LiquidityClassifier, these tail measures automatically become more conservative on low-liquidity symbols (where tails are fatter and data sparser).
- **Crisis Robustness:** The combination of robust returns (66), higher moments (69/70), and explicit tail modeling (61/64) directly attacks the "normal distribution in altcoins" problem highlighted in the manual.

## Recommended Early Integration Points

Highest immediate value / easiest to integrate:

1. **Point 64 (VaR/ES)** — Direct, high-impact replacement for any symmetric risk calculation. Use the ES value for conservative sizing/risk limits.
2. **Point 66 (Huber)** — Drop-in robust expected return. Very safe and immediately useful in any return-based feature or prior.
3. **Point 61 (EVT)** — When paired with 64, gives proper tail scaling. High priority for risk system.
4. **69/70 (Skew/Kurt)** — Lightweight and excellent as additional regime or DNA features. Easy to add in parallel with existing moments.

Suggested integration order: 66 → 64 → 61 → (69+70 as features).

## Suggested Next Batch

- Any remaining Group 5 points (e.g. 62, 63, 65, 67, 68, 71+ for covariance, AR, beta, etc.).
- Or a "Tail Risk Application" batch that wires 61/64 + previous vol estimators into concrete risk/sizing modules.
- Consider a small shared "tail_risk_calculator" helper that can return a bundle (VaR, ES, EVT scale, skew, kurt) for a given series.

**Summary MD file generated as requested:** `docs/KRONOS_V1_ALT_TAIL_RISK_BATCH_61_70_SUMMARY.md`

The batch is complete, validated, and ready. All sovereignty, engine, and pattern rules were followed. The new tail/robust tools meaningfully extend the previous volatility work.