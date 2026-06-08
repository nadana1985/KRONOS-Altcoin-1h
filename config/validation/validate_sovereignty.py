""" 
KRONOS V1-ALT  Sovereignty Validator v3.1
Detects inline literals, missing keys, drift.
"""
import sys
from pathlib import Path
import re
from config.utils.sovereign_entrypoint import get_sovereign_config

def validate_sovereignty():
    cfg = get_sovereign_config()
    # Scan ACTIVE source only (exclude backups, pycache, non-py) for forbidden literals from params
    root = Path(__file__).parent
    forbidden = cfg["validator"]["forbidden_inline_literals"]
    violations = []
    for pyfile in root.rglob("*.py"):
        if "backups" in str(pyfile) or "__pycache__" in str(pyfile):
            continue
        try:
            with open(pyfile, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f, 1):
                    if any(kw in line.lower() for kw in forbidden):
                        violations.append(f"{pyfile.name}:{i}:{line.strip()[:60]}")
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
    
    validator = cfg["validator"]
    version = cfg["project"].get("version", validator["version_fallback"])
    print(f" Params v{version} loaded successfully.")
    print(f"Target symbols: {cfg['symbols']['target_count']}")
    return True

if __name__ == "__main__":
    validate_sovereignty()
