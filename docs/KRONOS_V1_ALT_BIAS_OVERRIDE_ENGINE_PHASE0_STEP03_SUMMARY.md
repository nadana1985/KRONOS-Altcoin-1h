# KRONOS V1-ALT — Bias Override Engine (Phase 0, Step 0.3) Summary

**Phase:** Phase 0, Step 0.3 — Creation of the `BiasOverrideEngine`, the central thin orchestration / guardrail layer that unifies the Bias Override Registry and the Liquidity Tiering System.

**Created:**
- `kronos/quant_spec/bias_override_engine.py` (primary deliverable)
- Small enhancement to the smoke test in `kronos/quant_spec/bias_override_registry.py` (combined stack demonstration)

**Context:**  
This step follows directly after:
- Phase 0 Step 0.1 — Quant Bias Override Registry (100-point YAML + Pydantic registry)
- Phase 0 Step 0.2 — Dynamic Liquidity Tiering System (5-tier classifier + config)

The engine exists so that when we begin implementing the actual 100 points, the implementation code does not have to duplicate registry lookups, liquidity tier checks, status gating, or fallback decisions on every single bias override.

---

## Executive Summary

The `BiasOverrideEngine` is now the single place where all future bias override decisions are made.

It is a **thin orchestration layer**:
- It loads and holds live references to `BiasOverrideRegistry` and `LiquidityClassifier`.
- Its main job is to answer, for any `point_id`:  
  "Given the current registry status of this point and the live dynamic liquidity tier of this symbol, should we use the legacy `raw_value` or the new `override_value` the caller computed?"

Key behaviors:
- Automatically resolves the current liquidity tier (or accepts `force_tier` for testing).
- Respects the point's `status` (only "implemented", "validated", or "active" are treated as ready to apply overrides).
- Respects the point's `applies_to_liquidity` list (including the special value `"all"`).
- Returns the `raw_value` (safe legacy path) unless *all* gates are satisfied **and** the caller supplied an `override_value`.
- Emits structured, auditable logs for every decision (`[BIAS_OVERRIDE] point_id=... tier=... action=... reason=...`).
- Fully reloadable at runtime.
- Provides excellent diagnostics (`get_override_status`, `get_available_overrides`).

The engine deliberately contains **zero implementation** of any of the 100 quant replacements. Those live in the future point implementation sites.

---

## Precise Artifact & Changes

### 1. `kronos/quant_spec/bias_override_engine.py` (new)

Core class: `BiasOverrideEngine`

**Primary method:**
```python
cleaned = engine.apply_override(
    point_id="01",
    raw_value=old_calculation(...),
    df=recent_bars,
    symbol="SOMEALTUSDT",
    override_value=new_quant_version(...),   # optional
    force_tier=None,                          # optional (for testing)
    lookback=288,                             # forwarded to classifier
)
```

**Other public surface:**
- `reload()`
- `apply_overrides(list_of_dicts)` — batch version
- `get_available_overrides(liquidity_tier=None)` → list of point_ids ready for use at that tier (or any tier)
- `get_override_status(point_id, symbol, df, force_tier=None)` → rich diagnostic dict with:
  - `status`, `current_tier`, `applies_to_current_tier`, `is_implemented`
  - `recommended_action` ("pass_through" vs "apply_override_if_value_provided")
  - `reason`, `fallback_strategy` (from registry), `priority`, etc.
- `create_engine()` factory

**Design highlights (sovereignty & thinness):**
- No magic numbers or policy tables live in the engine except a very small, explicitly documented set of "active implementation statuses".
- All real policy lives in the two YAMLs + the point definitions.
- The engine only ever returns a value (raw or override). It never mutates data.
- `timestamp` parameter is accepted and logged for future time-aware rules but currently unused.
- Comprehensive docstring with the exact usage pattern future implementers should follow.

### 2. Update to `kronos/quant_spec/bias_override_registry.py`

- Extended the module's `__main__` smoke test with a short combined demonstration that imports and exercises `BiasOverrideEngine` together with the registry.
- This serves as the "integration smoke test" requested in the task.

---

## How This Engine Will Be Used When Implementing Actual Points

When we start turning "not_started" points into real code (e.g. point 01 "Hardcoded Alpha Threshold Bias", point 03 "Spatial Dimension Inflation Bias", etc.), the pattern will be:

1. The implementation site (could be inside `structural_engine.py`, a new `kronos/quant_spec/overrides/` module, the miner, or a dedicated bias layer) computes **both** versions:
   - The current/legacy/raw calculation (for safety and for points that are still disabled).
   - The new sovereign replacement described in the manual (`quant_replacement` field).

2. It then calls the engine as the final gate:

   ```python
   from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

   engine = BiasOverrideEngine()   # usually instantiated once at startup / in the orchestrator

   def compute_reversal_confidence(df, symbol, ...):
       raw = old_slot15_or_confidence_logic(df, ...)           # existing code path

       # The actual quant replacement for point "01"
       new_value = rolling_out_of_sample_quantile_veto(df, ...)

       # Let the engine decide
       final = engine.apply_override(
           point_id="01",
           raw_value=raw,
           df=df,
           symbol=symbol,
           override_value=new_value,
           lookback=288
       )
       return final
   ```

3. Benefits this gives us immediately:
   - While the point remains `status: "not_started"` in the registry → everyone always gets the raw value (zero risk of accidental activation).
   - When we flip the status to `"implemented"` (after backtests, walk-forward, etc.), the new logic activates automatically for symbols whose current dynamic tier is allowed by the point's `applies_to_liquidity`.
   - We can force a tier in tests: `force_tier="micro"` to verify conservative behavior.
   - `get_override_status("01", symbol, df)` becomes an instant diagnostic for why a particular symbol is (or is not) receiving the override.
   - Batch application and `get_available_overrides("low")` support phased/liquidity-aware rollout planning.
   - All decisions are logged in one consistent format for later analysis / dashboards.

This is exactly the "safer phased rollout", "centralized decision logic", and "better auditability" benefits listed in the task prompt.

---

## Verification

Successful runs (from this session):

- Full stack import of `BiasOverrideEngine` + `BiasOverrideRegistry` + `LiquidityClassifier`.
- `get_override_status` correctly reports `recommended_action="pass_through"` + `reason="status=not_started"` for current points.
- `apply_override` returns raw value when point is not implemented (even when `override_value` + `force_tier` are supplied).
- `force_tier` works for testing.
- `apply_overrides` (batch) works.
- `get_available_overrides()` correctly returns `[]` today (because no points have reached "implemented" status yet) and will populate as we activate points.
- Combined smoke test added to the registry's `__main__` executes without error.
- Engine's own rich `__main__` (synthetic data + status + force + batch) exercises the complete surface.

All sovereignty, Pydantic, reloadability, and logging patterns from Steps 0.1–0.2 are followed.

---

## Sovereignty & Constraints Preserved

- Zero new inline literals for policy, thresholds, or tier names (the five tier strings and active statuses are the minimal necessary vocabulary already defined by the prior two components).
- Behavior is 100% driven by the registry YAML (`status`, `applies_to_liquidity`, `fallback_strategy`, `priority`, ...) + the liquidity classifier config.
- No changes to core engine files, miner, structural slots, E2E harness, Option B, dual-mode, slot_15 veto, or `params_yaml.txt`.
- The engine is reloadable together with its two dependencies.
- Future point implementations remain free to contain whatever mathematics they need; the engine only performs the guard decision.

---

**File written:** `docs/KRONOS_V1_ALT_BIAS_OVERRIDE_ENGINE_PHASE0_STEP03_SUMMARY.md` (this document).

**Task complete.** The `BiasOverrideEngine` is now the central decision layer for the entire Quant Bias Override system. It completes the Phase 0 foundation (Registry + Liquidity Classifier + Orchestration Engine) and provides a clean, auditable, reloadable contract for the 100 point implementations that will follow.

All prior Phase 0 artifacts, Proxy Hardening work, and sovereignty guarantees remain fully intact.

Ready for the first real point implementation (recommended starting candidates: high-priority Group 1 points that have broad `"all"` liquidity applicability). 

Next natural steps after this foundation:
- Choose a point (e.g. 01 or 04)
- Implement the quant replacement logic in the appropriate module
- Wire the `apply_override(...)` call
- Flip the point's `status` in the registry when ready
- Use `get_override_status` + logs for validation

The engine makes that process safe and repeatable.