# KRONOS V1-ALT — Microstructure & Order Flow Batch Summary (Points 17, 19, 21, 22, 25, 26)

**Batch:** Microstructure & Order Flow (Group 2)  
**Implemented:** 6 points  
**Validation:** `scripts/validate_microstructure_batch.py` (high/low/mixed liquidity regimes + fallbacks + engine gating)  
**Status:** All points set to `"implemented"` / `validation_status="backtest_only"` after validation passed.

## Short Implementation Summary per Point

- **Point 17: Constant Spread Assumptions**  
  Corwin-Schultz High-Low Range Spread Estimator (dynamic two-bar gamma-based spread).  
  File: `point_17.py`. Uses `compute_corwin_schultz_spread`. Replaces fixed spread assumptions for execution and filtering.

- **Point 19: Static Wick Prominence Scaling**  
  Rolling Non-Parametric Beta-CDF Mapping for wick exhaustion (maps wick ratio to Beta CDF with configurable alpha/beta).  
  File: `point_19.py`. Uses `compute_beta_cdf_wick_exhaustion`. Dynamic, distribution-aware replacement for static wick_mult.

- **Point 21: Order Book Depth Ignorance**  
  Amihud Illiquidity Volume Impact Proxy (price impact lambda turned into exponential weight).  
  File: `point_21.py`. Uses `compute_amihud_illiq`. Turns raw volume into liquidity-impact-adjusted weight.

- **Point 22: Linear Bid-Ask Absorption Scaling**  
  Spread-Weighted Directional Delta Absorption (scales buy/sell volume by proximity to H/L within the bar, further weighted by local spread).  
  File: `point_22.py`. Uses `compute_spread_weighted_absorption`. Makes absorption directional and microstructure-aware.

- **Point 25: Static S/R Memory Decay Parameters**  
  Information-Entropy Adaptive Memory Half-Life (scales decay lambda by normalized entropy of recent counts/activity).  
  File: `point_25.py`. Uses `compute_entropy_adaptive_lambda`. Makes S/R memory decay faster in high-information regimes.

- **Point 26: Discrete State Transitions for Key Level Proximity**  
  Continuous Cauchy Proximity Kernels (smooth, heavy-tailed mapping of distance to nearest key level).  
  File: `point_26.py`. Uses `compute_cauchy_proximity_kernel`. Replaces step functions with a smooth Cauchy kernel.

## Shared Microstructure / Statistical Utilities Created

Extended `kronos/quant_spec/overrides/utils.py` (and exported):

- `compute_corwin_schultz_spread` (17)
- `compute_beta_cdf_wick_exhaustion` (19, with scipy fallback to empirical rank)
- `compute_spread_weighted_absorption` (22)
- `compute_entropy_adaptive_lambda` (25)
- `compute_cauchy_proximity_kernel` (26)

These build on prior Amihud/illiq helpers and are now available for reuse (e.g., spread can feed filtered volatility estimators from earlier batches).

## Key Parameter Choices in `liquidity_tiers.yaml` + Reasoning

Appended dedicated sections with conservative values tuned for 1h altcoin perps (emphasis on low-liquidity robustness):

- **Point 17:** `cs_window: 2`, `min_data_density: 50`, `fallback_spread: 0.001`  
  (Classic two-bar Corwin-Schultz; modest data requirement; conservative default spread.)

- **Point 19:** `beta_alpha: 2.0`, `beta_beta: 5.0`, `wick_window: 20`, `min_data_density: 60`, `fallback_wick: 0.5`  
  (Beta shape that gives more mass to extreme wicks; 20-bar window for responsiveness.)

- **Point 21:** `amihud_window: 20`, `amihud_lambda: 0.5`, `min_data_density: 50`, `fallback_illiq: 0.0`  
  (Matches prior Amihud usage; lambda provides meaningful but not extreme weighting.)

- **Point 22:** `absorption_window: 20`, `min_data_density: 50`, `fallback_absorption: 0.0`  
  (Short window keeps it responsive to current bar dynamics.)

- **Point 25:** `entropy_window: 24`, `base_lambda: 0.1`, `min_data_density: 50`, `fallback_lambda: 0.1`  
  (24-bar (~1 day) for entropy; base decay consistent with prior S/R work.)

- **Point 26:** `cauchy_gamma: 0.01`, `min_data_density: 40`, `fallback_proximity: 0.5`  
  (Small gamma gives sharp but smooth decay around key levels; safe fallback.)

All values prioritize low-liquidity safety and are fully overridable.

## Observations on How These Improve KRONOS

This batch directly upgrades execution modeling, liquidity awareness, and S/R feature quality:

- **Execution & Slippage Modeling:** Point 17 (dynamic spread) is foundational — can directly improve cost estimates and feed filters like Point 57 (bid-ask filtered vol).
- **Wick/Exhaustion & Slot 10:** Point 19 replaces the static wick_ratio_mult with a proper distributional mapping — much better for doji/exhaustion scoring on varying liquidity.
- **Liquidity-Aware Volume:** Point 21 (Amihud) turns raw volume into impact-weighted signals — critical for low-liquidity alts where volume is misleading.
- **Directional Absorption (Slot 00):** Point 22 makes absorption respect bar position and local spread — far more realistic than symmetric formulas during runs.
- **Adaptive S/R Memory:** Point 25 makes proximity decay (e.g. Point 49/50 style) regime-aware via entropy — decays faster when information flow is high.
- **Smooth Key Level Proximity:** Point 26 replaces discrete steps with a continuous, heavy-tailed Cauchy kernel — excellent for soft barriers, gradual conviction build-up, and avoiding cliff effects.

**Synergy with prior work:** These pair extremely well with the volatility batches (spread from 17 can clean range-based estimators; Amihud from 21 + vol from 46-60 gives true liquidity-adjusted risk; entropy from 25 can modulate GARCH memory or adaptive windows from Point 02/08).

## Recommended Early Integration Points

Highest immediate value / easiest wins:

1. **Point 17 (Corwin-Schultz)** — Foundational. Wire into any execution cost model or as a spread input to volatility filters.
2. **Point 21 (Amihud)** — Immediate upgrade for any volume-based feature or weighting (very safe, high impact on low-liq names).
3. **Point 26 (Cauchy Proximity)** — Easy win for all S/R and key-level features; smooths out discrete logic.
4. **Point 19 (Beta-CDF Wick)** — Direct upgrade to existing Slot 10 wick logic.
5. **Point 22 + 25** — Next for absorption (Slot 00) and adaptive S/R memory.

Prioritize 17 and 21 first — they have the broadest downstream impact.

## Suggested Next Batch

- Remaining Group 2 microstructure (e.g. 18, 20, 23, 24, 27–30) — many will reuse the new spread/entropy/proximity helpers.
- Or a "Microstructure Application" batch that wires these (especially 17/21/22/26) into concrete execution modeling, cost-aware signals, and S/R features in the structural engine.
- Consider a small shared `microstructure_features(df)` helper that returns a bundle (spread, illiq_weight, absorption, proximity_kernel, entropy_lambda) for easy consumption by higher-level logic.

**Summary MD file generated as requested:** `docs/KRONOS_V1_ALT_MICROSTRUCTURE_BATCH_17_26_SUMMARY.md`

All rules followed. Reusability was prioritized (5 new shared helpers + reuse of prior Amihud). Validation passed with correct safety behavior (raw returned while statuses were "not_started"). The batch is ready for integration into the structural engine, miner, or execution layer. The new tools meaningfully improve liquidity awareness and execution realism across the 530+ altcoin universe.