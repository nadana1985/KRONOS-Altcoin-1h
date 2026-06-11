"""
Point 03: Spatial Dimension Inflation - SVD-Based Orthogonal Bottleneck Compression
"""
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_svd_bottleneck_compression

_logger = logging.getLogger("kronos.bias_override.point_03")

_DEFAULT_CONFIG = {
    "n_components": 3,
    "noise_std": 0.01,
    "min_data_density": 300
}

def _load_point_03_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_03", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_03_override(neural_vector: np.ndarray, target_rank: Optional[int] = None, engine: Optional[BiasOverrideEngine] = None, df: Optional[pd.DataFrame] = None, symbol: str = '') -> np.ndarray:
    try:
        cfg = _load_point_03_config(engine)
        override_val = neural_vector
        
        # Assuming neural_vector is a 1D array or 2D matrix
        if isinstance(neural_vector, np.ndarray) and neural_vector.size > 0:
            matrix = neural_vector if neural_vector.ndim == 2 else neural_vector.reshape(1, -1)
            res = compute_svd_bottleneck_compression(matrix, cfg["n_components"], cfg["noise_std"])
            if "compressed" in res:
                compressed = res["compressed"]
                override_val = compressed.flatten() if neural_vector.ndim == 1 else compressed
                
        if engine:
            return engine.apply_override(point_id="03", raw_value=neural_vector, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_03] Error: {e}")
        return neural_vector