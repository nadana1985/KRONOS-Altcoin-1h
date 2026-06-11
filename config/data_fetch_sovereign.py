"""
KRONOS V1-ALT data_fetch_sovereign.py DEPRECATION REDIRECT WRAPPER
Any imports or executions of this file will trigger a deprecation warning
and forward calls to unified_ingestion_engine.py.
"""

import sys
import os
import warnings
from pathlib import Path

# Setup paths so imports resolve correctly
_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_this_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Emit deprecation warning
warnings.warn(
    "[DEPRECATION WARNING] config/data_fetch_sovereign.py is deprecated and will be removed. "
    "Use config/ingestion/unified_ingestion_engine.py instead.",
    DeprecationWarning,
    stacklevel=2
)

# Forward core functions from unified_ingestion_engine
from config.ingestion.unified_ingestion_engine import (
    fetch_all_symbols_data,
    fetch_full_history as unified_fetch_full_history,
    discover_symbols as unified_discover_symbols,
    _safe_name as safe_symbol_name
)

def discover_symbols(cfg=None):
    """Deprecated wrapper for discover_symbols."""
    print("[WARN] discover_symbols() via deprecated data_fetch_sovereign.py is redirected.")
    if cfg is None:
        from config.utils.sovereign_entrypoint import get_sovereign_config
        cfg = get_sovereign_config()
    
    import ccxt
    from config.ingestion.unified_ingestion_engine import setup_sovereign_logger
    logger, _ = setup_sovereign_logger(cfg)
    fetch_cfg = cfg["data_fetch"]
    exchange_name = fetch_cfg["exchange"]
    ex = getattr(ccxt, exchange_name)({'enableRateLimit': True, 'options': fetch_cfg["exchange_options"]})
    return unified_discover_symbols(ex, cfg, logger)

def fetch_full_history(symbol: str, ex, logger, cfg):
    """Deprecated wrapper for fetch_full_history."""
    print(f"[WARN] fetch_full_history({symbol}) via deprecated data_fetch_sovereign.py is redirected.")
    return unified_fetch_full_history(symbol, ex, logger, cfg)

def get_last_timestamp(filepath: str) -> int | None:
    """Deprecated helper to read parquet/csv timestamp."""
    print("[WARN] get_last_timestamp() via deprecated data_fetch_sovereign.py is redirected.")
    import pandas as pd
    if not os.path.exists(filepath):
        return None
    try:
        if filepath.endswith(".parquet"):
            df = pd.read_parquet(filepath, columns=['timestamp'])
        else:
            df = pd.read_csv(filepath, usecols=['timestamp'])
        if not df.empty:
            return int(df['timestamp'].max())
    except Exception:
        pass
    return None

if __name__ == "__main__":
    print("[DEPRECATION REDIRECT] Running unified_ingestion_engine.fetch_all_symbols_data() instead...")
    fetch_all_symbols_data()
