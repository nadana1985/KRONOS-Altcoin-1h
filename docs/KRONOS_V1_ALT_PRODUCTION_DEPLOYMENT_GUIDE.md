# KRONOS V1-ALT — Production Deployment Guide

**Version:** 1.0  
**Date:** June 9, 2026

---

## Quick Reference

| Action | Command |
|--------|---------|
| Enable overrides | `set_overrides_enabled(True)` |
| Disable overrides (instant fallback) | `set_overrides_enabled(False)` |
| Check override status | `is_overrides_enabled()` |
| Run mining | `python -m config.mining.reversal_signature_miner_sovereign` |
| Run A/B test | `python scripts/ab_test_overrides.py` |

---

## 1. Enabling/Disabling Overrides

### Master Switch (Global Toggle)

```python
from kronos.quant_spec.bias_override_engine import set_overrides_enabled, is_overrides_enabled

# Disable all overrides instantly → reverts to legacy static thresholds
set_overrides_enabled(False)

# Re-enable
set_overrides_enabled(True)

# Check current state
print(f"Overrides enabled: {is_overrides_enabled()}")
```

**When to disable:**
- Emergency rollback if unexpected behavior detected
- A/B comparison during development
- Debugging specific symbol issues

**Impact of disabling:**
- Phase 1: Reverts to static `confidence_min` veto, fixed windows
- Phase 2A: All 8 volatility estimators, tail risk, and supporting risk slots return defaults
- Phase 2B: Purge ratio and causal validation return defaults
- Phase 3: S/R and portfolio metadata return defaults
- ExecutionSimulator not called

### Per-Point Control

Each of the 42 wired points can be individually disabled via `liquidity_tiers.yaml`:

```yaml
overrides:
  point_01:
    status: "disabled"  # or "backtest_only" or "implemented"
```

---

## 2. Understanding Signature Metadata Fields

Each mined signature contains a `dna_vector` dict with the following metadata fields:

### Structural Slots (Legacy)
| Field | Description |
|-------|-------------|
| `slot_00` - `slot_15` | Core structural features from engine |

### Phase 1 Microstructure
| Field | Description |
|-------|-------------|
| `slot_32_spread` | Corwin-Schultz spread estimate |
| `slot_33_illiq_weight` | Amihud illiquidity weight |

### Phase 2A Volatility Toolkit
| Field | Description |
|-------|-------------|
| `slot_34_yz_vol` | Yang-Zhang volatility |
| `slot_35_rs_vol` | Rogers-Satchell volatility |
| `slot_36_mad_vol` | MAD robust volatility |
| `slot_37_gk_vol` | Garman-Klass volatility |
| `slot_38_park_vol` | Parkinson volatility |
| `slot_39_garch_vol` | GARCH(1,1) conditional volatility |
| `slot_40_downside_vol` | Downside semi-volatility |
| `slot_41_ba_filtered_vol` | Bid-ask filtered range-based volatility |

### Phase 2A Tail Risk
| Field | Description |
|-------|-------------|
| `slot_42_evt_tail_vol` | EVT/GPD tail volatility |
| `slot_43_var` | Value at Risk (95%) |
| `slot_44_es` | Expected Shortfall (95%) |
| `slot_45_huber_return` | Huber robust return estimate |

### Phase 2A Supporting Risk
| Field | Description |
|-------|-------------|
| `slot_46_kalman_beta` | Kalman dynamic beta (raw=1.0 without market data) |
| `slot_47_cusum_break` | CUSUM structural break indicator (0.0 or 1.0) |

### Phase 2B Validation Metadata
| Field | Description |
|-------|-------------|
| `meta_purge_ratio` | Fraction of training data lost to purging |
| `meta_effective_train` | Effective training samples after purging |
| `meta_causal_validated` | 1.0 if cross-sectional features are causally safe |

### Phase 3 S/R Metadata
| Field | Description |
|-------|-------------|
| `meta_sr_lambda` | Entropy-adaptive S/R decay rate |
| `meta_sr_proximity` | Cauchy proximity to nearest S/R level |

### Phase 3 Portfolio/Risk Metadata
| Field | Description |
|-------|-------------|
| `meta_jensen_alpha` | Jensen's risk-adjusted alpha (0.0 without market returns) |
| `meta_autocorr_flag` | Autocorrelation stability flag (0-1) |
| `meta_portfolio_weight` | Min-variance portfolio weight (placeholder=0.25) |
| `meta_risk_parity_weight` | Risk parity weight (placeholder=0.25) |

---

## 3. Interpreting Mining Logs

### Per-Symbol Output

```
✅ [MINER] BTCUSDT | bars=500 | slot_15=0.8500 | neural_conv=0.1200 | final_confidence=0.910 | phylum=phylum_1
  [OVERRIDES] BTCUSDT active exec_cost=55.2bps
  [PHASE2A] BTCUSDT vol=8 tail=4 risk=2 garch=0.0068 es=0.0180
  [PHASE3] BTCUSDT sr_lambda=0.0850 sr_prox=0.00123
  [PHASE3] BTCUSDT jensen_alpha=0.000000 autocorr=0.8500
```

**Key indicators:**
- `slot_15` < `confidence_min` → vetoed (no signature generated)
- `[OVERRIDES] active` → at least one override point fired
- `BREAK_DETECTED` → CUSUM detected structural break (slot_47 > 0.5)
- `exec_cost` → estimated execution cost in bps

### End-of-Run Summary

```
STATUS | OVERRIDE_SUMMARY | total_activations=42 | P1=4 P2A=14 P2B=2 P3=6
STATUS | OVERRIDE_DETAIL | P2A=14 P3=6 P1=4 P2B=2
STATUS | OVERRIDE_SYMBOLS | 4/10 symbols had override activations
STATUS | FINAL | processed=10/10 | hq=4 | veto_rate=60.0% | elapsed=0.5min | skips={}
```

---

## 4. Monitoring Best Practices

### Key Metrics to Watch

| Metric | Healthy Range | Alert If |
|--------|--------------|----------|
| Veto rate | 40-70% | <20% (too permissive) or >80% (too restrictive) |
| Avg confidence (active) | 0.5-0.9 | <0.3 (low quality signals) |
| GARCH vol | 0.005-0.05 | >0.1 (extreme volatility) |
| ES (Expected Shortfall) | 0.01-0.05 | >0.1 (tail risk event) |
| BREAK_DETECTED | 0-2 symbols | >3 (market regime change) |
| Execution cost | 30-80 bps | >150 bps (illiquid market) |

### Log Files

| File | Contents |
|------|----------|
| `logs/mining_status.log` | Full mining status log with overrides |
| `logs/mining_checkpoint.json` | JSON checkpoint for resume |

---

## Performance Optimization

The override runtime is warmed before the per-symbol mining loop:

| Optimization | Production Behavior |
|--------------|---------------------|
| YAML config cache | `liquidity_tiers.yaml` override config is loaded once via `override_config_cache` |
| Override pre-import | `point_XX` modules are imported before symbol iteration |
| Reused engine/harness | `BiasOverrideEngine` and `EvaluationHarness` are initialized once per process |
| Tier cache | Liquidity tier decisions are cached per dataframe/window |
| Point 01 vectorization | Slot-15 history is computed in one causal vectorized pass |

Latest 50-symbol real-shard benchmark: overrides ON averaged 362.2 ms/symbol versus 64.1 ms/symbol OFF, reducing overhead from ~40x to 5.65x and meeting the under-700 ms production target.

## 5. Rollback Procedure

### Instant Rollback (Recommended)

```python
from kronos.quant_spec.bias_override_engine import set_overrides_enabled
set_overrides_enabled(False)
```

**This immediately:**
- Reverts to static `confidence_min` veto
- Disables all volatility/tail risk slots
- Disables execution simulation
- Returns default metadata values

### Partial Rollback

Disable specific phases via YAML:

```yaml
# In liquidity_tiers.yaml, set status for specific points:
overrides:
  point_46:
    status: "backtest_only"  # disables Yang-Zhang vol
  point_51:
    status: "backtest_only"  # disables GARCH
```

### Full Legacy Revert

```python
set_overrides_enabled(False)
# Optionally, also reload the original params:
import importlib
import config.utils.sovereign_entrypoint as se
importlib.reload(se)
```

---

## 6. A/B Testing

### Synthetic Data Test

```bash
python scripts/ab_test_overrides.py
```

### Custom A/B Test

```python
from kronos.quant_spec.bias_override_engine import set_overrides_enabled
from config.mining.reversal_signature_miner_sovereign import mine_reversal_signature

# Test with overrides ON
set_overrides_enabled(True)
sig_on = mine_reversal_signature(df, symbol, neural, ctx=ctx)

# Test with overrides OFF
set_overrides_enabled(False)
sig_off = mine_reversal_signature(df, symbol, neural, ctx=ctx)

# Compare
print(f"ON:  confidence={sig_on['confidence']:.3f} dna_keys={len(sig_on['dna_vector'])}")
print(f"OFF: confidence={sig_off['confidence']:.3f} dna_keys={len(sig_off['dna_vector'])}")
```

---

## 7. Troubleshooting

| Issue | Likely Cause | Fix |
|-------|-------------|-----|
| All symbols vetoed | `confidence_min` too high | Lower `confidence_min` in params or adjust P01 quantile |
| No override activations | `_OVERRIDES_WIRED=False` | Check `kronos/` package import chain |
| GARCH returns 0.01 always | Insufficient data (< `min_data_density`) | Increase shard history length |
| Execution cost very high | Low liquidity (small `volume_usd`) | Increase `order_size_usd` or check symbol liquidity |
| Import errors | Path setup issue | Verify `KRONOS_PARAMS_PATH` env var is set |


