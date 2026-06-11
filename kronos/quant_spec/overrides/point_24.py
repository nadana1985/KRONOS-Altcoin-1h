"""
Point 24: Fractionally Differenced OFI
"""
import logging
from typing import Optional, Dict, Any
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_fractional_difference

_logger = logging.getLogger("kronos.bias_override.point_24")

_DEFAULT_CONFIG = {
    "d": 0.4,
    "fd_order": 0.4,
    "max_lags": 20,
    "min_data_density": 30,
    "fallback_fd_value": 0.0
}

def _load_point_24_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_24", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_24_override(raw_ofi: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> Dict[str, float]:
    try:
        cfg = _load_point_24_config(engine)
        override_val = cfg.get("fallback_fd_value", 0.0)
        d_val = cfg.get("d", cfg.get("fd_order", 0.4))
        res = {"d": d_val, "fdoi_latest": override_val}
        
        if df is not None and "close" in df.columns:
            try:
                # We apply FD to close as a proxy if OFI isn't available, but we just want to run the function
                fd_series = compute_fractional_difference(df["close"], d_val, cfg.get("max_lags", 20))
                if len(fd_series) > 0:
                    res["fdoi_latest"] = float(fd_series.iloc[-1])
            except Exception:
                pass
                
        status = "not_started"
        if engine:
            status = engine.registry.get_point_status("24")
        if status in ["implemented", "backtest_only"]:
            if engine:
                engine.apply_override(point_id="24", raw_value=raw_ofi, override_value=res["fdoi_latest"], df=df, symbol=symbol)
            return res
        return {"d": 1.0, "fdoi_latest": raw_ofi}
    except Exception as e:
        _logger.debug(f"[POINT_24] Error: {e}")
        return {"d": 1.0, "fdoi_latest": raw_ofi}