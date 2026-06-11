# KRONOS V1-ALT — Proxy Hardening Roadmap (Structural Slots 00-15)

**Phase:** Strategic plan to replace current simple proxies with best mathematical doctrines for stronger reversal signatures.

**Status:** Planning Document (as of 2026-06-08)  
**Reference:** 32-Slot Causal DNA Reality Audit, Full Kronos Neural Upgrade, Docs Realignment.

## Executive Summary

Current structural slots (00, 04, 07-11, 15) use pragmatic but simplified proxies.  
Goal: Upgrade to **mathematically rigorous, causal, vectorized formulations** while preserving:
- Zero inline literals
- All values from `params_yaml.txt` (thresholds + neural_slots)
- `slot_15` as absolute first veto gate
- Option B real shards, dual-mode, full causality, vectorization
- E2E safety + graceful degradation

Neural slots **16-23** already upgraded to distinct Kronos hidden states (when enabled).

## Prioritized Order (Impact × Feasibility × Compute Cost)

### Phase 1 — High Priority (Start Here)
1. **slot_09** → Full VPIN (highest microstructure edge)
2. **slot_04** → Proper multi-lag Hurst Exponent
3. **slot_15** → Sovereign Logistic Composite Gate

### Phase 2 — Medium Priority
4. **slot_00** → Order Flow Imbalance (OFI) + cumulative pressure
5. **slot_08** → Lightweight Regime Detection (GMM/ADX + volatility clustering)
6. **slot_07** → Amihud Illiquidity + Volume-Weighted Divergence

### Phase 3 — Lower Priority
7. **slot_10** → Multi-scale Candle Exhaustion Score
8. **slot_11** → Dynamic S/R Proximity with Decay

## Detailed Mathematical Doctrines & Formulas

All formulas will be **cfg-driven**. New params will go under `thresholds:` or new `structural:` section.

### slot_09 — VPIN (Volume Synchronized Probability of Informed Trading)
**Best Doctrine:** Bulk Volume Classification + Cumulative Imbalance

**Formula (Vectorized):**
```python
# params: vpin_window, vpin_buckets, eps
buy_vol = df['taker_buy_base_volume']
sell_vol = df['quote_volume'] - buy_vol   # or volume - taker_buy

delta = buy_vol - sell_vol
cum_delta = delta.rolling(vpin_window).sum()
total_vol = df['volume'].rolling(vpin_window).sum()

vpin = (cum_delta.abs() / (total_vol + eps)).clip(0, 1)
slot_09 = vpin.iloc[-1]
Params to add:

vpin_window: 100
vpin_buckets: 50 (for more advanced versions)


slot_04 — Hurst Exponent (Persistence Detection)
Best Doctrine: Rescaled Range Analysis over multiple lags + Detrended Moving Average (DMA)
Formula (Vectorized):
Python# params: hurst_lags, hurst_min_periods
def compute_hurst(series, lags):
    H = []
    for lag in lags:
        R_S = (series.rolling(lag).max() - series.rolling(lag).min()) / (series.rolling(lag).std() + eps)
        H.append(np.log(R_S.iloc[-1]) / np.log(lag) if lag > 1 else 0.5)
    return np.mean(H)  # or weighted

log_ret = np.log(df['close'] / df['close'].shift(1) + eps)
hurst = compute_hurst(log_ret, [5, 10, 20, 50])   # configurable lags
slot_04 = 0.5 - hurst   # mean-reversion bias (higher = stronger reversal potential)

slot_15 — Sovereign Composite Gate
Best Doctrine: Weighted logistic + entropy/confidence term
Formula:
Python# params: slot_weights dict, conf_min, entropy_weight
norm_slots = {k: clamp(slots[k]) for k in structural_keys}
weighted = sum(weights[k] * norm_slots[k] for k in weights)
entropy = -sum(p * np.log(p+eps) for p in norm_slots.values())   # diversity bonus
slot_15 = sigmoid(weighted + entropy_weight * entropy)
slot_15 = slot_15 * (conf_min / conf_min)  # cfg scaling
slot_15 = clamp(slot_15)

slot_00 — Order Flow Imbalance (OFI)
Formula:
Pythonofi = (taker_buy - (volume - taker_buy)).rolling(w).mean() / (volume.rolling(w).mean() + eps)
slot_00 = ofi.iloc[-1] * reversal_factor_gate
slot_08 — Regime Detection
Formula (Light):
Pythonadx = ta.ADX(...)  # or simple volatility clustering
regime_score = (recent_vol / long_vol) * (adx / 50)
slot_08 = clamp(regime_score)
(Full GMM possible in Phase 2 if cheap.)
Remaining Slots (slot_07, 10, 11)
Similar vectorized/causal upgrades with rolling statistics, percentiles, and decay functions.
Implementation Guidelines

Every new formula must read all constants from params_yaml.txt.
Keep compute_slots_sovereign(df, neural) signature unchanged.
Add structural: section in params for windows, lags, weights.
After each slot upgrade → create summary MD + E2E validation.
Final validation: correlation matrix + forward outcome stats.