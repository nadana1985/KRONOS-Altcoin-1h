"""
KRONOS V5.1 — Ablation Bootstrap

Config-driven ablation: controls which override points are active at startup
by modifying the neural.point_XX_enabled flags in the sovereign config.

Usage at startup:
    from config.ablation_bootstrap import apply_ablation_config
    apply_ablation_config()  # reads from params_yaml.txt -> backtest.ablation

Or via CLI:
    python -c "from config.ablation_bootstrap import apply_ablation_config; apply_ablation_config('core_dynamic')"
"""
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("kronos.ablation")

# ── All 26 enabled override points ──
ALL_OVERRIDE_POINTS = [1, 2, 3, 6, 11, 15, 19, 23, 24, 25, 28, 29, 35, 36, 44, 46, 47, 48, 52, 56, 57, 64, 66, 69, 72, 82]

# ── Group definitions (mirrors override_groups.yaml for runtime use) ──
OVERRIDE_GROUPS = {
    "core_dynamic": {"points": [1, 2, 3], "label": "Core Dynamic (01-03)"},
    "risk_tail": {"points": [15, 64, 72], "label": "Risk & Tail (15,64,72)"},
    "volatility": {"points": [48, 52, 56, 57], "label": "Volatility (48,52,56,57)"},
    "order_flow": {"points": [11, 24], "label": "Order Flow (11,24)"},
    "microstructure": {"points": [6, 19, 23, 25, 29], "label": "Microstructure (06,19,23,25,29)"},
    "robust_stats": {"points": [66, 69], "label": "Robust Stats (66,69)"},
    "validation": {"points": [35, 36, 82], "label": "Validation (35,36,82)"},
    "vol_batch2": {"points": [46, 47], "label": "Vol Batch2 (46,47)"},
    "misc_b5": {"points": [28, 44], "label": "Batch5 Misc (28,44)"},
}


def apply_ablation_config(override_group: Optional[str] = None) -> Dict[str, Any]:
    """
    Apply ablation configuration by modifying the params_yaml.txt neural section.

    When override_group is provided:
      - Only that group's points are enabled (all others disabled)
      - All other override points' point_XX_enabled flags are set to False

    When override_group is None:
      - Reads 'active_groups' from params_yaml.txt -> backtest.ablation
      - Enables only those groups' points

    Returns the modified config for inspection.
    """
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    params_path = os.path.join(_project_root, "params_yaml.txt")

    # Read current params_yaml.txt
    with open(params_path, "r", encoding="utf-8") as f:
        content = f.read()

    if override_group is not None:
        # Direct group override
        if override_group not in OVERRIDE_GROUPS:
            raise ValueError(f"Unknown override group: {override_group}. Options: {list(OVERRIDE_GROUPS.keys())}")
        active_points = set(OVERRIDE_GROUPS[override_group]["points"])
        logger.info("[ABLATION] Applying group: %s (points: %s)", override_group, sorted(active_points))
    else:
        # Read from params_yaml.txt
        try:
            import yaml
            cfg = yaml.safe_load(content)
            ablation_cfg = cfg.get("backtest", {}).get("ablation", {})
            if not ablation_cfg.get("enabled", False):
                logger.info("[ABLATION] Ablation not enabled in config — all points active")
                return cfg

            active_groups = ablation_cfg.get("active_groups", [])
            active_points = set()
            for g in active_groups:
                if g in OVERRIDE_GROUPS:
                    active_points.update(OVERRIDE_GROUPS[g]["points"])
                else:
                    logger.warning("[ABLATION] Unknown group in active_groups: %s", g)

            if not active_points:
                logger.info("[ABLATION] No active groups specified — all points active")
                return cfg

            logger.info("[ABLATION] Active groups: %s -> points: %s", active_groups, sorted(active_points))
        except Exception as e:
            logger.warning("[ABLATION] Failed to read ablation config: %s", e)
            return {}

    # Build the neural section overrides
    lines = content.split("\n")
    new_lines = []
    modified_count = 0

    for line in lines:
        modified_line = line
        for pt in ALL_OVERRIDE_POINTS:
            flag_key = f"point_{pt:02d}_enabled:"
            if flag_key in line:
                # Check if this point should be active
                should_enable = pt in active_points
                # Replace the value
                import re
                new_line = re.sub(
                    rf"({flag_key}\s*)(True|False)",
                    rf"\g<1>{should_enable}",
                    line
                )
                if new_line != line:
                    modified_line = new_line
                    modified_count += 1
                break

        new_lines.append(modified_line)

    # Write the modified params_yaml.txt
    new_content = "\n".join(new_lines)
    with open(params_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    logger.info("[ABLATION] Modified %d point_XX_enabled flags in params_yaml.txt", modified_count)
    logger.info("[ABLATION] Active points: %s | Disabled: %s",
                sorted(active_points),
                sorted(set(ALL_OVERRIDE_POINTS) - active_points))

    return {"active_points": sorted(active_points), "modified_count": modified_count}


def reset_to_full_config() -> None:
    """Reset all point_XX_enabled flags to True in params_yaml.txt."""
    _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    params_path = os.path.join(_project_root, "params_yaml.txt")

    with open(params_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    new_lines = []
    modified_count = 0

    import re
    for line in lines:
        modified_line = line
        for pt in ALL_OVERRIDE_POINTS:
            flag_key = f"point_{pt:02d}_enabled:"
            if flag_key in line:
                new_line = re.sub(
                    rf"({flag_key}\s*)(True|False)",
                    rf"\g<1>True",
                    line
                )
                if new_line != line:
                    modified_line = new_line
                    modified_count += 1
                break

        new_lines.append(modified_line)

    new_content = "\n".join(new_lines)
    with open(params_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    logger.info("[ABLATION] Reset: modified %d point_XX_enabled flags back to True", modified_count)


def get_active_points_from_config() -> List[int]:
    """Read params_yaml.txt and return the list of active override points
    based on point_XX_enabled flags. Useful for point modules to check if
    they should compute."""
    try:
        _project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        params_path = os.path.join(_project_root, "params_yaml.txt")

        import yaml
        with open(params_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        neural = cfg.get("neural", {})
        active = []
        for pt in ALL_OVERRIDE_POINTS:
            flag = neural.get(f"point_{pt:02d}_enabled", True)
            if flag:
                active.append(pt)
        return active
    except Exception:
        return ALL_OVERRIDE_POINTS


def is_point_enabled(point_id: str) -> bool:
    """Check if a specific override point is enabled based on config.
    Point modules should call this before doing any work.

    point_id: str like "01", "15", "64"
    """
    try:
        return int(point_id) in get_active_points_from_config()
    except Exception:
        return True


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Apply ablation config")
    parser.add_argument("--group", type=str, help="Override group name (e.g. core_dynamic)")
    parser.add_argument("--reset", action="store_true", help="Reset all points to enabled")
    args = parser.parse_args()

    if args.reset:
        reset_to_full_config()
        print("Reset all points to enabled.")
    elif args.group:
        result = apply_ablation_config(args.group)
        print(f"Applied group: {args.group}")
        print(f"Active points: {result['active_points']}")
    else:
        result = apply_ablation_config()
        print(f"Applied config-driven ablation.")
        print(f"Active points: {result.get('active_points', [])}")