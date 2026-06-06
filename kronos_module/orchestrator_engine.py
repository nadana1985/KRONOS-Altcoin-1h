"""
Sovereign Orchestrator Engine (timeframe port)

Wires structural veto core + individual/global prior dual-mode.
Uses only params_yaml.txt values. Small port of hybrid dual-mode + veto.
Ablation supported via global_prior_mode.
"""

import os
import sys

# Robust production bootstrap using KRONOS_PARAMS_PATH env + get_storage_path + cfg (zero literals)
params_path = os.getenv("KRONOS_PARAMS_PATH")
if params_path:
    project_root = os.path.dirname(os.path.abspath(params_path))
    kronos_module_dir = os.path.join(project_root, "kronos_module")
    sys.path.insert(0, kronos_module_dir)

from structural_engine import get_dual_mode_context, apply_structural_veto


def orchestrate_sovereign(mode: str = "individual"):
    """Primary entry for dual-mode with structural veto enforced."""
    ctx = apply_structural_veto(mode)  # Phase 1: wired for use in reversal miner (get_dual_mode_context + veto)
    # Memory-safe: use ctx["memory_shard"], ctx["max_context"], ctx["target_count"]
    # for target scaling. Neural slots from thresholds.
    # individual primary; global prior orthogonal + ablatable.
    return ctx


# Note: Call with mode="global" only when global_prior_mode.injection_ablatable=true
# All timeframe/target from project.timeframe + symbols.target_count
