"""
KRONOS V1-ALT — Bias Override Point 51: "Volatility Clustering Feedback Ignorance"

Manual description:
  "Modeling volatility as an independent, memoryless process."

Quant replacement:
  "Empirical GARCH(1,1) Volatility Tracker. Reconstruct conditional variance feedback
   loops dynamically: sigma_t^2 = omega + alpha * r_{t-1}^2 + beta * sigma_{t-1}^2."

Uses shared compute_garch_vol with configurable omega/alpha/beta from YAML.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_garch_vol, compute_close_to_close_vol
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_51")

_DEFAULT_POINT_51_CONFIG = {
    "garch_omega": 1e-6, "garch_alpha": 0.08, "garch_beta": 0.85,
    "garch_window": 50, "min_data_density": 60, "fallback_vol": 0.01
}


def _load_point_51_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_51", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_51_CONFIG


def compute_garch_volatility(
    close: pd.Series, config: Optional[Dict[str, Any]] = None,
) -> float:
    cfg = config or {}
    w = int(cfg.get("garch_window", 50))
    omega = float(cfg.get("garch_omega", 1e-6))
    alpha = float(cfg.get("garch_alpha", 0.08))
    beta = float(cfg.get("garch_beta", 0.85))
    min_d = int(cfg.get("min_data_density", 60))
    fb = float(cfg.get("fallback_vol", 0.01))

    if len(close) < min_d:
        return fb
    r = (close / close.shift(1) - 1.0).dropna()
    vol = compute_garch_vol(r, omega, alpha, beta, w)
    if not np.isfinite(vol) or vol <= 0:
        vol = fb
    logger.info("[POINT_51] garch(1,1) | a=%.2f b=%.2f w=%d -> vol=%.5f", alpha, beta, w, vol)
    return float(vol)


def compute_point_51_override(
    raw_vol: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> float:
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_51_config(engine)

    c = pd.to_numeric(df.get("close"), errors="coerce")
    raw_val = float(raw_vol) if np.isfinite(raw_vol) else compute_close_to_close_vol(c, int(cfg.get("garch_window", 50)))
    new_val = compute_garch_volatility(c, config=cfg)

    final = engine.apply_override(
        point_id="51",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_51] decision | %s raw=%.5f new=%.5f final=%.5f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 51 GARCH Smoke ===")
    engine = BiasOverrideEngine()
    n = 100
    rng = np.random.default_rng(51)
    # Clustered vol
    vols = np.ones(n) * 0.006
    vols[30:60] = 0.018
    rets = rng.normal(0, vols)
    c = 100 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({"close": c})
    raw = 0.008
    final = compute_point_51_override(raw, df, "TEST51", engine=engine)
    print(f"raw={raw:.4f} -> final={final:.4f}")
    print("Smoke done.")
