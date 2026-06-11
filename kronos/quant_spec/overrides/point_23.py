"""
Point 23: Eigenvalue-Driven Covariance Weighting
"""
import logging
from typing import Optional, Dict, Any
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_eigenvalue_covariance_weight

_logger = logging.getLogger("kronos.bias_override.point_23")

_DEFAULT_CONFIG = {
    "window": 50,
    "pca_window": 50,
    "min_data_density": 30,
    "fallback_weight": 0.5
}

def _load_point_23_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_23", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_23_override(raw_weight: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_23_config(engine)
        override_val = cfg["fallback_weight"]
        if df is not None and all(c in df.columns for c in ["close", "volume"]):
            try:
                override_val = compute_eigenvalue_covariance_weight(df["close"], df["volume"], cfg.get("window", cfg.get("pca_window", 50)), cfg.get("min_data_density", 30))
            except Exception:
                pass
        if engine:
            return engine.apply_override(point_id="23", raw_value=raw_weight, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_23] Error: {e}")
        return raw_weight