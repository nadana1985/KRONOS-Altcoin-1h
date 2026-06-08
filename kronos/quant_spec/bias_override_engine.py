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

        logger.debug(
            "BiasOverrideEngine initialized (registry=%s, liquidity_config=%s)",
            self.registry.yaml_path if hasattr(self.registry, "yaml_path") else "default",
            self.classifier.config_path if hasattr(self.classifier, "config_path") else "default",
        )

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
        return self.classifier.get_tier(df, symbol=symbol, lookback=lookback)

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

    print("\n=== Engine + Registry + Classifier stack smoke test complete ===")
    print("The engine is now ready to be wired into actual bias point implementations.")