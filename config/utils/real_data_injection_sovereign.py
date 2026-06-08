"""
KRONOS V1-ALT Sovereign Real Data Injection v3.1
Bridge to real API (per project.mode and symbols.filter, timeframe-driven).
"""

import os
import sys

# Robust production bootstrap using KRONOS_PARAMS_PATH env + get_storage_path + cfg (zero literals)
params_path = os.getenv("KRONOS_PARAMS_PATH")
if params_path:
    project_root = os.path.dirname(os.path.abspath(params_path))
    sys.path.insert(0, project_root)  # insert root so from config.xxx works for subdirs

from config.utils.sovereign_entrypoint import get_sovereign_config, get_storage_path
from config.ingestion.unified_ingestion_engine import fetch_all_symbols_data  # sole data path (cfg-driven)

def prepare_for_real_data() -> None:
    """Ablation gate for real API transition."""
    cfg = get_sovereign_config()
    print(f"KRONOS Ready for Real Data | Target={cfg['symbols']['target_count']}")
    print(f"Current use_real: {cfg['data_fetch']['use_real']}")
    print("Next: use ccxt path in unified_ingestion_engine when enabled in params.")
    print(f"Global prior injection ablatable: {cfg['global_prior_mode']['injection_ablatable']}")

if __name__ == "__main__":
    prepare_for_real_data()