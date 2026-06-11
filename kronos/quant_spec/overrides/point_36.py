"""
Point 36: OU Stochastic Bridge Gap Imputation
"""
import logging
from typing import Optional, Dict, Any, List
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_ou_stochastic_bridge

_logger = logging.getLogger("kronos.bias_override.point_36")

_DEFAULT_CONFIG = {
    "theta": 0.1,
    "sigma_scale": 1.0,
    "n_paths": 50,
    "min_data_density": 100,
    "fallback_fill": 0.0
}

def _load_point_36_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_36", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_36_override(fill_raw: float, close: pd.Series, gap_indices: List[int], df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_36_config(engine)
        override_val = cfg["fallback_fill"]
        if df is not None and "close" in df.columns:
            try:
                res = compute_ou_stochastic_bridge(df["close"], gap_indices, cfg["theta"], cfg["sigma_scale"], cfg["n_paths"])
                if len(res) > 0:
                    override_val = float(res.iloc[-1])
            except Exception:
                pass
        if engine:
            return engine.apply_override(point_id="36", raw_value=fill_raw, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_36] Error: {e}")
        return fill_raw