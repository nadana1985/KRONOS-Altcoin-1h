# KRONOS V1-ALT vs KRONOS_HYBRID-V5 — Gap Analysis Report

**Date:** 2026-06  
**Task:** Deep analysis of https://github.com/nadana1985/KRONOS_HYBRID-V5 (reference) vs current F:\kronos_v1_alt sovereign V1-ALT implementation. Identify all missing components, architectural gaps, and production readiness differences.  
**Ground Truth:** All prior phase MDs (Phase 0-3 + Production Hardening + E2E + Live Dashboard), params_yaml.txt v3.1, current code (structural_engine.py, orchestrator_engine.py, reversal_signature_miner_sovereign.py, feature usage in kronos.py, test_end_to_end.py, unified_ingestion_engine.py), and full reference repo content (README, structural_engine.py, neural_integration_engine.py, feature_builder_engine.py, miner_engine.py, data_engine.py, orchestrator_engine.py, params_yaml.txt, specs).  
**Actions:** Used web_fetch + open_page + raw content analysis on reference repo. Compared core engines, slot systems, data layers, neural usage, pipeline orchestration, and E2E validation approach. Zero tolerance for literals or assumptions.

---

## Executive Summary

The reference repo (KRONOS_HYBRID-V5) is a **complete, production-grade hybrid sovereign reversal signature mining engine** for high-performance walk-forward quantitative systems. It implements a strict two-stage gate (deterministic Structural Sovereign Core + orthogonal Neural Conviction Gate using real Kronos-mini transformer) that produces a 32-slot causal "DNA vector" per bar, followed by full sharded mining, forward evaluation, post-hoc stable ontology (HDBSCAN), Parquet + DuckDB storage, and rich backtesting/ablation infrastructure.

The current `kronos_v1_alt` repo is a **specialized, sovereign-config-driven altcoin reversal signal + forecasting system** that successfully ported key sovereignty concepts (structural veto, neural_slots abstraction, dual-mode individual/global prior with ablatable injection, robust KRONOS_PARAMS_PATH bootstrap, V5-style hybrid gating inside KronosPredictor, live extract/detect signals, and a wiring-focused E2E harness).

**Core status:** Significant architectural and functional gaps remain. The V1-ALT implementation is a deliberate simplification/focus on altcoin-scale reversal mining + live regime signals + Kronos forecasting with dual-mode. It is **not** a port of the full HYBRID-V5 hybrid pipeline. The E2E harness (even after Option B) exercises only the ported pieces and remains heavily print-driven with a placeholder Step 4.

All values in both systems are intended to come from `params_yaml.txt` (zero inline literals doctrine enforced in reference; largely followed in V1-ALT after prior phases).

**Major missing categories in V1-ALT:**
- Rich 15-slot structural feature set + microstructure (agg_trades)
- Real Kronos-mini neural gate for conviction (embeddings, L_p norm, vol-gated pooling)
- Full 32-slot DNA vector + feature builder
- Advanced data layer (BVC synthetic trades)
- Full sharded miner with forward metrics + post-hoc HDBSCAN ontology
- DuckDB + database engine
- Complete pipeline orchestration + backtest/ablation/validation suite
- Detailed V5 hybrid slot specs and supporting engines

Current V1-ALT strengths (unique or better adapted): explicit dual-mode global prior ablatable injection into Kronos, altcoin 530-symbol fallback + discovery, production-hardened bootstrap for direct script execution, focused reversal math + live signals/regime detection, Option B E2E robustness.

This gap analysis is the required next documentation step after the user-provided successful E2E transcript and the request to "read this repo and find what is missing".

---

## Strongest Risk / Strongest Wiring Violation / Strongest Remaining Violation / Strongest Production Risk / Strongest Visualization/Regime Risk / Strongest Runtime Failure Point

**Strongest Risk:** The current system claims "KRONOS V1-ALT" and "V5 Hybrid Gate enforced" in docs/harness, but lacks the actual hybrid structural+neural gate that defines the reference. Users (or future deployment) may assume full HYBRID-V5 fidelity when only a subset of concepts were ported. This creates expectation mismatch and potential incorrect signal quality in production.

**Strongest Wiring Violation:** `kronos_module/model/kronos.py` and `orchestrator_engine.py` wire KronosPredictor with sovereign_ctx + neural_slots + global prior injection + V5 window clipping, but this is used for *forecasting/generation*, not as the reference's `compute_neural_gate` (L_p conviction from transformer embeddings inside the mining decision loop). The reference treats the Kronos-mini as the orthogonal neural conviction layer *during signature detection*; V1-ALT uses it downstream.

**Strongest Remaining Violation:** No equivalent to reference `feature_builder_engine.build_full_dna_vector` (32-slot causal vector) or `structural_engine.compute_slots_sovereign` (15 detailed slots using agg_trades buy/sell_vol). Current reversal miner (`reversal_signature_miner_sovereign.py`) implements a single simplified reversal calculation using only a handful of `neural_slots` values on pure OHLCV. No microstructure, no spectral/Hurst/HMM/SR-KDE/etc. features.

**Strongest Production Risk:** Missing full data layer (`data_engine.py` with BVC + synthetic trades), database layer (DuckDB views + compact storage + post-hoc ontology), and complete pipeline (`orchestrator_engine.run_full_pipeline` + sharded walk-forward with precomputes + forward MFE/MAE + HDBSCAN global ontology). Current E2E harness + miner will not scale to full corpus or produce stable, queryable signatures with phylum labels. Hardcode validator and reproducibility guards are lighter than reference.

**Strongest Visualization/Regime Risk:** `detect_regime` and `extract_live_reversal_signals` (plus dashboard skeleton) are useful live signals, but they operate on a tiny reversal slot set. Reference regime logic would be derived from a rich 32-slot DNA vector + neural conviction. Current ablation (individual vs global) works for the dual-mode port but does not exercise the full hybrid slot system or neural gate.

**Strongest Runtime Failure Point:** 
- `test_end_to_end.py` (and the miner it drives) still relies on heavy print statements for "verification" (user explicitly flagged this). No assertions, no real model forward in Step 4, and the miner path only exercises simple reversal on whatever 1-2 shards exist (even after Option B).
- No `neural_integration_engine` equivalent means the "V5 Hybrid Gate" comments in kronos.py are partial (only window clipping + global prior; missing the conviction gate that actually decides signatures in the reference).
- Direct execution of full reference-style pipeline (`run_full_pipeline`, full corpus mining, backtests) will immediately fail due to missing modules (feature_builder_engine, neural_integration_engine, database_engine, etc.) and different params structure (reference uses "5m" + ETHUSDT + full structural slots; current is 1h alt perps reversal-focused).

All gaps were confirmed via direct raw content comparison of reference files vs current `kronos_module/model/structural_engine.py`, `orchestrator_engine.py`, `reversal_signature_miner_sovereign.py`, `kronos.py`, `test_end_to_end.py`, and `params_yaml.txt`.

---

## Surgical Gap Analysis & Port Plan (copy-paste ready high-level diffs / priorities)

No single small diff can close the gap — this is an architectural delta. Prioritized surgical ports below (smallest first, preserving current dual-mode + altcoin focus + sovereign bootstrap).

**Priority 1 — Minimal: Strengthen E2E to reduce "just prints" perception + exercise more real paths (addresses immediate user feedback)**

```diff
# In test_end_to_end.py
# Replace pure prints + return True with real side-effect + assertion checks
# (keep reporting prints for visibility, add substance)

-    print("E2E complete. Verify: ...")
-    return True
+    # Real verification
+    sig_dir = cfg["storage"]["signatures_individual_dir"]
+    btc_sig = os.path.join(sig_dir, "BTC_USDT_USDT_signature.parquet")
+    assert os.path.exists(btc_sig), "Expected signature file from miner"
+    sig_df = pd.read_parquet(btc_sig)
+    assert "confidence" in sig_df.columns and sig_df["confidence"].iloc[0] > 0.7
+
+    # Exercise real KronosPredictor forward (Step 4 substance)
+    from kronos_module.model.kronos import KronosPredictor
+    ctx = orchestrate_sovereign("individual")
+    predictor = KronosPredictor(sovereign_ctx=ctx)  # or equivalent wired constructor
+    # ... minimal causal input + generate call (respect max_context from slots)
+    # assert output shape / no crash
+
+    print("E2E complete. All real side-effects + assertions passed.")
+    return True
```

**Priority 2 — Add minimal neural gate path (closest to reference's orthogonal neural layer)**

- Create `kronos_module/model/neural_integration_engine.py` (surgical extract from reference, adapted to current neural_slots + dual-mode).
- Wire a `compute_neural_conviction(causal_df, current_idx, ctx)` that uses existing KronosPredictor (or loads kronos_small) for embeddings + L_p style score.
- In reversal miner or a new feature_builder, treat structural reversal confidence as floor + neural conviction as amplifier (non-blocking).

**Priority 3 — Richer structural features + microstructure (core of reference's 15 slots)**

- Extend current `structural_engine.py` or add `feature_builder_engine.py`.
- Add agg_trades synthesis (BVC or hash split) in ingestion path.
- Implement a subset of reference slots (start with wick_ratio, volume_price_divergence, ema_ribbon, microprice_deviation) that feed into current neural_slots + reversal logic.

**Priority 4 — Full pipeline + DB + ontology**

- Add `database_engine.py` (DuckDB views + compact signatures).
- Extend miner with forward metrics (MFE/MAE) and post-hoc HDBSCAN for stable labels.
- Update orchestrator with `run_full_pipeline` style entrypoint.

**Priority 5 — Specs + validator parity**

- Port/adapt key .md specs (V5_HYBRID_SLOT_DEFINITIONS.md, MINER_SPEC.md, etc.) into current docs.
- Enhance `validate_sovereignty.py` + hardcode checks to cover more reference patterns (agg_trades usage, causal slicing, SHA pinning for Kronos-mini).

**Reference files that are almost direct ports (with adaptation for dual-mode + 1h altcoins):**
- `structural_engine.py` (the 15-slot version)
- `neural_integration_engine.py`
- `feature_builder_engine.py`
- `miner_engine.py` (core loop + compile_global_ontology)
- `data_engine.py`
- `database_engine.py`
- `orchestrator_engine.py` (run_full_pipeline)
- `params_yaml.txt` (structural + kronos_mini + gate + aux + metadata sections)

Current `params_yaml.txt` already has good sovereign structure (project, storage, individual_mode, global_prior_mode, thresholds, data_fetch, validator). Extend it rather than replace.

---

## Validation Gate (exact commands + grep for gap confirmation)

**Exact reproduction of the analysis (run on clean workspace):**

```powershell
cd F:\kronos_v1_alt
$env:KRONOS_PARAMS_PATH = "F:\kronos_v1_alt\params_yaml.txt"

# 1. Confirm current structural scope (only dual-mode + reversal slots)
Select-String -Path kronos_module\model\structural_engine.py -Pattern "def |neural_slots|reversal_window|global_prior" | Select-Object -First 20

# 2. Confirm absence of reference neural gate / feature builder
Get-ChildItem -Recurse -Include *neural_integration*,*feature_builder* -ErrorAction SilentlyContinue | Select-Object FullName
Get-ChildItem -Recurse -Include *database_engine*,*data_engine* | Select-Object FullName

# 3. Confirm reference concepts missing in miner
Select-String -Path config\reversal_signature_miner_sovereign.py -Pattern "compute_slots|neural_gate|DNA|embedding|HDBSCAN|phylum|MFE|MAE" -ErrorAction SilentlyContinue

# 4. Run current E2E (should still pass post-Option B, but will show limited scope)
python F:\kronos_v1_alt\test_end_to_end.py | Select-String -Pattern "Step 2:|Processed|neural_slots|regime:"

# 5. Sovereign literal scan on both (reference claims full zero-literal; current mostly clean after prior phases)
python config\validate_sovereignty.py
```

**Post-run literal / concept grep (expected results on current tree):**
- No `compute_neural_gate`, no `slot_00`..`slot_14`, no `build_full_dna_vector`, no `compile_global_ontology`, no `agg_trades["buy_vol"]` in active reversal path.
- `test_end_to_end.py` still contains ~30-40 print statements in the main flow (as user observed).
- `kronos.py` has V5 window clipping + global prior comments, but no embedding extraction or L_p conviction.

All gates above were executed during this analysis session.

---

## Next Phase Trigger (only after verified PASS on gap closure)

**Status:** Gap analysis complete. Current V1-ALT is a solid, sovereign, dual-mode reversal + forecasting system with excellent bootstrap and live signals, but it is **not** a full port of HYBRID-V5's hybrid structural+neural signature mining engine.

**Immediate next (only after this MD + push):**
- Decide scope: "Stay focused on current reversal + dual-mode + Kronos forecasting" vs "Close the hybrid gap to become true V5-ALT".
- If closing gap: Start with Priority 1 (E2E assertions + real Step 4 Kronos forward) + Priority 2 (minimal neural gate wrapper around existing KronosPredictor).
- Extend `params_yaml.txt` with reference structural + kronos_mini + gate sections (merge, do not overwrite current dual-mode / reversal thresholds).
- Add `feature_builder_engine.py` and a slim `neural_integration_engine.py` (adapted).
- Update E2E harness to use the new DNA vector path and assert real side effects (files written, non-zero conviction, etc.).
- Re-run full user command + produce new transcript + updated E2E MD.
- Continue git discipline: commit this gap MD + any follow-on ports; push to https://github.com/nadana1985/KRONOS-Altcoin-1h (main).

All prior MDs + params_yaml.txt v3.1 remain ground truth. Zero tolerance for new inline literals. Dual-mode (individual primary + ablatable global prior) and robust bootstrap must be preserved during any porting.

**Run this to re-confirm current state on your machine (after pulling latest):**

```powershell
cd F:\kronos_v1_alt
$env:KRONOS_PARAMS_PATH = "F:\kronos_v1_alt\params_yaml.txt"
python F:\kronos_v1_alt\test_end_to_end.py
```

Expect the improved Option B output (2 symbols, real signatures written) + the same live regime/ablation prints. Then review this gap MD to decide the next concrete port.

---

**End of Gap Analysis Report.**  
Created as `KRONOS_V1_ALT_VS_HYBRID_V5_GAP_ANALYSIS.md`. Push this file + any follow-up changes to git. Next phase only after user confirmation on scope (focused reversal vs full hybrid closure).