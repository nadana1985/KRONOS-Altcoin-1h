"""
KRONOS V1-ALT Sovereign Symbol Mapper v3.1
Maps symbols using data_fetch.symbol_mapping to real CCXT tickers.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

from config.utils.sovereign_entrypoint import get_sovereign_config
from config.utils.symbol_discovery_sovereign import discover_symbols

def get_real_ticker(placeholder: str) -> str:
    """Config-driven mapping from the params file."""
    cfg = get_sovereign_config()
    mapping_cfg = cfg['data_fetch']['symbol_mapping']
    
    if not mapping_cfg['enabled']:
        return placeholder
    
    prefix = mapping_cfg['prefix']
    suffix = mapping_cfg['suffix']
    real_format = mapping_cfg['real_format']
    
    base = placeholder.replace(prefix, '').replace(suffix, '')
    return real_format.format(base=base)

def build_full_symbol_map() -> dict:
    """Build mapping safely - extract string symbol from discovery dicts."""
    raw_symbols = discover_symbols()  # Returns list of dicts
    symbol_map = {}
    
    for item in raw_symbols:
        if isinstance(item, dict):
            sym_str = item.get('symbol', str(item))  # Sovereign key extraction
        else:
            sym_str = str(item)
        symbol_map[sym_str] = get_real_ticker(sym_str)
    
    print(f"Sovereign symbol map built: {len(symbol_map)} entries")
    return symbol_map

if __name__ == "__main__":
    build_full_symbol_map()