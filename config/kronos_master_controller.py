"""
KRONOS V1-ALT Master Controller v3.1
Single entrypoint for sovereign pipeline orchestration.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

from sovereign_entrypoint import get_sovereign_config
from kronos_pipeline_sovereign import run_full_pipeline

def main():
    cfg = get_sovereign_config()
    print(f"=== KRONOS V1-ALT MASTER CONTROLLER v{cfg['project']['version']} ===")
    print(f"Project: {cfg['project']['name']} | Mode: {cfg['project']['mode']} | Timeframe: {cfg['project']['timeframe']}")
    
    run_full_pipeline()
    
    print("\n=== Master Controller Execution Complete ===")
    print("Sovereign config respected. All paths resolved from the params file.")
    print("Next Phase: Real API integration (see real_api_bridge_sovereign.py)")

if __name__ == "__main__":
    main()