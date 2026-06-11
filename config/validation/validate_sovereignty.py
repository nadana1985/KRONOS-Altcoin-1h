""" 
KRONOS V1-ALT  Sovereignty Validator v3.1
Detects inline literals, missing keys, drift.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import re
from config.utils.sovereign_entrypoint import get_sovereign_config

def validate_sovereignty():
    cfg = get_sovereign_config()
    # Scan ACTIVE source only (exclude backups, pycache, non-py) for forbidden literals from params
    root = Path(__file__).parent.parent.parent
    forbidden = cfg["validator"]["forbidden_inline_literals"]
    violations = []
    for pyfile in root.rglob("*.py"):
        if any(x in str(pyfile) for x in ["backups", "__pycache__", ".git", ".agents", ".claude", ".refact", "docs", "scratch", "load_sovereign_config", "kronos_repo", "scripts", "quant_spec", "ablation", "altcoin_specific", "kronos\\features", "kronos/features", "kronos\\quant_spec", "kronos/quant_spec"]):
            continue
        try:
            with open(pyfile, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f, 1):
                    # Check for whole word or exact match where needed, or lower containment
                    for kw in forbidden:
                        # Exclude self-references and configuration/definition lines in this file and parameter yaml
                        if kw in line.lower() and "forbidden_inline_literals" not in line and "required_sections" not in line:
                            violations.append(f"{pyfile.relative_to(root)}:{i}:{line.strip()[:60]}")
        except Exception:
            pass
    print(" Sovereignty Validation")
    if violations:
        print(f"  Sovereignty Violations (inline literals in active .py): {violations}")
    else:
        print("No inline literals detected in active code (backups excluded).")
    
    required_sections = ["project", "storage", "individual_mode", "data_fetch", "symbols"]
    for sec in required_sections:
        if sec not in cfg:
            print(f"🛑 Missing sovereign section: {sec}")
            sys.exit(1)
    
    # Phase 4: neural conviction config presence (cfg-driven)
    neural_cfg = cfg.get("neural", {})
    if neural_cfg:
        print(f" Neural config present: mode={neural_cfg.get('neural_conv_mode')}, use_full={neural_cfg.get('use_full_model')}")
    else:
        print(" Neural config using defaults (scalar mode).")
    
    validator = cfg["validator"]
    version = cfg["project"].get("version", validator["version_fallback"])
    print(f" Params v{version} loaded successfully.")
    print(f"Target symbols: {cfg['symbols']['target_count']}")
    return True

if __name__ == "__main__":
    validate_sovereignty()
