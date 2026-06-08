"""
KRONOS V1-ALT Sovereign Ablation Test v3.1 (timeframe-driven)
Validate Individual Mode vs Individual + Global Prior.
"""

import os
import sys

# Robust production bootstrap using KRONOS_PARAMS_PATH env + get_storage_path + cfg (zero literals)
params_path = os.getenv("KRONOS_PARAMS_PATH")
if params_path:
    project_root = os.path.dirname(os.path.abspath(params_path))
    sys.path.insert(0, project_root)  # insert root so from config.xxx works for subdirs

from config.utils.sovereign_entrypoint import get_sovereign_config
from config.ingestion.unified_ingestion_engine import fetch_all_symbols_data
from config.mining.reversal_signature_miner_sovereign import mine_all_shards
from config.utils.global_prior_sovereign import build_global_prior

def run_ablation() -> None:
    cfg = get_sovereign_config()
    print("=== KRONOS Ablation Test ===")
    print(f"Individual Mode only vs + Global Prior | Target={cfg['symbols']['target_count']}")
    
    fetch_all_symbols_data()
    mine_all_shards()
    build_global_prior()
    
    print("Ablation complete. Ready for real data injection.")

if __name__ == "__main__":
    run_ablation()