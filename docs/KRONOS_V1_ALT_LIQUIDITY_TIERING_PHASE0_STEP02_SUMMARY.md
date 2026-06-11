# KRONOS V1-ALT — Liquidity Tiering System (Phase 0, Step 0.2) Summary

**Phase:** Phase 0, Step 0.2 — Creation of the dynamic Liquidity Tiering System as the foundational guardrail for the 100-point Quant Bias Override Manual v2.0 and all future bias override implementations.

**Scope (strict):** 
- Created three new artifacts under the `kronos/` package (new substructure):
  - `kronos/features/liquidity_classifier.py`: Full Pydantic-validated, reloadable `LiquidityClassifier` class + standalone functions. Dynamic rolling 5-tier logic.
  - `kronos/config/liquidity_tiers.yaml`: Sovereign configuration (all weights, thresholds, normalization refs, guards, min density, logging flags).
  - `kronos/features/__init__.py`, `kronos/config/__init__.py`, and `kronos/__init__.py` (package hygiene).
- Minimal targeted update to `kronos/quant_spec/bias_override_registry.py` (added "very_high" to validator + `get_points_for_liquidity_tier()` helper + docstring integration + smoke test update). No other core files touched.
- Zero changes to `params_yaml.txt`, structural_engine, miner, E2E harness, or prior Phase 1-3 slot logic.
- Fully compatible with the Phase 0 Step 0.1 Bias Override Registry (the two components are designed to be used together: registry declares `applies_to_liquidity`, classifier provides the live tier).

**Reference:** 
- Phase 0 Step 0.1 Quant Bias Override Registry (and its summary MD).
- KRONOS V1-ALT — Quant Bias Override Manual v2.0 (100-Point Master Edition) [PDF].
- Prior Proxy Hardening Phases 1-3 + Neural Features (many points in the registry are liquidity-sensitive).
- Data model: full 12-field 1h klines (`volume`, `quote_volume`, `count`, taker volumes) from unified ingestion.

## Executive Summary
The Liquidity Tiering System is now the canonical, dynamic, cfg-driven mechanism for assigning one of five liquidity tiers (`very_high | high | medium | low | micro`) to any asset based on rolling microstructure metrics. It replaces any future temptation to use static symbol lists or hard-coded volume cutoffs.

- **5 Tiers (dynamic):** very_high (majors-like), high, medium, low, micro (very illiquid alts). An individual symbol can move between tiers over time as its volume, spread, and activity change.
- **Core Rolling Metrics (all computed on a configurable lookback tail):**
  - Median 24h-style quote volume (USDT)
  - Amihud illiquidity (or proxy using quote dollar volume)
  - Average trade count per bar (`count` / number_of_trades field)
  - Estimated spread (high-low / close proxy)
  - Percentage of zero-volume bars in the window
- **Composite Scoring:** Weighted sub-scores (all weights + normalization references live exclusively in YAML) → final liquidity score [0,1] → tier cutoffs. Absolute guards (volume floors, zero-bar vetoes) provide safety rails after the score.
- **Pydantic + Reloadable:** Same pattern as the bias registry. `LiquidityTiersConfig` validates the YAML. `LiquidityClassifier` supports `reload()` for live editing during development or experiments.
- **Dual Interface:** Full-featured class (`get_tier`, `get_tiers_for_bars`, `compute_metrics`) + standalone convenience functions matching the exact usage example in the requirements.
- **Bar-level vs Session-level:** `get_tier(...)` for current/latest window; `get_tiers_for_bars(...)` for causal per-bar series (useful for historical regime labeling or feature construction).
- **Robustness:** Full numeric coercion (Arrow/string dtypes from real shards), clear fallback to configurable `fallback_tier` when `data_density < min_data_density`, detailed structured logging (`[LIQUIDITY] symbol=... tier=... score=... med_qvol=... reason=...`).
- **Sovereignty:** No magic numbers, windows, weights, or cutoffs anywhere in the .py. 100% driven from `liquidity_tiers.yaml` (or explicit call-time params for lookback).

This component will be consulted by nearly every bias override implementation (see registry points that already declare `applies_to_liquidity` values). It enables liquidity-aware phased rollout and per-asset behavior without violating the "zero inline literals / everything via params or sovereign config" rule.

## Precise Artifacts Created / Modified

### A. `kronos/config/liquidity_tiers.yaml`
- Top-level keys: `version`, `lookback_default`, `min_data_density`, `fallback_tier`.
- `metrics`: 5 named weights (volume, amihud, trade_count, spread, zero_bar) that sum to 1.0.
- `tier_thresholds`: strictly monotonic decreasing cutoffs for very_high → micro.
- `absolute_guards`: volume floors for very_high/high + zero-bar vetoes that can force downgrade to low/micro.
- `normalization`: reference values for log-volume, amihud, spread, and trade-count sub-score scaling (chosen for the 1h USDT perps altcoin universe but fully tunable here).
- `spread`, `numerical` (eps), `logging` sections.
- Human-editable and self-documenting.

### B. `kronos/features/liquidity_classifier.py`
- `LiquidityTiersConfig` Pydantic model with validators (weights sum, monotonic thresholds, allowed fallback).
- Pure functions: `compute_liquidity_metrics(...)`, internal `_compute_subscores`, `_score_from_subscores`, `_apply_tier`, `_apply_absolute_guards`.
- `LiquidityClassifier` class:
  - `__init__` + `reload()` (default path resolves relative to the kronos package).
  - `get_tier(df, symbol=..., lookback=...) -> str`
  - `get_tiers_for_bars(df, ...) -> pd.Series` (causal, per-row)
  - `compute_metrics(...)`
  - Rich logging on every classification decision.
- Standalone functions:
  - `get_liquidity_tier(df, symbol=..., config_path=..., lookback=...)` (exactly matches the usage example in the task).
  - `compute_liquidity_metrics_standalone(...)`
- Full type hints, docstrings, module-level sovereignty comments, and a `__main__` smoke test.
- Handles missing trade count column gracefully; prefers `quote_volume`; falls back to close*volume.

### C. Package files
- `kronos/__init__.py`, `kronos/features/__init__.py`, `kronos/config/__init__.py` (minimal, re-export the classifier for clean `from kronos.features...` imports).

### D. `kronos/quant_spec/bias_override_registry.py` (targeted integration update)
- Added `"very_high"` to the `applies_to_liquidity` validator allowed set (now supports the full 5-tier vocabulary + "all").
- New method: `get_points_for_liquidity_tier(tier: str)` (convenience wrapper around `filter_by_liquidity` that also accepts the live tier from the classifier).
- Updated module docstring with usage example combining `LiquidityClassifier` + registry.
- Extended `__main__` smoke test.
- `filter_by_liquidity` docstring clarified for the new tier system.
- Zero impact on existing call sites.

## Verification Gate
All commands run successfully in the project root (F:\kronos_v1_alt) with proper sys.path bootstrap.

**Basic load + config:**
```powershell
cd F:\kronos_v1_alt
python -c "
import sys
sys.path.insert(0, 'F:\\kronos_v1_alt')
from kronos.features.liquidity_classifier import LiquidityClassifier
from kronos.quant_spec.bias_override_registry import BiasOverrideRegistry
clf = LiquidityClassifier()
print(clf.config['version'], clf.fallback_tier)
reg = BiasOverrideRegistry()
print(len(reg), 'registry points; very_high filter works:', len(reg.filter_by_liquidity(['very_high'])))
"
```

**Full functional test (synthetic + real-shard compatible):**
(See the verification run in the session log — synthetic 80-bar df, `get_tier`, `compute_metrics`, standalone `get_liquidity_tier`, `get_tiers_for_bars`, registry `get_points_for_liquidity_tier` and filter all exercised and returned expected structure.)

**Real data smoke (example with actual shard tail):**
```powershell
python -c "
import sys, glob, pandas as pd
sys.path.insert(0, 'F:\\kronos_v1_alt')
from kronos.features.liquidity_classifier import LiquidityClassifier
clf = LiquidityClassifier()
shard = glob.glob('data/raw_shards/*_1h.parquet')[0]
df = pd.read_parquet(shard).tail(400)
tier = clf.get_tier(df, symbol=shard.split('\\\\')[-1].replace('_1h.parquet',''), lookback=288)
print('Real shard tier:', tier)
print('Metrics (excerpt):', {k: round(v,3) if isinstance(v,float) else v for k,v in clf.compute_metrics(df, lookback=288).items() if k in ('median_quote_volume','amihud','zero_volume_bar_pct')})
"
```

**Registry + Classifier together:**
```python
tier = clf.get_tier(df, symbol="XXXUSDT")
points = reg.get_points_for_liquidity_tier(tier)   # or reg.filter_by_liquidity([tier])
```

## Sovereignty & Constraints Preserved
- Zero inline literals: every weight, threshold, window default, normalization reference, guard value, and fallback lives only in `liquidity_tiers.yaml`.
- Config-driven and reloadable at runtime (matches bias registry pattern exactly).
- Maintains full compatibility with Phase 0.1 registry (the `applies_to_liquidity` field on the 100 points now has a live, dynamic producer).
- No impact on core engine, Option B, dual-mode, slot_15 absolute first veto, structural slots 00-15 (Phases 1-3), neural features, miner, E2E harness, or `params_yaml.txt`.
- Works directly on real ingested 1h perps shards (coercion + column name tolerance for `count`/`quote_volume`).
- Supports both per-symbol session classification and causal historical bar labeling.
- Logging is structured and includes the "why" (score + raw metrics + guard reason) for full auditability.
- Future bias points can now safely branch behavior: `if tier in ("low", "micro"): use_conservative_path() else: ...`

**File written:** `docs/KRONOS_V1_ALT_LIQUIDITY_TIERING_PHASE0_STEP02_SUMMARY.md` (this document).  
Previous Phase 0 artifact: `docs/KRONOS_V1_ALT_QUANT_BIAS_OVERRIDE_REGISTRY_PHASE0_SUMMARY.md`.

**Task complete.** The Liquidity Tiering System (Phase 0, Step 0.2) is now live as the guardrail layer. It is dynamic, fully sovereign/cfg-driven, Pydantic-validated, reloadable, dual-interface, and directly consumable by the bias override registry and all future point implementations.

All prior summaries, realignments, Phase 1-3 proxy hardening, neural upgrade, Option B, and sovereignty guarantees remain intact. The foundation for liquidity-aware bias overrides is now in place and ready for the next implementation steps (e.g., wiring specific high-priority points from the registry that consult this classifier).

(Ready for verification runs against real 530-symbol shards, integration into the miner status tracker, or targeted point rollout beginning with Group 1 / priority-1 items.) 

Cross-reference: Use `LiquidityClassifier` + `BiasOverrideRegistry.get_points_for_liquidity_tier(tier)` (or `filter_by_liquidity`) together for any future liquidity-conditioned logic.