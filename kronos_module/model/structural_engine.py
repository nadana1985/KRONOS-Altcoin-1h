"""
KRONOS V1-ALT Sovereign Structural Engine (ported for 1h)

Provides structural veto core + individual/global prior dual-mode.
All values resolved from params_yaml.txt via sovereign loader.
Zero inline literals. Preserves orthogonal neural slot veto for scaling.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "config"))

from sovereign_entrypoint import get_sovereign_config


def get_structural_veto():
    """Enforce structural sections from params. Fails hard on missing keys (veto)."""
    cfg = get_sovereign_config()
    required = ["project", "storage", "individual_mode", "global_prior_mode", "symbols", "thresholds"]
    for sec in required:
        if sec not in cfg:
            raise KeyError(f"STRUCTURAL_VETO_FAILED: missing {sec} in params")
    return cfg


def get_dual_mode_context():
    """Return individual primary + global prior ablatable context. No literals."""
    cfg = get_structural_veto()
    ind = cfg["individual_mode"]
    gp = cfg["global_prior_mode"]
    sym = cfg["symbols"]
    proj = cfg["project"]
    thr = cfg["thresholds"]

    # orthogonal neural slot veto (from thresholds, for reversal/neural scaling)
    neural_slots = {
        "reversal_window": (thr["reversal_window_min"], thr["reversal_window_max"]),
        "reversal_factor": thr["reversal_window_factor"],
        "hash_mod": thr["reversal_hash_mod"],
        "variation": thr["reversal_variation_factor"],
        "strength_mult": thr["reversal_base_strength_multiplier"],
        "strength_add": thr["reversal_base_strength_add"],
        "confidence_clamp": (thr["reversal_confidence_clamp_min"], thr["reversal_confidence_clamp_max"]),
        "min_history": thr["reversal_min_history"],
        "confidence_min": thr["reversal_confidence_min"],
    }

    return {
        "timeframe": proj["timeframe"],
        "target_count": sym["target_count"],
        "individual": ind,
        "global_prior": gp,
        "neural_slots": neural_slots,
        "memory_shard": thr["memory_adaptive_shard_size"],
        "max_context": thr["max_context_tokens"],
        "is_individual_primary": ind["primary_output"],
        "global_injection_ablatable": gp["injection_ablatable"],
    }


def apply_structural_veto(mode: str = "individual"):
    """Small veto applicator for dual-mode. Use before model forward."""
    ctx = get_dual_mode_context()
    if mode == "individual" and not ctx["is_individual_primary"]:
        raise RuntimeError("STRUCTURAL_VETO: individual not primary per params")
    if mode == "global" and not ctx["global_injection_ablatable"]:
        raise RuntimeError("STRUCTURAL_VETO: global prior injection disabled per params")
    return ctx


# Ablation note: set global_prior_mode.injection_ablatable=false in params to ablate global prior.
# All scaling driven from symbols.target_count + project.timeframe.
