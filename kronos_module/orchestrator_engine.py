"""
Sovereign Orchestrator Engine (1h port)

Wires structural veto core + individual/global prior dual-mode.
Uses only params_yaml.txt values. Small port of hybrid dual-mode + veto.
Ablation supported via global_prior_mode.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "model"))

from structural_engine import get_dual_mode_context, apply_structural_veto


def orchestrate_sovereign(mode: str = "individual"):
    """Primary entry for dual-mode with structural veto enforced."""
    ctx = apply_structural_veto(mode)
    # Memory-safe: use ctx["memory_shard"], ctx["max_context"], ctx["target_count"]
    # for 530 symbol 1h scaling. Neural slots from thresholds.
    # individual primary; global prior orthogonal + ablatable.
    return ctx


# Note: Call with mode="global" only when global_prior_mode.injection_ablatable=true
# All timeframe/target from project.timeframe + symbols.target_count
