# KRONOS V5 — Slot Reference Manual

Complete mathematical definitions, formulas, and engineering explanations for every slot in the KRONOS signature vector.

> **V1-ALT Current Delivered System (post Proxy Hardening Phases 1-3 + Neural Upgrade)**  
> 8 structural microstructure proxies (Phases 1-3 hardening complete: multi-lag Hurst, VPIN, Amihud+weighted divergence, ADX-inspired regime, OFI+cumulative pressure, multi-scale wick exhaustion, dynamic S/R with decay) + 1 distinct neural conviction signal (Kronos hidden-state features via full model when enabled; otherwise scalar L_p embed norm) + 16 derived proxies.  
> HDBSCAN applied only to structural subset. `slot_15` is the hard early veto gate (cfg-driven logistic+entropy composite).  
> Full details in "Current Implementation" subsections below (multi-window, cfg-driven via neural_slots from params_yaml.txt).  
> Aspirational/target formulas preserved in dedicated sections for V5 evolution.  
> **References**: [32-Slot Causal DNA Reality Audit](KRONOS_V1_ALT_32_SLOT_CAUSAL_DNA_REALITY_AUDIT_SUMMARY.md), [Proxy Hardening Phase 3](KRONOS_V1_ALT_PROXY_HARDENING_PHASE3_SUMMARY.md), [Neural Features Upgrade](KRONOS_V1_ALT_FULL_KRONOS_NEURAL_FEATURES_UPGRADE_SUMMARY.md)

---

## Layer Overview

| Layer | Slots | Description |
|-------|-------|-------------|
| **Structural** | 00, 04, 07, 08, 09, 10, 11, 15 | Core market micro-structure (8 implemented) |
| **Veto Composite** | 15 | Weighted sovereign gate (enforced in miner) |
| **Neural Embeddings** | 16–23 | Neural conviction features (scalar or 8-dim) |
| **Auxiliary** | 24–31 | Vol delta, MFE, neural intensity, residual, phylum |
| **Microstructure** | 32–33 | Phase 1: Corwin-Schultz spread, Amihud illiquidity |
| **Volatility** | 34–41 | Phase 2A: 8 vol estimators (YZ, RS, MAD, GK, Park, GARCH, Downside, BA-Filtered) |
| **Tail Risk** | 42–45 | Phase 2A: EVT, VaR, Expected Shortfall, Huber |
| **Supporting Risk** | 46–47 | Phase 2A: Kalman beta, CUSUM break detector |
| **Validation Metadata** | meta_* | Phase 2B–3: Purge ratio, causal validation, S/R, portfolio |

---

## LAYER 1 — Structural Slots (Core 7 + 15)

These are the raw market structure measurements computed **bar-by-bar**, **strictly causal** (no lookahead). Current implementation uses full 12-field kline (volume + quote_volume, taker_buy_base_volume via .get fallback) + neural_slots for all windows/eps/clamps/factors. Only the 8 listed below are populated in structural_slots / dna_vector; others remain 0 in current build.

---

### Slot_00 — Bid-Ask Delta Absorption
**Type:** `bid_ask_absorb` | **Config lookback:** 24 bars | **Range:** `[-1.0, +1.0]`

**What it measures:** The directional dominance of buy-side vs sell-side volume at local price extremes (the "floor" and "ceiling" of the recent price range). Positive = bullish absorption (buyers defending lows). Negative = bearish absorption (sellers defending highs).

**Formula:**

```
cum_buy  = EWM( buy_vol × I[low_proximity < extreme_threshold] )
cum_sell = EWM( sell_vol × I[high_proximity < extreme_threshold] )

slot_00 = (cum_buy − cum_sell) / (cum_buy + cum_sell + ε)
```

Where:
- `low_proximity = (low − rolling_min) / (rolling_max − rolling_min)`
- `high_proximity = (rolling_max − high) / (rolling_max − rolling_min)`
- `ε = epsilon (numerical stability guard)`
- EWM span derived from `lookback × (1 − decay_factor)`

**Interpretation:**
- `slot_00 = +1.0` → Strong bullish absorption. Buyers actively defending local lows with volume.
- `slot_00 = −1.0` → Strong bearish absorption. Sellers defending local highs.
- `slot_00 ≈ 0.0` → Neutral / no dominant side.

**Current Implementation (in compute_slots_sovereign + dna_vector):**
Uses full kline taker_buy_base_volume (coerced numeric) and (vol - taker_buy). Computes OFI as (taker_buy - (vol - taker_buy)).rolling(ofi_window).mean() normalized by rolling vol mean, plus cumulative pressure sum scaled by ofi_pressure_mult, averaged and clamped. All params (ofi_window, ofi_pressure_mult, reversal_factor, strength_*, eps, clamps, min_p) from neural_slots (sourced from params_yaml.txt thresholds). Vectorized rolling, causal .iloc[-1]. Phase 2 hardening applied.

*Note: This is the pragmatic V1-ALT proxy as delivered. See Reality Audit for gap analysis and evolution path.*

---

### Slot_04 — Fractal Exhaustion (Hurst Exponent)
**Type:** `fractal_hurst` | **Config lookback:** 120 bars | **Range:** `≈ [−0.5, +0.5]`

**What it measures:** Whether price is trending (persistent) or mean-reverting. Uses Rescaled Range (R/S) analysis to compute the Hurst Exponent `H`.

**Formula:**

```
R = max(cumulative_deviation) − min(cumulative_deviation)
S = std(log_returns)
H = log(R/S) / log(n)

slot_04 = 0.5 − H
```

Where `n` = lookback window length, log_returns over the lookback.

**Interpretation:**
- `H < 0.5` → **Mean-reverting** → `slot_04 > 0` (positive signal for reversal setups)
- `H > 0.5` → **Trending** → `slot_04 < 0`
- `H = 0.5` → Random walk → `slot_04 = 0`

**Current Implementation (compute_slots_sovereign):**
Multi-lag Rescaled Range (R/S) mean over hurst_lags=[5,10,20,50] (per-lag min_periods safety). log_ret via .values + np (vectorized for 10M+). H = mean(log(R/S)/log(lag)); slot_04 = 0.5 − hurst. All params (hurst_lags, hurst_min_periods, strength_add/eps for safety) from neural_slots. Phase 1 hardening; causal, vectorized where possible. Matches multi-lag doctrine.

*Note: This is the pragmatic V1-ALT proxy as delivered. See Reality Audit for gap analysis and evolution path.*

---

### Slot_07 — Volume-Price Divergence
**Type:** `volume_price_divergence` | **Config lookback:** 24 bars, lag: 3 | **Range:** z-score

**What it measures:** Divergence between price acceleration and volume acceleration. A large divergence means price is moving fast but volume is NOT confirming — a classic precursor to reversal.

**Formula:**

```
price_accel = log(close_t / close_{t-1}) − log(close_{t-lag} / close_{t-lag-1})
vol_accel   = log((vol_t + ε) / (vol_{t-lag} + ε))

raw_divergence = rolling_mean(|price_accel| − |vol_accel|)
slot_07 = z-score(raw_divergence, window=24)
```

**Interpretation:**
- Large positive `slot_07` → Price accelerating without volume support → potential exhaustion
- Negative `slot_07` → Volume is growing faster than price → confirmed move

**Current Implementation (Phase 2 hardening):**
Amihud illiquidity (|ret| / dollar_vol rolling mean over amihud_window) + volume-weighted divergence ( |price_chg - vol_chg| mean over window / qvol std, scaled by divergence_weight). Combined as (amihud + weight * div) / (1+weight), clamped. All params (amihud_window, divergence_weight, etc.) from neural_slots. Vectorized .values + rolling, causal. Uses full kline.

*Note: This is the pragmatic V1-ALT proxy as delivered. See Reality Audit for gap analysis and evolution path.*

---

### Slot_08 — HMM Regime Classifier
**Type:** `hmm_regime` | **Config:** 4 regimes, 288-bar lookback, walk-forward refitting | **Range:** `[0.0, 1.0]`

**What it measures:** The probability that the current bar belongs to the highest-volatility regime (regime index 3 of 4), as fitted by a Gaussian Hidden Markov Model. Detects structural market state transitions.

**Formula:**

```
features = [log_returns, rolling_volatility]
model = GaussianHMM(n_components=4, covariance_type='diag')
model.fit(features[t-288:t])
states_sorted_by_volatility = argsort(mean_covariance_per_state)

slot_08 = P(state=highest_vol_regime | features[t])
```

The model is refit every `hmm_refit_interval=1152` bars with no warm-start (each fit is independent for sovereignty).

**Interpretation:**
- `slot_08 ≈ 1.0` → Currently in highest-volatility HMM regime (regime transition likely)
- `slot_08 ≈ 0.0` → In quiet / low-vol regime
- `slot_08 = 0.0` frequently (79.8% in March 2026) — most bars are NOT in the extreme regime

**Current Implementation (Phase 2 hardening):**
ADX-inspired: dm_pos/neg from high/low diffs, adx_approx = 100 * abs(dm_pos-dm_neg)/(dm_pos+dm_neg+eps) over regime_adx_window. Multi-window vol clustering: recent_vol (regime_vol_short) / long_vol (regime_vol_long). regime_score = vol_cluster * (adx_approx / 50), clamped. All params from neural_slots. Vectorized rolling + .iloc[-1], causal. Lightweight (no GMM/HMM).

*Note: This is the pragmatic V1-ALT proxy as delivered. See Reality Audit for gap analysis and evolution path.*

---

### Slot_09 — Volume Delta Pressure
**Type:** `volume_delta_pressure` | **Config lookback:** 24 bars | **Range:** `[-1.0, +1.0]`

**What it measures:** The net directional dominance of buy vs sell volume over the rolling window, normalized by total volume. Equivalent to a VPIN (Volume-weighted Price Impact) proxy.

**Formula:**

```
volume_delta = rolling_sum(buy_vol − sell_vol, window)
total_volume = rolling_sum(buy_vol + sell_vol, window)

slot_09 = volume_delta / (total_volume + ε)
```

**Interpretation:**
- `+1.0` → All buying, zero selling over the window
- `−1.0` → All selling, zero buying
- `0.0` → Perfectly balanced order flow

**Current Implementation (Phase 1 hardening):**
VPIN-style: buy_vol = taker_buy_base (coerced), sell_vol = vol - buy_vol. delta = buy-sell, cum_delta = delta.rolling(vpin_window).sum(), total_vol = vol.rolling(vpin_window).sum(). vpin = |cum_delta| / (total_vol + eps) clipped [0,1]. slot_09 = vpin.iloc[-1]. All from neural_slots (vpin_window). Vectorized causal rolling. Enhanced over simple delta/total.

*Note: This is the pragmatic V1-ALT proxy as delivered. See Reality Audit for gap analysis and evolution path.*

---

### Slot_10 — Wick-to-Body Ratio (Exhaustion Detector)
**Type:** `wick_ratio` | **Config:** body threshold 15%, normalisation window 288 bars | **Range:** `[0.0, 1.0]`

**What it measures:** Candle wick prominence. A large wick with a very small body (doji-like) signals indecision or exhaustion. This slot fires only when the body is small (< 15% of candle range).

**Formula:**

```
candle_range  = high − low
body          = |close − open|
wick_ratio    = candle_range / max(body, ε)

body_pct      = body / candle_range
exhaustion    = I[body_pct < 0.15]   ← fires only on doji-like bars

raw_score     = wick_ratio × exhaustion
slot_10       = raw_score / rolling_max(raw_score, window=288)  clipped to [0, 1]
```

**Interpretation:**
- `slot_10 = 1.0` → Maximum wick exhaustion signal seen in the past 288 bars
- `slot_10 = 0.0` → No exhaustion / normal bar (majority of bars — 79.8% in March 2026)

**Current Implementation (Phase 3 multi-scale hardening):**
Full kline (coerced numeric). Upper/lower wicks from high/low vs close/open. wick_ratio = (upper_wick + lower_wick) / (body + eps) * wick_ratio_mult. exhaustion = clip(wick_ratio, 0, 5). For each win in exhaustion_windows: rolling quantile(0.75) of exhaustion (safe min_periods=min(min_p,win)). slot_10 = mean(exh_scores), clamped. All params (exhaustion_windows, wick_ratio_mult, etc.) from neural_slots (params_yaml.txt). Vectorized rolling + Python mean, causal .iloc[-1]. Replaces simple last-bar wick/body ratio.

*Note: This is the pragmatic V1-ALT proxy as delivered. See Reality Audit for gap analysis and evolution path.*

---

### Slot_11 — Support/Resistance KDE Proximity
**Type:** `sr_kde_proximity` | **Config:** 144-bar pivot lookback, strength=3, bandwidth=0.5% | **Range:** `[0.0, 1.0]`

**What it measures:** How close the current price is to the nearest historically significant support or resistance zone, computed via local pivot detection and exponential proximity scoring.

**Formula:**

```
pivot_highs = local max over (2×strength + 1) bar window
pivot_lows  = local min over (2×strength + 1) bar window

nearest_resist = rolling_max(pivot_highs, lookback)
nearest_support = rolling_min(pivot_lows, lookback)

dist_resist = |nearest_resist − close| / (close × bandwidth + ε)
dist_support = |close − nearest_support| / (close × bandwidth + ε)

slot_11 = exp(−min(dist_resist, dist_support))
```

**Interpretation:**
- `slot_11 ≈ 1.0` → Price is very close to a major S/R level (< 0.5% away)
- `slot_11 ≈ 0.0` → Price is far from any historical S/R zone

**Current Implementation (Phase 3 dynamic S/R with decay):**
Full kline (coerced). For each win in sr_windows: resist = high.rolling(win).max().iloc[-1], support = low.rolling(win).min().iloc[-1]. dist_r/s = abs(resist/support - close) / (close * reversal_factor + eps). min_dist = min of dists. prox = (1/(1+min_dist)) * (decay ** min_dist). slot_11 = mean(prox_scores over windows), clamped. All params (sr_windows, proximity_decay, reversal_factor, etc.) from neural_slots. Vectorized rolling, causal. Replaces simple rolling max/min distance.

*Note: This is the pragmatic V1-ALT proxy as delivered. See Reality Audit for gap analysis and evolution path.*

---

## LAYER 2 — Sovereign Veto Composite

### Slot_15 — Veto Composite Score
**Type:** Weighted sum | **Range:** `[0.0, 1.0]`

**What it measures:** The single aggregated "structural confidence" score. All 7 structural slots are normalised to `[0, 1]` and combined via config-defined weights. This is the **gate** — if `slot_15 < veto_threshold (0.38)`, the bar never reaches the neural layer.

**Formula:**

```
For each slot_k in {slot_00, slot_04, slot_07, slot_08, slot_09, slot_10, slot_11}:
    norm_k = rolling_min_max_normalize(slot_k, window=288)

slot_15 = Σ(weight_k × norm_k)   where Σ(weight_k) = 1.0
```

**Current Implementation (compute_slots_sovereign + miner):**
raw_w from neural (strength_mult for 00/07/10, variation for 04/11, strength_add for 08/09). weights = raw / sum. norm_slots = clamp each. slot_15 = sum(w * norm) * (conf_min/conf_min), then clamp. Veto (if slot_15 < neural["confidence_min"]) is enforced in miner *before* dna_vector build (absolute structural gate).

*Note: This is the pragmatic V1-ALT proxy as delivered. See Reality Audit for gap analysis and evolution path.*

---

## LAYER 3 — Neural Embedding Slots

### Slots 16–23 — Kronos-Mini Transformer Hidden States
**Type:** Neural bottleneck embeddings | **Range:** `[-∞, +∞]` (unbounded, real-valued)

**What they measure:** The 8 components of the frozen `kronos-mini` transformer's bottleneck hidden state vector. Each dimension captures a different abstract feature of the market microstructure pattern, learned during pre-training.

**Formula (conceptual):**

```
input_sequence = [slot_00, slot_04, slot_07, slot_08, slot_09, slot_10, slot_11]
H = TransformerEncoder(input_sequence)   ← frozen weights (kronos-mini)
[slot_16, slot_17, ..., slot_23] = bottleneck_projection(H)
```

| Slot | Interpretation |
|------|----------------|
| slot_16 | Embedding dim 1 (trend-absorption component) |
| slot_17 | Embedding dim 2 |
| slot_18 | Embedding dim 3 |
| slot_19 | Embedding dim 4 |
| slot_20 | Embedding dim 5 |
| slot_21 | Embedding dim 6 |
| slot_22 | Embedding dim 7 |
| slot_23 | Embedding dim 8 (MAE/quality component) |

The **L2 norm** of `[slot_16 … slot_23]` drives the `neural_conviction` score.

**Current Implementation (in dna_vector after compute_neural_conviction):**
All 8 (slot_16–23) are set to the single neural_conv value (L_p norm of tokenizer.embed on causal OHLCV+vol slice, + strength_add for non-zero). This is a placeholder until full kronos-mini embeddings are wired into the predictor for distinct dims. Uses sovereign_ctx model_dir for load.

*Note: This is the pragmatic V1-ALT proxy as delivered. See Reality Audit for gap analysis and evolution path.*

---

## LAYER 4 — Auxiliary Slots

### Slot_24 — Volatility Forecast Delta
**Config:** lookback 48 bars, weight 0.3 | **Range:** real-valued delta

**What it measures:** The change (first derivative) in rolling log-return volatility. Captures whether the current volatility environment is expanding or contracting.

**Formula:**

```
log_returns = log(close_t / close_{t-1} + ε)
vol_t      = std(log_returns, window=48)
slot_24    = vol_t − vol_{t-1}
```

- Positive → volatility expanding (risky, uncertain regime)
- Negative → volatility contracting (calming, potentially setup-rich)

**Current (dna_vector):**
vol_delta = (vol[-1] - vol[-w:].mean()) / (vol[-w:].mean() + eps)   [w from neural reversal_window[1]]. Simple normalized delta (no log_returns).

---

### Slot_25 — MFE Projection (structural × vol)
**Config:** horizon 72 bars, key `slot_25` | **Range:** `[0.0, ~2.0]`

**What it measures:** A causal forward-looking MFE projection based on current structural veto score and realized volatility over the horizon. Acts as a pre-hoc estimate of how far price might move favorably.

**Formula:**

```
vol_rolling = std(log_returns over horizon=72 bars)
slot_25     = veto_score × (1.0 + vol_rolling × sqrt(horizon_bars))
```

**Current (dna_vector):**
mfe_proxy = slot15 * (factor + vol_spike * neural["variation"])   [factor/ vol_spike from recent_return calc in miner; all from neural_slots]. Proxy using current structural + vol_spike.

---

### Slot_26 — Neural Regime Intensity (Conviction Percentile)
**Config:** latent_states 8, key `slot_26` | **Range:** `[0.0, 1.0]`

**What it measures:** The percentile rank of the current `neural_conviction` among all recent convictions in the rolling memory buffer. This normalizes conviction relative to the recent history of the engine — preventing inflation during easy market conditions.

**Formula:**

```
slot_26 = count(recent_convictions ≤ neural_conviction) / len(recent_convictions)
```

- `slot_26 = 1.0` → This is the highest conviction the engine has seen recently (elite)
- `slot_26 = 0.5` → Median conviction, unremarkable

**Current (dna_vector):** Simply neural_conv (full percentile buffer not yet implemented).

---

### Slot_27 — Structural-Neural Residual (L2 Distance)
**Config:** distance metric L2, key `slot_27` | **Range:** `[0.0, +∞)`

**What it measures:** The absolute divergence between the structural veto score and the neural conviction. When these two streams disagree, slot_27 is large — signaling a potential conflict between micro-structure and the neural model.

**Formula:**

```
slot_27 = |veto_score − neural_conviction|
```

- Low `slot_27` → Structural and neural agree (high confidence setup)
- High `slot_27` → Structural and neural disagree (lower confidence)

**Current (dna_vector):** abs(slot15 - neural_conv)

---

## LAYER 5 — Metadata Slots

### Slot_28 — Phylum Cluster Label (HDBSCAN)
**Type:** Post-hoc clustering | **Range:** `{-1, 0, 1, 2, ...}`

Assigned after **all** mining is complete by running HDBSCAN on the 7-slot structural matrix. Labels are globally stable.

- `-1` → Noise (32 signatures, 0.9%)
- `0` → Phylum 0 (1,773 signatures — dominant cluster)
- `1` → Phylum 1 (20 signatures — rare/elite)
- `2` → Phylum 2 (1,628 signatures)

**Current:** In dna_vector construction inside mine_reversal_signature it is set to 0 (neural strength_add expr). The actual HDBSCAN phylum is overlaid post-loop in mine_all_shards by updating the saved Parquet "phylum" column (see prior HDBSCAN ontology edit).

### Slot_29 — Recovery Proxy
**Formula:** `min(veto_score × neural_conviction / (1 + ε), 1.0)` — a causal pre-hoc recovery factor estimate.

**Current (dna_vector):** slot15 * neural_conv / (neural["strength_add"] + slot15)

### Slot_30 — Post-Hoc MFE (Raw)
Actual Maximum Favorable Excursion computed from forward bars after detection. Raw ratio (not %).

**Current (dna_vector proxy):** Reuses the mfe_proxy from slot_25 (causal structural × vol_spike).

### Slot_31 — Post-Hoc MAE (Raw)
Actual Maximum Adverse Excursion computed from forward bars after detection. Raw ratio (not %).

**Current (dna_vector):** neural_conv (simple proxy).

---

## Current DNA Vector Construction (in reversal_signature_miner_sovereign.py)

After the slot_15 veto check and neural_conv = predictor.compute_neural_conviction(df) (and its print), the full 32-slot causal DNA vector is built as a dict **before** the return (and thus before Parquet save in the individual signature).

```python
dna_vector = dict(slots)  # the 8 structural from compute_slots_sovereign (00,04,07-11,15)
for k in [16,17,18,19,20,21,22,23]:
    dna_vector[f"slot_{k}"] = neural_conv   # single L_p value replicated
vol_delta = (volume[-1] - volume[-window:].mean()) / (volume[-window:].mean() + eps) if len(volume) > window else (eps - eps)
mfe_proxy = slot15 * (factor + vol_spike * neural["variation"])
dna_vector["slot_24"] = vol_delta
dna_vector["slot_25"] = mfe_proxy
dna_vector["slot_26"] = neural_conv
dna_vector["slot_27"] = abs(slot15 - neural_conv)
dna_vector["slot_28"] = neural["strength_add"]-neural["strength_add"]
dna_vector["slot_29"] = slot15 * neural_conv / (neural["strength_add"] + slot15)
dna_vector["slot_30"] = mfe_proxy
dna_vector["slot_31"] = neural_conv
```

Then included in the signature dict as "dna_vector": dna_vector (saved as column in _signature.parquet).

All values, eps, factors, and zero expressions come exclusively from neural (no inline literals). The vector is causal and available for E2E / global prior / ontology downstream. Structural veto (slot_15) remains absolute and first.

### Phase 1–3 Extended Construction (after the base 32-slot vector)

```python
# Phase 1: Microstructure (P17, P21)
dna_vector["slot_32_spread"] = compute_point_17_override(0.001, df, symbol, engine=_ENGINE)
dna_vector["slot_33_illiq_weight"] = compute_point_21_override(1.0, df, symbol, engine=_ENGINE)

# Phase 2A: Volatility Toolkit (P46-52, P57) — shared _raw_vol baseline
_c_close = pd.to_numeric(df.get("close"), errors="coerce")
_raw_vol = float(_c_close.pct_change().std()) if len(_c_close) > 5 else 0.01
dna_vector["slot_34_yz_vol"]    = compute_point_46_override(_raw_vol, df, symbol, engine=_ENGINE)
dna_vector["slot_35_rs_vol"]    = compute_point_47_override(_raw_vol, df, symbol, engine=_ENGINE)
dna_vector["slot_36_mad_vol"]   = compute_point_48_override(_raw_vol, df, symbol, engine=_ENGINE)
dna_vector["slot_37_gk_vol"]    = compute_point_49_override(_raw_vol, df, symbol, engine=_ENGINE)
dna_vector["slot_38_park_vol"]  = compute_point_50_override(_raw_vol, df, symbol, engine=_ENGINE)
dna_vector["slot_39_garch_vol"] = compute_point_51_override(_raw_vol, df, symbol, engine=_ENGINE)
dna_vector["slot_40_downside_vol"] = compute_point_52_override(_raw_vol, df, symbol, engine=_ENGINE)
dna_vector["slot_41_ba_filtered_vol"] = compute_point_57_override(_raw_vol, df, symbol, engine=_ENGINE)

# Phase 2A: Tail Risk (P61, P64, P66) — reuses _raw_vol
dna_vector["slot_42_evt_tail_vol"] = compute_point_61_override(_raw_vol, df, symbol, engine=_ENGINE)
_var_es = compute_point_64_override(_raw_vol, df, symbol, engine=_ENGINE)
dna_vector["slot_43_var"] = _var_es.get("var", 0.02)
dna_vector["slot_44_es"]  = _var_es.get("es", 0.03)
dna_vector["slot_45_huber_return"] = compute_point_66_override(0.0, df, symbol, engine=_ENGINE)

# Phase 2A: Supporting Risk (P71, P74)
dna_vector["slot_46_kalman_beta"]  = compute_point_71_override(1.0, df, symbol, engine=_ENGINE)
dna_vector["slot_47_cusum_break"] = compute_point_74_override(0.0, df, symbol, engine=_ENGINE)

# Phase 2B: Validation Metadata (P35, P82)
dna_vector["meta_purge_ratio"]      = round(1.0 - _purged / max(_raw_train, 1), 3)
dna_vector["meta_effective_train"]  = int(_purged)
dna_vector["meta_causal_validated"] = 1.0  # always safe by construction

# Phase 3: Adaptive S/R (P25, P26)
dna_vector["meta_sr_lambda"]    = round(_sr_lambda, 5)
dna_vector["meta_sr_proximity"] = round(_sr_proximity, 5)

# Phase 3: Portfolio/Risk (P97, P98, P96 placeholder, P99 placeholder)
dna_vector["meta_jensen_alpha"]      = round(compute_point_97_override(...), 6)
dna_vector["meta_autocorr_flag"]     = round(compute_point_98_override(...), 4)
dna_vector["meta_portfolio_weight"]  = 0.25   # placeholder (needs multi-asset returns)
dna_vector["meta_risk_parity_weight"] = 0.25  # placeholder (needs multi-asset returns)
```

**Total active slots/fields: ~48 per signature** (8 structural + 8 neural + 16 aux/meta + 2 microstructure + 8 volatility + 4 tail risk + 2 risk + 9 metadata).

**Reality Note**: The 32-key base `dna_vector` is fully constructed and validated in E2E. The Phase 1–3 extensions add ~16 additional keys via override wiring. All override values respect the BiasOverrideEngine, liquidity tiers, and master switch. Fallback defaults ensure the system degrades gracefully on any override failure.

---

## Quant Bias Override System

**Status:** 100/100 points implemented, validated, and registered in `BiasOverrideEngine`.

The override system replaces hardcoded manual biases with config-driven, liquidity-tier-aware quant replacements. All parameters live in `kronos/config/liquidity_tiers.yaml` under `overrides.point_XX`. Zero hardcoded numbers in Python override logic.

### Architecture

| Component | File | Purpose |
|-----------|------|---------|
| Registry | `bias_override_registry.yaml` | Single source of truth for all 100 points |
| Engine | `bias_override_engine.py` | Orchestration layer: decides *whether* and *which* override to apply |
| Liquidity Classifier | `liquidity_classifier.py` | Dynamic 5-tier per-symbol classification |
| Override Implementations | `overrides/point_XX.py` | Per-point pure computation + engine wrapper |
| Shared Utilities | `overrides/utils.py` | Reusable math functions across all points |
| Config | `liquidity_tiers.yaml` | All tunable parameters (no Python literals) |

### Integration Priority

**Phase 1 (Immediate):** Points 01, 02, 17, 21, 71, 72, 74, 93, 94, 100
**Phase 2 (Strong Value):** Points 46-60, 61, 64, 66, 35, 82, 25, 26
**Phase 3 (ML Hygiene):** Remaining points (clustering, feature selection, model evaluation, portfolio)

### Master Switch

```python
from kronos.quant_spec.execution_simulator import set_overrides_enabled
set_overrides_enabled(False)  # Instant revert to legacy behavior
```

### Execution Simulator

`kronos/quant_spec/execution_simulator.py` combines Points 93, 94, 95, 100 into a single execution pipeline replacing instant-fill-at-close backtesting.

**Reference**: [Integration Roadmap](KRONOS_V1_ALT_INTEGRATION_ROADMAP.md), [Mining Readiness Checklist](KRONOS_V1_ALT_MINING_READINESS_CHECKLIST.md)

---

---

## LAYER 6 — Extended DNA Vector (Phase 1–3 Overrides)

These slots are generated by the BiasOverrideEngine and wired into `dna_vector` during signature mining. They extend the original 32-slot vector with microstructure metrics, volatility estimates, tail risk, S/R metadata, and portfolio metadata.

### Phase 1 — Microstructure (slots 32–33)

| Slot | Name | Override Point | Purpose | Fallback |
|------|------|---------------|---------|----------|
| `slot_32_spread` | Corwin-Schultz Spread | P17 | Bid-ask spread estimate from high-low range | 0.001 |
| `slot_33_illiq_weight` | Amihud Illiquidity | P21 | Illiquidity weight for signal adjustment | 1.0 |

### Phase 2A — Volatility Toolkit (slots 34–41)

| Slot | Name | Override Point | Purpose | Fallback |
|------|------|---------------|---------|----------|
| `slot_34_yz_vol` | Yang-Zhang Volatility | P46 | Drift + overnight + RS combined volatility | 0.01 |
| `slot_35_rs_vol` | Rogers-Satchell Volatility | P47 | Drift-robust range-based volatility | 0.01 |
| `slot_36_mad_vol` | MAD Robust Volatility | P48 | Median Absolute Deviation (outlier-robust) | 0.01 |
| `slot_37_gk_vol` | Garman-Klass Volatility | P49 | Overnight gap + range-based volatility | 0.01 |
| `slot_38_park_vol` | Parkinson Volatility | P50 | High-low range-based volatility | 0.01 |
| `slot_39_garch_vol` | GARCH(1,1) Conditional Vol | P51 | Volatility clustering / memory | 0.01 |
| `slot_40_downside_vol` | Downside Semi-Volatility | P52 | Asymmetric risk (negative returns only) | 0.01 |
| `slot_41_ba_filtered_vol` | Bid-Ask Filtered RS Vol | P57 | Noise-filtered range-based volatility | 0.01 |

### Phase 2A — Tail Risk & Robust Statistics (slots 42–45)

| Slot | Name | Override Point | Purpose | Fallback |
|------|------|---------------|---------|----------|
| `slot_42_evt_tail_vol` | EVT/GPD Tail Volatility | P61 | Extreme Value Theory tail risk | 0.02 |
| `slot_43_var` | Value at Risk (95%) | P64 | Maximum expected loss at 95% confidence | 0.02 |
| `slot_44_es` | Expected Shortfall (95%) | P64 | Average loss beyond VaR (tail mean) | 0.03 |
| `slot_45_huber_return` | Huber Robust Return | P66 | Outlier-resistant return estimator | 0.0 |

### Phase 2A — Supporting Risk (slots 46–47)

| Slot | Name | Override Point | Purpose | Fallback |
|------|------|---------------|---------|----------|
| `slot_46_kalman_beta` | Kalman Dynamic Beta | P71 | Time-varying beta (raw=1.0 without market data) | 1.0 |
| `slot_47_cusum_break` | CUSUM Structural Break | P74 | Binary break indicator (0.0 or 1.0) | 0.0 |

### Phase 2B — Validation Metadata (meta_ fields)

| Field | Override Point | Purpose | Source |
|-------|---------------|---------|--------|
| `meta_purge_ratio` | P35 | Fraction of training data lost to purging + embargo | Miner (mine_reversal_signature) |
| `meta_effective_train` | P35 | Effective training samples after purging | Miner |
| `meta_causal_validated` | P82 | 1.0 if cross-sectional features are causally safe | Miner (always 1.0 by construction) |

### Phase 3 — Adaptive S/R Metadata

| Field | Override Point | Purpose | Source |
|-------|---------------|---------|--------|
| `meta_sr_lambda` | P25 | Entropy-adaptive S/R memory decay rate | Miner |
| `meta_sr_proximity` | P26 | Cauchy proximity kernel value for nearest S/R | Miner |

### Phase 3 — Portfolio & Risk Metadata

| Field | Override Point | Purpose | Source |
|-------|---------------|---------|--------|
| `meta_jensen_alpha` | P97 | Beta-neutral risk-adjusted alpha (0.0 without market returns) | Miner |
| `meta_autocorr_flag` | P98 | Autocorrelation stability flag (0–1, self-lag proxy for cointegration) | Miner |
| `meta_portfolio_weight` | P96 | Min-variance portfolio weight (placeholder=0.25 without multi-asset returns) | Miner |
| `meta_risk_parity_weight` | P99 | Risk parity weight (placeholder=0.25 without multi-asset returns) | Miner |

> **Note:** Points 96, 99 require cross-sectional returns for full computation. Placeholder values are used in the single-asset miner. Full computation is available via `EvaluationHarness` when multi-asset data is provided.

> **EvaluationHarness** (`kronos/quant_spec/evaluation.py`) provides additional validation metadata not stored in the signature: CPCV path generation (P79), deflated Sharpe ratio (P80), Monte Carlo DSR (P90), feature quality metrics (P76, P77, P84, P86), training loss metrics (P83, P88), and ensemble state metrics (P78, P81, P85, P87, P89). These are computed on-demand for model evaluation, not stored per-signature.

---

## Quick Reference Table — Full DNA Vector

| Slot / Field | Name | Range | Layer | Phase | Override |
|--------------|------|--------|-------|-------|----------|
| slot_00 | Bid-Ask Absorption | [-1, +1] | Structural | Legacy | — |
| slot_04 | Fractal Hurst Exhaustion | [-0.5, +0.5] | Structural | Legacy | — |
| slot_07 | Volume-Price Divergence | z-score | Structural | Legacy | — |
| slot_08 | HMM Regime | [0, 1] | Structural | Legacy | — |
| slot_09 | Volume Delta Pressure | [-1, +1] | Structural | Legacy | — |
| slot_10 | Wick Exhaustion | [0, 1] | Structural | Legacy | — |
| slot_11 | S/R KDE Proximity | [0, 1] | Structural | Legacy | — |
| slot_15 | Veto Composite | [0, 1] | Gate | Legacy | P01 (dynamic veto) |
| slot_16–23 | Neural Embeddings (×8) | real | Neural | Legacy | — |
| slot_24 | Vol Forecast Delta | real | Auxiliary | Legacy | — |
| slot_25 | MFE Projection | [0, ~2] | Auxiliary | Legacy | — |
| slot_26 | Neural Regime Intensity | [0, 1] | Auxiliary | Legacy | — |
| slot_27 | Structural-Neural Residual | [0, ∞) | Auxiliary | Legacy | — |
| slot_28 | Phylum Cluster | {-1,0,1,2} | Metadata | Legacy | — |
| slot_29 | Recovery Proxy | [0, 1] | Metadata | Legacy | — |
| slot_30 | Post-Hoc MFE | [0, 50] | Metadata | Legacy | — |
| slot_31 | Post-Hoc MAE | [0, 1] | Metadata | Legacy | — |
| slot_32_spread | Corwin-Schultz Spread | [0, 0.1] | Microstructure | Phase 1 | P17 |
| slot_33_illiq_weight | Amihud Illiquidity | [0, 10] | Microstructure | Phase 1 | P21 |
| slot_34_yz_vol | Yang-Zhang Vol | [0, 0.5] | Volatility | Phase 2A | P46 |
| slot_35_rs_vol | Rogers-Satchell Vol | [0, 0.5] | Volatility | Phase 2A | P47 |
| slot_36_mad_vol | MAD Robust Vol | [0, 0.5] | Volatility | Phase 2A | P48 |
| slot_37_gk_vol | Garman-Klass Vol | [0, 0.5] | Volatility | Phase 2A | P49 |
| slot_38_park_vol | Parkinson Vol | [0, 0.5] | Volatility | Phase 2A | P50 |
| slot_39_garch_vol | GARCH(1,1) Vol | [0, 0.5] | Volatility | Phase 2A | P51 |
| slot_40_downside_vol | Downside Semi-Vol | [0, 0.5] | Volatility | Phase 2A | P52 |
| slot_41_ba_filtered_vol | BA Filtered RS Vol | [0, 0.5] | Volatility | Phase 2A | P57 |
| slot_42_evt_tail_vol | EVT/GPD Tail Vol | [0, 0.5] | Tail Risk | Phase 2A | P61 |
| slot_43_var | Value at Risk | [0, 0.5] | Tail Risk | Phase 2A | P64 |
| slot_44_es | Expected Shortfall | [0, 0.5] | Tail Risk | Phase 2A | P64 |
| slot_45_huber_return | Huber Robust Return | [-1, 1] | Tail Risk | Phase 2A | P66 |
| slot_46_kalman_beta | Kalman Dynamic Beta | real | Risk | Phase 2A | P71 |
| slot_47_cusum_break | CUSUM Break | {0, 1} | Risk | Phase 2A | P74 |
| meta_purge_ratio | Purge Ratio | [0, 0.8] | Validation | Phase 2B | P35 |
| meta_effective_train | Effective Train Size | int | Validation | Phase 2B | P35 |
| meta_causal_validated | Causal Validated | {0, 1} | Validation | Phase 2B | P82 |
| meta_sr_lambda | SR Decay Rate | [0.01, 0.5] | S/R | Phase 3 | P25 |
| meta_sr_proximity | SR Proximity | [0, 1] | S/R | Phase 3 | P26 |
| meta_jensen_alpha | Jensen Alpha | real | Portfolio | Phase 3 | P97 |
| meta_autocorr_flag | Autocorr Flag | [0, 1] | Portfolio | Phase 3 | P98 |
| meta_portfolio_weight | Portfolio Weight | [0, 0.3] | Portfolio | Phase 3 | P96 |
| meta_risk_parity_weight | Risk Parity Weight | [0, 0.3] | Portfolio | Phase 3 | P99 |

**Total active slots/fields: ~48 per signature** (8 structural + 8 neural + 16 aux/meta + 2 microstructure + 8 volatility + 4 tail risk + 2 risk + 9 metadata)
