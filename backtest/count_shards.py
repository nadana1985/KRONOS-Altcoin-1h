"""Count available real shards."""
import sys, os
sys.path.insert(0, '.')
os.environ['KRONOS_PARAMS_PATH'] = os.path.join('.', 'params_yaml.txt')
from config.utils.sovereign_entrypoint import get_sovereign_config, get_storage_path
from config.utils.symbol_discovery_sovereign import discover_symbols_from_shards
cfg = get_sovereign_config()
raw_dir = get_storage_path(cfg, 'raw_shards_dir')
tf = cfg['project']['timeframe']
all_syms = discover_symbols_from_shards(raw_dir, tf)
print(f"Total real shards available: {len(all_syms)}")
# Print first 20 to verify
for s in all_syms[:20]:
    print(f"  {s['symbol']}")