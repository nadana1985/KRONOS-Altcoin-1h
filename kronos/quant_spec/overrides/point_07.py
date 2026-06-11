"""
KRONOS V1-ALT — Bias Override Point 07: "Arbitrary Formula Assembly Bias"

Manual description:
  "Manually defining structural-neural combinations imposes unverified
   mathematical shapes."

Quant replacement:
  "GP-Evolved Parsimonious Polynomial Mapping. Use Symbolic Regression to
   evolve the optimal predictive function mapped to a dynamic target Y:
   f(X)_GP s.t. min[MSE + alpha * AIC(f)]."

Practical implementation: BIC-penalized polynomial feature expansion with
automatic degree selection. Full GP symbolic regression is too compute-heavy
for real-time use, so this uses polynomial basis with parsimony penalty as
a practical approximation that captures the same spirit.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_parsimonious_polynomial_map
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_07")



_DEFAULT_POINT_07_CONFIG = {
            "max_degree": 3,
            "alpha_parsimony": 1.0,
            "min_data_density": 500,
            "fallback_degree": 1,
        }


def compute_parsimonious_mapping(
    X: np.ndarray,
    y: np.ndarray,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Compute BIC-penalized polynomial mapping from X to y."""
    cfg = config or {}
    max_deg = int(cfg.get("max_degree", 3))
    alpha = float(cfg.get("alpha_parsimony", 1.0))
    min_d = int(cfg.get("min_data_density", 500))
    fb_deg = int(cfg.get("fallback_degree", 1))

    if len(X) < min_d or len(y) < min_d:
        logger.info("[POINT_07] insufficient data (%d < %d) — fallback linear", len(X), min_d)
        if len(X) >= 2:
            coeffs = np.polyfit(X.ravel(), y, fb_deg)
            return {"coeffs": coeffs, "degree": fb_deg, "bic": 0.0, "predictions": np.polyval(coeffs, X.ravel())}
        return {"coeffs": np.array([0.0]), "degree": 0, "bic": np.inf, "predictions": np.zeros_like(y)}

    result = compute_parsimonious_polynomial_map(X, y, max_deg, alpha, min_samples=min_d)
    logger.info(
        "[POINT_07] parsimonious_poly | max_deg=%d alpha=%.2f -> degree=%d bic=%.1f",
        max_deg, alpha, result["degree"], result["bic"],
    )
    return result


def compute_point_07_override(
    raw_formula_result: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    X: Optional[np.ndarray] = None,
    y: Optional[np.ndarray] = None,
    **kwargs,
) -> dict:
    """Wrapper for Point 07. Returns parsimonious polynomial mapping result."""
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_07_config(engine)

    raw_val = float(raw_formula_result) if np.isfinite(raw_formula_result) else 0.0

    if X is None or y is None:
        # Generate demo data from df
        c = pd.to_numeric(df.get("close"), errors="coerce").dropna()
        v = pd.to_numeric(df.get("volume"), errors="coerce").dropna()
        n = min(len(c), len(v))
        if n < 2:
            return {"coeffs": np.array([0.0]), "degree": 0, "bic": np.inf, "engine_final": raw_val}
        X = c.iloc[-n:].values.reshape(-1, 1)
        y = v.iloc[-n:].values

    result = compute_parsimonious_mapping(X, y, config=cfg)

    # Engine routing uses BIC as quality proxy (lower is better, negate for override)
    bic_proxy = -result.get("bic", 0.0)
    engine_final = engine.apply_override(
        point_id="07",
        raw_value=raw_val,
        override_value=bic_proxy,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    result["engine_final"] = float(engine_final)
    return result


if __name__ == "__main__":
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 07 Parsimonious Polynomial Smoke ===")
    engine = BiasOverrideEngine()
    rng = np.random.default_rng(7)
    n = 100
    X = np.linspace(0, 10, n).reshape(-1, 1)
    y = 2.0 * X.ravel() ** 2 - 3.0 * X.ravel() + 5.0 + rng.normal(0, 2.0, n)
    df = pd.DataFrame({"close": X.ravel(), "volume": y})
    result = compute_point_07_override(0.0, df, "TEST07", engine=engine, X=X, y=y)
    print(f"  best degree: {result['degree']}")
    print(f"  coeffs: {result['coeffs']}")
    print(f"  BIC: {result['bic']:.2f}")

def _load_point_07_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_07", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_07_CONFIG

def compute_parsimonious_mapping(
    X: np.ndarray,
    y: np.ndarray,
    config: Optional[Dict[str, Any]] = None,
) -> dict:
    """Compute BIC-penalized polynomial mapping from X to y."""
    cfg = config or {}
    max_deg = int(cfg.get("max_degree", 3))
    alpha = float(cfg.get("alpha_parsimony", 1.0))
    min_d = int(cfg.get("min_data_density", 500))
    fb_deg = int(cfg.get("fallback_degree", 1))

    if len(X) < min_d or len(y) < min_d:
        logger.info("[POINT_07] insufficient data (%d < %d) — fallback linear", len(X), min_d)
        if len(X) >= 2:
            coeffs = np.polyfit(X.ravel(), y, fb_deg)
            return {"coeffs": coeffs, "degree": fb_deg, "bic": 0.0, "predictions": np.polyval(coeffs, X.ravel())}
        return {"coeffs": np.array([0.0]), "degree": 0, "bic": np.inf, "predictions": np.zeros_like(y)}

    result = compute_parsimonious_polynomial_map(X, y, max_deg, alpha, min_samples=min_d)
    logger.info(
        "[POINT_07] parsimonious_poly | max_deg=%d alpha=%.2f -> degree=%d bic=%.1f",
        max_deg, alpha, result["degree"], result["bic"],
    )
    return result


def compute_point_07_override(
    raw_formula_result: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    X: Optional[np.ndarray] = None,
    y: Optional[np.ndarray] = None,
    **kwargs,
) -> dict:
    """Wrapper for Point 07. Returns parsimonious polynomial mapping result."""
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_07_config(engine)

    raw_val = float(raw_formula_result) if np.isfinite(raw_formula_result) else 0.0

    if X is None or y is None:
        # Generate demo data from df
        c = pd.to_numeric(df.get("close"), errors="coerce").dropna()
        v = pd.to_numeric(df.get("volume"), errors="coerce").dropna()
        n = min(len(c), len(v))
        if n < 2:
            return {"coeffs": np.array([0.0]), "degree": 0, "bic": np.inf, "engine_final": raw_val}
        X = c.iloc[-n:].values.reshape(-1, 1)
        y = v.iloc[-n:].values

    result = compute_parsimonious_mapping(X, y, config=cfg)

    # Engine routing uses BIC as quality proxy (lower is better, negate for override)
    bic_proxy = -result.get("bic", 0.0)
    engine_final = engine.apply_override(
        point_id="07",
        raw_value=raw_val,
        override_value=bic_proxy,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    result["engine_final"] = float(engine_final)
    return result


if __name__ == "__main__":
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 07 Parsimonious Polynomial Smoke ===")
    engine = BiasOverrideEngine()
    rng = np.random.default_rng(7)
    n = 100
    X = np.linspace(0, 10, n).reshape(-1, 1)
    y = 2.0 * X.ravel() ** 2 - 3.0 * X.ravel() + 5.0 + rng.normal(0, 2.0, n)
    df = pd.DataFrame({"close": X.ravel(), "volume": y})
    result = compute_point_07_override(0.0, df, "TEST07", engine=engine, X=X, y=y)
    print(f"  best degree: {result['degree']}")
    print(f"  coeffs: {result['coeffs']}")
    print(f"  BIC: {result['bic']:.2f}")
    print("Smoke done.")
