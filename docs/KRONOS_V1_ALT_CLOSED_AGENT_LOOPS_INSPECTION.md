# KRONOS V1-ALT — Closed Agent Loops Deep Inspection Report

> **Date**: 2026-06-08  
> **Scope**: Comprehensive codebase scan for closed-loop opportunities across ingestion, mining, inference, backtesting, orchestration, sovereignty enforcement, and multi-agent integration.  
> **Principles Applied**: Zero-Hardcode Doctrine, Mathematical Sovereignty (Krinos Math), full auditability, low-drift, edge-capable design (AMD RX 560 + Lightning AI).

---

## 1. Codebase Overview

The KRONOS V1-ALT codebase is organized into four functional domains. This section provides a structural map of every relevant file.

### 1.1 Domain Map

| Domain | Path | Key Files | Lines | Role |
|--------|------|-----------|-------|------|
| **Ingestion** | `config/ingestion/` | `unified_ingestion_engine.py`, `real_api_bridge_sovereign.py` | 870 +  | Multi-symbol data fetch, validation, health scoring, checkpoint/recovery, delisting detection, HTML dashboard |
| **Mining & Features** | `config/mining/`, `kronos_module/model/` | `reversal_signature_miner_sovereign.py`, `structural_engine.py`, `kronos.py`, `module.py` | 407 + 259 + 857 + 570 | Per-symbol 32-slot DNA computation, neural conviction (PyTorch), HDBSCAN phylum clustering, inference |
| **Orchestration** | `kronos_module/`, `config/utils/` | `orchestrator_engine.py`, `kronos_pipeline_sovereign.py`, `global_prior_sovereign.py`, `ablation_test_sovereign.py` | 107 + 34 + 45 + 32 | Dual-mode wiring (individual/global), structural veto, regime detection, pipeline sequencing |
| **Validation** | `config/validation/` | `validate_sovereignty.py`, `load_sovereign_config.py` | 52 + 132 | Inline literal scanning, config loading with YAML anchor resolution, path resolution |
| **Test** | Root | `test_end_to_end.py` | 159 | E2E harness with real shards, real miner, neural conviction assertions, ablation toggle |
| **Config** | Root | `params_yaml.txt` | — | Single source of truth for all parameters, storage paths, thresholds (Zero-Hardcode) |

### 1.2 Data Flow (Current — Open Loop)

```
params_yaml.txt
      │
      ▼
  load_sovereign_config()
      │
      ▼
 fetch_all_symbols_data()    ───→ logs/ingestion_summary.html
      │
      ▼
 mine_all_shards()           ───→ signatures/*.parquet
      │                               │
      ▼                               ▼
 build_global_prior()         ───→ global_prior.parquet
      │
      ▼
 E2E / Orchestration         ───→ console output only
```

**Critical Observation**: There is **zero feedback** between stages. No stage knows whether the next stage succeeded. No quality metrics flow backward to earlier stages. No adaptive parameter adjustment occurs based on results. This is a pure open-loop pipeline.

### 1.3 Key Pain Points Identified (Cross-Referenced)

| Pain Point | Source | Evidence |
|------------|--------|----------|
| Mining stagnation | `structural_engine.py` L237, `reversal_signature_miner_sovereign.py` L399 | Slot weights are static; HDBSCAN errors silently swallowed |
| Sovereignty regression | `validate_sovereignty.py` L10-30 | 1225+ historical violations; validator is stateless, not in pipeline |
| Inference degradation | `kronos.py` L586, L595-659 | Model loading silently falls back; no benchmark instrumentation |
| Signal quality unknown | `reversal_signature_miner_sovereign.py` L355-363 | Only confidence threshold exists; no cross-symbol distribution analysis |
| No backtesting | Entire codebase | No OOS validation, no Sharpe, no walk-forward, no overfitting detection |
| No inter-stage feedback | `kronos_pipeline_sovereign.py` L15-34 | Strictly sequential; `orchestrator_engine.py` has no event model |

---

## 2. High-Priority Loop Opportunities

### 2.1 Loop #1: Backtest Integrity + Walk-Forward + Overfitting Detection

**High Priority — Impact: Highest, Effort: High, Risk: Medium**

#### Files
- **Primary**: `config/mining/reversal_signature_miner_sovereign.py` (L255-404)
- **Data source**: `kronos_module/model/structural_engine.py` (L114-259)
- **New module**: `kronos_module/backtest/`

#### Current State (Open Loop)
The mining pipeline generates reversal signatures with confidence scores but has no mechanism to:
- Evaluate whether those signatures would have been profitable out-of-sample
- Detect overfitting in slot weight parameters (`raw_w` at `structural_engine.py:237`)
- Perform walk-forward validation across different market regimes
- Compute any trading metric (Sharpe, win rate, max drawdown)
- Compare individual vs global prior signal quality on historical data

The E2E test (`test_end_to_end.py:L124-131`) only checks that `confidence >= min_conf` — it verifies the sign of the confidence, not its predictive power.

#### Proposed Closed Loop Structure

```
┌─────────────────────────────────────────────────────┐
│  BACKTEST LOOP (post-mining, pre-publication)       │
├─────────────────────────────────────────────────────┤
│                                                      │
│  OBSERVE:                                            │
│   for each mined signature {symbol, timestamp,       │
│     reversal_type, confidence, slot_15,              │
│     dna_vector}:                                     │
│     load corresponding shard {open,high,low,close,   │
│       volume}                                        │
│     hold out last N bars as OOS test set             │
│     use N-1 bars for slot computation                │
│     bar N+1 = prediction target                      │
│                                                      │
│  ACT:                                                │
│   compute directional_accuracy =                     │
│     mean(sign(predicted_return) == sign(actual_ret))  │
│   compute Sharpe (annualized) =                      │
│     mean(return) / std(return) * sqrt(24*365)        │
│   compute profit_factor =                            │
│     gross_profit / gross_loss                        │
│   compute max_drawdown = peak_to_trough              │
│   compute signal_decay = accuracy vs hold_time       │
│                                                      │
│  EVALUATE:                                           │
│   if directional_accuracy < 0.52:                    │
│     → SEVERE: signals no better than random          │
│   if Sharpe < 0.5:                                   │
│     → WARNING: risk-adjusted return inadequate       │
│   compute overfitting_score =                        │
│     (IS_sharpe - OOS_sharpe) / IS_sharpe             │
│   if overfitting_score > 0.3:                        │
│     → OVERFIT: reject current weight set             │
│                                                      │
│  VERIFY:                                             │
│   if any SEVERE flag:                                │
│     → block signature publication                    │
│     → emit structured alert with diagnostics         │
│   if OVERFIT flag:                                   │
│     → suggest slot weight rebalancing                │
│     → do not block, but flag for human review        │
│                                                      │
│  ADAPT:                                              │
│   store backtest results in checkpoint               │
│   update slot weights if improvement confirmed       │
│   across 3+ consecutive mining runs                  │
│                                                      │
└─────────────────────────────────────────────────────┘
```

#### Walk-Forward Validation Scheme

```
┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐
│ Regime  │  │ Regime  │  │ Regime  │  │ Regime  │
│ Block 1 │→│ Block 2 │→│ Block 3 │→│ Block 4 │
│ (Train) │  │ (Test)  │  │ (Train) │  │ (Test)  │
└─────────┘  └─────────┘  └─────────┘  └─────────┘
     │            │            │            │
     ▼            ▼            ▼            ▼
   Sharpe₁      Sharpe₂      Sharpe₃      Sharpe₄
     │            │            │            │
     └────────────┴─────┬─────┴────────────┘
                        ▼
              stability = std(Sharpe) / mean(Sharpe)
              if stability > 2.0 → overfitted to regime
```

- Regime blocks identified using slot_08 (ADX-inspired trend strength) transitions
- Each block must have minimum `min_history` bars (from params)
- Final metric: walk-forward Sharpe, stability score

#### Implementation Plan

| Step | File | Description |
|------|------|-------------|
| 1 | `kronos_module/backtest/__init__.py` | Module init, exports |
| 2 | `kronos_module/backtest/evaluator.py` | Core backtest: load shard, compute directional accuracy, Sharpe, profit factor, max DD |
| 3 | `kronos_module/backtest/metrics.py` | Pure functions: `directional_accuracy()`, `sharpe_ratio()`, `max_drawdown()`, `profit_factor()`, `confidence_calibration()` |
| 4 | `kronos_module/backtest/overfitting.py` | Walk-forward splitter, overfitting score, stability computation, regime block detection |
| 5 | `kronos_module/backtest/checkpoint.py` | Backtest result persistence (JSONL format), delta tracking across runs |
| 6 | `config/mining/reversal_signature_miner_sovereign.py` | Integrate call to `backtest.evaluator.evaluate()` after HDBSCAN phylum (replacing the bare `try/except pass` block) |
| 7 | `params_yaml.txt` | Add `thresholds.backtest_min_sharpe`, `backtest_min_accuracy`, `backtest_max_overfitting`, `backtest_enabled` |
| 8 | `kronos_module/orchestrator_engine.py` | Wire backtest gate into `extract_live_reversal_signals` |

#### Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Lookahead bias | All splits timestamp-based, never index-based. Verify no `shift(-1)` or future `iloc` in backtest path. Slot_15 entropy term must not leak future. |
| Computation cost (500+ symbols) | Sample first N symbols per batch for backtest; full run configurable via `backtest_sample_size`. Parallelize per symbol. |
| False positives (good strategies rejected) | Relax thresholds during bootstrap phase. Use progressive gates (WARNING vs BLOCK levels). |

---

### 2.2 Loop #2: Inference Performance Hardening & Benchmark

**Priority: 2 — Impact: High, Effort: Medium, Risk: Low-Medium**

#### Files
- **Primary**: `kronos_module/model/kronos.py` (L519-710)
- **Dependency**: `kronos_module/model/module.py` (BSQuantizer, TransformerBlock)

#### Current State (Open Loop)

```
KronosPredictor.__init__():
    device = heuristic(CUDA > MPS > CPU)        ← no benchmark validation
    model = try: load_model() except: pass       ← silent fallback (L586)
    
compute_neural_conviction():
    if model_loaded and tokenizer:
        try: inference() except: return 0.0     ← silent fallback (L659)
    else:
        return scalar_norm(embedding only)      ← no visibility of fallback
    
generate():
    use_amp = try: autocast() except: standard  ← no correctness check (L632-640)
```

**Critical Issues**:
1. Silent fallback paths make it impossible to distinguish "model working" from "model degraded"
2. No warmup step before first inference (critical for `torch.compile`)
3. No latency/throughput instrumentation
4. Mixed precision enabled without numerical correctness verification against FP32 baseline
5. Device heuristic ignores edge-case realities (AMD RX 560 has different perf characteristics than NVIDIA)

#### Proposed Closed Loop Structure

```
┌─────────────────────────────────────────────────────┐
│  INFERENCE BENCHMARK LOOP (init + periodic)         │
├─────────────────────────────────────────────────────┤
│                                                      │
│  OBSERVE:                                            │
│   at KronosPredictor init:                           │
│     create synthetic benchmark tensor                │
│     (batch=1, seq_len=max_context, feat=7)           │
│     if GPU available:                                │
│       benchmark CPU: 10 forward passes, time         │
│       benchmark GPU: 10 forward passes, time         │
│     if torch.compile available:                      │
│       benchmark compiled: 10 passes, time            │
│     track: latency_mean, latency_std,                │
│       throughput_bars_per_sec,                       │
│       peak_memory_MB, device_temp                    │
│                                                      │
│  ACT:                                                │
│   select optimal configuration:                      │
│     device = argmin(latency) among {CPU, GPU}        │
│     if GPU latency_improvement < 1.2x:               │
│       prefer CPU (avoid PCIe transfer overhead)      │
│     if compile latency_improvement > 1.1x:           │
│       enable torch.compile with warmup               │
│     enable mixed_precision only if:                  │
│       max(abs(FP16_pred - FP32_pred)) < amp_max_diff │
│                                                      │
│  EVALUATE:                                           │
│   after every N=100 inference calls:                 │
│     re-benchmark (silent, 2 passes only)             │
│     if latency increased > 20% since last full       │
│       benchmark: flag as DRIFT                       │
│     if throughput dropped > 30%:                     │
│       flag as DEGRADED                               │
│                                                      │
│  VERIFY:                                             │
│   if state == DRIFT:                                 │
│     re-run full benchmark, select new config         │
│   if state == DEGRADED:                              │
│     fall back to scalar neural_conv mode             │
│     emit runtime alert with timing diagnostics       │
│   if model load failed (silent fallback active):     │
│     → log detailed failure reason (OOM, CUDA err,   │
│       file not found, version mismatch)              │
│     → attempt model reload with CPU-only fallback    │
│                                                      │
│  ADAPT:                                              │
│   store benchmark results in ctx["benchmark"]        │
│   persist best configuration to checkpoint           │
│   for cold-start optimization on next run            │
│                                                      │
└─────────────────────────────────────────────────────┘
```

#### Benchmark Integration Points

| Point | Timing | Measure |
|-------|--------|---------|
| `KronosPredictor.__init__()` | Once at construction | Full benchmark, device selection |
| `compute_neural_conviction()` | Silent every 100 calls | Quick latency check |
| `generate()` | Silent every 50 calls | Throughput check |
| Pipeline completion | Once per run | Summary stats to logs/ |
| Dashboard update | On request | Real-time latency gauge |

#### Implementation Plan

| Step | File | Description |
|------|------|-------------|
| 1 | `kronos_module/model/benchmark.py` | `InferenceBenchmark` class with warmup, timing (time.perf_counter), memory tracking (torch.cuda.max_memory_allocated), device iteration |
| 2 | `kronos_module/model/kronos.py` | Modify `KronosPredictor.__init__` to run benchmark after model load; store results in `self.benchmark_results` |
| 3 | `kronos_module/model/kronos.py` | Add `_verify_amp_correctness(FP32_pred, FP16_pred)` static method |
| 4 | `kronos_module/model/kronos.py` | Add periodic benchmark check in `compute_neural_conviction` and `generate` (configurable interval from params) |
| 5 | `params_yaml.txt` | Add `neural.benchmark_enabled`, `neural.benchmark_interval`, `neural.amp_max_diff`, `neural.max_inference_latency_ms` |
| 6 | `config/utils/sovereign_entrypoint.py` | Propagate `ctx["benchmark"]` to dashboard/events |

---

### 2.3 Loop #3: Signal/Regime Quality Validation

**Priority: 3 — Impact: High, Effort: Medium, Risk: Low**

#### Files
- **Primary**: `config/mining/reversal_signature_miner_sovereign.py` (L255-404)
- **Dependency**: `kronos_module/model/structural_engine.py` (slot_08 regime)
- **Dependency**: `config/utils/global_prior_sovereign.py` (global prior for comparison)

#### Current State (Open Loop)
After mining, the only quality filter is a scalar confidence threshold (`sig["confidence"] >= min_conf` at L355). There is no:
- **Cross-symbol distribution analysis**: Are signals degenerate (all same confidence)? Are they diverse?
- **Temporal consistency**: Does consecutive bar mining produce contradictory signals?
- **Regime-aware calibration**: Slot_08 regime score should modulate acceptance threshold
- **Signal-to-noise ratio**: How much does neural_conv add vs raw structural slots?
- **Phylum stability**: Are HDBSCAN clusters meaningful (silhouette score)?

The `MiningStatusTracker` logs per-symbol stats but never aggregates them into a meta-quality metric.

#### Proposed Closed Loop Structure

```
┌─────────────────────────────────────────────────────┐
│  SIGNAL QUALITY VALIDATION LOOP (post-mining)       │
├─────────────────────────────────────────────────────┤
│                                                      │
│  OBSERVE:                                            │
│   collect from all mined symbols:                    │
│     {confidence, slot_15, neural_conv,               │
│      structural_slots, phylum, reversal_type}        │
│   per symbol, also collect:                          │
│     regime_label (from slot_08 regime detection)     │
│     history_length (bars available)                  │
│                                                      │
│  ACT:                                                │
│   compute meta-quality metrics:                      │
│     signal_diversity =                               │
│       nunique(confidence) / total_symbols            │
│       → should be HIGH (>0.3 indicates diversity)    │
│     confidence_entropy =                             │
│       -sum(p_i * log(p_i)) for confidence buckets    │
│       → should be >0 (avoid degenerate single-val)   │
│     neural_delta =                                   │
│       mean(abs(neural_conv - slot_15))               │
│       → should be > cfg["thresholds"]["min_nc_delta"]│
│     phylum_silhouette =                              │
│       silhouette_score(X, labels)                    │
│       → should be > 0.3 for meaningful clusters      │
│     regime_calibration =                             │
│       accuracy per regime bucket                     │
│       → should be consistent across regimes          │
│                                                      │
│  EVALUATE:                                           │
│   composite_quality = weighted_sum(metrics)          │
│   if composite_quality < cfg["thresholds"]["         │
│       min_signal_quality"]:                          │
│     → reduce min_conf gradually, re-evaluate         │
│     → if still below threshold after 3 iterations:   │
│         HALT mining, emit structured alert           │
│   if signal_diversity < 0.05:                        │
│     → DEGENERATE: all signals same confidence        │
│     → check slot_15 gate, check min_history          │
│   if phylum_silhouette < 0.1:                        │
│     → random/overlapping clusters                    │
│     → reduce HDBSCAN min_cluster_size, retry         │
│                                                      │
│  VERIFY:                                             │
│   if DEGENERATE or RANDOM_CLUSTERS:                  │
│     → do NOT publish signatures as final             │
│     → emit diagnostics for human review              │
│   else:                                              │
│     → PROCEED with publication                       │
│                                                      │
│  ADAPT:                                              │
│   store meta-quality in checkpoint for drift         │
│   tracking across mining runs                        │
│   if consecutive runs show degenerating quality:     │
│     → flag for parameter review                      │
│                                                      │
└─────────────────────────────────────────────────────┘
```

#### Calibration Bucket Scheme

```
Confidence buckets:  [0.0-0.1), [0.1-0.2), ..., [0.9-1.0]
For each bucket:
    compute: accuracy = correct_directions / total_in_bucket
    compute: calibration_error = |accuracy - bucket_midpoint|
    
Well-calibrated: calibration_error < 0.05 for all buckets
Overconfident:  accuracy < bucket_midpoint (model too confident)
Underconfident: accuracy > bucket_midpoint (model too cautious)
```

#### Implementation Plan

| Step | File | Description |
|------|------|-------------|
| 1 | `kronos_module/validation/signal_quality.py` | `SignalQualityValidator` class with all meta-metric computations |
| 2 | `config/mining/reversal_signature_miner_sovereign.py` | Integrate into `mine_all_shards` after the per-symbol loop (replace bare try/except) |
| 3 | `params_yaml.txt` | Add `thresholds.min_signal_quality`, `min_nc_delta`, `min_phylum_silhouette`, `enable_signal_quality_gate` |
| 4 | `kronos_module/orchestrator_engine.py` | Wire quality gate into `extract_live_reversal_signals` |

---

### 2.4 Loop #4: Ingestion Quality Gate → Adaptive Re-Fetch

**Priority: 4 — Impact: High, Effort: Low-Medium, Risk: Low**

#### Files
- **Primary**: `config/ingestion/unified_ingestion_engine.py` (L62-149, L231-312, L470-543)
- **Dependency**: `config/validation/load_sovereign_config.py` (storage path resolution)

#### Current State (Open Loop)
Ingestion runs unconditionally. `validate_and_fix_data` (L62) computes health scores and auto-fixes NaN/outliers but does **not** gate usability. Key issues:
- Low-health shards (health < 70) silently propagate to the miner
- The checkpoint system (`load_checkpoint`/`save_checkpoint` at L187-200) tracks timestamps but not quality
- No degraded ratio computation across the symbol universe
- No adaptive action based on systemic quality degradation (e.g., exchange issues, rate-limit changes)

#### Proposed Closed Loop Structure

```
┌─────────────────────────────────────────────────────┐
│  INGESTION QUALITY GATE LOOP (during fetch)         │
├─────────────────────────────────────────────────────┤
│                                                      │
│  OBSERVE:                                            │
│   per-symbol shard:                                  │
│     after fetch + validate_and_fix_data:             │
│       health_score = {0, ..., 100}                   │
│       degraded_flags = {gap_flag, nan_flag,          │
│         outlier_flag, incomplete_flag}               │
│                                                      │
│  ACT:                                                │
│   if health_score < cfg["thresholds"]["              │
│       min_shard_health"] (default=70):               │
│     → log shard as DEGRADED with full diagnostics   │
│     → attempt selective re-fetch:                    │
│         only fetch missing timestamp ranges          │
│         (use existing checkpoint as baseline)        │
│         apply exponential backoff (2^attempt secs)   │
│     → if re-fetch fails or health still < threshold: │
│         mark symbol as LOW_QUALITY for downstream    │
│         (miner can still process but with flag)      │
│   else:                                              │
│     → mark symbol as PASS                           │
│                                                      │
│  EVALUATE:                                           │
│   after all symbols fetched:                         │
│     degraded_ratio = degraded_symbols / total        │
│     avg_health = mean(health_score of all shards)    │
│     health_delta = avg_health - previous_avg_health  │
│     (from last run's checkpoint)                     │
│                                                      │
│  VERIFY:                                             │
│   if degraded_ratio > cfg["thresholds"]["            │
│       max_degraded_ratio"] (e.g., 0.05):             │
│     → HALT pipeline:                                │
│         print structured ERROR_RECOVERY_DASHBOARD    │
│         suggest exchange status check                │
│         suggest rate limit / worker adjustment       │
│   if health_delta < -10:                             │
│     → WARNING: systemic quality degradation         │
│     → continue but flag for human review             │
│   else:                                              │
│     → PROCEED to mining                             │
│                                                      │
│  ADAPT:                                              │
│   update checkpoint with per-symbol quality metadata:│
│     {symbol, health_score, degraded_flags,           │
│      timestamp_range, fetch_attempts}               │
│   adjust rate_limit_delay or max_workers if          │
│     degraded_ratio correlates with fetch timing      │
│                                                      │
└─────────────────────────────────────────────────────┘
```

#### Integration Points

| Pipeline Point | Action |
|---------------|--------|
| After `fetch_full_history` per symbol | Store health score alongside shard |
| After `ThreadPoolExecutor` completes | Compute aggregate quality stats |
| Before `generate_metrics_summary` | Gate on degraded_ratio |
| Before miner invocation | Pass `LOW_QUALITY` symbol list so miner can log separately |

#### Implementation Plan

| Step | File | Description |
|------|------|-------------|
| 1 | `config/ingestion/unified_ingestion_engine.py` | Modify `validate_and_fix_data` to return tuple `(report, is_usable)` and persist health_score to checkpoint |
| 2 | `config/ingestion/unified_ingestion_engine.py` | Add `QualityGate` class that collects per-symbol health, computes aggregate stats, gates continuation |
| 3 | `config/ingestion/unified_ingestion_engine.py` | Wire QualityGate into `fetch_all_symbols_data` before `generate_metrics_summary` |
| 4 | `config/mining/reversal_signature_miner_sovereign.py` | Accept and log `low_quality_symbols` list to tag degraded shards during mining |
| 5 | `params_yaml.txt` | Add `thresholds.min_shard_health`, `thresholds.max_degraded_ratio` |

---

### 2.5 Loop #5: Multi-Agent Orchestration Loop

**Priority: 5 — Impact: High, Effort: Medium, Risk: Low**

#### Files
- **Primary**: `kronos_module/orchestrator_engine.py` (entire file), `config/utils/kronos_pipeline_sovereign.py` (entire file)
- **Dependency**: `config/utils/sovereign_entrypoint.py`
- **Dashboard**: `config/ingestion/unified_ingestion_engine.py` L612-702 (HTML dashboard generator)

#### Current State (Open Loop)
Pipeline is strictly sequential with no inter-stage feedback:
```
run_full_pipeline():
    fetch_all_symbols_data()       # Stage 1 — no awareness of Stage 2
    mine_all_shards()              # Stage 2 — no awareness of Stage 3
    build_global_prior()          # Stage 3 — no awareness back to Stage 1
```

Each stage is entirely self-contained. The orchestrator has no event model, no shared state, no mechanism for one stage to influence another's behavior.

`extract_live_reversal_signals()` calls `mine_all_shards()` which takes potentially hours for 500+ symbols — no progress streaming or checkpoint feedback to the orchestrator.

`detect_regime()` returns a regime string, but nothing consumes it to adjust mining parameters.

#### Proposed Closed Loop Structure

```
┌─────────────────────────────────────────────────────────────────────┐
│  PIPELINE ORCHESTRATION EVENT LOOP                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  OBSERVE:                                                            │
│   at each stage boundary, create PipelineEvent:                      │
│     {stage, status, metrics, timestamp, artifact_path}              │
│     stages: [INGESTION, MINING, PRIOR_BUILD, INFERENCE, DASHBOARD]  │
│     metrics per stage (example):                                    │
│       INGESTION: {symbols_attempted, symbols_succeeded,              │
│                   avg_health, degraded_ratio, total_bars,            │
│                   elapsed_seconds}                                   │
│       MINING: {symbols_mined, high_quality_count, veto_rate,        │
│                avg_confidence, phylum_count, elapsed_seconds}        │
│       PRIOR_BUILD: {signatures_loaded, mean_confidence,             │
│                     high_quality_ratio}                              │
│                                                                      │
│  ACT:                                                                │
│   push PipelineEvent to shared pipeline log (JSON Lines at           │
│     logs/pipeline_events.jsonl)                                      │
│   orchestrator consumes events and makes stage-gate decisions:       │
│     if INGESTION.symbols_succeeded < 10:                             │
│       → HALT: insufficient data for mining                          │
│     if INGESTION.avg_health < 60:                                    │
│       → WARN: degraded ingestion may impact mining quality          │
│     if MINING.high_quality_count == 0:                               │
│       → HALT: prior build will have no meaningful input             │
│     if MINING.veto_rate > 0.9:                                       │
│       → WARN: slot_15 vetoing almost all symbols, check params      │
│                                                                      │
│  EVALUATE:                                                           │
│   for each stage, compute delta vs previous run:                     │
│     ingestion_health_delta = current_avg_health - previous_avg       │
│     mining_yield_delta = current_hq_ratio - previous_hq_ratio       │
│     prior_distribution_shift = KL(prior_current || prior_previous)  │
│   if any delta exceeds cfg["thresholds"]["max_pipeline_drift"]:     │
│     → emit DRIFT_ALERT with structured diagnostics                  │
│                                                                      │
│  VERIFY:                                                             │
│   if DRIFT_ALERT:                                                    │
│     → create recovery checkpoint                                     │
│     → optionally HALT (configurable via pipeline.halt_on_drift)      │
│   if any HALT condition met:                                         │
│     → save pipeline state, exit gracefully                           │
│     → on next run, resume from last successful stage                 │
│                                                                      │
│  ADAPT:                                                              │
│   orchestrator selects pipeline path based on state:                 │
│     if mining_yield > threshold → run full pipeline                  │
│     if mining_yield degraded but > minimum → run with relaxed        │
│       thresholds, notify human                                       │
│     if mining_yield < minimum → skip prior build, emit warning       │
│   store event history for dashboard consumption                      │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

#### PipelineEvent Schema

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional

@dataclass
class PipelineEvent:
    stage: str                    # INGESTION | MINING | PRIOR_BUILD | INFERENCE | DASHBOARD
    status: str                   # STARTED | COMPLETED | FAILED | SKIPPED | HALTED
    timestamp: datetime
    run_id: str                   # UUID per pipeline run
    metrics: Dict[str, Any]       # Stage-specific metrics
    artifact_path: Optional[str] = None
    error: Optional[str] = None
    parent_run_id: Optional[str] = None  # For resume/recovery tracking
```

#### Implementation Plan

| Step | File | Description |
|------|------|-------------|
| 1 | `kronos_module/pipeline_events.py` | `PipelineEvent` dataclass, `PipelineLogger` (writes to `logs/pipeline_events.jsonl`), `PipelineEventReader` (reads for dashboard) |
| 2 | `config/utils/kronos_pipeline_sovereign.py` | Inject `PipelineLogger` into `run_full_pipeline`, add event emission at each stage boundary |
| 3 | `config/ingestion/unified_ingestion_engine.py` | Add event emission to `fetch_all_symbols_data` |
| 4 | `config/mining/reversal_signature_miner_sovereign.py` | Add event emission to `mine_all_shards` |
| 5 | `config/utils/global_prior_sovereign.py` | Add event emission to `build_global_prior` |
| 6 | `kronos_module/orchestrator_engine.py` | Add `orchestrate_pipeline()` that consumes events and makes gate decisions |
| 7 | `params_yaml.txt` | Add `pipeline.halt_on_drift`, `pipeline.max_pipeline_drift` |
| 8 | Dashboard HTML | Add pipeline event visualization (D3.js timeline or simple JSON viewer) |

---

### 2.6 Loop #6: Sovereignty & Hardcode Audit Continuous Loop

**Priority: 6 — Impact: High, Effort: Low-Medium, Risk: Low**

#### Files
- **Primary**: `config/validation/validate_sovereignty.py` (entire file, 52 lines)
- **Secondary**: `config/validation/load_sovereign_config.py`

#### Current State (Open Loop)
The sovereignty validator:
- Runs only on demand (`python -m config.validation.validate_sovereignty`)
- Scans only the validation directory (`.parent` = `config/validation/`) — not the entire repo
- Checks only inline literals via regex keyword matching (very limited)
- Prints violations to stdout — no persistent audit trail
- No delta tracking against previous runs
- Not integrated into the pipeline (no pre-stage sovereignty gate)
- No structural checks (hardcoded column names, magic numbers > 5, hardcoded path strings, hardcoded constants)

**Historical context**: 1225+ sovereignty violations have been found and fixed. Without a continuous loop, regression is inevitable.

#### Proposed Closed Loop Structure

```
┌─────────────────────────────────────────────────────┐
│  SOVEREIGNTY AUDIT CONTINUOUS LOOP (pipeline init)  │
├─────────────────────────────────────────────────────┤
│                                                      │
│  OBSERSE:                                            │
│   on every pipeline initialization:                  │
│     scan all .py files in active source:             │
│       config/, kronos_module/, altcoin_specific/,    │
│       scripts/, root .py files                       │
│     scanners:                                        │
│       a) LiteralScanner: detect inline numeric       │
│          literals > threshold (e.g., 5) that are     │
│          not config keys or standard library consts  │
│       b) ColumnNameScanner: detect hardcoded column  │
│          names (must come from cfg['kline_fields'']) │
│       c) PathLiteralScanner: detect hardcoded paths  │
│          (must use get_storage_path)                 │
│       d) MagicNumberScanner: detect magic numbers    │
│          in arithmetic, slicing, indexing            │
│       e) ImportScanner: detect imports from          │
│          non-sovereign paths                         │
│                                                      │
│  ACT:                                                │
│   generate structured audit report:                  │
│     {run_id, timestamp, git_commit_hash,             │
│      files_scanned, violations: [                    │
│        {file, line, scanner_type, severity, context, │
│         suggested_fix}],                             │
│      violation_counts_by_type,                       │
│      total_violations}                               │
│   save to logs/sovereignty_audit_{run_id}.json       │
│   compute delta: current_violations -                │
│     previous_violations (load last audit)            │
│                                                      │
│  EVALUATE:                                           │
│   if total_violations > 0:                           │
│     → NEW_VIOLATIONS: list each with file:line       │
│   if delta > 0:                                      │
│     → REGRESSION: N new violations since last run    │
│   compute violation_density =                        │
│     violations / total_lines_scanned                 │
│   if violation_density > cfg["thresholds"]["         │
│       max_violation_density"]:                       │
│     → CRITICAL: systemic sovereignty failure         │
│                                                      │
│  VERIFY:                                             │
│   if total_violations > cfg["thresholds"]["          │
│       max_sovereignty_violations"]:                  │
│     → HARD VETO: BLOCK pipeline execution            │
│     → emit structured error report                   │
│   if REGRESSION and not VETO:                        │
│     → WARNING: continue but flag for review          │
│   else:                                              │
│     → PROCEED: sovereignty intact                    │
│                                                      │
│  ADAPT:                                              │
│   update violation baseline in checkpoint            │
│   on PROCEED: update "last_clean_run" timestamp      │
│   if regression fixed in subsequent run:             │
│     → log "sovereignty restored" metric              │
│                                                      │
└─────────────────────────────────────────────────────┘
```

#### Scanner Details

| Scanner | What It Detects | Example Violation | Suggested Fix |
|---------|----------------|-------------------|---------------|
| LiteralScanner | Numeric literals > `max_literal` (configurable, default=5) | `window = 100` | `window = neural["vpin_window"]` |
| ColumnNameScanner | Hardcoded OHLCV column names not from cfg | `df['close']` (in non-structural code) | `df[cfg['kline_fields'][3]]` |
| PathLiteralScanner | Hardcoded path strings | `'data/raw_shards/'` | `get_storage_path(cfg, 'raw_shards_dir')` |
| MagicNumberScanner | Numbers in arithmetic/slicing/indexing | `[0,4,7,8,9,10,11,15]` | Define slot list in params |
| ImportScanner | Direct imports bypassing sovereign path | `from external_lib import X` | Route through sovereign entrypoint |

#### Integration Point

The sovereignty gate must run **before any pipeline stage** — i.e., inside or immediately after `get_sovereign_config()` in `sovereign_entrypoint.py`. This ensures:
1. Every pipeline invocation starts with a sovereignty check
2. Veto happens before any data is fetched or any compute is done
3. The audit log is persistent and comparable across runs

#### Implementation Plan

| Step | File | Description |
|------|------|-------------|
| 1 | `config/validation/validate_sovereignty.py` | Rewrite with modular scanners (literal, column_name, path, magic_number, import) |
| 2 | `config/validation/validate_sovereignty.py` | Add structured audit report output (JSON), delta computation, baseline loading |
| 3 | `config/validation/sovereignty_gate.py` | `SovereigntyGate` class that integrates with pipeline: configurable severity levels (VETO | WARN | PASS) |
| 4 | `config/utils/sovereign_entrypoint.py` | Wire SovereigntyGate into `get_sovereign_config()` |
| 5 | `params_yaml.txt` | Add `validator.max_sovereignty_violations`, `validator.max_violation_density`, `validator.max_literal`, `validator.enable_pipeline_gate` |
| 6 | `kronos_module/pipeline_events.py` | Add SOVEREIGNTY_AUDIT as a pipeline stage |

---

### 2.7 Loop #7: Mining/Feature Engineering Adaptive Loop

**Priority: 7 — Impact: High, Effort: Medium-High, Risk: Medium**

#### Files
- **Primary**: `kronos_module/model/structural_engine.py` (L114-259, especially L237-248 for slot_15 weights)
- **Secondary**: `config/mining/reversal_signature_miner_sovereign.py` (L30-112 for mine_reversal_signature)

#### Current State (Open Loop)
The slot weights in `compute_slots_sovereign` are **hardcoded per-run** (though cfg-driven, they're static within a run):
```python
# structural_engine.py:237
raw_w = {
    "slot_00": neural["strength_mult"],
    "slot_04": neural["variation"],
    "slot_07": neural["strength_mult"],
    "slot_08": neural["strength_add"],
    "slot_09": neural["strength_add"],
    "slot_10": neural["strength_mult"],
    "slot_11": neural["variation"]
}
```

There is no:
- **Feature importance tracking**: Which slots actually contribute to final confidence?
- **Window parameter optimization**: Is `vpin_window=100` optimal in current market regime?
- **Distribution drift detection**: Are slot distributions shifting across time?
- **Adaptive reweighting**: Should slot weights change when regime changes?
- **Collinearity detection**: Are any slots redundant (`corr > 0.95`)?

#### Proposed Closed Loop Structure

```
┌─────────────────────────────────────────────────────┐
│  FEATURE ENGINEERING ADAPTIVE LOOP (per mining run) │
├─────────────────────────────────────────────────────┤
│                                                      │
│  OBSERVE:                                            │
│   collect from all mined symbols:                    │
│     per-slot values (slot_00 through slot_31)        │
│     dna_vector for each symbol                       │
│     phylum labels from HDBSCAN                       │
│                                                      │
│  ACT:                                                │
│   compute feature analytics:                         │
│     slot_correlation_matrix = corr(slot_values)      │
│       → detect collinearity: pairs with |r| > 0.95  │
│     slot_importance = permutation_importance:         │
│       for each slot:                                 │
│         permute its values across symbols            │
│         measure delta in slot_15 variance            │
│         high_delta = important feature               │
│     window_sensitivity:                              │
│       for each window param (vpin_w, ofi_w, etc.):   │
│         test ±25% variation                          │
│         measure slot_15 stability                    │
│     distribution_drift:                              │
│       compare current slot distributions to          │
│       previous run (KS test, p < 0.01)               │
│                                                      │
│  EVALUATE:                                           │
│   if slot_correlation_matrix shows r > 0.95:         │
│     → COLLINEAR: flag redundant slot pair            │
│     → recommend consolidation or removal             │
│   if slot_importance < cfg["thresholds"]["           │
│       min_slot_importance"]:                         │
│     → LOW_VALUE: slot contributes negligibly         │
│     → flag for review                                │
│   if slot_15 variance across symbols < threshold:    │
│     → DEGENERATE: gate not discriminating            │
│   if distribution_drift detected:                    │
│     → DRIFT: feature distributions have shifted      │
│                                                      │
│  VERIFY:                                             │
│   if DEGENERATE:                                     │
│     → re-randomize slot_15 weights                   │
│     → re-mine test batch (first 50 symbols)          │
│     → verify diversity restored                      │
│   if COLLINEAR:                                      │
│     → do NOT block, but flag for next params update  │
│   if DRIFT:                                          │
│     → continue, but log distribution comparison      │
│                                                      │
│  ADAPT:                                              │
│   if importance-based reweighting would improve      │
│     slot_15 variance (confirmed by test batch):      │
│     → apply weight update for this run only          │
│     → store proposed update in checkpoint            │
│   if consistent improvement across 3+ runs:          │
│     → persist weight update to params                │
│     → (human reviews before commit)                  │
│                                                      │
└─────────────────────────────────────────────────────┘
```

#### Slot Importance Computation (Permutation Method)

```
For each target slot S in {slot_00, slot_04, ..., slot_11}:
    1. Record baseline slot_15 distribution across all symbols
    2. Permute the values of slot S across symbols (breaks relationship)
    3. Recompute slot_15 with permuted values
    4. Compute delta = |baseline_slot15_variance - permuted_variance|
    5. Importance_score = delta / sum(all_deltas)
    
High importance: slot's variance contributes significantly to gate
Low importance: slot could be set to constant without changing gate output
```

#### Implementation Plan

| Step | File | Description |
|------|------|-------------|
| 1 | `kronos_module/validation/feature_analytics.py` | `FeatureAnalyzer` class with correlation matrix, permutation importance, window sensitivity, distribution drift (KS test) |
| 2 | `config/mining/reversal_signature_miner_sovereign.py` | Integrate after mining loop (collect slot values across all symbols, run analyzer) |
| 3 | `kronos_module/model/structural_engine.py` | Add `reweight_slots(weights: dict)` function for adaptive reweighting |
| 4 | `params_yaml.txt` | Add `thresholds.min_slot_importance`, `thresholds.max_slot_collinearity`, `thresholds.feature_drift_pvalue` |

---

### 2.8 Loop #8: Human-in-the-Loop Gates

**Priority: 8 — Impact: Medium-High, Effort: Medium, Risk: Low**

#### Files
- **New module**: `kronos_module/trading/signal_gate.py`
- **Dependency**: `kronos_module/orchestrator_engine.py`
- **Dependency**: `config/mining/reversal_signature_miner_sovereign.py`

#### Current State
No human-in-the-loop gates exist. The pipeline runs fully autonomously. There is no mechanism for:
- Approval before live execution (future feature)
- Approval before major parameter changes
- Approval before delisting/archiving symbols
- Approval before model weight updates

#### Proposed Closed Loop (Live Execution Gate)

```
┌─────────────────────────────────────────────────────┐
│  HUMAN-IN-THE-LOOP SIGNAL GATE (live exec only)     │
├─────────────────────────────────────────────────────┤
│                                                      │
│  OBSERVE:                                            │
│   when live_execution_mode = true:                   │
│     for each generated trading signal:               │
│       {symbol, direction, confidence, slot_15,       │
│        neural_conv, regime_flags,                   │
│        entry_price, stop_loss, take_profit}          │
│                                                      │
│  ACT:                                                │
│   compute signal_risk_score:                         │
│     confidence_factor = map(confidence → [0,1])      │
│     slot15_factor = map(slot_15 → [0,1])            │
│     regime_factor = regime_compatibility             │
│     exposure_factor = 1 - current_exposure / max     │
│     risk_score = weighted_sum(above)                 │
│                                                      │
│  EVALUATE:                                           │
│   if risk_score > cfg["thresholds"]["                │
│       auto_exec_threshold"] (e.g., 0.85):             │
│     → AUTO_EXEC: execute immediately                 │
│   if risk_score > cfg["thresholds"]["                │
│       manual_review_threshold"] (e.g., 0.60):         │
│     → REVIEW: structure signal proposal for human    │
│     → emit to dashboard / queue                      │
│   else:                                              │
│     → DISCARD: log reason, no action                 │
│                                                      │
│  VERIFY:                                             │
│   human reviews proposal (via dashboard or CLI):     │
│     approve → execute signal                         │
│     reject → log rejection reason                    │
│     modify → adjust params, execute modified         │
│                                                      │
│  ADAPT:                                              │
│   record human decision for RL dataset:              │
│     {signal_id, risk_score, decision, timestamp}     │
│   periodically analyze:                              │
│     human_approval_rate vs risk_score                │
│     adjust thresholds to match human preference      │
│                                                      │
└─────────────────────────────────────────────────────┘
```

#### Signal Proposal Structure (for Human Review)

```json
{
  "signal_id": "sig_20260608_btcusdt_a1b2c3",
  "timestamp": "2026-06-08T21:15:00Z",
  "symbol": "BTC/USDT",
  "direction": "LONG",
  "confidence": 0.87,
  "risk_score": 0.72,
  "slot_15": 0.82,
  "regime": "trending_mean_reverting",
  "neural_conviction": [0.45, 0.62, 0.31, 0.78, 0.55, 0.41, 0.69, 0.50],
  "entry": 67500.00,
  "stop_loss": 66150.00,
  "take_profit": 70200.00,
  "current_exposure_pct": 15.3,
  "max_exposure_pct": 30.0,
  "reasoning_summary": "Strong slot_15 (0.82) + neural conviction (0.62) aligned. Regime trending. Entry near S/R support."
}
```

---

## 3. Priority Ranking Summary

| Rank | Loop Name | Impact | Effort | Risk | Sovereignty | Performance | Auditability |
|------|-----------|--------|--------|------|-------------|-------------|--------------|
| 1 | **Backtest + Overfitting Detection** | Highest | High | Medium | Medium | Medium | High |
| 2 | **Inference Benchmarking** | High | Medium | Low-Med | Low | Highest | High |
| 3 | **Signal Quality Validation** | High | Medium | Low | High | Low | High |
| 4 | **Ingestion Quality Gate** | High | Low-Med | Low | Medium | Medium | High |
| 5 | **Multi-Agent Orchestration** | High | Medium | Low | Low | Low-Med | High |
| 6 | **Sovereignty Audit Continuous** | High | Low-Med | Low | Highest | Low | Highest |
| 7 | **Feature Engineering Adaptive** | High | Med-High | Medium | Medium | Low-Med | High |
| 8 | **Human-in-the-Loop Gates** | Med-High | Medium | Low | Low | Low | Medium |

### Priority Rationale

1. **Backtest + Overfitting (#1)**: The single biggest gap in production readiness. Without OOS validation, there is zero evidence that reversal signals have predictive power. This is foundational — all other loops benefit from knowing whether signals actually work.

2. **Inference Benchmarking (#2)**: Directly addresses the AMD RX 560 / edge deployment requirement. Ensures model doesn't silently degrade in production. Falls back gracefully when compute degrades.

3. **Signal Quality Validation (#3)**: Catches degenerate mining states (all signals same confidence, random clusters, no neural diversity). Without this, the pipeline can produce voluminous but worthless output.

4. **Ingestion Quality Gate (#4)**: Prevents garbage-in-garbage-out at the earliest stage. Low effort, high impact. Stops degraded shards from wasting mining compute.

5. **Multi-Agent Orchestration (#5)**: Foundational for all higher-level coordination. Without this, stages operate in isolation. Provides the event model that all other loops can consume.

6. **Sovereignty Audit (#6)**: Directly addresses the 1225+ historical violations. Low effort, prevents regression. The gate component ensures sovereignty is maintained continuously.

7. **Feature Engineering Adaptive (#7)**: Breaks mining stagnation by detecting and correcting slot weight degeneracy. Higher risk because weight changes must be validated before production adoption.

8. **Human-in-the-Loop (#8)**: Critical for live execution but currently lower priority since live trading is not yet active. Design the gate now so it's ready when needed.

---

## 4. Cross-Cutting Infrastructure Recommendations

### 4.1 Common Evaluation Registry

Create `kronos_module/eval/` as a shared metrics hub that ALL loops import from:

```
kronos_module/eval/
├── __init__.py              # Exports: EvalRegistry, EvalMetric
├── metrics.py               # Shared metric functions:
│   ├── directional_accuracy()
│   ├── sharpe_ratio()
│   ├── confidence_calibration()
│   ├── signal_diversity()
│   ├── slot_correlation()
│   ├── distribution_drift_ks()
│   └── latency_stats()
├── registry.py              # EvalRegistry: stores metrics keyed by (run_id, stage, metric_name)
├── persistence.py            # JSONL writer/reader for eval data
└── dashboard.py             # Data aggregation for dashboard consumption
```

All eight loops would push metrics to `EvalRegistry`. The dashboard consumes from `EvalRegistry` instead of ad-hoc per-loop logging.

### 4.2 Unified Checkpoint System

Replace the current ad-hoc checkpoint in `MiningStatusTracker._checkpoint` with a unified system:

```python
@dataclass
class PipelineCheckpoint:
    run_id: str
    timestamp: datetime
    stage: str                  # INGESTION | MINING | PRIOR_BUILD | INFERENCE
    stage_status: str           # COMPLETED | FAILED | PARTIAL
    metrics: Dict[str, Any]     # Per-stage metrics
    quality_gates: Dict[str, bool]  # Which gates passed/failed
    artifact_paths: Dict[str, str]  # Paths to generated artifacts
    loop_iterations: int        # How many adaptive loop iterations were run
    next_action: str            # PROCEED | RETRY | HALT | HUMAN_REVIEW
```

**All loops** would read/write from `PipelineCheckpoint`. This ensures:
- Cause-effect traceability (loop iteration N → metrics change → gate decision)
- Resume capability on failure (pick up from last checkpoint)
- Full audit trail for compliance

### 4.3 GBrain / DeRonin Integration Points

The codebase has no GBrain long-term memory or DeRonin agentic stack implementation yet. The orchestration loop (#5) provides the foundation:

| Component | Role | Integration Point |
|-----------|------|-------------------|
| **GBrain** | Long-term memory across runs | Consumes `PipelineCheckpoint` history, stores `EvalRegistry` data, provides trend analysis |
| **DeRonin** | Agentic decision-making | Consumes `PipelineEvent`s, makes stage-gate decisions, dispatches adaptive actions |
| **Cognee** | Knowledge graph | Connects slot relationships, regime patterns, signal-to-outcome mappings |

When these components are implemented, each closed loop becomes an agent that:
1. Reads state from GBrain (historical context)
2. Observes current pipeline events
3. Makes decisions via DeRonin agent (or rule-based fallback)
4. Writes outcomes back to GBrain
5. Updates Cognee knowledge graph with learned relationships

### 4.4 Common Evaluation Gates

Define these evaluation gates that multiple loops can use:

| Gate Name | Input | Output | Used By |
|-----------|-------|--------|---------|
| `HealthGate(health_score, threshold)` | Float | PASS/WARN/FAIL | Loop #4 (Ingestion) |
| `DiversityGate(entropy, threshold)` | Float | PASS/DEGENERATE | Loop #3 (Signal Quality) |
| `OverfittingGate(IS_sharpe, OOS_sharpe)` | (Float, Float) | PASS/OVERFIT | Loop #1 (Backtest) |
| `LatencyGate(latency_ms, threshold)` | Float | PASS/DRIFT/DEGRADED | Loop #2 (Inference) |
| `SovereigntyGate(violations, threshold)` | (Int, Int) | PASS/REGRESSION/VETO | Loop #6 (Sovereignty) |
| `CollinearityGate(corr_matrix, threshold)` | Matrix | PASS/COLLINEAR | Loop #7 (Features) |
| `RiskGate(risk_score, auto_thr, manual_thr)` | Float | AUTO/REVIEW/DISCARD | Loop #8 (HITL) |

Each gate is a pure function: `(metric_value, threshold) → GateDecision`. All loops use the same gate interface.

---

## 5. Risks and Mitigations

### 5.1 Backtest Loop Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Lookahead bias in signal validation | Low | Critical | Timestamp-based splits only. Historical data must NOT include forward-looking information. Verify all slicing is `iloc[-window:]` or `tail(window)`, never `iloc[:window]` for testing. |
| Survivorship bias | Medium | High | Include symbols that have since been delisted (they should still be in archive). The backtest should test on the symbol universe as it existed at the time. |
| Overfitting to backtest window | Medium | Medium | Walk-forward validation across regime blocks. Require consistent performance across multiple non-overlapping test periods. |
| Computational cost for 500+ symbols | High | Medium | Use stratified sampling: backtest on 50-100 representative symbols per run, cycle the sample each run. Store full backtest results in checkpoint for aggregate analysis. |

### 5.2 Inference Loop Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Benchmark adds startup latency | High | Low | Benchmark timeout (configurable, default 30s). Fall back to heuristic if timeout exceeded. |
| GPU benchmark interferes with other processes | Medium | Low | Run benchmark at lowest priority (`nice`/`ionice`). Use `torch.cuda.empty_cache()` between passes. |
| AMP correctness diff non-deterministic | Medium | Medium | Run AMP verification 3 times, take max diff. If high variance, disable AMP. |
| torch.compile fails silently | Low | Low | Catch compile exception, proceed with eager mode. Benchmark distinguishes compiled vs eager automatically. |

### 5.3 Signal Quality Loop Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Degeneracy detection false positive (market is genuinely low-signal) | Medium | Medium | DETECT but do not BLOCK. Flag for human review. Allow override via `params.override_signal_quality_gate`. |
| HDBSCAN silhouette score unreliable for small clusters | Medium | Low | Only compute silhouette when `n_clusters > 1` and `n_samples > 50`. Use adjusted Rand index for stability instead. |
| Confidence calibration unreliable with small N | High | Low | Require minimum 100 samples per calibration bucket. Merge sparse buckets. |

### 5.4 Ingestion Gate Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Stringent health threshold blocks pipeline on exchange issues | Medium | High | Progressive thresholds: WARN at 50, BLOCK at 30. Allow override. |
| Re-fetch loop triggers rate limits | Medium | Medium | Max re-fetch attempts = 3. Exponential backoff. Respect rate limit delay. |
| Health score metric unstable | Low | Medium | Store raw per-metric values alongside composite health. Allow dashboard drill-down. |

### 5.5 Orchestration Loop Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Pipeline event log grows unbounded | High | Low | Rotate logs after N events or M days. Compress old events. |
| Gate decision causes pipeline to halt incorrectly | Medium | Medium | All gates have PASS/WARN/FAIL levels. Only FAIL halts. WARN logs and continues. Provide manual override via env var `KRONOS_BYPASS_GATES=1`. |
| Delta tracking fails on first run (no baseline) | Low | Low | Initialize with empty baseline. Delta = 0 on first run. |

### 5.6 Sovereignty Loop Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| False positives (valid code flagged as violation) | Medium | Medium | Maintain allowlist in params. Review false positives, add to allowlist. |
| Gate blocks pipeline during active development | High | Medium | Allow override via `params.validator.enable_pipeline_gate = false`. Continue to log violations, just don't block. |
| Scanner performance on large codebase | Low | Low | Cache scanner results, only re-scan modified files (use git diff). |

### 5.7 Feature Engineering Loop Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Permutation importance is O(N*K) where K=number of slots | Medium | Low | Run importance only on a sample (first 200 symbols). Not every run — configurable `importance_interval`. |
| Adaptive reweighting produces worse results | Medium | High | Test batch before applying to full run. Revert if test batch slot_15 variance decreases. Require 3-run consistency before permanent adoption. |
| Collinearity detection flags temporary correlation | Low | Low | Flag but do not act. Only propose consolidation if collinearity persists across 3+ runs. |

### 5.8 Human-in-the-Loop Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Human unavailable for review | Medium | Medium | Timeout on review requests. If no response within N minutes, fall to DISCARD (conservative). |
| Excessive review requests overwhelm human | High | Medium | Adjust `manual_review_threshold` to reduce volume. Clustering similar signals. Batch review. |
| Human makes worse decisions than autonomous system | Medium | Low | Track human decision outcomes vs auto-exec outcomes. Periodically suggest threshold adjustment. |

---

## 6. Next Actions: Concrete Refactoring Plan

### Phase 1: Foundation (Priority 1 + Infrastructure)

**Target**: Backtest module + Evaluation Registry + Unified Checkpoint

#### Week 1-2: Module Creation

| Day | Task | Files |
|-----|------|-------|
| 1 | Create `kronos_module/backtest/` package with `__init__.py` | New files |
| 1 | Implement `metrics.py`: `directional_accuracy()`, `sharpe_ratio()`, `max_drawdown()`, `profit_factor()`, `confidence_calibration()` | `kronos_module/backtest/metrics.py` |
| 2 | Implement `evaluator.py`: OOS holdout, per-symbol evaluation, aggregate statistics | `kronos_module/backtest/evaluator.py` |
| 3 | Implement `overfitting.py`: walk-forward splitter, overfitting score, regime block detection | `kronos_module/backtest/overfitting.py` |
| 4 | Implement `checkpoint.py`: JSONL storage, delta computation, baseline loading | `kronos_module/backtest/checkpoint.py` |
| 5 | Create `kronos_module/eval/` package with `registry.py`, `metrics.py` | New files |
| 5-6 | Wire backtest into `mine_all_shards`, replace bare `try/except pass` block | `config/mining/reversal_signature_miner_sovereign.py` |
| 6 | Add backtest thresholds to `params_yaml.txt` | `params_yaml.txt` |

#### Week 2-3: Integration & Testing

| Day | Task | Files |
|-----|------|-------|
| 7 | Unit tests for all backtest metrics (use synthetic known-outcome data) | `kronos_module/backtest/tests/` |
| 8 | Integration test: run backtest on 50 symbols, verify OOS accuracy < IS accuracy (always) | New test |
| 9 | Verify causally strict: audit all timestamp splits for lookahead | All backtest files |
| 10 | Dashboard integration: backtest metrics in HTML summary | `config/ingestion/unified_ingestion_engine.py` (extend `generate_html_summary`) |
| 10 | Documentation update: backtest usage, metric definitions, interpretation guide | `docs/` |

### Phase 2: Performance + Quality (Priorities 2, 3, 4)

**Target**: Inference benchmark, signal quality validation, ingestion quality gate

#### Week 4-5

| Day | Task | Files |
|-----|------|-------|
| 11 | Implement `InferenceBenchmark` class with warmup, timing, memory tracking | `kronos_module/model/benchmark.py` |
| 12 | Integration into `KronosPredictor.__init__` and periodic check in inference paths | `kronos_module/model/kronos.py` |
| 13 | Implement `SignalQualityValidator` with diversity, entropy, silhouette, calibration | `kronos_module/validation/signal_quality.py` |
| 14 | Implement `QualityGate` for ingestion with per-symbol health tracking | `config/ingestion/unified_ingestion_engine.py` |
| 15 | Wire all quality gates, add threshold params | Multiple files |

### Phase 3: Orchestration + Sovereignty (Priorities 5, 6, 7)

**Target**: Pipeline events, sovereignty audit loop, feature analytics

#### Week 6-7

| Day | Task | Files |
|-----|------|-------|
| 16 | Implement `PipelineEvent` dataclass and `PipelineLogger` | `kronos_module/pipeline_events.py` |
| 17 | Inject event emission into all pipeline stages | Multiple files |
| 18 | Implement `SovereigntyGate` with modular scanners | `config/validation/` |
| 19 | Wire sovereignty gate into `get_sovereign_config()` | `config/utils/sovereign_entrypoint.py` |
| 20 | Implement `FeatureAnalyzer` with correlation, importance, drift | `kronos_module/validation/feature_analytics.py` |
| 21 | Full integration test: all eight loops in sequence | `test_end_to_end.py` (extend) |

### Phase 4: Human-in-the-Loop + Dashboard (Priority 8)

**Target**: Signal gate, dashboard visualization

#### Week 8

| Day | Task | Files |
|-----|------|-------|
| 22 | Implement `SignalGate` with risk scoring, structured proposals | `kronos_module/trading/signal_gate.py` |
| 23 | Dashboard integration: live gate status, review queue, decision history | Dashboard HTML + new endpoint |
| 24 | Final integration test: E2E with all loops active | `test_end_to_end.py` |

---

## 7. Summary

| Metric | Current State | After All Loops |
|--------|--------------|-----------------|
| Pipeline validation | None (no OOS testing) | Backtest-driven: directional accuracy, Sharpe, overfitting score |
| Sovereignty enforcement | Stateless scanner, not in pipeline | Continuous veto gate on every pipeline init |
| Inference hardening | Silent fallback to scalar | Benchmark-driven device/compile/AMP selection, drift detection |
| Signal quality | Single confidence threshold | Meta-quality: diversity, entropy, silhouette, calibration |
| Ingestion reliability | No quality gate | Health-gated with adaptive re-fetch |
| Inter-stage coordination | None | Event-driven orchestration with gates |
| Feature health | Static weights | Adaptive importance tracking, collinearity detection |
| Human oversight | None | Risk-scored signal gate with structured proposals |

The eight closed loops transform KRONOS V1-ALT from an open-loop pipeline into a self-monitoring, self-adapting, auditable system. Each loop follows the same pattern: **Observe → Act → Evaluate → Verify → Adapt or Exit**. All loops are bounded, verifiable, and evaluation-gated — no unbounded optimization loops that could diverge or hallucinate.

The #1 priority (backtest + overfitting) is the foundational gap. Without it, the system generates signals with zero quantitative evidence of predictive power. With it, every other loop gains context for its decisions.