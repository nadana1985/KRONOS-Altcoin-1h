"""
KRONOS V1-ALT — Bias Override Point 20: "Trade-Count Uniform Weighting"

Manual description:
  "Treating raw trade count as a stationary linear variable, ignoring
   institutional algorithmic slicing and retail concentration."

Quant replacement:
  "Normalized Shannon Count Entropy. Measure trade density concentration
   relative to the volume profile:
   Entropy_t = - sum (V_i / (Count_t + eps)) * ln(V_i / (Count_t + eps))."

Uses shared compute_shannon_count_entropy.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import compute_shannon_count_entropy
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_20")



_DEFAULT_POINT_20_CONFIG = {
            "entropy_window": 50,
            "n_bins": 10,
            "min_data_density": 150,
            "fallback_entropy": 0.5,
        }


def compute_trade_entropy(
    volume: pd.Series,
    trade_count: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Compute normalized Shannon entropy of trade density."""
    cfg = config or {}
    w = int(cfg.get("entropy_window", 50))
    n_bins = int(cfg.get("n_bins", 10))
    min_d = int(cfg.get("min_data_density", 150))
    fb = float(cfg.get("fallback_entropy", 0.5))

    v = pd.to_numeric(volume, errors="coerce").dropna()
    cnt = pd.to_numeric(trade_count, errors="coerce").dropna()
    n = min(len(v), len(cnt))
    if n < min_d:
        logger.info("[POINT_20] insufficient data — fallback entropy %.3f", fb)
        return fb

    entropy = compute_shannon_count_entropy(v, cnt, w, n_bins)
    logger.info("[POINT_20] shannon_entropy | window=%d bins=%d -> entropy=%.4f", w, n_bins, entropy)
    return entropy


def compute_point_20_override(
    raw_entropy: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    volume_col: str = "volume",
    count_col: str = "count",
    **kwargs,
) -> float:
    """Wrapper for Point 20. Returns normalized Shannon entropy in [0, 1]."""
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_20_config(engine)

    raw_val = float(raw_entropy) if np.isfinite(raw_entropy) else float(cfg.get("fallback_entropy", 0.5))

    v = pd.to_numeric(df.get(volume_col), errors="coerce")
    cnt = pd.to_numeric(df.get(count_col), errors="coerce")
    if v is None or cnt is None:
        return raw_val

    new_val = compute_trade_entropy(v, cnt, config=cfg)

    final = engine.apply_override(
        point_id="20",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_20] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 20 Shannon Count Entropy Smoke ===")
    engine = BiasOverrideEngine()
    rng = np.random.default_rng(20)
    n = 200
    # Uniform trade distribution (high entropy)
    vol_uniform = rng.uniform(500_000, 1_000_000, n)
    count_uniform = rng.randint(1000, 2000, n).astype(float)
    # Concentrated trade distribution (low entropy — institutional slicing)
    vol_concentrated = np.concatenate([
        np.full(n // 4, 10_000_000),
        np.full(n - n // 4, 100_000),
    ])
    count_concentrated = np.concatenate([
        np.full(n // 4, 10),  # few huge trades
        np.full(n - n // 4, 5000),  # many small trades
    ])
    df_u = pd.DataFrame({"volume": vol_uniform, "count": count_uniform})
    df_c = pd.DataFrame({"volume": vol_concentrated, "count": count_concentrated})
    e_u = compute_point_20_override(0.5, df_u, "UNIFORM", engine=engine)
    e_c = compute_point_20_override(0.5, df_c, "CONCENTRATED", engine=engine)
    print(f"  uniform entropy:     {e_u:.4f} (should be higher)")
    print(f"  concentrated entropy: {e_c:.4f}")

def _load_point_20_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_20", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_20_CONFIG

def compute_trade_entropy(
    volume: pd.Series,
    trade_count: pd.Series,
    config: Optional[Dict[str, Any]] = None,
) -> float:
    """Compute normalized Shannon entropy of trade density."""
    cfg = config or {}
    w = int(cfg.get("entropy_window", 50))
    n_bins = int(cfg.get("n_bins", 10))
    min_d = int(cfg.get("min_data_density", 150))
    fb = float(cfg.get("fallback_entropy", 0.5))

    v = pd.to_numeric(volume, errors="coerce").dropna()
    cnt = pd.to_numeric(trade_count, errors="coerce").dropna()
    n = min(len(v), len(cnt))
    if n < min_d:
        logger.info("[POINT_20] insufficient data — fallback entropy %.3f", fb)
        return fb

    entropy = compute_shannon_count_entropy(v, cnt, w, n_bins)
    logger.info("[POINT_20] shannon_entropy | window=%d bins=%d -> entropy=%.4f", w, n_bins, entropy)
    return entropy


def compute_point_20_override(
    raw_entropy: float,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    volume_col: str = "volume",
    count_col: str = "count",
    **kwargs,
) -> float:
    """Wrapper for Point 20. Returns normalized Shannon entropy in [0, 1]."""
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_20_config(engine)

    raw_val = float(raw_entropy) if np.isfinite(raw_entropy) else float(cfg.get("fallback_entropy", 0.5))

    v = pd.to_numeric(df.get(volume_col), errors="coerce")
    cnt = pd.to_numeric(df.get(count_col), errors="coerce")
    if v is None or cnt is None:
        return raw_val

    new_val = compute_trade_entropy(v, cnt, config=cfg)

    final = engine.apply_override(
        point_id="20",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_20] decision | %s raw=%.4f new=%.4f final=%.4f", symbol, raw_val, new_val, final)
    return float(final)


if __name__ == "__main__":
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
    print("=== Point 20 Shannon Count Entropy Smoke ===")
    engine = BiasOverrideEngine()
    rng = np.random.default_rng(20)
    n = 200
    # Uniform trade distribution (high entropy)
    vol_uniform = rng.uniform(500_000, 1_000_000, n)
    count_uniform = rng.randint(1000, 2000, n).astype(float)
    # Concentrated trade distribution (low entropy — institutional slicing)
    vol_concentrated = np.concatenate([
        np.full(n // 4, 10_000_000),
        np.full(n - n // 4, 100_000),
    ])
    count_concentrated = np.concatenate([
        np.full(n // 4, 10),  # few huge trades
        np.full(n - n // 4, 5000),  # many small trades
    ])
    df_u = pd.DataFrame({"volume": vol_uniform, "count": count_uniform})
    df_c = pd.DataFrame({"volume": vol_concentrated, "count": count_concentrated})
    e_u = compute_point_20_override(0.5, df_u, "UNIFORM", engine=engine)
    e_c = compute_point_20_override(0.5, df_c, "CONCENTRATED", engine=engine)
    print(f"  uniform entropy:     {e_u:.4f} (should be higher)")
    print(f"  concentrated entropy: {e_c:.4f} (should be lower)")
    print("Smoke done.")
