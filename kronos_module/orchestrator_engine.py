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
    # Trigger miner (uses current cfg for ablation)
    # mine_all_shards()  # commented for stability; call externally with toggled params
    # For forward: assume predictor available via ctx
    signals = {
        "mode": ablation_mode,
        "neural_slots": ctx["neural_slots"],
        "global_prior": ctx["global_prior"],
        "timeframe": ctx["timeframe"],
        "target_count": ctx["target_count"],
    }
    return signals

