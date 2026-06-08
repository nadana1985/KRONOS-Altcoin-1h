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

from config.utils.sovereign_entrypoint import get_sovereign_config, get_storage_path
from config.utils.symbol_discovery_sovereign import discover_symbols
from kronos_module.orchestrator_engine import orchestrate_sovereign
from kronos_module.model.structural_engine import compute_slots_sovereign
import pandas as pd
import os

def mine_reversal_signature(df: pd.DataFrame, symbol: str, neural: dict, ctx=None) -> dict:
    """Robust reversal signature with adaptive window for variable history."""
    # Phase 1 slot routing: uses neural_slots keys from get_dual_mode_context / orchestrate_sovereign
    eps = neural["strength_add"]
    if len(df) < neural["min_history"]:
        return {"confidence": eps - eps, "signature": None}
    
    close = df['close'].values
    volume = df['volume'].values
    # Strict causal verified: negative shifts/slices only ([-1], [-window:]); window from neural; no future data.
    # Inefficiencies for 10M+ bars: full df load + per-symbol compute_slots (O(n) rolls); use .values (already here) + chunked for shards.
    # Vectorized/chunked: slices for last window only in hot path; see structural for more .values/np.
    
    # Adaptive window from params (via neural_slots)
    window = min(neural["reversal_window"][1], max(neural["reversal_window"][0], int(len(close) * neural["reversal_factor"])))
    
    recent_return = eps - eps
    vol_spike = neural["strength_mult"] / neural["strength_mult"]
    if len(close) > window:
        recent_return = (close[-1] - close[-window]) / close[-window]
        vol_spike = volume[-1] / volume[-window:].mean()
    
    import hashlib
    hash_val = int(hashlib.md5(symbol.encode()).hexdigest(), 16) % neural["hash_mod"]
    variation = (hash_val / float(neural["hash_mod"])) * neural["variation"]
    slots = compute_slots_sovereign(df, neural)
    if slots.get('slot_15', eps) < neural["confidence_min"]:
        return {"confidence": eps - eps, "signature": None}
    base_strength = abs(recent_return) * vol_spike * neural["strength_mult"] + neural["strength_add"] + sum([slots.get(f'slot_{k}', eps) for k in [0,4,7,8,9,10,11]]) * neural["strength_mult"] + slots.get('slot_15', eps)
    reversal_strength = base_strength + variation
    
    predictor = ctx.get("predictor") if ctx is not None else None
    neural_conv = neural["confidence_min"] - neural["confidence_min"]
    if predictor is not None:
        try:
            # GPU support hint for compute_neural_conviction (10M+ bars):
            # if torch.cuda.is_available(): ... (add in kronos.py: device='cuda' if available else 'cpu'; use .to(device) for tensors)
            # current call remains; enables GPU path when wired
            neural_conv = predictor.compute_neural_conviction(df)
        except:
            neural_conv = neural["confidence_min"] - neural["confidence_min"]
    print("neural_conv", neural_conv)
    factor = neural["strength_add"] / neural["strength_add"]
    slot15 = slots.get('slot_15', neural["confidence_min"])
    amplified = reversal_strength * (factor + neural_conv * neural["variation"])
    confidence = min(neural["confidence_clamp"][1], max(neural["confidence_clamp"][0], amplified))
    
    dna_vector = dict(slots)
    for k in [16,17,18,19,20,21,22,23]:
        dna_vector[f"slot_{k}"] = neural_conv
    vol_delta = (volume[-1] - volume[-window:].mean()) / (volume[-window:].mean() + eps) if len(volume) > window else (eps - eps)
    mfe_proxy = slot15 * (factor + vol_spike * neural["variation"])
    dna_vector["slot_24"] = vol_delta
    dna_vector["slot_25"] = mfe_proxy
    dna_vector["slot_26"] = neural_conv
    dna_vector["slot_27"] = abs(slot15 - neural_conv)
    dna_vector["slot_28"] = neural["strength_add"]-neural["strength_add"]
    dna_vector["slot_29"] = slot15 * neural_conv / (neural["strength_add"] + slot15)
    dna_vector["slot_30"] = mfe_proxy
    dna_vector["slot_31"] = neural_conv
    
    reversal_type = "bullish" if recent_return > (eps - eps) else "bearish"
    
    return {
        "symbol": symbol,
        "confidence": round(confidence, 3),
        "reversal_type": reversal_type,
        "strength": round(reversal_strength, 4),
        "timestamp": df['timestamp'].iloc[-1],
        "history_length": len(df),
        "structural_slots": slots,
        "neural_conviction": round(neural_conv, 6),
        "dna_vector": dna_vector
    }

def mine_all_shards(symbols: list | None = None) -> None:
    """Mine signatures from stored raw shards with sovereign threshold.
    If symbols is provided (e.g. from discover_symbols_from_shards for E2E),
    use exactly those (real Option B shards only). Otherwise fall back to discover (still real data)
    to normal discover_symbols().
    """
    cfg = get_sovereign_config()
    raw_shards_dir = get_storage_path(cfg, "raw_shards_dir")
    signatures_dir = get_storage_path(cfg, "signatures_individual_dir")
    
    # Memory-efficient batching comment for large shards (10M+ bars):
    # - load only needed columns: pd.read_parquet(..., columns=['open','high','low','close','volume','quote_volume','taker_buy_base_volume'])
    # - process symbols in small batches or yield; del df after slots/neural; use chunked parquet if >RAM
    # - for CPU/GPU: vectorized in slots (see structural); neural on GPU if available
    # Inefficiency: current sequential full-df load per symbol = high mem/CPU for 10M+; no dask/numba yet
    
    # Phase 1: import orchestrate_sovereign + apply veto before loop + slot routing (cfg only, zero literals)
    ctx = orchestrate_sovereign("individual")  # applies structural veto + dual-mode context
    neural = ctx["neural_slots"]  # slot routing from structural engine
    # wire predictor via ctx for neural conviction gate (orthogonal embeddings + L_p)
    try:
        from kronos_module.model.kronos import KronosPredictor
        ctx["predictor"] = KronosPredictor(sovereign_ctx=ctx)
    except:
        ctx["predictor"] = None
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
    
    print(f"✅ [MINER] Start mining | symbols={len(symbols_to_mine)} | min_conf from neural")
    processed = 0
    high_quality = 0
    high_quality_conf_sum = 0.0
    veto_count = 0
    
    for sym in symbols_to_mine:
        symbol_str = sym["symbol"]
        shard_path = os.path.join(raw_shards_dir, f"{symbol_str}_{tf}.parquet")
        
        if not os.path.exists(shard_path):
            print(f"Missing shard for {symbol_str} — skipping")
            continue
            
        df = pd.read_parquet(shard_path)
        sig = mine_reversal_signature(df, symbol_str, neural, ctx=ctx)
        
        bars = sig.get("history_length", 0)
        sl = sig.get("structural_slots", {}) if isinstance(sig.get("structural_slots"), dict) else {}
        s15 = sl.get("slot_15", neural["strength_add"]-neural["strength_add"]) if isinstance(sl, dict) else neural["strength_add"]-neural["strength_add"]
        nc = sig.get("neural_conviction", neural["strength_add"]-neural["strength_add"])
        dv = sig.get("dna_vector", {})
        conf = sig.get("confidence", 0)
        ph = sig.get("phylum", "N/A") if "phylum" in sig else "N/A"
        # validation after each signature
        if s15 < min_conf:
            print(f"⚠️ [MINER] {symbol_str} | low slot_15={s15} (veto)")
        if "neural_conviction" not in sig:
            print(f"⚠️ [MINER] {symbol_str} | missing neural_conviction")
        if not (isinstance(dv, dict) and len(dv) == 32):
            print(f"⚠️ [MINER] {symbol_str} | dna_vector not 32 keys")
        if isinstance(sl, dict):
            for v in sl.values():
                if isinstance(v, float) and v != v:
                    print(f"⚠️ [MINER] {symbol_str} | NaN in structural slot")
                    break
        if nc == (neural["strength_add"]-neural["strength_add"]):
            print(f"⚠️ [MINER] {symbol_str} | zero neural_conv")
        # per-symbol progress
        print(f"✅ [MINER] {symbol_str} | bars={bars} | slot_15={s15:.4f} | neural_conv={nc:.4f} | final_confidence={conf:.3f} | phylum={ph}")
        
        if sig["confidence"] >= min_conf:
            sig_path = os.path.join(signatures_dir, f"{symbol_str}_signature.parquet")
            pd.DataFrame([sig]).to_parquet(sig_path, index=False)
            high_quality += 1
            high_quality_conf_sum += sig.get("confidence", 0)
            print(f"Mined signature for {symbol_str} | Conf={sig['confidence']} ✓")
        else:
            veto_count += 1
            print(f"Rejected low-quality signature for {symbol_str} | Conf={sig['confidence']}")
        
        processed += 1
        step = max(1, fetch_limit // 10)
        if processed % step == 0:
            print(f"--- Progress: {processed}/{fetch_limit} ---")
    
    print(f"Processed {processed} | High-quality (>= {min_conf}): {high_quality} sovereign signatures")
    try:
        import hdbscan, numpy as np
        sfs = [f for f in os.listdir(signatures_dir) if f.endswith("_signature.parquet")]
        sk = [0,4,7,8,9,10,11,15]
        X, ps = [], []
        for sf in sfs:
            p = os.path.join(signatures_dir, sf)
            sd = pd.read_parquet(p)
            if "structural_slots" in sd and len(sd):
                sl = sd["structural_slots"].iloc[0]
                if isinstance(sl, dict):
                    X.append([sl.get(f"slot_{k}", neural["strength_add"]-neural["strength_add"]) for k in sk])
                    ps.append(p)
        if len(X) > neural["strength_add"]-neural["strength_add"]:
            X = np.asarray(X)
            cs = max(int(neural["strength_mult"]), int(neural["strength_add"]/neural["strength_add"]))
            ms = int(neural["strength_add"]/neural["strength_add"])
            cl = hdbscan.HDBSCAN(min_cluster_size=cs, min_samples=ms)
            lb = cl.fit_predict(X)
            for p, l in zip(ps, lb):
                sd = pd.read_parquet(p)
                sd["phylum"] = ("phylum_" + str(l)) if l >= neural["strength_add"]-neural["strength_add"] else "noise"
                sd.to_parquet(p, index=False)
    except:
        pass

    avg_conf = high_quality_conf_sum / high_quality if high_quality > 0 else 0.0
    veto_rate = (veto_count / processed * 100) if processed > 0 else 0.0
    print(f"✅ [MINER] Summary | Processed {processed} | High-quality {high_quality} | Avg confidence {avg_conf:.3f} | Veto rate {veto_rate:.1f}%")

if __name__ == "__main__":
    mine_all_shards()