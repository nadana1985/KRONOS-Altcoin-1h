# KRONOS V1-ALT — Production Integration Roadmap

**Last updated:** June 9, 2026

## Current State
- All 100 bias override points implemented, validated, and registered in BiasOverrideEngine
- **Phase 1 complete:** Points 01, 02, 17, 21, 93, 94, 95, 100 wired into live mining pipeline
- **Phase 2A complete:** Points 46-52, 57 (volatility toolkit), 61, 64, 66 (tail risk), 71, 74 (supporting risk) wired into miner dna_vector
- Master switch (`OVERRIDES_ENABLED`) operational in bias_override_engine.py
- ExecutionSimulator combines Points 93, 94, 95, 100 into realistic execution pipeline
- A/B testing validates overrides ON vs OFF on synthetic and real data

---

## Phased Integration Plan

### Phase 1 — Immediate High Impact ✅ COMPLETE

| Point | What it replaced | Integration target | Status |
|-------|-----------------|-------------------|--------|
| 01 | `reversal_confidence_min: 0.72` static veto | Dynamic quantile veto in miner | ✅ Wired |
| 02 | Fixed `vpin_window`, `ofi_window` | Volatility-scaled windows | ✅ Wired |
| 17 | Static spread assumptions | Corwin-Schultz spread in dna_vector | ✅ Wired |
| 21 | Hard volume filter | Amihud illiquidity weight in dna_vector | ✅ Wired |
| 93 | Zero latency assumption | Latency slippage in ExecutionSimulator | ✅ Wired |
| 94 | Constant fee assumption | Dynamic execution costs in ExecutionSimulator | ✅ Wired |
| 95 | Instant fill assumption | TWAP execution in ExecutionSimulator | ✅ Wired |
| 100 | Fixed position sizing | Impact-aware sizing in ExecutionSimulator | ✅ Wired |

**Import chain fixes:** Unconditional `__file__`-derived path setup in `orchestrator_engine.py` and `structural_engine.py`. Lazy `.kronos` import in `kronos_module/model/__init__.py` prevents `kronos/` package shadowing.

### Phase 2A — Volatility & Tail Risk ✅ COMPLETE

| Point | What it replaced | Integration target | Status |
|-------|-----------------|-------------------|--------|
| 46 | Close-to-close vol | Yang-Zhang vol → slot_34 | ✅ Wired |
| 47 | Close-to-close vol | Rogers-Satchell vol → slot_35 | ✅ Wired |
| 48 | Close-to-close vol | MAD robust vol → slot_36 | ✅ Wired |
| 49 | Close-to-close vol | Garman-Klass vol → slot_37 | ✅ Wired |
| 50 | Close-to-close vol | Parkinson vol → slot_38 | ✅ Wired |
| 51 | Memoryless vol | GARCH(1,1) tracker → slot_39 | ✅ Wired |
| 52 | Symmetric vol | Downside semi-vol → slot_40 | ✅ Wired |
| 57 | Raw spread vol | Bid-ask filtered RS → slot_41 | ✅ Wired |
| 61 | No tail modeling | EVT/GPD tail vol → slot_42 | ✅ Wired |
| 64 | Symmetric tail risk | VaR + Expected Shortfall → slots 43,44 | ✅ Wired |
| 66 | Sample mean returns | Huber robust return → slot_45 | ✅ Wired |
| 71 | Static beta | Kalman dynamic beta → slot_46 | ✅ Wired (raw=1.0 without market data) |
| 74 | No break detection | CUSUM structural break → slot_47 | ✅ Wired |

**Key design:** All 14 Phase 2A points feed as auxiliary slots in `dna_vector`, available for downstream risk-aware decisions. Per-symbol logging reports vol/tail/risk slot counts, GARCH vol, ES, and BREAK_DETECTED flag.

### Phase 2B — Validation & Causality ✅ COMPLETE
| Point | Purpose | Integration target | Status |
|-------|---------|-------------------|--------|
| 35 | Combinatorial purging & embargoing | meta_purge_ratio + meta_effective_train in signature | ✅ Wired |
| 79 | CPCV path calculations | evaluation.py → EvaluationHarness.generate_cpcv_paths | ✅ Wired |
| 80 | Deflated Sharpe Ratio | evaluation.py → EvaluationHarness.compute_deflated_sharpe | ✅ Wired |
| 82 | Causally lagged cross-sectional info | meta_causal_validated in signature + evaluation.py | ✅ Wired |
| 90 | Monte Carlo DSR evaluations | evaluation.py → EvaluationHarness.run_monte_carlo_dsr | ✅ Wired |

**New file:** `kronos/quant_spec/evaluation.py` — EvaluationHarness class wiring Points 79, 80, 90 into a coherent model evaluation framework. Provides: CPCV path generation, purged train size estimation, deflated Sharpe, Monte Carlo DSR, full evaluate_model(), and validate_causal_lag(). All respect BiasOverrideEngine and master switch with graceful fallbacks.

### Phase 3 — Supporting / ML Hygiene, Portfolio & Adaptive S/R ✅ COMPLETE
| Point | Purpose | Integration target | Status |
|-------|---------|-------------------|--------|
| 25 | Entropy-adaptive memory half-life | `meta_sr_lambda` in dna_vector | ✅ Wired |
| 26 | Cauchy proximity kernels | `meta_sr_proximity` in dna_vector | ✅ Wired |
| 76 | MI distance feature weighting | evaluation.py → compute_feature_quality_metrics | ✅ Wired |
| 77 | PCA distance projections | evaluation.py → compute_feature_quality_metrics | ✅ Wired |
| 78 | Vol-symmetric barrier labels | evaluation.py → compute_ensemble_state_metrics | ✅ Wired |
| 81 | MST network pruning | evaluation.py → compute_ensemble_state_metrics | ✅ Wired |
| 83 | Info-weighted loss | evaluation.py → compute_training_loss_metrics | ✅ Wired |
| 84 | Mahalanobis distance | evaluation.py → compute_feature_quality_metrics | ✅ Wired |
| 85 | BMA ensemble weighting | evaluation.py → compute_ensemble_state_metrics | ✅ Wired |
| 86 | mRMR feature selection | evaluation.py → compute_feature_quality_metrics | ✅ Wired |
| 87 | LOESS local regression | evaluation.py → compute_ensemble_state_metrics | ✅ Wired |
| 88 | Linex asymmetric loss | evaluation.py → compute_training_loss_metrics | ✅ Wired |
| 89 | GMM soft state membership | evaluation.py → compute_ensemble_state_metrics | ✅ Wired |
| 96 | Min-variance portfolio weight | dna_vector placeholder (needs multi-asset) | ✅ Registered |
| 97 | Jensen's alpha | `meta_jensen_alpha` in dna_vector | ✅ Wired |
| 98 | Cointegration/autocorr flag | `meta_autocorr_flag` in dna_vector | ✅ Wired |
| 99 | Dynamic risk parity weight | dna_vector placeholder (needs multi-asset) | ✅ Registered |

**Key design:** Group A (25, 26) directly enhance slot_11 S/R logic. Group B (76-89) provide ML training hygiene via EvaluationHarness. Group C (96-99) provide portfolio/risk metadata — P96/P99 require multi-asset returns for full computation.

---

## Engine Wiring Strategy

### How BiasOverrideEngine is called from the pipeline:

```python
# In miner (reversal_signature_miner_sovereign.py):
from kronos.quant_spec.bias_override_engine import (
    BiasOverrideEngine, is_overrides_enabled
)

_ENGINE = BiasOverrideEngine()
_OVERRIDES_WIRED = True

# Phase 1: Dynamic veto
from kronos.quant_spec.overrides.point_01 import compute_point_01_override
effective_veto = compute_point_01_override(
    current_slot15=slot_15_raw, df=df, symbol=symbol,
    neural=neural, engine=_ENGINE
)

# Phase 2A: Volatility toolkit
from kronos.quant_spec.overrides.point_46 import compute_point_46_override
dna_vector["slot_34_yz_vol"] = compute_point_46_override(_raw_vol, df, symbol, engine=_ENGINE)
```

### Fallback Strategy (Always Revert to Raw)
The engine's `apply_override()` returns `raw_value` when:
1. Point status is not "implemented" → pass_through
2. Current liquidity tier not in applies_to_liquidity → pass_through
3. No override_value supplied → pass_through
4. Master switch is OFF → pass_through

### Master Switch
```python
from kronos.quant_spec.bias_override_engine import set_overrides_enabled
set_overrides_enabled(False)  # Instant legacy fallback
```

---

## dna_vector Slot Map

| Slots | Category | Points |
|-------|----------|--------|
| 00, 04, 07-11, 15 | Structural engine slots | Legacy + Phase 1 (02 window scaling) |
| 16-23 | Neural conviction features | Kronos predictor |
| 24-31 | Derived meta-features | Vol delta, MFE, neural conv |
| 32-33 | Microstructure (Phase 1) | P17 spread, P21 illiquidity |
| 34-41 | Volatility toolkit (Phase 2A) | P46-52, P57 |
| 42-45 | Tail risk (Phase 2A) | P61, P64, P66 |
| 46-47 | Supporting risk (Phase 2A) | P71, P74 |

---

## Risk Mitigation
- Each integration adds ONE override at a time
- All overrides wrapped in try/except with fallback defaults
- Master switch provides instant revert to legacy behavior
- A/B testing validates ON vs OFF before production deployment
