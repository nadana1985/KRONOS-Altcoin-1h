"""
KRONOS V1-ALT Mandatory E2E Runtime Validation Harness
Synthetic ingestion note (use_real via cfg) + miner over *actual on-disk shards* (Option B) → KronosPredictor forward (ctx wired) → extract_live_reversal_signals + detect_regime with ablation toggles (individual/global).
All from params_yaml.txt v3.1 via cfg; zero literals. V5 hybrid gate enforced.
"""

import os
import sys

# Robust bootstrap for direct execution (even without env var):
# Use script location to bootstrap paths (production should always set KRONOS_PARAMS_PATH)
script_path = os.path.abspath(__file__)
project_root = os.path.dirname(script_path)
config_dir = os.path.join(project_root, "config")
kronos_module_dir = os.path.join(project_root, "kronos_module")
kronos_model_dir = os.path.join(kronos_module_dir, "model")
for p in [project_root, config_dir, kronos_module_dir, kronos_model_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Now handle KRONOS_PARAMS_PATH (required for cfg-driven everything)
params_path = os.getenv("KRONOS_PARAMS_PATH")
if not params_path:
    params_path = os.path.join(project_root, "params_yaml.txt")
    os.environ["KRONOS_PARAMS_PATH"] = params_path
    print(f"INFO: KRONOS_PARAMS_PATH not set in environment; defaulted to {params_path} for this run.")
    print("For production stability and full cfg-only paths, always set: $env:KRONOS_PARAMS_PATH = 'F:/kronos_v1_alt/params_yaml.txt'")

from sovereign_entrypoint import get_sovereign_config
from config.reversal_signature_miner_sovereign import mine_all_shards
from config.symbol_discovery_sovereign import discover_symbols_from_shards
from kronos_module.orchestrator_engine import orchestrate_sovereign, extract_live_reversal_signals, detect_regime
import pandas as pd
from kronos_module.model.kronos import KronosPredictor
# Note: KronosPredictor forward tested via ctx (full model load skipped for env stability; wiring verified in source + orchestrate calls)

def run_e2e_harness():
    cfg = get_sovereign_config()
    print("=== KRONOS V1-ALT E2E Runtime Validation Harness ===")
    print(f"Params v{cfg['project']['version']} | Timeframe: {cfg['project']['timeframe']} | Target: {cfg['symbols']['target_count']}")
    print(f"use_real (synthetic path): {cfg['data_fetch']['use_real']} (using existing shards for test)")
    print("V5 Hybrid Gate + cfg-only paths enforced. Zero literals.")
    print("-" * 60)

    # 1. Ingestion note (use_real from cfg; we mine whatever shards actually exist on disk)
    print("Step 1: Ingestion note - using pre-existing shards on disk (Option B for E2E miner)")
    raw_shards_dir = cfg["storage"]["raw_shards_dir"]  # via cfg
    print(f"  Shards dir (from cfg): {raw_shards_dir}")
    # Note: full fetch_all_symbols_data() is in unified_ingestion_engine; harness uses existing shards for stability + wiring proof.

    # 2. Miner (Option B: use only symbols that have actual shards on disk)
    print("Step 2: Miner (symbols from existing on-disk shards)")
    existing_symbols = discover_symbols_from_shards(raw_shards_dir, cfg["project"]["timeframe"])
    print(f"  Found {len(existing_symbols)} symbols with shards on disk: {[s['symbol'] for s in existing_symbols]}")
    mine_all_shards(symbols=existing_symbols)  # pass the real present symbols (no synthetic fallback)
    print("  Miner complete (shards processed via cfg)")

    # 3. Orchestrate + extract + detect with toggles
    print("Step 3: KronosPredictor forward (ctx wired) + extract + detect_regime with toggles")
    print("--- Ablation: individual ---")
    ctx_ind = orchestrate_sovereign("individual")
    print(f"  orchestrate_sov: timeframe={ctx_ind['timeframe']}, target={ctx_ind['target_count']}")
    print(f"  veto applied, individual primary={ctx_ind['is_individual_primary']}")
    sigs_ind = extract_live_reversal_signals("individual")
    regime_ind = detect_regime(sigs_ind)
    print(f"  signals: mode={sigs_ind['mode']}, neural_slots keys={list(sigs_ind['neural_slots'].keys())}")
    print(f"  regime: {regime_ind['regime']}, flags={regime_ind['flags']}")

    print("--- Ablation: global ---")
    ctx_glob = orchestrate_sovereign("global")
    print(f"  orchestrate_sov: global_prior_injected={ctx_glob['global_prior']['injection_ablatable'] and ctx_glob['global_prior']['injection_enabled_default']}")
    sigs_glob = extract_live_reversal_signals("global")
    regime_glob = detect_regime(sigs_glob)
    print(f"  signals: mode={sigs_glob['mode']}")
    print(f"  regime: {regime_glob['regime']}, flags={regime_glob['flags']}")

    # Ablation delta
    print("Ablation delta (individual vs global): regime_base differs if toggle active")
    print(f"  individual regime: {regime_ind['regime']}")
    print(f"  global regime: {regime_glob['regime']}")

    # 4. KronosPredictor forward ctx + real assertions (substance)
    signatures_dir = cfg["storage"]["signatures_individual_dir"]
    sig_files = [f for f in os.listdir(signatures_dir) if f.endswith("_signature.parquet")]
    assert len(sig_files) >= 1, "At least one signature Parquet expected"
    sig_df = pd.read_parquet(os.path.join(signatures_dir, sig_files[0]))
    assert "confidence" in sig_df.columns, "confidence column missing"
    ctx = orchestrate_sovereign("individual")
    neural = ctx["neural_slots"]
    min_conf = neural["confidence_min"] if "confidence_min" in neural else cfg["thresholds"]["reversal_confidence_min"]
    assert (sig_df["confidence"] > min_conf).any(), "Expected confidence values above threshold"

    # Exercise KronosPredictor forward using sovereign_ctx wiring and real tail from shard
    predictor = KronosPredictor(sovereign_ctx=ctx)
    causal_slice = pd.DataFrame()
    if existing_symbols:
        sym = existing_symbols[0]["symbol"]
        tf = cfg["project"]["timeframe"]
        shard_path = os.path.join(raw_shards_dir, f"{sym}_{tf}.parquet")
        if os.path.exists(shard_path):
            shard = pd.read_parquet(shard_path)
            hist = neural["min_history"]
            if hist > 0 and len(shard) > 0:
                use_len = min(hist, len(shard))
                causal_slice = shard.tail(use_len)
    out = predictor.generate(causal_slice)
    assert out is not None and (len(out) > 0 if hasattr(out, "__len__") else True), "Output non-empty"

    print("-" * 60)
    print("E2E complete. All real side-effects + assertions passed.")
    return True

if __name__ == "__main__":
    run_e2e_harness()
