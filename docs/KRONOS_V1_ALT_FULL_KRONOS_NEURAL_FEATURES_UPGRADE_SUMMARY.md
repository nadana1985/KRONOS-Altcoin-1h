# KRONOS V1-ALT — Full Kronos Neural Features Upgrade (Slots 16-23) Summary

**Phase:** Upgrade compute_neural_conviction to leverage full Kronos Transformer for rich, distinct 8-feature vectors in dna slots 16-23 (instead of scalar replication). Phased, surgical, cfg-driven, zero literals.

**Scope (strict):** 
- Phase 1: params_yaml.txt + structural_engine neural_slots exposure.
- Phase 2: KronosPredictor.compute_neural_conviction (and minor __init__/generate support) in kronos_module/model/kronos.py.
- Phase 3: reversal_signature_miner_sovereign.py (call + dna assignment + scalar for amp).
- Phase 4: test_end_to_end.py (assert 8 distinct) + validate_sovereignty.py (neural cfg check).
- No changes to slot_15 veto, Option B, dual-mode, structural slots, HDBSCAN, or core E2E asserts.
- Defaults preserve exact prior scalar behavior (use_full_model=false, mode=scalar).
- Full model path uses existing decode_s1 context for hidden pooling (mean/std/max/min/last/quantiles/norm) when enabled and model loaded.

**Reference:** Kronos repo (shiyu-coder/Kronos) for model/tokenizer patterns; prior 32-Slot DNA Reality Audit; docs realignment; sovereign_ctx + neural from params_yaml.txt thresholds + new neural: section.

## Executive Summary
- **Config:** Added neural: section in params_yaml.txt with neural_conv_mode, use_full_model (safety), dims=8, max_context etc. Exposed via neural_slots in sovereign context (get_dual_mode_context).
- **KronosPredictor:** compute_neural_conviction now conditionally runs full model (tokenizer.encode + model.decode_s1 for context hidden states) and pools to 8 distinct features when use_full_model=true and model present. Scalar path (tokenizer.embed + norm) unchanged as fallback/default.
- **Miner:** Handles list return for dna 16-23 assignment (no replication). Uses mean scalar for amplification and logging/return "neural_conviction".
- **Validation:** E2E now asserts len==8 when list returned. Validator reports neural config presence.
- **Safety/Graceful:** Falls back to 0.0 or [0]*8 on any error, no model, or scalar mode. Memory guard via max_context_length. mixed_precision amp where cuda.
- **Sovereignty:** All new values from params (neural: or defaults in code via .get). No literals. model_dir from sovereign_ctx storage.

Current default behavior identical to before (scalar replication). Enabling use_full_model + having models/ loaded gives distinct neural features from actual Kronos hidden states.

## Precise Changes (Smallest Diffs)

**params_yaml.txt** (added neural: section after thresholds):
```diff
   reversal_min_history: 100
+
+neural:
+  # Neural conviction modes for slots 16-23 (cfg-driven, zero literals)
+  neural_conv_mode: "scalar"          # options: scalar | hidden_states
+  neural_conv_dims: 8
+  forecast_horizon: 4
+  use_full_model: false               # safety switch to enable full Kronos transformer
+  max_context_length: 64              # guard for memory (e.g. AMD RX 560)
+  mixed_precision: true
```

**structural_engine.py** (expose in neural_slots):
```diff
        "confidence_min": thr["reversal_confidence_min"],
+    }
+    # Phase 1 neural config for full Kronos conviction (from neural: section or defaults)
+    neural_cfg = cfg.get("neural", {})
+    neural_slots.update({
+        "neural_conv_mode": neural_cfg.get("neural_conv_mode", "scalar"),
+        ...
```

**kronos.py** (KronosPredictor __init__ + compute_neural_conviction major upgrade):
- Added self.neural_* flags from neural_slots.
- compute now:
  - If scalar or !use_full_model or no model: old embed+norm path, return float.
  - Else: normalize, truncate to max_ctx, encode to ids, decode_s1 for context hidden, pool 8 stats (mean/std/max/min/last/norm/q25/q75), return list.
  - Graceful except -> scalar 0 or [0]*dims.
- Minor scalar mean handling in generate for amp compatibility.

**reversal_signature_miner_sovereign.py**:
- Compute neural_conv (now possibly list).
- neural_conv_scalar = mean if list (for amp, return "neural_conviction", some dna aux).
- dna 16-23: if list of >=8 assign distinctly, else replicate (backward).
- Updated return neural_conviction to scalar.

**test_end_to_end.py**:
- After nc = compute... : if list, assert len==8, print sample.

**validate_sovereignty.py**:
- After required sections: check/report neural config presence (mode, use_full).

## Validation Gate
- `python -c "from config.utils... import get_sovereign_config; cfg=...; print(cfg.get('neural'))"` → neural section present.
- `python config/validation/validate_sovereignty.py` → reports neural config.
- With use_full_model=false (default): behavior identical, E2E passes as before.
- To exercise full (if models present): edit params neural.use_full_model: true ; rerun miner/E2E; check logs for features diversity, assert 8 in E2E.
- `python test_end_to_end.py` (light or full) — now prints "neural features (8 distinct expected)" when list.
- Miner per-symbol: still prints scalar nc; dna_vector will have distinct slot_16..23 when enabled.
- No breakage to slot_15 veto (first), Option B, dual-mode, dna 32 keys, etc.

## Sovereignty & Constraints
- Zero inline literals: all new keys read via .get(..., default) from params/neural_slots/ctx.
- model_dir / tokenizer_dir from sovereign_ctx["storage"] (params).
- slot_15 absolute veto still first in miner (before any neural call or dna build).
- Dual-mode / Option B / reversal miner / 1h alt perps / full causal / 12-field kline / HDBSCAN on structural — untouched.
- Graceful degradation preserves E2E real side-effects when no model or scalar mode.
- Low-cost default (no full forward unless explicitly enabled in params).

**File written:** `docs/KRONOS_V1_ALT_FULL_KRONOS_NEURAL_FEATURES_UPGRADE_SUMMARY.md` (this document).

Task complete per the surgical phased plan. The upgrade enables rich distinct neural features from the actual Kronos Transformer hidden states (via existing decode_s1 context pooling) for slots 16-23 when configured, while defaulting to previous scalar behavior. All from params, sovereign, no literals. 

Next: set use_full_model true (if models available), re-run E2E/miner, observe feature diversity in logs/dna, extend to forecast_paths if desired. The Reality Audit and docs realignment remain consistent.