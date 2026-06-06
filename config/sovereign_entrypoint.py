"""
KRONOS V1-ALT Sovereign Entrypoint v3.1
Enforces load_sovereign_config() as ONLY access point.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

from load_sovereign_config import load_sovereign_config, get_storage_path

def get_sovereign_config():
    """Single canonical loader. Never bypass."""
    return load_sovereign_config()

# Usage: import and call get_sovereign_config() (cfg is single source)
if __name__ == "__main__":
    cfg = get_sovereign_config()
    print("Sovereign config locked.")
    print(f"Individual mode: {cfg['individual_mode']['enabled']}")
    data_dir = get_storage_path(cfg, "data_dir")
    print(f"Data dir: {data_dir}")