"""
KRONOS V1-ALT Sovereign Reversal Signature Miner v3.1
Mines reversal signatures from raw shards (timeframe from params).
Fully sovereign config-driven (neural params from thresholds).
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

# Phase 1 wiring: add kronos_module for orchestrate_sovereign (structural veto + dual-mode)
# Robust production: use env + cfg (get_storage_path) for path resolution, zero literals
params_path = os.getenv("KRONOS_PARAMS_PATH")
if params_path:
    project_root = os.path.dirname(os.path.abspath(params_path))
    kronos_module_dir = os.path.join(project_root, "kronos_module")
    if kronos_module_dir not in sys.path:
        sys.path.insert(0, kronos_module_dir)

from sovereign_entrypoint import get_sovereign_config, get_storage_path
from symbol_discovery_sovereign import discover_symbols
from orchestrator_engine import orchestrate_sovereign
from model.structural_engine import compute_slots_sovereign
import pandas as pd
import os

def mine_reversal_signature(df: pd.DataFrame, symbol: str, neural: dict) -> dict:
    """Robust reversal signature with adaptive window for variable history."""
    # Phase 1 slot routing: uses neural_slots keys from get_dual_mode_context / orchestrate_sovereign
    if len(df) < neural["min_history"]:
        return {"confidence": 0.0, "signature": None}
    
    close = df['close'].values
    volume = df['volume'].values
    
    # Adaptive window from params (via neural_slots)
    window = min(neural["reversal_window"][1], max(neural["reversal_window"][0], int(len(close) * neural["reversal_factor"])))
    
    recent_return = (close[-1] - close[-window]) / close[-window] if len(close) > window else 0.0
    vol_spike = volume[-1] / volume[-window:].mean() if len(volume) > window else 1.0
    
    import hashlib
    hash_val = int(hashlib.md5(symbol.encode()).hexdigest(), 16) % neural["hash_mod"]
    variation = (hash_val / float(neural["hash_mod"])) * neural["variation"]
    slots = compute_slots_sovereign(df, neural)
    if slots.get('slot_15', 0) < neural["reversal_confidence_min"]:
        return {"confidence": 0.0, "signature": None}
    base_strength = abs(recent_return) * vol_spike * neural["strength_mult"] + neural["strength_add"] + sum([slots.get(f'slot_{k}',0) for k in [0,4,7,8,9,10,11]]) * neural["strength_mult"] + slots.get('slot_15',0)
    reversal_strength = base_strength + variation
    
    confidence = min(neural["confidence_clamp"][1], max(neural["confidence_clamp"][0], reversal_strength))
    
    reversal_type = "bullish" if recent_return > 0 else "bearish"
    
    return {
        "symbol": symbol,
        "confidence": round(confidence, 3),
        "reversal_type": reversal_type,
        "strength": round(reversal_strength, 4),
        "timestamp": df['timestamp'].iloc[-1],
        "history_length": len(df),
        "structural_slots": slots
    }

def mine_all_shards(symbols: list | None = None) -> None:
    """Mine signatures from stored raw shards with sovereign threshold.
    If symbols is provided (e.g. from discover_symbols_from_shards for E2E),
    use exactly those (no synthetic fallback, no hard 530 cap). Otherwise fall back
    to normal discover_symbols().
    """
    cfg = get_sovereign_config()
    raw_shards_dir = get_storage_path(cfg, "raw_shards_dir")
    signatures_dir = get_storage_path(cfg, "signatures_individual_dir")
    
    # Phase 1: import orchestrate_sovereign + apply veto before loop + slot routing (cfg only, zero literals)
    ctx = orchestrate_sovereign("individual")  # applies structural veto + dual-mode context
    neural = ctx["neural_slots"]  # slot routing from structural engine
    min_conf = neural["confidence_min"]
    tf = ctx["timeframe"]
    
    os.makedirs(signatures_dir, exist_ok=True)
    
    if symbols is None:
        symbols = discover_symbols()
        fetch_limit = cfg["symbols"]["target_count"]
        symbols_to_mine = symbols[:fetch_limit]
    else:
        # E2E / on-disk mode: mine exactly the symbols that have shards present
        symbols_to_mine = symbols
        fetch_limit = len(symbols_to_mine)
    
    processed = 0
    high_quality = 0
    
    for sym in symbols_to_mine:
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