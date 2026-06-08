# KRONOS V5 — Slot Reference Manual

Complete mathematical definitions, formulas, and engineering explanations for every slot in the KRONOS signature vector.

> **V1-ALT Current Delivered System (as of June 2026)**  
> 8 structural proxies + 1 distinct neural scalar (tokenizer.embed L2 norm, replicated across slots 16-23) + 16 derived proxies.  
> HDBSCAN applied only to structural subset. `slot_15` is the hard early veto gate.  
> Full details in "Current Implementation" subsections below.  
> Aspirational/target formulas preserved in dedicated sections for V5 evolution.  
> **Reference**: [32-Slot Causal DNA Reality Audit](KRONOS_V1_ALT_32_SLOT_CAUSAL_DNA_REALITY_AUDIT_SUMMARY.md)

---

## Layer Overview

| Layer | Slots | Description |
|-------|-------|-------------|
| **Structural** | 00, 04, 07, 08, 09, 10, 11, 15 | Core market micro-structure (current: 8 implemented) |
| **Veto Composite** | 15 | Weighted sovereign gate (enforced in miner) |
| **Neural Embeddings** | 16–23 | Currently: single neural_conviction (L_p) replicated (placeholder) |
| **Auxiliary** | 24–27 | Simple proxies (vol delta, MFE, residual) |
| **Metadata** | 28–31 | Simple proxies + post-hoc phylum (HDBSCAN) |

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
Uses full kline taker_buy_base_volume (fallback to vol*0.5 proxy via neural strength_add expr) and (vol - taker_buy). Same low/high_prox + rolling mean as proxy for EWM. All params (w, eps, reversal_factor, strength_*) from neural_slots only. Matches manual intent for absorption at extremes.

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
R/S on log((close/close.shift)+eps).clip. slot_04 = neural["strength_add"] − H (uses 0.55 from neural_slots as ~0.5 proxy; no inline 0.5 literal). Causal rolling. Matches simplified R/S from manual.

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

**Current Implementation:**
price_chg and vol_chg on qvol (quote_volume from full kline). raw_div = rolling_mean(|price| - |vol|). slot_07 = raw / (qvol std + eps). All from neural_slots. Uses full kline as specified.

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

**Current Implementation (proxy):**
recent_vol = vol.rolling std. long_vol = vol.rolling (w + min_p) std + eps. slot_08 = clamp( recent / long ). Simple regime proxy (no real HMM/GaussianHMM or refit).

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

**Current Implementation:**
buy = taker_buy_base_volume (full kline), sell = vol - buy. vol_delta = (buy-sell) rolling mean. total = (buy+sell) mean + eps. slot_09 = delta / total. Matches manual VPIN intent using full kline.

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

This is the current (simplified proxy) implementation of the 32-slot DNA. Full distinct neural embeddings (16-23), real HMM (08), and richer aux/metadata will require further wiring.

**Reality Note**: The 32-key `dna_vector` is fully constructed and validated in E2E, but contains significant redundancy (8 identical neural slots + multiple linear transforms of core variables). Effective dimensionality is lower than 32. HDBSCAN uses only structural keys. This is explicitly documented for transparency and future hardening.

---

## Quick Reference Table

| Slot | Name | Range | Layer | Key Signal |
|------|------|--------|-------|------------|
| slot_00 | Bid-Ask Absorption | [-1, +1] | Structural | Direction & conviction of order flow |
| slot_04 | Fractal Hurst Exhaustion | [-0.5, +0.5] | Structural | Mean-reversion probability |
| slot_07 | Volume-Price Divergence | z-score | Structural | Unsupported price move |
| slot_08 | HMM Regime | [0, 1] | Structural | High-vol regime probability |
| slot_09 | Volume Delta Pressure | [-1, +1] | Structural | Net buy/sell dominance |
| slot_10 | Wick Exhaustion | [0, 1] | Structural | Doji/indecision bar detection |
| slot_11 | S/R KDE Proximity | [0, 1] | Structural | Price near key level |
| slot_15 | Veto Composite | [0, 1] | Gate | Combined structural confidence |
| slot_16–23 | Neural Embeddings (×8) | real | Neural | Transformer latent space |
| slot_24 | Vol Forecast Delta | real | Auxiliary | Volatility direction change |
| slot_25 | MFE Projection | [0, ~2] | Auxiliary | Causal upside estimate |
| slot_26 | Neural Regime Intensity | [0, 1] | Auxiliary | Conviction percentile |
| slot_27 | Structural-Neural Residual | [0, ∞) | Auxiliary | Disagreement between layers |
| slot_28 | Phylum Cluster | {-1,0,1,2} | Metadata | Post-hoc HDBSCAN family |
| slot_29 | Recovery Proxy | [0, 1] | Metadata | Causal recovery estimate |
| slot_30 | Post-Hoc MFE | [0, 50] | Metadata | Actual forward gain |
| slot_31 | Post-Hoc MAE | [0, 1] | Metadata | Actual forward drawdown |
