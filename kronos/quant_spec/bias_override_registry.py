"""
KRONOS V1-ALT Quant Bias Override Registry

This module provides a validated, queryable registry for the 100-point Quant Bias Override Manual.
It serves as the single source of truth for bias corrections in the structural and neural layers.

All entries are loaded from bias_override_registry.yaml and validated with Pydantic.
The registry enforces sovereignty: no hard-coded magic numbers or assumptions outside the YAML.

Liquidity integration (Phase 0 Step 0.2):
    The 5-tier dynamic LiquidityClassifier (kronos.features.liquidity_classifier) is the
    recommended source for deciding which overrides apply to a given asset at runtime.
    Registry points declare 'applies_to_liquidity' (now including "very_high").
    Use filter_by_liquidity(["low", "micro"]) or the new get_points_for_liquidity_tier(tier).

Usage:
    from kronos.quant_spec.bias_override_registry import BiasOverrideRegistry
    from kronos.features.liquidity_classifier import LiquidityClassifier

    registry = BiasOverrideRegistry()
    clf = LiquidityClassifier()
    tier = clf.get_tier(df, symbol="SOMEALTUSDT", lookback=288)
    points = registry.get_points_for_liquidity_tier(tier)   # or filter_by_liquidity([tier])
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
import yaml
import os
from pathlib import Path

class BiasPoint(BaseModel):
    """Pydantic model for a single bias override point. Enforces schema and types."""
    point_id: str = Field(..., description="Zero-padded ID (01-100)")
    title: str = Field(..., description="Short descriptive title of the bias")
    group: int = Field(..., ge=1, le=7, description="Group number (1-7) from the manual")
    description: str = Field(..., description="1-2 sentence summary of the bias and its impact")
    manual_bias: str = Field(..., description="Description of the original human/manual bias")
    quant_replacement: str = Field(..., description="Description of the proposed quantitative replacement method")
    status: str = Field("not_started", description="Implementation status")
    applies_to_liquidity: List[str] = Field(["all"], description="Liquidity tiers this override applies to (very_high, high, medium, low, micro, all)")
    complexity: str = Field("medium", description="Implementation complexity estimate")
    compute_intensity: str = Field("medium", description="Runtime compute intensity estimate")
    min_data_density: Optional[int] = Field(200, description="Minimum recommended bars/observations")
    fallback_strategy: str = Field(..., description="Safe fallback when the quant method cannot be applied")
    implementation_file: Optional[str] = Field(None, description="Path to implementation module once done")
    validation_status: str = Field("pending", description="Validation maturity level")
    priority: int = Field(3, ge=1, le=5, description="Rollout priority (1=highest impact/lowest risk)")
    dependencies: List[str] = Field(default_factory=list, description="List of point_ids this depends on")
    notes: str = Field("", description="Implementation notes, caveats, or warnings")

    @validator("point_id")
    def validate_point_id(cls, v):
        if not v.isdigit() or not (1 <= int(v) <= 100):
            raise ValueError("point_id must be a zero-padded string between '01' and '100'")
        return v.zfill(2)

    @validator("status")
    def validate_status(cls, v):
        allowed = {"not_started", "planned", "in_progress", "implemented", "validated", "deprecated"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v

    @validator("validation_status")
    def validate_validation_status(cls, v):
        allowed = {"pending", "backtest_only", "walkforward_validated", "live_validated"}
        if v not in allowed:
            raise ValueError(f"validation_status must be one of {allowed}")
        return v

    @validator("applies_to_liquidity")
    def validate_liquidity(cls, v):
        allowed = {"all", "very_high", "high", "medium", "low", "micro"}
        if not all(x in allowed for x in v):
            raise ValueError(f"applies_to_liquidity items must be from {allowed}")
        return v

    @validator("complexity", "compute_intensity")
    def validate_complexity(cls, v):
        allowed = {"low", "medium", "high", "very_high"}
        if v not in allowed:
            raise ValueError(f"complexity/compute_intensity must be one of {allowed}")
        return v


class BiasOverrideRegistry:
    """
    Runtime registry for the 100-point bias override manual.

    Loads and validates the YAML on initialization (or reload()).
    Provides query methods for phased rollout, liquidity filtering, dependency checking, etc.

    Sovereignty note: The registry itself contains no hard-coded thresholds or magic numbers.
    All values (including defaults) come from the YAML or are passed at construction time.
    """

    def __init__(self, yaml_path: Optional[str] = None):
        if yaml_path is None:
            # Default location relative to this file
            base = Path(__file__).parent
            yaml_path = base / "bias_override_registry.yaml"
        self.yaml_path = Path(yaml_path)
        self._points: Dict[str, BiasPoint] = {}
        self.reload()

    def reload(self) -> None:
        """Reload and re-validate the YAML at runtime (useful for live editing during development)."""
        if not self.yaml_path.exists():
            raise FileNotFoundError(f"Bias override registry not found at {self.yaml_path}")

        with open(self.yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict) or "bias_overrides" not in data:
            raise ValueError("YAML must contain a top-level 'bias_overrides' list")

        raw_points = data["bias_overrides"]
        self._points = {}
        for item in raw_points:
            point = BiasPoint(**item)
            self._points[point.point_id] = point

    def get_point(self, point_id: str) -> BiasPoint:
        """Return a single point by zero-padded ID (e.g. '01')."""
        if point_id not in self._points:
            raise KeyError(f"Point {point_id} not found in registry")
        return self._points[point_id]

    def get_points_by_group(self, group: int) -> List[BiasPoint]:
        """Return all points belonging to a given group (1-7)."""
        return [p for p in self._points.values() if p.group == group]

    def get_active_points(self) -> List[BiasPoint]:
        """Return points that are not yet deprecated."""
        return [p for p in self._points.values() if p.status != "deprecated"]

    def filter_by_liquidity(self, liquidity_levels: List[str]) -> List[BiasPoint]:
        """
        Filter points that apply to any of the requested liquidity levels.
        Use ["all"] to get everything, or ["low", "micro"] for conservative rollout.
        Supports the 5-tier dynamic system (very_high | high | medium | low | micro).
        """
        result = []
        for p in self._points.values():
            if "all" in p.applies_to_liquidity or any(l in p.applies_to_liquidity for l in liquidity_levels):
                result.append(p)
        return result

    def get_points_for_liquidity_tier(self, tier: str) -> List[BiasPoint]:
        """
        Convenience: return points applicable to a specific dynamic tier (from LiquidityClassifier).
        Always includes points marked "all". Tier must be one of very_high/high/medium/low/micro.
        """
        if tier not in {"very_high", "high", "medium", "low", "micro"}:
            raise ValueError(f"Unknown liquidity tier: {tier}")
        return self.filter_by_liquidity([tier])

    def get_points_by_priority(self, max_priority: int = 3) -> List[BiasPoint]:
        """Return points with priority <= max_priority (lower number = higher priority)."""
        return [p for p in self._points.values() if p.priority <= max_priority]

    def get_points_by_status(self, status: str) -> List[BiasPoint]:
        """Return points currently at a given status."""
        return [p for p in self._points.values() if p.status == status]

    def get_implementation_plan(self, max_priority: int = 3) -> Dict[int, List[str]]:
        """
        Return a simple phased plan: group -> list of point_ids ready for implementation.
        Respects priority and dependencies (basic topological sort by priority for now).
        """
        plan: Dict[int, List[str]] = {}
        candidates = sorted(
            self.get_points_by_priority(max_priority),
            key=lambda p: (p.priority, int(p.point_id))
        )
        for p in candidates:
            if p.status == "not_started" and all(dep in self._points and self._points[dep].status != "not_started" for dep in p.dependencies):
                plan.setdefault(p.group, []).append(p.point_id)
        return plan

    def to_dict(self) -> Dict[str, Any]:
        """Return the entire registry as a plain dict (useful for serialization or inspection)."""
        return {pid: p.dict() for pid, p in self._points.items()}

    def __len__(self) -> int:
        return len(self._points)

    def __getitem__(self, point_id: str) -> BiasPoint:
        return self.get_point(point_id)


if __name__ == "__main__":
    # Example usage / smoke test
    registry = BiasOverrideRegistry()
    print(f"Loaded {len(registry)} bias override points.")
    print("Group 1 points:", [p.point_id for p in registry.get_points_by_group(1)])
    print("High priority active:", [p.point_id for p in registry.get_points_by_priority(1) if p.status != "deprecated"])
    print("Points applicable to micro liquidity:", len(registry.filter_by_liquidity(["micro"])))
    print("Points for a very_high tier (demo):", len(registry.get_points_for_liquidity_tier("very_high")))
    print("Implementation plan (priority <= 2):", registry.get_implementation_plan(2))

    # Combined smoke test with the new BiasOverrideEngine (Phase 0.3)
    try:
        from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
        import pandas as pd
        import numpy as np

        print("\n--- BiasOverrideEngine integration demo ---")
        engine = BiasOverrideEngine()
        print(f"Engine loaded with {len(engine.registry)} registry points.")

        # Tiny synthetic df
        np.random.seed(123)
        df = pd.DataFrame({
            "close": np.linspace(1, 1.1, 60),
            "high": np.linspace(1, 1.1, 60) + 0.01,
            "low": np.linspace(1, 1.1, 60) - 0.01,
            "volume": np.random.uniform(5e5, 2e6, 60),
            "quote_volume": np.random.uniform(3e5, 1.5e6, 60),
            "count": np.random.randint(200, 4000, 60),
        })

        status = engine.get_override_status("01", symbol="DEMOUSDT", df=df)
        print(f"Point 01 status snapshot: action={status['recommended_action']}, reason={status['reason']}")

        raw = 0.71
        final = engine.apply_override("01", raw_value=raw, df=df, symbol="DEMOUSDT")
        print(f"apply_override('01') returned raw (as expected while status=not_started): {final}")

        print("Combined registry + classifier + engine demo complete.")
    except Exception as e:
        print(f"(Engine demo skipped or failed: {e})")