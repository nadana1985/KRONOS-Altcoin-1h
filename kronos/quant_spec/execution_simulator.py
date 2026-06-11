"""
KRONOS V1-ALT — Execution Simulator (Points 93, 94, 95, 100)

Realistic backtesting execution model replacing instant-fill-at-close.
Combines latency slippage, dynamic costs, TWAP, and impact-aware sizing.
All parameters from liquidity_tiers.yaml via BiasOverrideEngine.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger("kronos.execution_simulator")

# Module-level import for performance (avoids per-call import overhead)
from kronos.quant_spec.bias_override_engine import (
    is_overrides_enabled as _overrides_enabled,
    set_overrides_enabled,  # re-export for backward compatibility
)

# Performance: Pre-import point modules at module level (not inside methods)
from kronos.quant_spec.overrides.point_93 import compute_point_93_override
from kronos.quant_spec.overrides.point_94 import compute_point_94_override
from kronos.quant_spec.overrides.point_95 import compute_point_95_override
from kronos.quant_spec.overrides.point_100 import compute_point_100_override

def apply_point_with_fallback(
    point_id: str, raw_value: Any, df: pd.DataFrame, symbol: str,
    engine=None, override_fn=None, **kwargs,
) -> Any:
    """Apply a single point override with master switch fallback."""
    if not _overrides_enabled():
        return raw_value
    if engine is None:
        from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
        engine = BiasOverrideEngine()
    override_value = None
    if override_fn is not None:
        try:
            override_value = override_fn()
        except Exception as e:
            logger.warning("[OVERRIDES] Point %s override_fn failed: %s", point_id, e)
    return engine.apply_override(
        point_id=point_id, raw_value=raw_value, df=df, symbol=symbol,
        override_value=override_value, **kwargs,
    )

class ExecutionSimulator:
    """Combines Points 93, 94, 95, 100 into a single execution simulation pipeline."""

    def __init__(self, engine=None):
        if engine is None:
            from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
            self.engine = BiasOverrideEngine()
        else:
            self.engine = engine

    def simulate_execution(
        self, signal_price: float, volatility: float, df: pd.DataFrame,
        symbol: str, order_size_usd: float, volume_usd: float, **kwargs,
    ) -> Dict[str, Any]:
        """Simulate realistic execution: latency + costs + TWAP + sizing."""
        # Point 93: Latency-adjusted price (module-level import)
        p93 = compute_point_93_override(
            signal_price, df, symbol, engine=self.engine, volatility=volatility, **kwargs)
        executed_price = p93.get("engine_final_price", signal_price)
        slippage_bps = p93.get("slippage_bps", 0.0)

        # Point 94: Dynamic cost (module-level import)
        p94 = compute_point_94_override(
            10.0, df, symbol, engine=self.engine,
            order_size_usd=order_size_usd, volume_usd=volume_usd, **kwargs)
        cost_bps = p94.get("engine_final_cost_bps", 10.0)

        # Point 95: TWAP execution (module-level import)
        p95 = compute_point_95_override(executed_price, df, symbol, engine=self.engine, **kwargs)
        twap_price = p95.get("engine_final_price", executed_price)

        # Point 100: Impact-aware sizing (module-level import)
        p100 = compute_point_100_override(
            order_size_usd, df, symbol, engine=self.engine,
            volatility=volatility, volume_usd=volume_usd, **kwargs)
        final_size = p100.get("engine_final_size", order_size_usd)

        total_cost_bps = slippage_bps + cost_bps
        total_cost_usd = final_size * total_cost_bps / 10000.0
        net_price = twap_price * (1 + total_cost_bps / 10000.0)

        return {
            "signal_price": signal_price, "executed_price": executed_price,
            "twap_price": twap_price, "net_price": net_price,
            "slippage_bps": slippage_bps, "cost_bps": cost_bps,
            "total_cost_bps": total_cost_bps, "total_cost_usd": total_cost_usd,
            "order_size_usd": order_size_usd, "final_size_usd": final_size,
            "impact_adjustment": p100.get("impact_adjustment", 1.0), "symbol": symbol,
        }

if __name__ == "__main__":
    print("=== ExecutionSimulator Smoke ===")
    rng = np.random.default_rng(42)
    n = 100
    df = pd.DataFrame({
        "open": 100 + np.cumsum(rng.normal(0, 0.5, n)),
        "high": 101 + np.cumsum(rng.normal(0, 0.5, n)),
        "low": 99 + np.cumsum(rng.normal(0, 0.5, n)),
        "close": 100 + np.cumsum(rng.normal(0, 0.5, n)),
        "volume": rng.uniform(1e6, 1e8, n),
        "quote_volume": rng.uniform(1e6, 1e8, n),
        "count": rng.integers(100, 5000, n),
    })
    df["high"] = df[["high", "close"]].max(axis=1)
    df["low"] = df[["low", "close"]].min(axis=1)
    sim = ExecutionSimulator()
    r = sim.simulate_execution(100.0, 0.02, df, "TESTUSDT", 5000.0, 1e7)
    print(f"Signal=${r['signal_price']:.2f} Net=${r['net_price']:.2f} Cost={r['total_cost_bps']:.1f}bps Size=${r['final_size_usd']:.0f}")
    from kronos.quant_spec.bias_override_engine import set_overrides_enabled
    set_overrides_enabled(False)
    raw = apply_point_with_fallback("93", 100.0, df, "TESTUSDT")
    print(f"Master OFF -> raw={raw}")
    set_overrides_enabled(True)
    print("Done.")
