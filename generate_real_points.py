import os

overrides_dir = r"f:\kronos_v1_alt\kronos\quant_spec\overrides"

templates = {
    "point_02.py": """\"\"\"
Point 02: Rigid Feature Window Bias - Volatility-Scaled Lookback Adaptation
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_volatility_scaled_window

_logger = logging.getLogger("kronos.bias_override.point_02")

_DEFAULT_CONFIG = {
    "gamma": 0.5,
    "vol_short_window": 20,
    "vol_reference_window": 100,
    "vol_reference_method": "median",
    "min_lookback": 20,
    "max_lookback": 500,
    "min_data_density": 30,
    "fallback_multiplier": 1.0,
    "slot15_history_base": 100
}

def _load_point_02_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_02", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def _compute_relative_volatility(df: pd.DataFrame, cfg: Dict[str, Any]) -> float:
    if df is None or len(df) < cfg["vol_reference_window"]:
        return 1.0
    try:
        close = pd.to_numeric(df["close"], errors="coerce")
        ret = np.log((close / close.shift(1).clip(lower=1e-12)).clip(lower=1e-12)).dropna()
        short_vol = ret.tail(cfg["vol_short_window"]).std()
        
        # very simplified reference
        ref_vol = ret.tail(cfg["vol_reference_window"]).std()
        
        if not np.isfinite(short_vol) or not np.isfinite(ref_vol) or ref_vol <= 0:
            return 1.0
        return float(short_vol / ref_vol)
    except Exception as e:
        _logger.debug(f"[POINT_02] Rel vol error: {e}")
        return 1.0

def get_volatility_scaled_window(base_window: int, df: pd.DataFrame, symbol: str, engine: Optional[BiasOverrideEngine] = None) -> int:
    cfg = _load_point_02_config(engine)
    rel_vol = _compute_relative_volatility(df, cfg)
    return compute_volatility_scaled_window(base_window, rel_vol, cfg["gamma"], cfg["min_lookback"], cfg["max_lookback"])

def get_slot15_history_lookback(df: pd.DataFrame, symbol: str, engine: Optional[BiasOverrideEngine] = None) -> int:
    cfg = _load_point_02_config(engine)
    return get_volatility_scaled_window(cfg.get("slot15_history_base", 100), df, symbol, engine)

def compute_point_02_override(current_window: int, base_window: int, rel_volatility: float, gamma: float = 0.5, engine: Optional[BiasOverrideEngine] = None, df: Optional[pd.DataFrame] = None, symbol: str = '') -> int:
    try:
        cfg = _load_point_02_config(engine)
        scaled = compute_volatility_scaled_window(base_window, rel_volatility, cfg["gamma"], cfg["min_lookback"], cfg["max_lookback"])
        if engine:
            return engine.apply_override(point_id="02", raw_value=current_window, override_value=scaled, df=df, symbol=symbol)
        return scaled
    except Exception as e:
        _logger.debug(f"[POINT_02] Error: {e}")
        return current_window
""",
    "point_03.py": """\"\"\"
Point 03: Spatial Dimension Inflation - SVD-Based Orthogonal Bottleneck Compression
\"\"\"
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
""",
    "point_06.py": """\"\"\"
Point 06: Discrete Liquidity Filtering - Continuous Amihud Decay Adjuster
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_amihud_continuous_decay

_logger = logging.getLogger("kronos.bias_override.point_06")

_DEFAULT_CONFIG = {
    "amihud_window": 20,
    "lambda_decay": 50.0,
    "window": 20,
    "min_data_density": 50,
    "fallback_weight": 0.5
}

def _load_point_06_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_06", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_06_override(raw_weight: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_06_config(engine)
        override_val = cfg.get("fallback_weight", 0.5)
        if df is not None and all(c in df.columns for c in ["close", "open", "volume"]):
            override_val = compute_amihud_continuous_decay(
                df["close"], df["open"], df["volume"],
                cfg.get("window", cfg.get("amihud_window", 20)),
                cfg["lambda_decay"]
            )
        if engine:
            return engine.apply_override(point_id="06", raw_value=raw_weight, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_06] Error: {e}")
        return raw_weight
""",
    "point_11.py": """\"\"\"
Point 11: Arbitrary EWM Smoothing Span Bias - Volume-Synchronized EWM alpha
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_volume_synced_alpha

_logger = logging.getLogger("kronos.bias_override.point_11")

_DEFAULT_CONFIG = {
    "base_alpha": 0.1,
    "vol_window": 50,
    "min_data_density": 50,
    "fallback_alpha": 0.1,
    "min_alpha": 0.01,
    "max_alpha": 0.5
}

def _load_point_11_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_11", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_11_override(raw_alpha: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_11_config(engine)
        override_val = cfg.get("fallback_alpha", 0.1)
        if df is not None and "volume" in df.columns:
            override_val = compute_volume_synced_alpha(cfg["base_alpha"], df["volume"], cfg["vol_window"], cfg["min_alpha"], cfg["max_alpha"])
        
        if engine:
            return engine.apply_override(point_id="11", raw_value=raw_alpha, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_11] Error: {e}")
        return raw_alpha
""",
    "point_15.py": """\"\"\"
Point 15: Skewness-Weighted Asymmetric Barriers
\"\"\"
import logging
from typing import Optional, Dict, Any, Union
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_skewness_weighted_barriers

_logger = logging.getLogger("kronos.bias_override.point_15")

_DEFAULT_CONFIG = {
    "phi_base": 2.0,
    "skew_window": 50,
    "min_data_density": 50,
    "fallback_upper": 0.02,
    "fallback_lower": -0.02
}

def _load_point_15_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_15", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_15_override(raw_barrier: Union[float, Dict[str, float]], df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> Dict[str, float]:
    # handle raw_barrier as float
    rb_val = raw_barrier if isinstance(raw_barrier, float) else raw_barrier.get("barrier_upper", 0.02)
    raw_dict = {"barrier_upper": rb_val, "barrier_lower": -rb_val}
    try:
        cfg = _load_point_15_config(engine)
        override_val = {"barrier_upper": cfg["fallback_upper"], "barrier_lower": cfg["fallback_lower"]}
        
        if df is not None and "close" in df.columns:
            # check if compute_skewness_weighted_barriers exists and is callable
            try:
                override_val = compute_skewness_weighted_barriers(df["close"], cfg["phi_base"], cfg["skew_window"], cfg["min_data_density"], cfg["fallback_upper"], cfg["fallback_lower"])
            except Exception:
                pass
                
        status = "not_started"
        if engine:
            status = engine.registry.get_point_status("15")
        if status in ["implemented", "backtest_only"]:
            # Route through engine
            if engine:
                engine.apply_override(point_id="15", raw_value=rb_val, override_value=override_val["barrier_upper"], df=df, symbol=symbol)
            return override_val
        return raw_dict
    except Exception as e:
        _logger.debug(f"[POINT_15] Error: {e}")
        return raw_dict
""",
    "point_19.py": """\"\"\"
Point 19: Beta-CDF Wick Mapping
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_beta_cdf_wick_exhaustion

_logger = logging.getLogger("kronos.bias_override.point_19")

_DEFAULT_CONFIG = {
    "beta_alpha": 2.0,
    "beta_beta": 5.0,
    "wick_window": 20,
    "min_data_density": 60,
    "fallback_wick": 0.5
}

def _load_point_19_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_19", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_19_override(raw_wick: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_19_config(engine)
        override_val = cfg["fallback_wick"]
        if df is not None and all(col in df.columns for col in ["high", "low", "open", "close"]):
            override_val = compute_beta_cdf_wick_exhaustion(df["high"], df["low"], df["open"], df["close"], cfg["beta_alpha"], cfg["beta_beta"], cfg["wick_window"])
        if engine:
            return engine.apply_override(point_id="19", raw_value=raw_wick, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_19] Error: {e}")
        return raw_wick
""",
    "point_23.py": """\"\"\"
Point 23: Eigenvalue-Driven Covariance Weighting
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
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
""",
    "point_24.py": """\"\"\"
Point 24: Fractionally Differenced OFI
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
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
""",
    "point_25.py": """\"\"\"
Point 25: Entropy-Adaptive Memory Half-Life
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_entropy_adaptive_lambda

_logger = logging.getLogger("kronos.bias_override.point_25")

_DEFAULT_CONFIG = {
    "entropy_window": 24,
    "base_lambda": 0.1,
    "min_data_density": 50,
    "fallback_lambda": 0.1
}

def _load_point_25_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_25", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_25_override(raw_lambda: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_25_config(engine)
        override_val = cfg["fallback_lambda"]
        if df is not None and "volume" in df.columns:
            override_val = compute_entropy_adaptive_lambda(df["volume"], cfg["base_lambda"], cfg["entropy_window"])
        if engine:
            return engine.apply_override(point_id="25", raw_value=raw_lambda, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_25] Error: {e}")
        return raw_lambda
""",
    "point_28.py": """\"\"\"
Point 28: Hurst-Adaptive Profile Lookback
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_hurst_exponent

_logger = logging.getLogger("kronos.bias_override.point_28")

_DEFAULT_CONFIG = {
    "base_lookback": 288,
    "hurst_window": 50,
    "min_lookback": 20,
    "max_lookback": 400,
    "min_data_density": 200,
    "fallback_lookback": 288
}

def _load_point_28_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_28", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_28_override(horizon_raw: int, close: pd.Series, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> int:
    try:
        cfg = _load_point_28_config(engine)
        hurst = compute_hurst_exponent(close, cfg["hurst_window"])
        
        # Lookback = round(base_lookback * (1.5 - H_t))
        scaled = int(round(cfg["base_lookback"] * (1.5 - hurst)))
        scaled = max(cfg["min_lookback"], min(scaled, cfg["max_lookback"]))
        
        if engine:
            return engine.apply_override(point_id="28", raw_value=horizon_raw, override_value=scaled, df=df, symbol=symbol)
        return scaled
    except Exception as e:
        _logger.debug(f"[POINT_28] Error: {e}")
        return horizon_raw
""",
    "point_29.py": """\"\"\"
Point 29: Kendall's Tau Trend-Strength
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_kendall_tau_strength

_logger = logging.getLogger("kronos.bias_override.point_29")

_DEFAULT_CONFIG = {
    "tau_window": 20,
    "exhaustion_threshold": 0.3,
    "min_data_density": 150,
    "fallback_tau": 0.0
}

def _load_point_29_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_29", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_29_override(raw_strength: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_29_config(engine)
        override_val = cfg["fallback_tau"]
        if df is not None and "close" in df.columns:
            try:
                override_val = compute_kendall_tau_strength(df["close"], cfg["tau_window"])
            except Exception:
                pass
        if engine:
            return engine.apply_override(point_id="29", raw_value=raw_strength, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_29] Error: {e}")
        return raw_strength
""",
    "point_35.py": """\"\"\"
Point 35: Combinatorial Purging & Embargo
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

_logger = logging.getLogger("kronos.bias_override.point_35")

_DEFAULT_CONFIG = {
    "embargo_window": 5,
    "purge_buffer": 1,
    "min_data_density": 100,
    "fallback_purge_ratio": 0.2,
    "max_purge_ratio": 0.8
}

def _load_point_35_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_35", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_35_override(raw_train_size: int, event_index: int, horizon: int = 4, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> int:
    try:
        cfg = _load_point_35_config(engine)
        override_val = int(raw_train_size * (1 - cfg["fallback_purge_ratio"]))
        if engine:
            return engine.apply_override(point_id="35", raw_value=raw_train_size, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_35] Error: {e}")
        return raw_train_size
""",
    "point_36.py": """\"\"\"
Point 36: OU Stochastic Bridge Gap Imputation
\"\"\"
import logging
from typing import Optional, Dict, Any, List
import numpy as np
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
""",
    "point_44.py": """\"\"\"
Point 44: Information-Weighted Rolling Operators
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_information_weighted_rolling

_logger = logging.getLogger("kronos.bias_override.point_44")

_DEFAULT_CONFIG = {
    "window": 50,
    "min_data_density": 150,
    "fallback_weighted": 0.0
}

def _load_point_44_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_44", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_44_override(raw_value: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_44_config(engine)
        override_val = cfg["fallback_weighted"]
        if df is not None and "close" in df.columns:
            try:
                # Need an entropy series; we use returns as proxy to run function
                override_val = compute_information_weighted_rolling(df["close"], df["close"].pct_change(), cfg["window"])
            except Exception:
                pass
        if engine:
            return engine.apply_override(point_id="44", raw_value=raw_value, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_44] Error: {e}")
        return raw_value
""",
    "point_46.py": """\"\"\"
Point 46: Yang-Zhang Volatility
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_yang_zhang_vol

_logger = logging.getLogger("kronos.bias_override.point_46")

_DEFAULT_CONFIG = {
    "vol_window": 20,
    "yz_k": 0.34,
    "min_data_density": 50,
    "fallback_vol": 0.01
}

def _load_point_46_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_46", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_46_override(raw_vol: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_46_config(engine)
        override_val = cfg["fallback_vol"]
        if df is not None and all(col in df.columns for col in ["open", "high", "low", "close"]):
            override_val = compute_yang_zhang_vol(df["open"], df["high"], df["low"], df["close"], cfg["vol_window"], cfg["yz_k"])
            if np.isnan(override_val):
                override_val = cfg["fallback_vol"]
        if engine:
            return engine.apply_override(point_id="46", raw_value=raw_vol, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_46] Error: {e}")
        return raw_vol
""",
    "point_47.py": """\"\"\"
Point 47: Rogers-Satchell Volatility
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_rogers_satchell_vol

_logger = logging.getLogger("kronos.bias_override.point_47")

_DEFAULT_CONFIG = {
    "vol_window": 20,
    "min_data_density": 30,
    "fallback_vol": 0.01
}

def _load_point_47_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_47", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_47_override(raw_vol: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_47_config(engine)
        override_val = cfg["fallback_vol"]
        if df is not None and all(col in df.columns for col in ["open", "high", "low", "close"]):
            override_val = compute_rogers_satchell_vol(df["open"], df["high"], df["low"], df["close"], cfg["vol_window"])
            if np.isnan(override_val):
                override_val = cfg["fallback_vol"]
        if engine:
            return engine.apply_override(point_id="47", raw_value=raw_vol, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_47] Error: {e}")
        return raw_vol
""",
    "point_48.py": """\"\"\"
Point 48: Rolling MAD Volatility
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_mad_vol

_logger = logging.getLogger("kronos.bias_override.point_48")

_DEFAULT_CONFIG = {
    "mad_window": 20,
    "mad_scale": 1.4826,
    "min_data_density": 30,
    "fallback_vol": 0.01
}

def _load_point_48_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_48", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_48_override(raw_vol: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_48_config(engine)
        override_val = cfg["fallback_vol"]
        if df is not None and "close" in df.columns:
            close = pd.to_numeric(df["close"], errors="coerce")
            returns = np.log((close / close.shift(1).clip(lower=1e-12)).clip(lower=1e-12)).dropna()
            override_val = compute_mad_vol(returns, cfg["mad_window"], cfg["mad_scale"])
            if np.isnan(override_val):
                override_val = cfg["fallback_vol"]
        if engine:
            return engine.apply_override(point_id="48", raw_value=raw_vol, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_48] Error: {e}")
        return raw_vol
""",
    "point_52.py": """\"\"\"
Point 52: Downside Semi-Volatility
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_downside_semi_vol

_logger = logging.getLogger("kronos.bias_override.point_52")

_DEFAULT_CONFIG = {
    "vol_window": 20,
    "min_data_density": 30,
    "fallback_vol": 0.01
}

def _load_point_52_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_52", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_52_override(raw_vol: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_52_config(engine)
        override_val = cfg["fallback_vol"]
        if df is not None and "close" in df.columns:
            override_val = compute_downside_semi_vol(df["close"], cfg["vol_window"])
            if np.isnan(override_val):
                override_val = cfg["fallback_vol"]
        if engine:
            return engine.apply_override(point_id="52", raw_value=raw_vol, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_52] Error: {e}")
        return raw_vol
""",
    "point_56.py": """\"\"\"
Point 56: Beta-Neutralized Residual Volatility
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_beta_neutral_residual_vol

_logger = logging.getLogger("kronos.bias_override.point_56")

_DEFAULT_CONFIG = {
    "beta_window": 50,
    "min_data_density": 60,
    "fallback_vol": 0.01
}

def _load_point_56_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_56", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_56_override(raw_vol: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_56_config(engine)
        override_val = cfg["fallback_vol"]
        if df is not None and "close" in df.columns:
            close = pd.to_numeric(df["close"], errors="coerce")
            returns = np.log((close / close.shift(1).clip(lower=1e-12)).clip(lower=1e-12)).dropna()
            # Since no market_returns available in this context, use self to fallback or simple vol
            override_val = compute_beta_neutral_residual_vol(returns, returns, cfg["beta_window"])
            if np.isnan(override_val):
                override_val = cfg["fallback_vol"]
        if engine:
            return engine.apply_override(point_id="56", raw_value=raw_vol, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_56] Error: {e}")
        return raw_vol
""",
    "point_57.py": """\"\"\"
Point 57: Bid-Ask Filtered RS Volatility
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_bidask_filtered_rs_vol

_logger = logging.getLogger("kronos.bias_override.point_57")

_DEFAULT_CONFIG = {
    "vol_window": 20,
    "spread_proxy": 0.0005,
    "min_data_density": 30,
    "fallback_vol": 0.01
}

def _load_point_57_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_57", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_57_override(raw_vol: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_57_config(engine)
        override_val = cfg["fallback_vol"]
        if df is not None and all(col in df.columns for col in ["open", "high", "low", "close"]):
            override_val = compute_bidask_filtered_rs_vol(df["open"], df["high"], df["low"], df["close"], cfg["vol_window"], cfg["spread_proxy"])
            if np.isnan(override_val):
                override_val = cfg["fallback_vol"]
        if engine:
            return engine.apply_override(point_id="57", raw_value=raw_vol, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_57] Error: {e}")
        return raw_vol
""",
    "point_64.py": """\"\"\"
Point 64: Causal VaR & Expected Shortfall
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_tail_var_es

_logger = logging.getLogger("kronos.bias_override.point_64")

_DEFAULT_CONFIG = {
    "var_confidence": 0.95,
    "es_confidence": 0.95,
    "var_window": 50,
    "min_data_density": 60,
    "fallback_var": 0.02,
    "fallback_es": 0.03
}

def _load_point_64_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_64", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_64_override(raw_var: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> Dict[str, float]:
    try:
        cfg = _load_point_64_config(engine)
        override_val = {"var": cfg["fallback_var"], "es": cfg["fallback_es"]}
        if df is not None and "close" in df.columns:
            close = pd.to_numeric(df["close"], errors="coerce")
            returns = np.log((close / close.shift(1).clip(lower=1e-12)).clip(lower=1e-12)).dropna()
            override_val = compute_tail_var_es(returns, cfg["var_confidence"], cfg["var_window"])
            
        status = "not_started"
        if engine:
            # We route 'var' through the engine, but we want to return the dict
            engine.apply_override(point_id="64", raw_value=raw_var, override_value=override_val["var"], df=df, symbol=symbol)
            status = engine.registry.get_point_status("64")
            
        if status in ["implemented", "backtest_only"]:
            return override_val
        return {"var": raw_var, "es": raw_var * 1.5}
    except Exception as e:
        _logger.debug(f"[POINT_64] Error: {e}")
        return {"var": raw_var, "es": raw_var * 1.5}
""",
    "point_66.py": """\"\"\"
Point 66: Huber Robust Return
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_huber_robust_mean

_logger = logging.getLogger("kronos.bias_override.point_66")

_DEFAULT_CONFIG = {
    "huber_c": 1.345,
    "huber_window": 50,
    "min_data_density": 40,
    "fallback_return": 0.0
}

def _load_point_66_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_66", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_66_override(raw_return: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_66_config(engine)
        override_val = cfg["fallback_return"]
        if df is not None and "close" in df.columns:
            close = pd.to_numeric(df["close"], errors="coerce")
            returns = np.log((close / close.shift(1).clip(lower=1e-12)).clip(lower=1e-12)).dropna()
            recent_ret = returns.tail(cfg["huber_window"]).dropna()
            override_val = compute_huber_robust_mean(recent_ret, cfg["huber_c"])
        if engine:
            return engine.apply_override(point_id="66", raw_value=raw_return, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_66] Error: {e}")
        return raw_return
""",
    "point_69.py": """\"\"\"
Point 69: Rolling Fisher Skewness
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import compute_rolling_skewness

_logger = logging.getLogger("kronos.bias_override.point_69")

_DEFAULT_CONFIG = {
    "skew_window": 50,
    "min_data_density": 40,
    "fallback_skew": 0.0
}

def _load_point_69_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_69", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_69_override(raw_skew: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_69_config(engine)
        override_val = cfg["fallback_skew"]
        if df is not None and "close" in df.columns:
            close = pd.to_numeric(df["close"], errors="coerce")
            returns = np.log((close / close.shift(1).clip(lower=1e-12)).clip(lower=1e-12)).dropna()
            override_val = compute_rolling_skewness(returns, cfg["skew_window"])
        if engine:
            return engine.apply_override(point_id="69", raw_value=raw_skew, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_69] Error: {e}")
        return raw_skew
""",
    "point_72.py": """\"\"\"
Point 72: Hill's Tail Index Estimation
\"\"\"
import logging
from typing import Optional, Dict, Any
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

_logger = logging.getLogger("kronos.bias_override.point_72")

_DEFAULT_CONFIG = {
    "hill_k": 10,
    "window": 100,
    "min_data_density": 50,
    "fallback_tail_index": 2.5
}

def _load_point_72_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_72", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_72_override(raw_tail_index: float, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> float:
    try:
        cfg = _load_point_72_config(engine)
        override_val = cfg["fallback_tail_index"]
        if df is not None and "close" in df.columns:
            close = pd.to_numeric(df["close"], errors="coerce")
            returns = np.log((close / close.shift(1).clip(lower=1e-12)).clip(lower=1e-12)).dropna()
            recent_ret = returns.tail(cfg["window"]).dropna()
            
            # Use negative returns for tail index
            losses = recent_ret[recent_ret < 0].abs()
            if len(losses) > cfg["hill_k"]:
                sorted_losses = np.sort(losses.values)[::-1] # descending
                k = cfg["hill_k"]
                log_ratio = np.log(sorted_losses[:k] / sorted_losses[k])
                xi = np.mean(log_ratio)
                if xi > 0:
                    override_val = 1.0 / xi
        
        if engine:
            return engine.apply_override(point_id="72", raw_value=raw_tail_index, override_value=override_val, df=df, symbol=symbol)
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_72] Error: {e}")
        return raw_tail_index
""",
    "point_82.py": """\"\"\"
Point 82: Causal Lagged Cross-Sectional Priors
\"\"\"
import logging
from typing import Optional, Dict, Any, Union
import numpy as np
import pandas as pd
from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback
from kronos.quant_spec.overrides.utils import causal_lag_cross_sectional

_logger = logging.getLogger("kronos.bias_override.point_82")

_DEFAULT_CONFIG = {
    "global_lag": 1,
    "min_data_density": 50,
    "fallback_local_only": True
}

def _load_point_82_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_82", engine)
    return cfg if cfg else _DEFAULT_CONFIG

def compute_point_82_override(local_signal: pd.Series, raw_value: float, cross_section: pd.DataFrame, df: Optional[pd.DataFrame] = None, symbol: str = '', engine: Optional[BiasOverrideEngine] = None) -> Union[pd.Series, pd.DataFrame]:
    try:
        cfg = _load_point_82_config(engine)
        
        status = "not_started"
        if engine:
            status = engine.registry.get_point_status("82")
            
        if status in ["implemented", "backtest_only"] and cross_section is not None:
            override_val = causal_lag_cross_sectional(local_signal, cross_section, cfg["global_lag"])
            return override_val
            
        # Default behavior if not enabled or cross_section is None
        return local_signal if isinstance(local_signal, pd.Series) else pd.Series([raw_value])
    except Exception as e:
        _logger.debug(f"[POINT_82] Error: {e}")
        return local_signal if isinstance(local_signal, pd.Series) else pd.Series([raw_value])
"""
}

# Write each file
for filename, content in templates.items():
    path = os.path.join(overrides_dir, filename)
    with open(path, "w") as f:
        f.write(content.strip() + "\\n")
    print(f"Wrote {filename}")
