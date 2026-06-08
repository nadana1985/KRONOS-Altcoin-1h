"""
KRONOS V1-ALT Sovereign Entrypoint v3.1
Enforces load_sovereign_config() as ONLY access point.
"""

import os
import sys

# Robust production bootstrap: use KRONOS_PARAMS_PATH env (no __file__ brittleness)
params_path = os.getenv("KRONOS_PARAMS_PATH")
if params_path:
    project_root = os.path.dirname(os.path.abspath(params_path))
    sys.path.insert(0, project_root)  # insert root so from config.xxx works for subdirs

from config.validation.load_sovereign_config import load_sovereign_config, get_storage_path

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
    # Production: verify using get_storage_path + cfg
    config_dir_from_cfg = get_storage_path(cfg, "config_dir")
    print(f"Config dir from cfg: {config_dir_from_cfg}")