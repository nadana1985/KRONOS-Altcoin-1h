"""
KRONOS V1-ALT Sovereign Data Fetch v3.1 (moved to backups; superseded by unified_ingestion_engine)
TRUE FULL HISTORY + GAP VALIDATOR (runs once per symbol after download)
"""

import sys
from pathlib import Path
import logging
import json
from datetime import datetime
sys.path.insert(0, str(Path(__file__).parent.absolute()))

from sovereign_entrypoint import get_sovereign_config
from load_sovereign_config import get_storage_path
from unified_ingestion_engine import parse_timeframe_to_ms
import ccxt
import pandas as pd
import time
import os

def setup_sovereign_logger():
    cfg = get_sovereign_config()
    logs_dir = get_storage_path(cfg, "logs_dir")
    os.makedirs(logs_dir, exist_ok=True)
    log_file = os.path.join(logs_dir, f"data_fetch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | KRONOS-FETCH | %(levelname)s | %(message)s',
        handlers=[logging.FileHandler(log_file, encoding='utf-8'), logging.StreamHandler(sys.stdout)]
    )
    logger = logging.getLogger(__name__)
    logger.info(f"Sovereign fetch log initialized → {log_file}")
    return logger, log_file

def log_symbol_status(logger, symbol: str, status: str, candles: int = 0, filepath: str = None, details: str = ""):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "status": status,
        "candles_fetched": candles,
        "filepath": filepath,
        "details": details
    }
    logger.info(json.dumps(entry))
    if filepath and os.path.exists(filepath):
        size_kb = os.path.getsize(filepath) / 1024
        print(f"✅ Stored {symbol} → {filepath} ({candles} candles, {size_kb:.1f} KB)")

def validate_no_gaps(df: pd.DataFrame, symbol: str, logger) -> bool:
    """Sovereign gap validator - runs once after full download per symbol."""
    if len(df) < 2:
        logger.warning(f"⚠️ {symbol}: Too few candles for gap check")
        return True
    
    df = df.sort_values('timestamp').reset_index(drop=True)
    cfg_local = get_sovereign_config()
    tf = cfg_local["project"]["timeframe"]
    tc = cfg_local["time_constants"]
    expected_diff = parse_timeframe_to_ms(tf, tc)
    gaps = []
    for i in range(1, len(df)):
        actual = df['timestamp'].iloc[i] - df['timestamp'].iloc[i-1]
        if actual != expected_diff:
            gaps.append((i, df['timestamp'].iloc[i-1], df['timestamp'].iloc[i], actual))
    
    if gaps:
        logger.warning(f"⚠️ {symbol}: {len(gaps)} gaps detected in {len(df):,} candles!")
        return False
    
    logger.info(f"✅ {symbol}: GAP VALIDATION PASSED — {len(df):,} continuous candles (tf from params)")
    return True

def discover_symbols(cfg):
    fetch_cfg = cfg["data_fetch"]
    exchange_name = fetch_cfg["exchange"]
    ex = getattr(ccxt, exchange_name)({'enableRateLimit': True, 'options': fetch_cfg["exchange_options"]})
    markets = ex.load_markets()
    sym_cfg = cfg["symbols"]
    target_count = sym_cfg["target_count"]
    filter_quote = sym_cfg["filter_quote"]
    filter_type = sym_cfg["filter_type"]
    filter_active = sym_cfg["filter_active"]
    usdt_perps = [
        sym for sym, m in markets.items()
        if (m.get('type') == filter_type or m.get('swap', False)) and
           m.get('quote') == filter_quote and 
           m.get('active', filter_active) and 
           (f"/{filter_quote}" in sym or f":{filter_quote}" in sym)
    ]
    discovered = usdt_perps[:target_count]
    logger.info(f"Discovered {len(discovered)} ACTIVE {filter_quote} perpetuals")
    return discovered

def safe_symbol_name(symbol: str) -> str:
    """Clean symbol for filesystem."""
    return symbol.replace('/', '_').replace(':', '_').replace('-', '_')

def get_last_timestamp(filepath: str) -> int | None:
    if not os.path.exists(filepath):
        return None
    try:
        df = pd.read_parquet(filepath)
        if len(df) > 0:
            return int(df['timestamp'].max())
    except Exception as e:
        logger.warning(f"Failed to read existing shard {filepath}: {e}")
    return None

def fetch_full_history(symbol: str, ex, logger, cfg):
    raw_shards_dir = get_storage_path(cfg, "raw_shards_dir")
    os.makedirs(raw_shards_dir, exist_ok=True)
    safe_name = safe_symbol_name(symbol)
    ind_cfg = cfg.get("individual_mode", {})
    db_format = ind_cfg["db_format"]
    tf = cfg.get("project", {})["timeframe"]
    filepath = os.path.join(raw_shards_dir, f"{safe_name}_{tf}.{db_format}")
    
    fetch_limits = cfg["data_fetch"]["fetch_limits"]
    max_limit = fetch_limits["max_ohlcv"]
    tc = cfg["time_constants"]
    current_ms = int(time.time() * tc["ms_per_second"])
    since = get_last_timestamp(filepath)
    if since is None:
        lookback_years = cfg["data_fetch"]["genesis_lookback_years"]
        since = current_ms - (lookback_years * tc["days_per_year"] * tc["hours_per_day"] * tc["minutes_per_hour"] * tc["seconds_per_minute"] * tc["ms_per_second"])
    all_ohlcv = []
    total_new = 0
    pages = 0
    is_resume = get_last_timestamp(filepath) is not None
    
    try:
        logger.info(f"Starting {'resume' if is_resume else 'FULL'} fetch for {symbol} | initial_since={since}")
        while True:
            pages += 1
            logger.info(f"  Page {pages} | since={since}")
            
            ohlcv = ex.fetch_ohlcv(
                symbol,
                timeframe=cfg["project"]["timeframe"],
                limit=max_limit,
                since=since
            )
            
            if not ohlcv or len(ohlcv) == 0:
                logger.info(f"  No more data after {pages} pages")
                break
                
            all_ohlcv.extend(ohlcv)
            total_new += len(ohlcv)
            since = ohlcv[-1][0] + 1
            
            time.sleep(0.5)
            
            if len(ohlcv) < max_limit:
                logger.info(f"  Last partial page ({len(ohlcv)} candles) - full history complete")
                break
        
        if total_new > 0:
            if is_resume and os.path.exists(filepath):
                existing = pd.read_parquet(filepath)
                new_df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df = pd.concat([existing, new_df]).drop_duplicates(subset=['timestamp']).sort_values('timestamp')
            else:
                df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            df.to_parquet(filepath, compression='snappy')
            
            # Sovereign Gap Validation (runs once per symbol)
            is_valid = validate_no_gaps(df, symbol, logger)
            
            status = "resume_completed" if is_resume else "full_completed"
            details = f"{pages} pages | {'Resume' if is_resume else 'Full'} | {'VALID' if is_valid else 'GAPS'}"
            log_symbol_status(logger, symbol, status, len(df), filepath, details)
            return df
        else:
            log_symbol_status(logger, symbol, "partial", 0, None, "No new data")
            return None
    except ccxt.BadSymbol:
        log_symbol_status(logger, symbol, "not_found", 0, None, "BadSymbol")
        return None
    except Exception as e:
        log_symbol_status(logger, symbol, "error", total_new, None, str(e))
        return None

if __name__ == "__main__":
    global logger
    logger, _ = setup_sovereign_logger()
    cfg = get_sovereign_config()
    symbols = discover_symbols(cfg)
    fetch_cfg = cfg["data_fetch"]
    exchange_name = fetch_cfg["exchange"]
    ex = getattr(ccxt, exchange_name)({'enableRateLimit': True, 'options': fetch_cfg["exchange_options"]})
    logger.info(f"Starting FULL HISTORY fetch for {len(symbols)} perpetuals (per params)")
    # Full run (no test slice; use cfg target_count)
    for sym in symbols:
        logger.info(f"Processing {sym}")
        fetch_full_history(sym, ex, logger, cfg)
    logger.info("✅ Sovereign full history fetch session complete.")