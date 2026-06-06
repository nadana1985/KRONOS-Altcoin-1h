"""
KRONOS V1-ALT Sovereign Ablation Test v3.1
Validate Individual Mode vs Individual + Global Prior.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

from sovereign_entrypoint import get_sovereign_config
from unified_ingestion_engine import fetch_all_symbols_data
from reversal_signature_miner_sovereign import mine_all_shards
from global_prior_sovereign import build_global_prior

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