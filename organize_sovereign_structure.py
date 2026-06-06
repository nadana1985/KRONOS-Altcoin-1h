from sovereign_entrypoint import get_sovereign_config, get_storage_path
import shutil
import os

cfg = get_sovereign_config()
base = get_storage_path(cfg, "base_path")
config_dir = get_storage_path(cfg, "config_dir")

# Create sovereign dirs
os.makedirs(config_dir, exist_ok=True)
os.makedirs(get_storage_path(cfg, "data_dir"), exist_ok=True)

# Move core files to config_dir
files_to_move = [
    "load_sovereign_config.py",
    "sovereign_entrypoint.py",
    "symbol_discovery_sovereign.py",
    "validate_sovereignty.py"
]

for f in files_to_move:
    src = os.path.join(base, f)
    if os.path.exists(src):
        dst = os.path.join(config_dir, f)
        shutil.move(src, dst)
        print(f"Moved: {f} -> {dst}")

print("Sovereign structure enforced.")