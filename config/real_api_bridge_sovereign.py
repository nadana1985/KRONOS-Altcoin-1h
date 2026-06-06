"""
KRONOS V1-ALT Sovereign Real API Bridge v3.1
Controlled transition point from current to real data (per data_fetch.exchange).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

from sovereign_entrypoint import get_sovereign_config, get_storage_path
from unified_ingestion_engine import fetch_all_symbols_data

def activate_real_bridge() -> None:
    """Ablation-ready bridge for real data."""
    cfg = get_sovereign_config()
    print("=== KRONOS Real API Bridge Activated ===")
    print(f"Target symbols: {cfg['symbols']['target_count']}")
    print("Global Prior Mode: Enabled + Injection Default: True")
    
    # Real bridge flag (controlled via params)
    print(f"\nuse_real from params: {cfg['data_fetch']['use_real']}")
    print("Transition controlled by data_fetch section.")

if __name__ == "__main__":
    activate_real_bridge()