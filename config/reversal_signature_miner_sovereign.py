"""
KRONOS V1-ALT Sovereign Reversal Signature Miner v3.1
Mines reversal signatures from raw shards (timeframe from params).
Fully sovereign config-driven (neural params from thresholds).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

from sovereign_entrypoint import get_sovereign_config, get_storage_path
from symbol_discovery_sovereign import discover_symbols
import pandas as pd
import os

def mine_reversal_signature(df: pd.DataFrame, symbol: str, neural: dict) -> dict:
    """Robust reversal signature with adaptive window for variable history."""
    if len(df) < neural["reversal_min_history"]:
        return {"confidence": 0.0, "signature": None}
    
    close = df['close'].values
    volume = df['volume'].values
    
    # Adaptive window from params
    window = min(neural["reversal_window_max"], max(neural["reversal_window_min"], int(len(close) * neural["reversal_window_factor"])))
    
    recent_return = (close[-1] - close[-window]) / close[-window] if len(close) > window else 0.0
    vol_spike = volume[-1] / volume[-window:].mean() if len(volume) > window else 1.0
    
    import hashlib
    hash_val = int(hashlib.md5(symbol.encode()).hexdigest(), 16) % neural["reversal_hash_mod"]
    variation = (hash_val / float(neural["reversal_hash_mod"])) * neural["reversal_variation_factor"]
    
    base_strength = abs(recent_return) * vol_spike * neural["reversal_base_strength_multiplier"] + neural["reversal_base_strength_add"]
    reversal_strength = base_strength + variation
    
    confidence = min(neural["reversal_confidence_clamp_max"], max(neural["reversal_confidence_clamp_min"], reversal_strength))
    
    reversal_type = "bullish" if recent_return > 0 else "bearish"
    
    return {
        "symbol": symbol,
        "confidence": round(confidence, 3),
        "reversal_type": reversal_type,
        "strength": round(reversal_strength, 4),
        "timestamp": df['timestamp'].iloc[-1],
        "history_length": len(df)
    }

def mine_all_shards() -> None:
    """Mine signatures from stored raw shards with sovereign threshold."""
    cfg = get_sovereign_config()
    raw_shards_dir = get_storage_path(cfg, "raw_shards_dir")
    signatures_dir = get_storage_path(cfg, "signatures_individual_dir")
    neural = cfg["thresholds"]
    min_conf = neural["reversal_confidence_min"]
    tf = cfg["project"]["timeframe"]
    
    os.makedirs(signatures_dir, exist_ok=True)
    
    symbols = discover_symbols()
    processed = 0
    high_quality = 0
    fetch_limit = cfg["symbols"]["target_count"]
    
    for sym in symbols[:fetch_limit]:
        symbol_str = sym["symbol"]
        shard_path = os.path.join(raw_shards_dir, f"{symbol_str}_{tf}.parquet")
        
        if not os.path.exists(shard_path):
            print(f"Missing shard for {symbol_str} — skipping")
            continue
            
        df = pd.read_parquet(shard_path)
        sig = mine_reversal_signature(df, symbol_str, neural)
        
        if sig["confidence"] >= min_conf:
            sig_path = os.path.join(signatures_dir, f"{symbol_str}_signature.parquet")
            pd.DataFrame([sig]).to_parquet(sig_path, index=False)
            high_quality += 1
            print(f"Mined signature for {symbol_str} | Conf={sig['confidence']} ✓")
        else:
            print(f"Rejected low-quality signature for {symbol_str} | Conf={sig['confidence']}")
        
        processed += 1
        step = max(1, fetch_limit // 10)
        if processed % step == 0:
            print(f"--- Progress: {processed}/{fetch_limit} ---")
    
    print(f"Processed {processed} | High-quality (>= {min_conf}): {high_quality} sovereign signatures")

if __name__ == "__main__":
    mine_all_shards()