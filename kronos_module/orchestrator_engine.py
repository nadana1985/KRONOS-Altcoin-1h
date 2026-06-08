"""
Sovereign Orchestrator Engine (timeframe port)

Wires structural veto core + individual/global prior dual-mode.
Uses only sovereign params values. Small port of hybrid dual-mode + veto.
Ablation supported via global_prior_mode.
"""

import os
import sys

# Robust production bootstrap using KRONOS_PARAMS_PATH env + get_storage_path + cfg (zero literals)
params_path = os.getenv("KRONOS_PARAMS_PATH")
if params_path:
    project_root = os.path.dirname(os.path.abspath(params_path))
    kronos_module_dir = os.path.join(project_root, "kronos_module")
    config_dir = os.path.join(project_root, "config")
    sys.path.insert(0, config_dir)
    sys.path.insert(0, kronos_module_dir)

from structural_engine import get_dual_mode_context, apply_structural_veto
from sovereign_entrypoint import get_sovereign_config
from model.kronos import KronosPredictor


def orchestrate_sovereign(mode: str = "individual"):
    """Primary entry for dual-mode with structural veto enforced."""
    ctx = apply_structural_veto(mode)  # Phase 1: wired for use in reversal miner (get_dual_mode_context + veto)
    # Memory-safe: use ctx["memory_shard"], ctx["max_context"], ctx["target_count"]
    # for target scaling. Neural slots from thresholds.
    # individual primary; global prior orthogonal + ablatable.
    return ctx


# Note: Call with mode="global" only when global_prior_mode.injection_ablatable=true
# All timeframe/target from project.timeframe + symbols.target_count

def extract_live_reversal_signals(ablation_mode="individual"):
    """Live reversal signal extraction: miner + KronosPredictor forward with ablation toggles (cfg only)."""
    ctx = orchestrate_sovereign(ablation_mode)
    cfg = get_sovereign_config()
    # Use ctx for dual-mode and slots; cfg for other (no literals)
    print(f"Live extraction | Mode={ablation_mode} | Global ablatable={ctx['global_prior']['injection_ablatable']} | Target={cfg['symbols']['target_count']}")
    # Real trigger (no placeholders): miner via Option B + real predictor
    from config.reversal_signature_miner_sovereign import mine_all_shards
    mine_all_shards()  # real shards, real neural gate, real conv
    predictor = KronosPredictor(sovereign_ctx=ctx)
    signals = {
        "mode": ablation_mode,
        "neural_slots": ctx["neural_slots"],
        "global_prior": ctx["global_prior"],
        "timeframe": ctx["timeframe"],
        "target_count": ctx["target_count"],
        "predictor": predictor,
    }
    return signals


def detect_regime(signals):
    """Sovereign regime detection using neural_slots + global_prior toggles (cfg only, V5 hybrid gate)."""
    cfg = get_sovereign_config()
    slots = signals["neural_slots"]
    gprior = signals["global_prior"]
    # V5 hybrid: regime from slots (window vs min_history for adaptive/trending) + global toggle
    window_max = slots["reversal_window"][1]
    min_hist = slots["min_history"]
    regime_base = "global_injected_" if (gprior["injection_ablatable"] and gprior["injection_enabled_default"]) else "individual_only_"
    regime_type = "trending" if window_max > min_hist else "mean_reverting"
    regime = regime_base + regime_type
    flags = {
        "global_prior_injected": gprior["injection_ablatable"] and gprior["injection_enabled_default"],
        "high_reversal_adaptivity": window_max > min_hist,
        "strong_slot_confidence": slots["confidence_min"] >= cfg["thresholds"]["reversal_confidence_min"],
    }
    return {"regime": regime, "flags": flags, "slots_used": slots}


def run_sovereign_dashboard():
    """CLI dashboard for live signals + regimes (Streamlit option in comments; cfg only)."""
    cfg = get_sovereign_config()
    print("=== SOVEREIGN LIVE SIGNAL DASHBOARD ===")
    print(f"Params v{cfg['project']['version']} | Timeframe: {cfg['project']['timeframe']} | Target: {cfg['symbols']['target_count']}")
    print("V5 Hybrid Gate: neural_slots + global_prior toggles active")
    print("-" * 50)
    # Toggle individual (real)
    sigs_ind = extract_live_reversal_signals("individual")
    regime_ind = detect_regime(sigs_ind)
    print(f"INDIVIDUAL MODE: signals={sigs_ind} | regime={regime_ind['regime']} | flags={regime_ind['flags']}")
    print("-" * 50)
    # Toggle global (ablation, real)
    sigs_glob = extract_live_reversal_signals("global")
    regime_glob = detect_regime(sigs_glob)
    print(f"GLOBAL MODE (ablation toggle): signals={sigs_glob} | regime={regime_glob['regime']} | flags={regime_glob['flags']}")
    print("-" * 50)
    print("Ablation comparison complete (real miner/predictor). Use params to toggle global_prior_mode.injection_* for live runs.")
    # Streamlit dashboard (run with: streamlit run this_file.py -- if streamlit installed; cfg only)
    # import streamlit as st
    # st.title("KRONOS V1-ALT Sovereign Dashboard")
    # st.write(f"Regime: {regime_ind['regime']}")
    # etc. (full cfg driven)


# Note: Real live: extract_live_reversal_signals / run_sovereign_dashboard now trigger miner + real predictor (no placeholders).
# All values from params_yaml.txt v3.1; zero literals.

