"""
KRONOS V1-ALT Sovereign Symbol Discovery v3.1
Broad capture using filter params from symbols section.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.absolute()))

import ccxt
from sovereign_entrypoint import get_sovereign_config

def discover_symbols() -> list:
    cfg = get_sovereign_config()
    target_count = cfg["symbols"]["target_count"]
    
    fetch_cfg = cfg["data_fetch"]
    exchange_name = fetch_cfg["exchange"]
    sym_cfg = cfg["symbols"]
    filter_mode = sym_cfg["filter"]
    print(f"KRONOS DISCOVERY: Target={target_count} | Mode=real_{exchange_name} | Filter={filter_mode} | Junk=KEPT")
    
    try:
        exchange_opts = fetch_cfg["exchange_options"]
        exchange = getattr(ccxt, exchange_name)({
            'enableRateLimit': True,
            'options': exchange_opts
        })
        print("[DISCOVERY] Loading markets...")
        markets = exchange.load_markets()
        print(f"Loaded {len(markets)} total markets from {exchange_name}")
        
        sym_filter = cfg["symbols"]
        perpetuals = []
        for symbol, market in markets.items():
            if (sym_filter["filter_quote"] in symbol and
                (market.get('type') == sym_filter["filter_type"] or market.get('swap', False)) and
                market.get('active', sym_filter["filter_active"])):
                # normalize to match unified data path and params symbol_mapping
                mapping = cfg["data_fetch"]["symbol_mapping"]
                if mapping["enabled"]:
                    prefix = mapping["prefix"]
                    suffix = mapping["suffix"]
                    real_format = mapping["real_format"]
                    base = symbol.split('/')[0] if '/' in symbol else symbol.split(':')[0] if ':' in symbol else symbol
                    symbol = real_format.format(base=base)
                perpetuals.append({
                    "symbol": symbol,
                    "volume_24h": 0,
                    "tags": []
                })
        
        discovered = perpetuals[:target_count]
        
        print(f"Discovered {len(discovered)} real perpetuals (ALL junk kept per filter)")
        if discovered:
            print("Sample:", [s['symbol'] for s in discovered[:10]])
        return discovered
        
    except Exception as e:
        print(f"Real {exchange_name} discovery failed: {e}")
    
    # Fallback using data_fetch.symbol_fallback section (cfg only)
    discovered = []
    mapping = cfg["data_fetch"]["symbol_mapping"]
    prefix = mapping["prefix"]
    suffix = mapping["suffix"]
    symbol_fallback = cfg["data_fetch"]["symbol_fallback"]
    for i in range(target_count):
        discovered.append({
            "symbol": symbol_fallback["format"].format(prefix=prefix, i=i, suffix=suffix),
            "volume_24h": symbol_fallback["volume_24h"],
            "tags": symbol_fallback["tags"]
        })
    print(f"Discovered {len(discovered)} symbols (symbol_fallback from params)")
    return discovered

def discover_symbols_from_shards(raw_shards_dir: str, timeframe: str) -> list:
    """Discover symbols by scanning existing parquet shard files on disk.
    Used for E2E harness and offline runs (Option B): mine only what data is actually present.
    Returns list in the same shape as discover_symbols() for compatibility with the miner.
    No network, no synthetic fallback.
    """
    import glob
    import os

    pattern = os.path.join(raw_shards_dir, f"*_{timeframe}.parquet")
    shard_files = glob.glob(pattern)

    discovered = []
    for path in sorted(shard_files):
        basename = os.path.basename(path)
        # Expect: SYMBOLNAME_TIMEFRAME.parquet  (e.g. BTC_USDT_USDT_1h.parquet)
        suffix = f"_{timeframe}.parquet"
        if basename.endswith(suffix):
            symbol = basename[: -len(suffix)]
            discovered.append({
                "symbol": symbol,
                "volume_24h": 0,
                "tags": []
            })

    return discovered


if __name__ == "__main__":
    symbols = discover_symbols()
    print(f"Final sovereign discovery count: {len(symbols)}")