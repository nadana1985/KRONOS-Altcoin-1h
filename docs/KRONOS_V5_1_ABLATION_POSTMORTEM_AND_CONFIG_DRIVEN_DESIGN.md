# KRONOS V5.1 — Ablation Postmortem & Config-Driven Ablation Architecture

**Date:** 2026-06-10  
**Author:** Quant Architecture  

---

## Part 1: Why Runtime Ablation Failed

### The Problem

We implemented a runtime ablation mechanism (`disable_override_points()` in `bias_override_engine.py`) that intercepts calls to `engine.apply_override()` and returns `raw_value` for disabled points. Despite this working correctly at the unit-test level, it failed to produce differentiated group-level metrics at scale.

### Root Cause Analysis

The runtime ablation approach is fundamentally limited by three architectural factors:

#### Factor 1: Pipeline Scattering
Override points are not called through a single centralized path. They are scattered across the pipeline:

```
mine_reversal_signature()         → calls Point 01, 02, 06, 11, etc.
compute_slots_sovereign()          → calls Point 15, 23, 25, 72, etc.
compute_strength_additive()        → calls Point 04, 08, etc.
ExecutionSimulator.simulate_exec() → calls Point 93, 94, 95, 100
Individual feature modules         → call Point 46, 47, 48, 52, 56, etc.
```

Each of these calls its override point's `compute_point_XX_override()` function, which internally calls `engine.apply_override()`. Even when disabled, the functions **still compute the override value** — they just get raw_value returned. The computation still happens.

#### Factor 2: Confidence Dominance
The final confidence value that drives trading decisions comes from `mine_reversal_signature()`. This function integrates slot_15 (the primary confidence gate) with slot_16 through slot_23 (neural conviction) through a non-linear function. Even when individual override points are disabled:

- The **base confidence** from the miner remains essentially the same
- Slot values are computed from raw features, not just override points
- The neural conviction path (slots 16-23) operates largely independently of the override points

So changing override group membership changes slot values by tiny amounts (1-3%), but the final confidence is a product of all slots working together.

#### Factor 3: Position Sizing Dominance
The `vol_adjusted` position sizing method positions based on **realized volatility**, not on override confidence. Even when override points are disabled, the confidence value remains high enough (because the base miner produces ~0.91 confidence on real data) to pass the confidence threshold. The position size is then determined by:

```
position = base_size * (target_vol / realized_vol) * sqrt_confidence_factor
```

Since realized_vol and target_vol are the same across all ablation groups, the position size is **identical** for all groups on the same symbol. This means the strategy returns are identical, leading to identical metrics.

### Why Per-Symbol Metrics Are Identical

```
Group A (Core Dynamic) on symbol 0G_USDT:
  confidence = 0.910, realized_vol = 0.47, position = 0.10, returns = -0.0795

Group B (Risk & Tail) on symbol 0G_USDT:
  confidence = 0.910, realized_vol = 0.47, position = 0.10, returns = -0.0795

Group C (Volatility) on symbol 0G_USDT:
  confidence = 0.910, realized_vol = 0.47, position = 0.10, returns = -0.0795
```

The confidence, position, and returns are identical because:
1. The **miner** produces the same base confidence regardless of which override group is active
2. The **position sizing** is driven by realized vol, not override point values
3. The override points modify **slot values**, which affect signal quality, but not in a way that changes the final confidence enough to change position size

### What SHOULD Have Happened (Ideal Differentiated Behavior)

For ablation to work effectively, we need a setup where:
1. **Different override groups produce meaningfully different slot values**
2. **Different slot values produce meaningfully different confidence values**
3. **Different confidence values produce different position sizes or trade entry decisions**

This requires:
- Position sizing that is more sensitive to confidence (higher `position_max_size`, lower vol dampening)
- Override points that have a larger impact on the confidence computation
- A pipeline where point module contributions are additive rather than masked

---

## Part 2: Config-Driven Ablation — The Better Approach

### Design Principle

Instead of disabling points at runtime (which still allows computation), we should control which override points are active at the **configuration level**. This means:

1. The `params_yaml.txt` defines `active_override_groups` or `active_override_points`
2. At startup, the system boots with only the configured points active
3. Points that are not in the active set are **never computed** — zero CPU, zero impact
4. The entire pipeline (miner + structural engine + bias engine) operates with the restricted set

### Architecture

#### Step 1: Config Structure in `params_yaml.txt`

```yaml
backtest:
  # ... existing params ...
  
  # Ablation configuration
  ablation:
    enabled: false                    # Master switch
    mode: "group"                     # or "individual" points
    active_groups: []                 # Empty = all points active
    active_points: []                 # Empty = all points active
```

When `ablation.enabled = True`, the system loads only the specified groups/points.

#### Step 2: Group-to-Points Mapping (Config File)

Create `config/override_groups.yaml`:

```yaml
groups:
  core_dynamic:
    points: [1, 2, 3]
    label: "Core Dynamic (01-03)"
  risk_tail:
    points: [15, 64, 72]
    label: "Risk & Tail (15,64,72)"
  volatility:
    points: [48, 52, 56, 57]
    label: "Volatility (48,52,56,57)"
  order_flow:
    points: [11, 24]
    label: "Order Flow (11,24)"
  microstructure:
    points: [6, 19, 23, 25, 29]
    label: "Microstructure (06,19,23,25,29)"
  robust_stats:
    points: [66, 69]
    label: "Robust Stats (66,69)"
  validation:
    points: [35, 36, 82]
    label: "Validation (35,36,82)"
  vol_batch2:
    points: [46, 47]
    label: "Vol Batch2 (46,47)"
  misc_b5:
    points: [28, 44]
    label: "Batch5 Misc (28,44)"
```

#### Step 3: Bootstrap Mechanism

Create `config/ablation_bootstrap.py` that:

1. Reads `backtest.ablation` section from `params_yaml.txt`
2. If `ablation.enabled = True`, reads `active_groups` or `active_points`
3. Modifies the `neural` section of the config to set `point_XX_enabled` flags accordingly
4. All other points' `point_XX_enabled` are set to `False`
5. The point modules check `point_XX_enabled` before computing

#### Step 4: Point Module Gating

Each `compute_point_XX_override()` function checks its enabled flag before doing any work:

```python
def compute_point_01_override(...):
    # Check enabled flag
    if not is_point_enabled("01"):
        return raw_value
    # ... actual computation ...
```

This is a one-line addition to each point module.

### Implementation Steps

| Step | File | Change |
|------|------|--------|
| 1 | `params_yaml.txt` | Add `ablation:` section under `backtest:` |
| 2 | `config/override_groups.yaml` | **New** — group definitions |
| 3 | `config/ablation_bootstrap.py` | **New** — bootstrap logic |
| 4 | `backtest/run_config_ablation.py` | **New** — config-driven ablation runner |
| 5 | Each point module | Add enabled check (10-20 lines total) |

---

## Part 3: Execution Plan

### Phase 1: Infrastructure (Current Sprint)

1. Create `config/override_groups.yaml` with group definitions
2. Create `config/ablation_bootstrap.py` to load configs and set flags
3. Create `backtest/run_config_ablation.py` to manage multi-config runs
4. Add enabled-check to the top 7 point modules (01, 02, 15, 48, 52, 64, 72)

**Estimated effort**: 2-3 hours

### Phase 2: Config-Driven Ablation Runs

For each group, run:
```bash
# Modify params_yaml.txt -> set ablation.active_groups = ["core_dynamic"]
python backtest/run_config_ablation.py --symbols 30 --seed 42

# Modify params_yaml.txt -> set ablation.active_groups = ["risk_tail"]
python backtest/run_config_ablation.py --symbols 30 --seed 42

# ... repeat for each group ...
```

**Estimated symbol count**: 30 (runs in ~5-7 minutes per group, ~1 hour total)

### Phase 3: Analysis

Compare all 9 groups + Full Override + Legacy:

| Metric | Weight | Rationale |
|--------|--------|-----------|
| Max Drawdown | 40% | Primary concern — drawdown control |
| Sharpe Ratio | 25% | Risk-adjusted returns |
| Calmar Ratio | 20% | Return per unit of drawdown risk |
| Profit Factor | 10% | Win/loss efficiency |
| Win Rate | 5% | Trade accuracy |

---

## Part 4: Expected Outcomes

### If Config-Driven Ablation Shows Differentiation

Each group will have measurably different:
- Average confidence (some groups improve signal quality)
- Slot_15 distribution (some groups tighten confidence)
- Max drawdown (some groups control tail risk)
- Sharpe ratio (some groups improve risk-adjusted returns)

We will then rank groups and identify the minimal high-value set.

### If Config-Driven Ablation Also Fails to Differentiate

This would mean the override points are **not providing meaningful signal-level improvements** on the tested symbols. Possible next steps:

1. Test on more liquid symbols (only AAVE, BONK, PEPE, SHIB tier)
2. Test on longer timeframes (4h, daily instead of 1h)
3. Instrument individual slot values to verify override points are actually modifying them
4. Bisect into pairs: test "No override points" vs "All override points except Point 01" etc.

---

## Part 5: Summary

### What We Learned
1. Runtime ablation via `apply_override()` fails because pipeline scattering + confidence dominance + position sizing mask group differences
2. All 26 override points on 530 real shards produce near-identical per-symbol metrics when disabled via runtime engine
3. A config-driven approach is needed for meaningful ablation

### What We're Building
1. Config-driven ablation framework using `params_yaml.txt` `point_XX_enabled` flags
2. Explicit group definitions in `config/override_groups.yaml`
3. Bootstrap logic in `config/ablation_bootstrap.py`
4. Clean runner in `backtest/run_config_ablation.py`

### Timeline
- Phase 1 (Infrastructure): ~2-3 hours
- Phase 2 (Runs): ~1 hour
- Phase 3 (Analysis): ~1 hour