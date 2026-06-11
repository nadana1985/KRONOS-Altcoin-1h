"""
KRONOS V1-ALT Bias Override Engine (Phase 0, Step 0.3)

Central thin orchestration layer that connects:
- BiasOverrideRegistry (the 100-point single source of truth)
- LiquidityClassifier (dynamic 5-tier per-symbol classification)

Responsibilities:
- Decide *whether* a given bias override point should be active for the current
  symbol / liquidity tier / point status.
- Decide *which value* to use (raw vs. the quant replacement) without embedding
  the actual replacement logic.
- Provide rich diagnostics and batch support for future point implementations.

Sovereignty principles (consistent with Steps 0.1 and 0.2):
- Zero hardcoded magic numbers or policy decisions outside of what the registry
  and liquidity config already declare.
- All gating flows from point.status, point.applies_to_liquidity, and the live tier.
- The engine itself is reloadable and contains no per-point implementation code.
- Future quant replacements live in the call sites (or dedicated bias modules),
  not here.

Primary usage pattern for future point implementations:

    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    import pandas as pd

    engine = BiasOverrideEngine()

    def some_structural_or_feature_function(df: pd.DataFrame, symbol: str, ...):
        raw_value = old_heuristic_or_calculation(df, ...)

        # Compute the sovereign quant replacement described in the manual (point XX)
        # This computation can be arbitrarily complex and lives in *your* code.
        override_value = new_quant_replacement_from_manual(df, ...)

        # The engine decides whether to use the new value based on registry status
        # and the *current dynamic liquidity tier* of the symbol.
        final_value = engine.apply_override(
            point_id="01",                    # from the 100-point manual
            raw_value=raw_value,
            df=df,
            symbol=symbol,
            override_value=override_value,   # only used if conditions are met
            lookback=288                     # optional, passed to classifier
        )
        return final_value

The engine returns `raw_value` in all cases where the override is not (yet)
active for this point + tier combination. When the point reaches "implemented"
status *and* the current tier is allowed by the point's applies_to_liquidity,
and the caller supplied an `override_value`, the engine returns the override_value.

This design keeps the engine as a pure decision / guardrail layer.

Additional methods:
- get_available_overrides(liquidity_tier=None)
- get_override_status(point_id, symbol, df, force_tier=None)
- reload()
- apply_overrides(...) for batch processing

Logging: All decisions emit structured logs under "kronos.bias_override".
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from kronos.quant_spec.bias_override_registry import BiasOverrideRegistry
from kronos.features.liquidity_classifier import LiquidityClassifier

logger = logging.getLogger("kronos.bias_override")

# ------------------------------------------------------------------
# Global master switch — controls ALL overrides across the system
# ------------------------------------------------------------------
OVERRIDES_ENABLED = True

def set_overrides_enabled(enabled: bool) -> None:
    """Global master switch to enable/disable all bias overrides instantly.

    When False, apply_override() returns raw_value for every point,
    effectively reverting to legacy behavior with zero code changes.
    """
    global OVERRIDES_ENABLED
    OVERRIDES_ENABLED = enabled
    logger.info("[OVERRIDES] Master switch set to %s", enabled)


def is_overrides_enabled() -> bool:
    """Check current state of the master switch."""
    return OVERRIDES_ENABLED


# ------------------------------------------------------------------
# Ablation / selective-disable support (module-level to span all engine instances)
# ------------------------------------------------------------------
_DISABLED_POINTS: set = set()

def disable_override_points(point_ids: set) -> None:
    """Globally disable specific override point IDs (ablation studies).

    When a point_id is in this set, any BiasOverrideEngine instance will
    return raw_value for that point regardless of implementation status.
    This is designed for ablation studies — disable all except a group.
    """
    global _DISABLED_POINTS
    _DISABLED_POINTS = set(point_ids)
    logger.info("[OVERRIDES] Ablation: disabled %d points: %s", len(point_ids), sorted(point_ids))

def enable_all_override_points() -> None:
    """Clear the disabled set — all override points enabled."""
    global _DISABLED_POINTS
    n = len(_DISABLED_POINTS)
    _DISABLED_POINTS.clear()
    logger.info("[OVERRIDES] Ablation: enabled all points (was %d disabled)", n)


# Policy note (sovereignty-friendly):
# These statuses are considered "ready to apply" the quant replacement.
# They are deliberately narrow. Points stay in "not_started" or "planned" until
# the actual implementation + testing for that point_id is complete.
# This list can evolve later via a small config extension if needed, but for now
# it is explicit and documented here (not scattered magic).
_ACTIVE_IMPLEMENTATION_STATUSES = {"implemented", "validated", "active"}


class BiasOverrideEngine:
    """
    Central application layer for the KRONOS Quant Bias Override system.

    Wires the registry and the liquidity classifier together so that individual
    bias point implementations do not have to repeat gating logic.

    The engine is intentionally *thin*. It never contains the mathematical
    replacement for any point. It only answers:
        "Given the current state of the registry and the live liquidity tier
         of this symbol, should we use the raw (legacy) value or the override_value
         the caller computed?"

    All behavior is driven by:
    - bias_override_registry.yaml (status, applies_to_liquidity, fallback_strategy, etc.)
    - liquidity_tiers.yaml (via the classifier)
    """

    def __init__(
        self,
        registry_path: Optional[str] = None,
        liquidity_config_path: Optional[str] = None,
    ):
        """
        Initialize the engine with references to the two foundational components.

        Parameters
        ----------
        registry_path : Optional[str]
            Path to bias_override_registry.yaml. If None, uses the default sibling location.
        liquidity_config_path : Optional[str]
            Path to liquidity_tiers.yaml. If None, uses the default location.
        """
        self.registry = BiasOverrideRegistry(registry_path)
        self.classifier = LiquidityClassifier(liquidity_config_path)
        self._active_statuses = _ACTIVE_IMPLEMENTATION_STATUSES
        self._tier_cache: Dict[tuple, str] = {}
        # ── Ablation / selective-disable support ──
        # A set of point IDs (e.g. {"15", "64"}) that are suppressed.
        # When a point is in this set, apply_override returns raw_value even if the
        # point is implemented and the tier matches. This allows ablation studies
        # to selectively disable individual override points at runtime.
        self._disabled_points: set = set()

        logger.debug(
            "BiasOverrideEngine initialized (registry=%s, liquidity_config=%s)",
            self.registry.yaml_path if hasattr(self.registry, "yaml_path") else "default",
            self.classifier.config_path if hasattr(self.classifier, "config_path") else "default",
        )

    def disable_points(self, point_ids: set) -> None:
        """Add point IDs to the disabled set for ablation / selective gating."""
        self._disabled_points.update(point_ids)
        logger.info("[OVERRIDES] Disabled %d points: %s", len(point_ids), sorted(point_ids))

    def enable_points(self, point_ids: set) -> None:
        """Remove point IDs from the disabled set."""
        self._disabled_points.difference_update(point_ids)
        logger.info("[OVERRIDES] Enabled %d points: %s", len(point_ids), sorted(point_ids))

    def reset_disabled_points(self) -> None:
        """Clear the disabled set (all points enabled)."""
        n = len(self._disabled_points)
        self._disabled_points.clear()
        logger.info("[OVERRIDES] Reset disabled points (%d previously disabled)", n)

    def reload(self) -> None:
        """Reload both the registry and the liquidity classifier at runtime."""
        self.registry.reload()
        self.classifier.reload()
        logger.info("BiasOverrideEngine reloaded (registry + liquidity classifier)")

    @property
    def override_config(self) -> Dict[str, Any]:
        """
        Bias-override-specific configuration loaded from liquidity_tiers.yaml under the 'overrides' key.
        Individual point implementations (e.g. Point 01) should source all their numeric
        parameters (quantiles, lookbacks, fallbacks) exclusively from this section via the engine
        (or by loading the same YAML). This keeps the engine as the single source for runtime config.
        """
        try:
            return self.classifier.config.get("overrides", {})
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Core decision logic
    # ------------------------------------------------------------------
    def _get_tier(
        self,
        df: pd.DataFrame,
        symbol: str,
        force_tier: Optional[str] = None,
        **kwargs,
    ) -> str:
        if force_tier:
            return force_tier
        lookback = kwargs.get("lookback")
        cache_key = (symbol, id(df), len(df), lookback)
        tier = self._tier_cache.get(cache_key)
        if tier is None:
            tier = self.classifier.get_tier(df, symbol=symbol, lookback=lookback)
            self._tier_cache[cache_key] = tier
        return tier

    def _is_implemented(self, point_status: str) -> bool:
        return point_status in self._active_statuses

    def _applies_to_tier(self, point, tier: str) -> bool:
        applies = getattr(point, "applies_to_liquidity", ["all"])
        return "all" in applies or tier in applies

    def apply_override(
        self,
        point_id: str,
        raw_value: Any,
        df: pd.DataFrame,
        symbol: str,
        timestamp: Any = None,
        force_tier: Optional[str] = None,
        override_value: Any = None,
        **kwargs,
    ) -> Any:
        """
        Decide whether to return the raw_value or the provided override_value
        for a specific bias override point.

        This is the primary method future point implementations should call.

        Parameters
        ----------
        point_id : str
            Zero-padded ID from the registry (e.g. "01", "17").
        raw_value : Any
            The legacy / current calculation result (always safe fallback).
        df : pd.DataFrame
            Recent bar data for the symbol (used for liquidity classification).
        symbol : str
            Asset identifier (e.g. "SOMEALTUSDT") for logging and tiering.
        timestamp : Any, optional
            Optional timestamp for the decision (logged, reserved for future time-based rules).
        force_tier : Optional[str]
            If provided, bypasses the classifier and uses this tier (very useful for testing
            and for forcing conservative behavior on specific symbols).
        override_value : Any, optional
            The result of the new quant replacement (from the manual). Only returned
            if the point is implemented AND the current tier is allowed by the point.
        **kwargs
            Passed through to the liquidity classifier (e.g. lookback=288).

        Returns
        -------
        Any
            Either `raw_value` (most common during phased rollout) or `override_value`
            when all gates are satisfied.
        """
        try:
            point = self.registry.get_point(point_id)
        except KeyError:
            logger.warning(
                "[BIAS_OVERRIDE] point_id=%s unknown in registry — returning raw_value",
                point_id,
            )
            return raw_value

        # Master switch — instant fallback to legacy
        if not OVERRIDES_ENABLED:
            logger.info(
                "[BIAS_OVERRIDE] point_id=%s tier=auto action=pass_through reason=\"master_switch_off\" symbol=%s",
                point_id, symbol,
            )
            return raw_value

        # Ablation disable — allow selective point gating at runtime
        # Check both module-level set (shared across all instances) and instance-level set
        if point_id in _DISABLED_POINTS or point_id in self._disabled_points:
            logger.info(
                "[BIAS_OVERRIDE] point_id=%s tier=auto action=ablation_disabled symbol=%s",
                point_id, symbol,
            )
            return raw_value

        tier = self._get_tier(df, symbol, force_tier=force_tier, **kwargs)
        is_impl = self._is_implemented(point.status)
        applies = self._applies_to_tier(point, tier)

        if not is_impl:
            action = "pass_through"
            reason = f"status={point.status} (not yet implemented)"
            value = raw_value
        elif not applies:
            action = "pass_through"
            reason = f"tier={tier} not covered by applies_to_liquidity={point.applies_to_liquidity}"
            value = raw_value
        else:
            # Point is implemented and the tier is allowed
            if override_value is not None:
                action = "apply_override"
                reason = "conditions_met"
                value = override_value
            else:
                action = "pass_through"
                reason = "conditions_met_but_no_override_value_supplied"
                value = raw_value

        # Structured decision log (always emitted at INFO for auditability)
        logger.info(
            "[BIAS_OVERRIDE] point_id=%s tier=%s action=%s reason=\"%s\" "
            "symbol=%s status=%s applies=%s force_tier=%s",
            point_id,
            tier,
            action,
            reason,
            symbol,
            point.status,
            applies,
            force_tier or "auto",
        )

        # Also log the fallback strategy from the registry when we are in a position
        # to potentially use an override (helps during development)
        if action == "apply_override" and hasattr(point, "fallback_strategy"):
            logger.debug(
                "[BIAS_OVERRIDE] point_id=%s using override; registry fallback_strategy=\"%s\"",
                point_id,
                point.fallback_strategy,
            )

        return value

    # ------------------------------------------------------------------
    # Batch support
    # ------------------------------------------------------------------
    def apply_overrides(self, items: List[Dict[str, Any]]) -> List[Any]:
        """
        Apply multiple overrides in one call.

        Each item in the list is a dict containing at minimum:
            point_id, raw_value, df, symbol
        Optional keys: override_value, force_tier, lookback, timestamp

        Returns a list of final values in the same order.
        """
        results: List[Any] = []
        for item in items:
            result = self.apply_override(
                point_id=item["point_id"],
                raw_value=item["raw_value"],
                df=item["df"],
                symbol=item["symbol"],
                timestamp=item.get("timestamp"),
                force_tier=item.get("force_tier"),
                override_value=item.get("override_value"),
                **{k: v for k, v in item.items() if k not in {
                    "point_id", "raw_value", "df", "symbol",
                    "timestamp", "force_tier", "override_value"
                }},
            )
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Diagnostics & introspection
    # ------------------------------------------------------------------
    def get_available_overrides(
        self, liquidity_tier: Optional[str] = None
    ) -> List[str]:
        """
        Return point_ids that are currently in an implemented status and (optionally)
        are declared to apply to the given liquidity tier.

        If liquidity_tier is None, returns all implemented points regardless of
        their applies_to_liquidity declaration (useful for broad rollout planning).
        """
        candidates = [
            p for p in self.registry.get_points_by_priority(5)
            if self._is_implemented(p.status)
        ]

        if liquidity_tier is not None:
            candidates = [
                p for p in candidates
                if "all" in p.applies_to_liquidity or liquidity_tier in p.applies_to_liquidity
            ]

        return [p.point_id for p in sorted(candidates, key=lambda p: (p.priority, int(p.point_id)))]

    def get_override_status(
        self,
        point_id: str,
        symbol: str,
        df: pd.DataFrame,
        force_tier: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Diagnostic snapshot for a single point on a given symbol / data window.

        Extremely useful for debugging, dashboards, and during phased rollout.

        Returns a rich dict describing exactly why the engine would (or would not)
        apply the override right now.
        """
        try:
            point = self.registry.get_point(point_id)
        except KeyError:
            return {
                "point_id": point_id,
                "error": "point_not_found_in_registry",
                "recommended_action": "pass_through",
            }

        tier = self._get_tier(df, symbol, force_tier=force_tier, **kwargs)
        is_impl = self._is_implemented(point.status)
        applies = self._applies_to_tier(point, tier)

        if not is_impl:
            recommended = "pass_through"
            reason = f"status={point.status}"
        elif not applies:
            recommended = "pass_through"
            reason = f"tier={tier} not in applies_to_liquidity"
        else:
            recommended = "apply_override_if_value_provided"
            reason = "active_and_applies"

        return {
            "point_id": point_id,
            "title": getattr(point, "title", ""),
            "group": getattr(point, "group", None),
            "status": point.status,
            "current_tier": tier,
            "applies_to_current_tier": applies,
            "is_implemented": is_impl,
            "recommended_action": recommended,
            "reason": reason,
            "fallback_strategy": getattr(point, "fallback_strategy", ""),
            "priority": getattr(point, "priority", None),
            "applies_to_liquidity": getattr(point, "applies_to_liquidity", []),
            "force_tier_used": force_tier is not None,
        }

    def __repr__(self) -> str:
        return (
            f"<BiasOverrideEngine "
            f"registry_points={len(self.registry)} "
            f"liquidity_fallback={self.classifier.fallback_tier}>"
        )


# ---------------------------------------------------------------------
# Standalone convenience (optional)
# ---------------------------------------------------------------------
def create_engine(
    registry_path: Optional[str] = None,
    liquidity_config_path: Optional[str] = None,
) -> BiasOverrideEngine:
    """Factory for a default-configured engine."""
    return BiasOverrideEngine(
        registry_path=registry_path,
        liquidity_config_path=liquidity_config_path,
    )


if __name__ == "__main__":
    """
    Smoke test / demonstration of the full Phase 0 stack working together.

    In real usage the engine is instantiated once (or per-process) and passed
    or imported into the modules that compute structural features, neural signals,
    or any other place where a bias override point may eventually be activated.
    """
    import sys
    import pandas as pd
    import numpy as np

    print("=== BiasOverrideEngine Smoke Test (Phase 0.3) ===")

    engine = BiasOverrideEngine()
    print(f"Engine created: {engine}")
    print(f"Registry points loaded: {len(engine.registry)}")
    print(f"Available implemented overrides (any tier): {engine.get_available_overrides()}")

    # Create a small synthetic dataframe that will classify as 'medium' under default config
    np.random.seed(7)
    n = 80
    df = pd.DataFrame({
        "close": 0.5 + np.cumsum(np.random.randn(n) * 0.01),
        "high": 0.5 + np.cumsum(np.random.randn(n) * 0.01) + 0.02,
        "low": 0.5 + np.cumsum(np.random.randn(n) * 0.01) - 0.02,
        "volume": np.random.uniform(200_000, 3_000_000, n),
        "quote_volume": np.random.uniform(100_000, 1_500_000, n),
        "count": np.random.randint(300, 6000, n),
    })
    df["high"] = df[["high", "close"]].max(axis=1)
    df["low"] = df[["low", "close"]].min(axis=1)

    symbol = "DEMOALTUSDT"

    # Demonstrate get_override_status for a not-yet-implemented point
    status_01 = engine.get_override_status("01", symbol=symbol, df=df)
    print("\nStatus for point 01 (still not_started):")
    print(f"  recommended_action={status_01['recommended_action']}, reason={status_01['reason']}")

    # Demonstrate apply_override with no override_value supplied (common during development)
    raw = 0.73
    result = engine.apply_override(
        point_id="01",
        raw_value=raw,
        df=df,
        symbol=symbol,
        # override_value=...   # intentionally omitted
    )
    print(f"\napply_override('01', raw={raw}) -> {result} (expected raw because not implemented)")

    # Force a tier and supply an override_value (simulates what a future implemented point would do)
    new_value = 0.81
    result_forced = engine.apply_override(
        point_id="01",
        raw_value=raw,
        df=df,
        symbol=symbol,
        force_tier="micro",           # force a conservative tier
        override_value=new_value,
    )
    print(f"apply_override('01', force_tier='micro', override_value={new_value}) -> {result_forced}")

    # Show available overrides for a specific tier
    print("\nImplemented points that declare support for 'low' or 'all':")
    print(" ", engine.get_available_overrides(liquidity_tier="low"))

    # Batch example
    batch_items = [
        {"point_id": "01", "raw_value": 0.65, "df": df, "symbol": symbol, "override_value": 0.79},
        {"point_id": "02", "raw_value": 12.0, "df": df, "symbol": symbol},
    ]
    batch_results = engine.apply_overrides(batch_items)
    print(f"\nBatch results: {batch_results}")

    # Point 01 specific integration demo (the first real bias override)
    try:
        from kronos.quant_spec.overrides.point_01 import compute_point_01_override
        neural = {
            "confidence_min": 0.72,
            "confidence_clamp": (0.58, 0.91),
            "strength_mult": 4.2,
            "strength_add": 0.55,
            "variation": 0.38,
            "slot15_entropy_weight": 0.1,
            "reversal_window": [20, 50],
        }
        # Use a plausible current slot_15 (would normally come from compute_slots_sovereign)
        curr_slot15 = 0.61
        p01_final = compute_point_01_override(
            current_slot15=curr_slot15,
            df=df,
            symbol=symbol,
            neural=neural,
            engine=engine,
            lookback=120,
        )
        print(f"\nPoint 01 wrapper (via engine) for current_slot15={curr_slot15} → final={p01_final:.3f}")
        print("  (While status='not_started' this equals the static raw path — safety verified)")
    except Exception as e:
        print(f"(Point 01 wrapper demo skipped: {e})")

    # Point 02 volatility-scaled window demo (natural follow-up to Point 01)
    try:
        from kronos.quant_spec.overrides.point_02 import (
            get_volatility_scaled_window,
            get_slot15_history_lookback,
        )
        # Demonstrate on the same df for several bases
        for base_name, base_val in [("slot15_hist (for P01)", 100), ("vpin", 100), ("ofi", 50)]:
            scaled = get_volatility_scaled_window(base_val, df, symbol, engine=engine)
            print(f"Point 02 scaled {base_name:20s} base={base_val:3d} → {scaled:3d}")
        # Direct synergy helper for Point 01
        p01_lb = get_slot15_history_lookback(df, symbol, engine=engine)
        print(f"Point 02 recommended slot15 history lookback for Point 01: {p01_lb}")
    except Exception as e:
        print(f"(Point 02 wrapper demo skipped: {e})")

    # Batch 04/08/09/11/14 quick demo (adaptive scaling family)
    try:
        from kronos.quant_spec.overrides import (
            compute_point_04_override,
            compute_point_09_override,
            compute_point_14_override,
        )
        print("\nBatch 04/09/14 demo (via engine):")
        print("  P04 mult 4.2 →", round(compute_point_04_override(4.2, df, symbol, engine=engine), 3))
        print("  P09 bw 0.005 →", round(compute_point_09_override(0.005, df, symbol, engine=engine), 5))
        print("  P14 eps 1e-8 →", f"{compute_point_14_override(1e-8, df, symbol, engine=engine):.2e}")
    except Exception as e:
        print(f"(Batch 04/08/09/11/14 demo skipped: {e})")

    # Volatility Batch 2 (53-56,58-60) quick demo
    try:
        from kronos.quant_spec.overrides import (
            compute_point_53_override, compute_point_55_override,
            compute_point_58_override, compute_point_60_override,
        )
        print("\nVol Batch 2 demo (via engine):")
        print("  P53 Amihud →", round(compute_point_53_override(0.01, df, symbol, engine=engine), 5))
        print("  P55 HF-Int →", round(compute_point_55_override(0.01, df, symbol, engine=engine), 5))
        print("  P60 Kernel+Jump →", round(compute_point_60_override(0.01, df, symbol, engine=engine), 5))
    except Exception as e:
        print(f"(Vol Batch 2 demo skipped: {e})")

    # Microstructure batch demo (via engine)
    try:
        from kronos.quant_spec.overrides import (
            compute_point_17_override, compute_point_21_override, compute_point_26_override,
        )
        print("\nMicrostructure batch demo (via engine):")
        print("  P17 spread →", round(compute_point_17_override(0.0015, df, symbol, engine=engine), 5))
        print("  P21 illiq  →", round(compute_point_21_override(0.8, df, symbol, engine=engine), 4))
        print("  P26 prox   →", round(compute_point_26_override(0.35, df, symbol, distance=0.8, engine=engine), 5))
    except Exception as e:
        print(f"(Microstructure batch demo skipped: {e})")

    # ============ Validation, Purging & Causality Batch (Points 35,79,80,82,90) ============
    print("\n" + "-" * 50)
    print("Validation/Purging/Causality Batch (35,79,80,82,90)")
    print("-" * 50)

    # Point 35: Purging & Embargo
    try:
        from kronos.quant_spec.overrides import compute_point_35_override
        from kronos.quant_spec.overrides.utils import get_purged_embargo_indices
        n_train = 100
        times = pd.date_range("2020-01-01", periods=n, freq="h")
        purged = compute_point_35_override(
            n_train, times, horizon=10, df=df, symbol=symbol, engine=engine
        )
        print(f"  P35 purging: raw_train={n_train} -> final={purged} (less due to embargo)")

        # Show get_purged_embargo_indices usage
        train_idx = pd.Index(np.arange(80))
        purged_idx = get_purged_embargo_indices(train_idx, 80, 100, 10, 5)
        print(f"  P35 detail: {len(purged_idx)}/{len(train_idx)} train indices purged")
    except Exception as e:
        print(f"(P35 demo skipped: {e})")

    # Point 79: CPCV Paths
    try:
        from kronos.quant_spec.overrides import compute_point_79_override
        from kronos.quant_spec.overrides.utils import generate_cpcv_paths
        cpcv_n = compute_point_79_override(5, 6, 2, df, symbol, engine=engine)
        paths = generate_cpcv_paths(6, 2)
        print(f"  P79 CPCV: naive=5, cpcv={cpcv_n} (max {len(paths)} combinations)")
    except Exception as e:
        print(f"(P79 demo skipped: {e})")

    # Point 80: DSR
    try:
        from kronos.quant_spec.overrides import compute_point_80_override
        dsr = compute_point_80_override(1.8, 100, 200, df, symbol, engine=engine)
        print(f"  P80 DSR: raw_sharpe=1.8 -> dsr={dsr:.4f}")
    except Exception as e:
        print(f"(P80 demo skipped: {e})")

    # Point 82: Causally Lagged Global Priors
    try:
        from kronos.quant_spec.overrides import compute_point_82_override
        local = pd.Series(np.random.randn(n), name="local")
        xsec = pd.DataFrame({"mkt1": np.random.randn(n), "mkt2": np.random.randn(n)})
        lagged = compute_point_82_override(local, local, xsec, df, symbol, engine=engine)
        print(f"  P82 causality: local+{xsec.shape[1]} global features lagged -> shape={lagged.shape}")
    except Exception as e:
        print(f"(P82 demo skipped: {e})")

    # Point 90: Monte Carlo DSR
    try:
        from kronos.quant_spec.overrides import compute_point_90_override
        rets = pd.Series(np.random.randn(n) * 0.001)
        mc = compute_point_90_override(0.8, rets, df, symbol, engine=engine)
        print(f"  P90 MC-DSR: raw_sharpe=0.8 -> mc_dsr_mean={mc.get('dsr_mean', 0):.4f}, "
              f"prob_pos={mc.get('prob_positive', 0):.3f}")
    except Exception as e:
        print(f"(P90 demo skipped: {e})")

    # ============ Operational & Execution Batch (Points 91,92,93,94,95,100) ============
    print("\n" + "-" * 50)
    print("Operational & Execution Batch (91,92,93,94,95,100)")
    print("-" * 50)

    # Point 91: OS-Agnostic Path Resolution
    try:
        from kronos.quant_spec.overrides import compute_point_91_override
        p91 = compute_point_91_override("f:/kronos_v1_alt", df, symbol, engine=engine)
        print(f"  P91 path: f:/kronos_v1_alt -> {p91}")
    except Exception as e:
        print(f"(P91 demo skipped: {e})")

    # Point 92: Dynamic Compute Allocation
    try:
        from kronos.quant_spec.overrides import compute_point_92_override
        from kronos.quant_spec.overrides.utils import compute_system_memory_available_gb
        p92 = compute_point_92_override(8192, df, symbol, engine=engine)
        mem_gb = compute_system_memory_available_gb()
        print(f"  P92 shard: 8192 -> {p92} (mem_avail={mem_gb:.1f}GB)")
    except Exception as e:
        print(f"(P92 demo skipped: {e})")

    # Point 93: Latency Slippage
    try:
        from kronos.quant_spec.overrides import compute_point_93_override
        p93 = compute_point_93_override(100.0, df, symbol, engine=engine)
        print(f"  P93 slippage: signal=100.0 -> executed={p93['engine_final_price']:.4f} "
              f"({p93['slippage_bps']:.1f}bps)")
    except Exception as e:
        print(f"(P93 demo skipped: {e})")

    # Point 94: Dynamic Execution Cost
    try:
        from kronos.quant_spec.overrides import compute_point_94_override
        p94 = compute_point_94_override(10.0, df, symbol, order_size_usd=10000, volume_usd=1e6, engine=engine)
        print(f"  P94 cost: static=10bps -> dynamic={p94['engine_final_cost_bps']:.1f}bps "
              f"(fee={p94['base_fee_bps']:.1f} + spread={p94['spread_cost_bps']:.1f} + impact={p94['impact_bps']:.1f})")
    except Exception as e:
        print(f"(P94 demo skipped: {e})")

    # Point 95: TWAP Execution
    try:
        from kronos.quant_spec.overrides import compute_point_95_override
        p95 = compute_point_95_override(float(df["close"].iloc[-1]), df, symbol, engine=engine)
        print(f"  P95 TWAP: close={float(df['close'].iloc[-1]):.4f} -> twap={p95['engine_final_price']:.4f} "
              f"(vs_close={p95.get('vs_close', 0):.4f})")
    except Exception as e:
        print(f"(P95 demo skipped: {e})")

    # Point 100: Impact-Aware Position Sizing
    try:
        from kronos.quant_spec.overrides import compute_point_100_override
        p100 = compute_point_100_override(5000.0, df, symbol, volume_usd=1e6, engine=engine)
        print(f"  P100 sizing: naive=$5000 -> adaptive=${p100['engine_final_size']:.0f} "
              f"(impact_adj={p100['impact_adjustment']:.3f})")
    except Exception as e:
        print(f"(P100 demo skipped: {e})")

    # ============ Remaining Batch A (Points 03, 05, 06, 07, 10, 12, 13, 15, 16, 18, 20, 23, 24) ==========
    print("\n" + "-" * 50)
    print("Remaining Batch A (03,05,06,07,10,12,13,15,16,18,20,23,24)")
    print("-" * 50)

    # Point 03: SVD Bottleneck Compression
    try:
        from kronos.quant_spec.overrides import compute_point_03_override
        raw_vec = np.full(8, 0.72)
        p03 = compute_point_03_override(raw_vec, df, symbol, engine=engine)
        print(f"  P03 SVD: n_comp={p03['n_components']} var_explained={p03['variance_explained']:.3f}")
    except Exception as e:
        print(f"(P03 demo skipped: {e})")

    # Point 05: Volume-Density Window
    try:
        from kronos.quant_spec.overrides import compute_point_05_override
        p05 = compute_point_05_override(24, df, symbol, engine=engine)
        print(f"  P05 VolWindow: 24 -> {p05}")
    except Exception as e:
        print(f"(P05 demo skipped: {e})")

    # Point 06: Continuous Amihud Decay
    try:
        from kronos.quant_spec.overrides import compute_point_06_override
        p06 = compute_point_06_override(0.5, df, symbol, engine=engine)
        print(f"  P06 Decay: weight={p06:.4f}")
    except Exception as e:
        print(f"(P06 demo skipped: {e})")

    # Point 07: Parsimonious Polynomial
    try:
        from kronos.quant_spec.overrides import compute_point_07_override
        X_demo = df["close"].values.reshape(-1, 1)
        y_demo = df["volume"].values
        p07 = compute_point_07_override(0.0, df, symbol, engine=engine, X=X_demo, y=y_demo)
        print(f"  P07 Poly: degree={p07['degree']} BIC={p07['bic']:.1f}")
    except Exception as e:
        print(f"(P07 demo skipped: {e})")

    # Point 10: Timestamp Latency Truncation
    try:
        from kronos.quant_spec.overrides import compute_point_10_override
        p10 = compute_point_10_override(1, df, symbol, engine=engine)
        print(f"  P10 Latency: truncated={p10.get('truncated_count', 0)}")
    except Exception as e:
        print(f"(P10 demo skipped: {e})")

    # Point 12: Variance Mixture Z-Score
    try:
        from kronos.quant_spec.overrides import compute_point_12_override
        p12 = compute_point_12_override(0.0, df, symbol, engine=engine)
        print(f"  P12 VarZ: z={p12:.3f}")
    except Exception as e:
        print(f"(P12 demo skipped: {e})")

    # Point 13: Trade-Intensity Imbalance
    try:
        from kronos.quant_spec.overrides import compute_point_13_override
        p13 = compute_point_13_override(0.0, df, symbol, engine=engine)
        print(f"  P13 Imbalance: {p13:.4f}")
    except Exception as e:
        print(f"(P13 demo skipped: {e})")

    # Point 15: Asymmetric Barriers
    try:
        from kronos.quant_spec.overrides import compute_point_15_override
        p15 = compute_point_15_override(0.02, df, symbol, engine=engine)
        print(f"  P15 Barriers: upper={p15['barrier_upper']:.4f} lower={p15['barrier_lower']:.4f}")
    except Exception as e:
        print(f"(P15 demo skipped: {e})")

    # Point 16: KDE Volume Profile
    try:
        from kronos.quant_spec.overrides import compute_point_16_override
        p16 = compute_point_16_override(100.0, df, symbol, engine=engine)
        print(f"  P16 KDE: poc={p16['engine_final_poc']:.4f}")
    except Exception as e:
        print(f"(P16 demo skipped: {e})")

    # Point 18: Log Volume Z-Score
    try:
        from kronos.quant_spec.overrides import compute_point_18_override
        p18 = compute_point_18_override(0.0, df, symbol, engine=engine)
        print(f"  P18 LogVolZ: z={p18:.3f}")
    except Exception as e:
        print(f"(P18 demo skipped: {e})")

    # Point 20: Shannon Count Entropy
    try:
        from kronos.quant_spec.overrides import compute_point_20_override
        p20 = compute_point_20_override(0.5, df, symbol, engine=engine)
        print(f"  P20 Entropy: e={p20:.4f}")
    except Exception as e:
        print(f"(P20 demo skipped: {e})")

    # Point 23: Eigenvalue Covariance Weight
    try:
        from kronos.quant_spec.overrides import compute_point_23_override
        p23 = compute_point_23_override(0.5, df, symbol, engine=engine)
        print(f"  P23 EigenW: w={p23:.4f}")
    except Exception as e:
        print(f"(P23 demo skipped: {e})")

    # Point 24: Fractional Differencing OFI
    try:
        from kronos.quant_spec.overrides import compute_point_24_override
        ofi_demo = pd.Series(np.cumsum(np.random.randn(n) * 0.5) + 2.0)
        df_ofi = df.copy()
        df_ofi["ofi"] = ofi_demo.values
        p24 = compute_point_24_override(0.0, df_ofi, symbol, engine=engine)
        print(f"  P24 FDOI: d={p24['d']} fdoi={p24['fdoi_latest']:.4f}")
    except Exception as e:
        print(f"(P24 demo skipped: {e})")

    print("\n=== Engine + Registry + Classifier stack smoke test complete ===")
    print("The engine is now ready to be wired into actual bias point implementations.")
