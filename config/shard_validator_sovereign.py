"""
KRONOS V1-ALT Sovereign Shard Validator v3.1
Validates stored raw shards against sovereign config.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

from sovereign_entrypoint import get_sovereign_config, get_storage_path
import pandas as pd
import os

def validate_raw_shards() -> None:
    """Validate parquet shards in raw_shards_dir."""
    cfg = get_sovereign_config()
    raw_shards_dir = get_storage_path(cfg, "raw_shards_dir")
    
    files = [f for f in os.listdir(raw_shards_dir) if f.endswith('.parquet')]
    print(f"Found {len(files)} raw shards in {raw_shards_dir}")
    
    sample_file = os.path.join(raw_shards_dir, files[0]) if files else None
    if sample_file:
        df = pd.read_parquet(sample_file)
        print(f"Sample shard shape: {df.shape}")
        print(f"Columns: {df.columns.tolist()}")
        print(f"Date range: {df['timestamp'].min()} → {df['timestamp'].max()}")
    
    # Sovereignty check
    target = cfg["symbols"]["target_count"]
    print(f"Target coverage: {len(files)}/{target} symbols")

if __name__ == "__main__":
    validate_raw_shards()