# KRONOS V1-ALT — 32-Slot Causal DNA vs. Reality Architectural Audit Summary

**Phase:** Deep line-by-line architectural audit focused exclusively on the "32-Slot Causal DNA vs. Reality" inconsistency. Inspected: kronos_module/model/structural_engine.py, kronos_module/model/kronos.py, config/mining/reversal_signature_miner_sovereign.py, docs/slot_reference_manual.md, params_yaml.txt, test_end_to_end.py, README.md, and related recent summaries (DNA vector implementation, slot reference manual update, HDBSCAN post-hoc, miner logging/validation, reorg, git push hygiene, etc.).

**Scope:** Evidence-based, no hallucinations. All claims grounded in direct reads of source + docs. Prioritize fixes that maintain "zero inline literal / sovereign config-driven" doctrine. References recent reorg (docs/ + config subpackages), essential files, diff cleanup to docs/diffs/, and the pattern of surgical smallest-diff changes.

**Output Structure:** Follows the exact requested audit format (A/B/C) while using the canonical KRONOS summary MD conventions (Executive Summary, detailed findings with file:line, Reality vs. Claim matrix, Root Cause, Concrete Proposal with short/medium/long-term + metrics + doc updates, Validation, Sovereignty preserved).

## Executive Summary

The system is a robust, fully sovereign, real-shards (Option B), cfg-driven (params_yaml.txt v3.1 → neural_slots via get_dual_mode_context / orchestrate_sovereign) reversal signature mining engine with an absolute structural veto (slot_15 first) and dual-mode (individual primary + ablatable global prior). 

However, there is a significant gap between high-level claims ("Full 32-slot causal DNA", "Kronos-Mini Transformer Hidden States" for neural slots, sophisticated causal pattern-discovery) and delivered implementation:

- Only **8 structural proxies** (not the full ideal formulas for HMM, proper R/S, EWM absorption, etc.).
- **Neural "conviction"** (slots 16-23) is a single scalar (L2 norm of tokenizer.embed on short normalized tail) **replicated 8×**.
- DNA vector (32 keys) is real structural 8 + replicated neural 8 + 16 simple derived proxies (many reusing the same recent_return / vol_spike / slot15 / neural_conv variables + explicit `neural["strength_add"]-neural["strength_add"]` zeros).
- HDBSCAN phylum is post-hoc **only on the 8 structural slots**, not the full DNA.
- slot_15 is a useful ad-hoc weighted heuristic gate (enforced early and hard), not a deep sovereign composite.
- No training/fine-tuning/gradient flow in hot path; full Kronos model forward is stubbed (`pass`); heavy graceful degradation to 0.0.

The engine is a **sophisticated configurable heuristic microstructure scoring system** (short-window momentum/vol spike + structural proxies + early veto + embedding-norm gate) rather than a complete deep causal 32-slot DNA discovery system. This is pragmatic for 530+ altcoin 1h USDT perps scale but inconsistent with documentation and summary claims.

All values remain cfg-driven (no new inline literals introduced in this audit). Recent work (full kline 12-field, vectorized 10M+ paths, dna_vector construction, HDBSCAN overlay, miner validation checks for 32-key dna + non-NaN + slot_15, slot manual update to document "Current Implementation", reorg to docs/, git push of hygiene) made the pipeline real and E2E-passing, but the naming/claims were not fully realigned.

## A. Detailed Technical Summary

### Structural Slot Proxies and Stubs (Slots 00, 04, 07-11, 15 veto composite)

**Implemented slots** (only these 8; returned from `compute_slots_sovereign`):

From [kronos_module/model/structural_engine.py](/F:/kronos_v1_alt/kronos_module/model/structural_engine.py) lines 86-176 (`compute_slots_sovereign(df, neural)`):

- **slot_00** (bid-ask delta absorption proxy): 
  ```python
  taker_buy = df.get('taker_buy_base_volume', vol * neural["strength_add"] / (neural["strength_add"] + neural["strength_add"]))
  ... low_prox / high_prox via rolling min/max + reversal_factor gate ...
  buy_proxy = (taker_buy * (low_prox < ...)).rolling(w).mean().iloc[-1]
  slot_00 = (buy_proxy - sell_proxy) / (buy_proxy + sell_proxy + eps)
  ```
  Comment: "# slot_00 bid-ask proxy on extremes/vol (no aggtrades)". Uses full 12-field kline via .get with fallback that itself uses the eps value.

- **slot_04** (fractal exhaustion / hurst approx):
  ```python
  log_ret = np.log( (df['close'] / df['close'].shift(1) + eps).clip(lower=eps).values )
  ... cum_dev, R = max - min rolling, S = std + eps, H = (R / S) / w
  slot_04 = neural["strength_add"] - H
  ```
  Comment: "R/S simplified". Vectorized for 10M+.

- **slot_07** (volume-price divergence): Vectorized price_chg / vol_chg (on quote_volume) using .values + np.concatenate + clip + rolling mean / std + eps.

- **slot_08** (HMM regime classifier proxy):
  ```python
  # slot_08 HMM proxy (vol regime)
  recent_vol = vol.rolling(w).std().iloc[-1]
  long_vol = vol.rolling(long_w).std().iloc[-1] + eps
  slot_08 = min(clamp_max, max(clamp_min, recent_vol / long_vol if long_vol > eps else clamp_min))
  ```
  Pure vol std ratio clamp. No GaussianHMM, no refitting.

- **slot_09** (volume delta pressure / VPIN proxy): `(taker_buy - (vol-taker_buy)).rolling.mean() / total + eps`.

- **slot_10** (wick-to-body exhaustion): Last-bar only candle_range / body + body_pct < neural["reversal_factor"] gate, then normalize by rolling hl range + clamp.

- **slot_11** (S/R proximity): Rolling max/min as nearest levels + dist normalized by close * reversal_factor + eps → clamp formula.

- **slot_15** (veto composite):
  ```python
  raw_w = {"slot_00": strength_mult, "slot_04": variation, "slot_07": strength_mult, "slot_08": strength_add, "slot_09": strength_add, "slot_10": strength_mult, "slot_11": variation}
  weights = {k: v / tot for k,v in raw_w.items()}
  norm_slots = {k: clamp(slot_k) for ...}
  slot_15 = sum(weights[k] * norm_slots[k] ...) * (conf_min / conf_min)
  slot_15 = min/max(clamp)
  ```
  Ad-hoc linear combination using neural keys as weights. Normalized + clamped.

**Numerical / stability / vectorization issues:**
- `eps = neural["strength_add"]` (0.55 from params) reused for almost every guard, zero, and even the taker fallback. Couples stability to a strength hyperparam.
- Many full-history `.rolling(w, min_periods=min_p).iloc[-1]` after loading entire shard (explicit 10M+ inefficiency comments in the file).
- Good vectorization in places (close_vals[1:]/close_vals[:-1] for price_chg, np for log_ret).
- Strict causal: negative shifts/rolling only. Verified in comments and code.

**Enforcement in miner** ([config/mining/reversal_signature_miner_sovereign.py](/F:/kronos_v1_alt/config/mining/reversal_signature_miner_sovereign.py) line 54):
```python
slots = compute_slots_sovereign(df, neural)
if slots.get('slot_15', eps) < neural["confidence_min"]:
    return {"confidence": eps - eps, "signature": None}
```
Absolute first gate (before dna_vector, neural amp, or save). Re-checked in logging/validation (lines 167-177).

**Vs. slot_reference_manual.md claims:**
The manual contains the ideal formulas (GaussianHMM refit every hmm_refit_interval, proper log(R/S)/log(n) for Hurst, EWM for slot_00, exp(-min dist) for SR, etc.). However, it was updated in a prior phase (see KRONOS_V1_ALT_SLOT_REFERENCE_MANUAL_UPDATE_SUMMARY.md) to add "**Current Implementation**" subsections that honestly document the proxies (e.g., slot_08: "Simple regime proxy (no real HMM...)"; neural 16-23: "single neural_conv value replicated"; aux as "simple proxies"). Layer overview table already notes "Currently: single neural_conviction (L_p) replicated (placeholder)".

### Neural Conviction Implementation (Slots 16-23 and gating)

From [kronos_module/model/kronos.py](/F:/kronos_v1_alt/kronos_module/model/kronos.py):

**KronosPredictor.compute_neural_conviction** (lines 585-612):
```python
if not ... _model_loaded or tokenizer is None: return 0.0
df = df_or_slots.tail(min(len(df_or_slots), l))  # l = neural["min_history"]
x = df[cols].values... ; x = (x - mean) / (std + eps)  # eps = strength_add
x_emb = torch.from_numpy... 
emb = self.tokenizer.embed(x_emb)  # ONLY the initial nn.Linear embed
if self.model is not None:
    try:
        # real model forward path active (Kronos loaded from sovereign_ctx["model_dir"]...)
        pass
    except Exception:
        pass
return torch.norm(emb, p=2, dim=-1).mean().item()
except Exception:
    return 0.0
```

- Primarily **L2 norm of the tokenizer's first embedding layer** on a short normalized recent price/vol window (open/high/low/close/volume/amount). Not full transformer hidden states, not conditioned on structural slots 00-15.
- Full Kronos model forward is explicitly stubbed with `pass`.
- No training code, no fine-tuning, no gradient flow, no loss anywhere in the mining or prediction hot path.
- Loading via `from_pretrained` from sovereign_ctx paths (params storage: kronos_small_dir / kronos_tokenizer_dir under models_dir; note spelling "kronus_module" in some params storage entries vs actual kronos_module dir). Gitignored.
- Reproducibility: Depends on external pretrained HF weights + local files. No SHA256 pinning in the inspected code.
- Temporal: Recent tail window only (vs. structural full-shard rolling stats).
- Used for amplification in miner (line 66) and generate paths. Also in E2E harness (test_end_to_end.py:85).

In miner: neural_conv starts as `neural["confidence_min"] - neural["confidence_min"]` (0-expr), updated if predictor present, printed, then used in `amplified = reversal_strength * (factor + neural_conv * variation)`.

Comments acknowledge "GPU support hint" and "HYBRID-V5 slot gating" but the hot-path conviction remains the embed-norm.

### 32-Slot DNA Vector Construction and Redundancy (in miner + structural)

Built in `mine_reversal_signature` ([config/mining/reversal_signature_miner_sovereign.py](/F:/kronos_v1_alt/config/mining/reversal_signature_miner_sovereign.py) lines 75-87), **after** slot_15 veto and neural_conv calc:

```python
dna_vector = dict(slots)  # 8 structural (00,04,07-11,15)
for k in [16,17,18,19,20,21,22,23]:
    dna_vector[f"slot_{k}"] = neural_conv   # exact same scalar, 8 times
vol_delta = (volume[-1] - volume[-window:].mean()) / (volume[-window:].mean() + eps) ...
mfe_proxy = slot15 * (factor + vol_spike * neural["variation"])
dna_vector["slot_24"] = vol_delta
dna_vector["slot_25"] = mfe_proxy
dna_vector["slot_26"] = neural_conv
dna_vector["slot_27"] = abs(slot15 - neural_conv)
dna_vector["slot_28"] = neural["strength_add"]-neural["strength_add"]  # 0
dna_vector["slot_29"] = slot15 * neural_conv / (neural["strength_add"] + slot15)
dna_vector["slot_30"] = mfe_proxy
dna_vector["slot_31"] = neural_conv
```

Exact block also quoted verbatim in slot_reference_manual.md "Current DNA Vector Construction" section and in the original DNA implementation summary.

**HDBSCAN / phylum** (miner lines 200-222, post-loop only):
- Collects X using only structural keys `sk = [0,4,7,8,9,10,11,15]`.
- Fits HDBSCAN (cs/ms derived from neural strength_* via 0-exprs).
- Overwrites saved Parquet files with a `"phylum"` **column** ("phylum_N" or "noise").
- Phylum is **not** placed inside the dna_vector dict at construction time. HDBSCAN summary confirms "on the structural_slots matrix".

**Redundancy & correlation critique:**
- 8 neural slots are bitwise identical.
- Aux/metadata heavily reuse the same in-scope variables (recent_return, vol_spike, window, slot15, neural_conv, factor=strength_add/strength_add, eps).
- Multiple slots are linear transforms or copies of each other.
- This severely reduces effective dimensionality of the "32-slot" vector. Impacts HDBSCAN (which ignores most of it) and any downstream analysis.
- Causality: Generally good (tail slices, negative shifts). NaN/padding: miner logging explicitly warns on missing neural_conv, non-32 dna, NaN in structural (lines 169-179). Adaptive window in miner uses neural reversal_window + reversal_factor.

**Additional issues:**
- Symbol-hash variation (miner:50-52): `hashlib.md5(symbol). % hash_mod * variation` — non-causal per-symbol bias.
- Validation in E2E (test_end_to_end.py:127-128, 171-172 in miner): asserts slot_15 >= min_conf and len(dna)==32 (which passes because of the padding construction, even with redundancy).

### Overall Architectural Inconsistency vs. Claims

**High-level claims** (README.md:3 "Full 32-slot causal DNA", slot_reference_manual ideal formulas + layer descriptions, multiple DNA/HDBSCAN/summary MDs, E2E harness language):
- Full 32 distinct causal features from deep microstructure + transformer latents.
- Sovereign core with orthogonal neural veto.
- Zero literals, dual-mode, Option B real shards only.

**Delivered reality** (code + manual's own "Current Implementation" sections + DNA vector summary admission of "placeholder" + HDBSCAN summary):
- 8 causal microstructure heuristic proxies (using full 12-field kline + neural params).
- 1 distinct neural signal (short-window embed L2) replicated across 8 slots.
- 16+ simple derived proxies + zeros.
- Early hard structural veto (valuable).
- Post-hoc clustering on structural subset only.
- The slot manual was explicitly updated in a prior surgical step to document the gap (KRONOS_V1_ALT_SLOT_REFERENCE_MANUAL_UPDATE_SUMMARY.md).

**Reality vs. Claim matrix**

| Aspect                  | Claim (README / ideal manual formulas / summaries) | Reality (code + "Current Implementation" notes) |
|-------------------------|----------------------------------------------------|-------------------------------------------------|
| Structural slots (8)   | HMM, proper R/S log(R/S)/log(n), EWM absorption, full formulas | 8 proxies (vol-ratio for 08, last-bar wick for 10, rolling SR dist for 11, strength_add - H for 04, etc.) |
| Neural 16-23           | Kronos-Mini Transformer hidden states / bottleneck (8 distinct dims) | Single scalar (tokenizer.embed L2 norm on tail) replicated 8× (kronos.py:603,610; miner:76-77) |
| Neural conviction      | Rich model forward / deep conviction               | tokenizer.embed + torch.norm(p=2).mean(); model forward = pass; fallback 0.0 |
| DNA vector (32)        | Full 32-slot causal DNA                            | dict(slots) + replication loop + vol_delta/mfe/conv/residual/0-expr proxies |
| HDBSCAN phylum         | Post-hoc ontology on full DNA                      | Only on structural 8 keys (miner:202); "phylum" column added post-loop |
| slot_15                | Sovereign weighted gate / robust composite         | Ad-hoc neural-key weights + hard early return (miner:54) |
| Overall character      | Deep causal pattern-discovery system               | Configurable heuristic scorer + embed-norm gate + early veto |
| Sovereignty            | Zero literals, all from params via cfg             | Mostly (neural_slots everywhere); exceptions: heavy eps reuse, hash_mod symbol bias, some project_root fallbacks |

## B. Root Cause Analysis

- **Evolutionary surgical process**: Strict "ONLY edit X file(s), smallest diff, output precise diffs, give summary md" discipline (visible across DNA vector summary, slot manual update, miner logging, HDBSCAN, reorg, essential files, git push hygiene). Focus was on making the pipeline real (Option B shards, slot_15 veto first, dna_vector 32 keys present, E2E asserts pass, no placeholders in hot paths) rather than making every slot semantically rich.
- **Sovereignty + practicality over feature completeness**: Heavy investment in bootstrap (KRONOS_PARAMS_PATH, sys.path, get_sovereign_config), dual-mode ctx, neural_slots injection, graceful degradation, full 12-field kline, vectorized 10M+ comments, and reorg hygiene. Expensive components (per-bar GaussianHMM refits, full Kronos forward in mining loop for 530 symbols, distinct embedding dimensions, rolling percentile buffers) were left as aspirational.
- **External model pragmatics**: Kronos (HF + custom nn modules in kronos.py) is a full sequence model. Using only the cheap initial `embed` + norm for the "neural conviction gate" (with full model path stubbed) allowed "neural" claims + orthogonal gating without requiring training pipelines or high per-symbol cost on altcoins.
- **Documentation & claim lag**: The slot_reference_manual was updated post-implementation (KRONOS_V1_ALT_SLOT_REFERENCE_MANUAL_UPDATE_SUMMARY.md) to add "Current Implementation" blocks. However, top-level claims in README, DNA implementation summary ("full 32-slot causal DNA"), and subsequent push summaries continued aspirational language because the surgical task was "make the vector exist and pass 32-key checks."
- **Altcoin/scale realities**: Variable history shards, low-liquidity symbols, 1h perps, large target_count=530. Cheap rolling proxies + one scalar neural gate + absolute early veto are far more operable than heavy per-bar models. The hash_mod variation and strength_add-as-eps reuse are symptoms of rapid config-driven iteration.
- **Reorg context**: Recent reorg (KRONOS_V1_ALT_REPO_REORG_SUMMARY.md + git push) + essential files + diff cleanup to docs/diffs/ cleaned structure but did not alter the core feature implementations or retroactively tighten claims.

## C. Concrete Proposal to Resolve the Inconsistencies

Prioritized, actionable, and sovereignty-preserving (all new values must come from params_yaml.txt thresholds / neural_slots / storage; no new hard literals; keep slot_15 absolute first; preserve Option B + dual-mode + real shards).

### Short-term fixes (immediate, smallest surface)

- **Documentation realignment (highest priority, no code change)**: 
  - Update README.md Architecture section: replace "Full 32-slot causal DNA" with accurate description + pointer to slot_reference_manual "Current Implementation".
  - In slot_reference_manual.md: Promote the "Current Implementation" subsections and add a prominent top box: "V1-ALT Current Delivered System (as of 2026): 8 structural proxies + 1 distinct neural scalar (embed L2 norm) replicated 8× + 16 derived proxies. HDBSCAN on structural subset only. slot_15 is the hard configurable gate."
  - Create or update a dedicated "DNA Reality vs. Aspirational" note in the main GITIGNORE_README_STRUCTURE_SUMMARY.md or a new cross-ref.
- Add `scripts/analyze_dna_redundancy.py` (cfg-driven only): load signatures_individual_dir Parquets, extract dna_vector dicts into matrix, compute correlation matrix (pandas/numpy), effective rank / PCA, % zero neural_conv, slot_15 distribution, veto rate per symbol. Write report to logs/ + a summary MD fragment. Run as part of post-mine or E2E.
- Technical debt (still cfg-driven):
  - structural_engine.py:105 taker_buy fallback — replace self-referential strength_add expr with a dedicated neutral value from neural (e.g. add "taker_buy_fallback_ratio" under thresholds).
  - Centralize a true small `eps` key in params thresholds instead of overloading reversal_base_strength_add.
  - Consider deprecating or documenting the symbol-hash variation (miner:50-52) as a non-causal bias term.
  - Align params storage "kronus_module" spelling with actual "kronos_module" dir (or make loading fully tolerant).
- Extend `config/validation/validate_sovereignty.py` with a non-fatal "feature completeness" section that reports current layer cardinalities (8 structural, 1 neural signal, etc.) and cross-references the manual.

### Medium-term improvements

- Explicitly decide the sovereign structural set size: Either expand compute_slots_sovereign with a few additional cheap causal full-kline features (documented in params) or declare the current 8 as the complete V1-ALT structural layer.
- Improve neural gate: Option A — use more of the tokenizer (or a cheap decode/encode path) to produce distinct values for slots 16-23 instead of pure replication. Option B — rename the signal to "embed_norm_gate" in code/docs and treat the block transparently as replicated. Keep model forward stubbed or wire it only for high-conviction candidates.
- Run HDBSCAN (or a follow-on clustering) on a de-duplicated or full dna_vector (or structural + distinct neural components). Store the features actually used for clustering.
- Build on existing 10M+ / memory comments: add tail-only or incremental rolling computation for structural slots when history length >> reversal_window (controlled by params).
- Add liquidity / data-quality guards inside mining using existing data_fetch thresholds (min_24h_volume_usd, etc.) before computing slots.

### Long-term architectural recommendations

- Align toward the HYBRID-V5 patterns repeatedly referenced in code comments and phase docs (pre-computation of richer features, post-hoc ontology / global prior, ablatable injection) while strictly preserving: absolute slot_15 structural veto as first gate, Option B real-shards-only, dual-mode, zero literals via params, altcoin scale.
- Add rigorous forward validation on the mined signatures: for high-confidence signatures, measure realized forward returns / MFE / hit rate over configurable horizons (using the actual subsequent bars from shards). Compute precision/recall-style metrics for "reversal edge" prediction. Store as additional columns or separate validation Parquets. This is the only objective way to assess whether the current heuristic + norm gate has edge on low-liquidity alts.
- Optional "lite vs full" neural path: cheap embed-norm for every bar during mining; expensive full Kronos forward only for candidates that pass slot_15 + neural_conv thresholds (or during global prior construction).
- Track effective dimensionality, feature correlations, and per-phylum statistics as first-class outputs (written alongside phylum).

### Specific metrics / validation steps to add (cfg-driven)

- Correlation matrix + count of |corr| > 0.7 pairs across the 32 dna_vector dimensions (across all high-quality signatures).
- Effective rank of the dna matrix (or PCA cumulative explained variance at 95%).
- slot_15 veto firing rate (% of processed bars that returned early) globally and per-symbol.
- % of signatures with neural_conv == 0 (or < threshold).
- Phylum size distribution + intra-phylum dna variance.
- Forward outcome stats for high-quality signatures: distribution of next-N-bar returns, realized MFE vs. slot_25/30 proxies.
- All runnable via scripts (e.g. `python scripts/analyze_dna_redundancy.py --output logs/dna_audit_YYYYMMDD.md`). Include in E2E harness or post `mine_all_shards`.

### Suggested updates to docs and sovereignty validator

- README.md, top-level claims in future summaries, and Architecture section: accurate one-sentence description + "See slot_reference_manual.md (Current Implementation sections) for the delivered 32-slot reality."
- slot_reference_manual.md: Keep ideal formulas in a clearly labeled aspirational / target section. Make current delivered system the primary documented reality.
- Sovereignty validator: Add the layer cardinality report + "proxy awareness" (scan for known stub comments like "# slot_08 HMM proxy", "replicated", "placeholder" and surface them).
- Reference this audit summary and the slot manual update summary in the main structure doc.

## Validation Gate

**Commands (set KRONOS_PARAMS_PATH first):**
- Reproduce findings: Inspect the 4 core files + slot_reference_manual.md + params_yaml.txt thresholds section + recent summaries in docs/ (DNA vector, slot manual update, HDBSCAN, miner logging, reorg, git push).
- Run redundancy analysis (once the short-term script exists): `python scripts/analyze_dna_redundancy.py`
- Re-run E2E: `$env:KRONOS_PARAMS_PATH='F:/kronos_v1_alt/params_yaml.txt'; python test_end_to_end.py`
- Miner + dna inspection: `python -c "import pandas as pd, glob, os; ... load a _signature.parquet and print len(dna_vector), list(dna_vector.keys())[:10], set of neural slots 16-23 values, phylum column"`
- Sovereignty: `python config/validation/validate_sovereignty.py`
- After doc updates: `git diff` on README + slot_reference_manual.md; confirm no new literals.

**Evidence files referenced (non-exhaustive):** structural_engine.py:86-176, kronos.py:585-612 (and predictor __init__/generate), reversal_signature_miner_sovereign.py:28-101 + 200-222, slot_reference_manual.md (ideal + Current Implementation + DNA construction block), params_yaml.txt (thresholds + storage), test_end_to_end.py (asserts + harness), README.md, KRONOS_V1_ALT_FULL_32_SLOT_DNA_VECTOR_SUMMARY.md, KRONOS_V1_ALT_SLOT_REFERENCE_MANUAL_UPDATE_SUMMARY.md, KRONOS_V1_ALT_HDBSCAN_ONTOLOGY_POSTHOC_SUMMARY.md, KRONOS_V1_ALT_MINER_LOGGING_VALIDATION_SUMMARY.md, KRONOS_V1_ALT_REPO_REORG_SUMMARY.md, KRONOS_V1_ALT_GIT_PUSH_DIFF_CLEANUP_SUMMARY.md, and docs/diffs/ artifacts from prior surgical steps.

## Sovereignty & Constraints Preserved

- Zero new inline literals in this audit or proposed fixes (all scaling, windows, eps, clamps, zeros, factors continue to derive exclusively from params_yaml.txt via cfg / neural_slots / sovereign_ctx).
- Dual-mode (individual primary + ablatable global prior), Option B (real shards only via discover_from_shards or provided list), reversal miner with absolute slot_15 structural veto first (before dna/neural amp/save), full 12-field kline, causal rolling/negative slices, KronosPredictor(sovereign_ctx=...), E2E real asserts, HDBSCAN post-processing, 10M+ vectorization/GPU/memory comments — all untouched.
- Recent hygiene (reorg to clean docs/ + config/ subpackages, essential __init__/requirements, diff artifacts moved to docs/diffs/ with ignore rule, git push of 0daf100) remains intact.
- Proposed changes (docs realignment, new analysis script, small cfg-driven technical debt fixes, validator extension) are additive or clarifications only; they strengthen the ability to reason about the current delivered system without breaking the sovereign pipeline.

**File written:** `docs/KRONOS_V1_ALT_32_SLOT_CAUSAL_DNA_REALITY_AUDIT_SUMMARY.md` (this document).

Task complete per the requested audit format and the project's long-standing "give summary md file" convention after deep work. The audit is evidence-based and positions the team to either (a) honestly document the current pragmatic heuristic engine or (b) incrementally evolve it toward richer features while keeping the sovereignty doctrine. All prior E2E-passing real-side-effect guarantees and cfg-driven nature are preserved. 

See also the diffs/ folder for prior precise change records and the slot_reference_manual.md for the most up-to-date "Current Implementation" documentation.