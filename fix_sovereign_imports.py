import sys
import os
from pathlib import Path

# Sovereign path resolution
sys.path.insert(0, str(Path("config").absolute()))

print("Sovereign import path fixed for config/")

# Verify imports
try:
    from sovereign_entrypoint import get_sovereign_config
    cfg = get_sovereign_config()
    print("✅ Sovereign imports restored")
    print(f"Individual mode: {cfg['individual_mode']['enabled']}")
except Exception as e:
    print(f"❌ Import error: {e}")