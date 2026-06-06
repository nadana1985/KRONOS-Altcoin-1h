"""
KRONOS V1-ALT Sovereign Pipeline Orchestrator v3.1
End-to-end Individual + optional Global Prior Mode.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

from sovereign_entrypoint import get_sovereign_config
from unified_ingestion_engine import fetch_all_symbols_data
from reversal_signature_miner_sovereign import mine_all_shards
from global_prior_sovereign import build_global_prior

def run_full_pipeline() -> None:
    """Orchestrate sovereign Individual + Global Prior pipeline."""
    cfg = get_sovereign_config()
    target = cfg["symbols"]["target_count"]
    print(f"Starting KRONOS V1-ALT Individual Mode | Target={target}")
    
    print("\n=== Phase 1: Sovereign Data Fetch ===")
    fetch_all_symbols_data()
    
    print("\n=== Phase 2: Reversal Signature Mining ===")
    mine_all_shards()
    
    print("\n=== Phase 3: Global Prior Derivation (Ablatable) ===")
    build_global_prior()
    
    print("\n=== KRONOS Pipeline Complete ===")
    print(f"Mode from params: {cfg['project']['mode']} | use_real: {cfg['data_fetch']['use_real']}")

if __name__ == "__main__":
    run_full_pipeline()