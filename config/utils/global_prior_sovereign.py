"""
KRONOS V1-ALT Sovereign Global Prior v3.1
Cross-symbol phylum prior derivation (orthogonal & ablatable).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # insert project root for subpackage imports

from config.utils.sovereign_entrypoint import get_sovereign_config, get_storage_path
import pandas as pd
import os

def build_global_prior() -> None:
    """Build cross-symbol sovereign prior from individual signatures."""
    cfg = get_sovereign_config()
    signatures_dir = get_storage_path(cfg, "signatures_individual_dir")
    global_prior_dir = get_storage_path(cfg, "signatures_global_prior_dir")
    os.makedirs(global_prior_dir, exist_ok=True)
    
    sig_files = [f for f in os.listdir(signatures_dir) if f.endswith('_signature.parquet')]
    print(f"Building global prior from {len(sig_files)} individual signatures")
    
    all_sigs = []
    for f in sig_files:
        df = pd.read_parquet(os.path.join(signatures_dir, f))
        all_sigs.append(df)
    
    if all_sigs:
        global_df = pd.concat(all_sigs, ignore_index=True)
        prior_path = os.path.join(global_prior_dir, "global_prior.parquet")
        global_df.to_parquet(prior_path, index=False)
        
        print(f"Global prior built: {len(global_df)} signatures")
        print(f"Mean confidence: {global_df['confidence'].mean():.3f}")
        print(f"High-quality ratio: {(global_df['confidence'] >= cfg['thresholds']['reversal_confidence_min']).mean():.1%}")
        
        # Store config reference for injection
        cfg_path = os.path.join(global_prior_dir, "global_prior_config.txt")
        with open(cfg_path, "w") as f:
            f.write(f"enabled={cfg['global_prior_mode']['enabled']}\n")
            f.write(f"injection_enabled_default={cfg['global_prior_mode']['injection_enabled_default']}\n")

if __name__ == "__main__":
    build_global_prior()