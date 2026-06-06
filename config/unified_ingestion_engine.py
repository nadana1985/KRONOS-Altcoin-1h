"""
KRONOS V1-ALT — Unified Ingestion Engine v3.7
CLEAN CONFIG TRAVERSAL + FILTERS FROM PARAMS + SOVEREIGN SYMBOL MAPPING
"""
import sys
from pathlib import Path
import logging
import json
from datetime import datetime, timezone
import ccxt
import pandas as pd
import time
import os
sys.path.insert(0, str(Path(__file__).parent.absolute()))
from sovereign_entrypoint import get_sovereign_config
from load_sovereign_config import get_storage_path

def setup_sovereign_logger(cfg):
    logs_dir = get_storage_path(cfg, "logs_dir")
    os.makedirs(logs_dir, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(logs_dir, f"data_fetch_{timestamp}.log")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | KRONOS-CORE | %(levelname)s | %(message)s',
        handlers=[logging.FileHandler(log_file, encoding='utf-8'), logging.StreamHandler(sys.stdout)]
    )
    return logging.getLogger(__name__), log_file

def parse_timeframe_to_ms(timeframe_str: str, tc: dict) -> int:
    unit = timeframe_str[-1]
    val = int(timeframe_str[:-1])
    multipliers = tc["unit_multipliers"]
    if unit not in multipliers:
        raise ValueError(f"CRITICAL: Unmapped sovereign timeframe token: {unit}")
    return val * multipliers[unit] * tc["ms_per_second"]

def validate_no_gaps(df: pd.DataFrame, symbol: str, timeframe_ms: int, logger) -> bool:
    if len(df) < 2:
        return True
    diffs = df['timestamp'].diff().dropna()
    gap_mask = diffs != timeframe_ms
    if gap_mask.any():
        total_gaps = gap_mask.sum()
        logger.warning(f"⚠️ {symbol}: {total_gaps} temporal gaps detected.")
        return False
    return True

def discover_symbols(ex, cfg, logger):
    logger.info("Initializing remote market structures...")
    ex.load_markets()
    sym_cfg = cfg["symbols"]
    fetch_cfg = cfg["data_fetch"]
    target_count = sym_cfg["target_count"]
    filter_mode = sym_cfg["filter"]
    min_vol = sym_cfg["min_24h_volume_usd"]
    exclude_tags = sym_cfg["exclude_tags"]
    filter_quote = sym_cfg["filter_quote"]
    filter_type = sym_cfg["filter_type"]
    filter_active = sym_cfg["filter_active"]
    filter_keyword = sym_cfg["filter_keyword"]
    
    discovered = []
    for sym, m in ex.markets.items():
        is_active = m.get('active', filter_active)
        is_perp = (m.get('type') == filter_type or m.get('swap', False))
        is_usdt = (m.get('quote') == filter_quote)
        is_excluded = any(tag in sym.lower() for tag in exclude_tags)
        
        if filter_mode == filter_keyword and is_perp and is_usdt and is_active and not is_excluded:
            info = m.get('info', {})
            volume_quote = float(info.get('volumeQuote', info.get('quoteVolume', 0)) or 0)
            if volume_quote >= min_vol or (fetch_cfg["use_real"] and volume_quote == 0):
                base = sym.split('/')[0] if '/' in sym else sym.split(':')[0] if ':' in sym else sym
                mapping = fetch_cfg["symbol_mapping"]
                real_format = mapping["real_format"]
                discovered.append(real_format.format(base=base))
    return discovered[:target_count]

def fetch_full_history(symbol: str, ex, logger, cfg):
    proj_cfg = cfg["project"]
    fetch_cfg = cfg["data_fetch"]
    ind_cfg = cfg["individual_mode"]
    tf = proj_cfg["timeframe"]
    raw_shards_dir = get_storage_path(cfg, "raw_shards_dir")
    tc = cfg["time_constants"]
    timeframe_ms = parse_timeframe_to_ms(tf, tc)
    db_format = ind_cfg["db_format"]
    safe_name = symbol.replace('/', '_').replace(':', '_').replace('-', '_')
    filepath = os.path.join(raw_shards_dir, f"{safe_name}_{tf}.{db_format}")
    
    current_ms = int(time.time() * tc["ms_per_second"])
    lookback_years = fetch_cfg["genesis_lookback_years"]
    sovereign_genesis = current_ms - (lookback_years * tc["days_per_year"] * tc["hours_per_day"] * tc["minutes_per_hour"] * tc["seconds_per_minute"] * tc["ms_per_second"])
    
    if os.path.exists(filepath):
        try:
            existing_df = pd.read_parquet(filepath, columns=['timestamp']) if db_format == "parquet" else pd.read_csv(filepath, usecols=['timestamp'])
            since = int(existing_df['timestamp'].max()) + 1 if not existing_df.empty else sovereign_genesis
            is_resume = True
        except Exception:
            since = sovereign_genesis
            is_resume = False
    else:
        since = sovereign_genesis
        is_resume = False
       
    all_ohlcv = []
    max_limit = fetch_cfg["fetch_limits"]["max_ohlcv"]
    max_retries = fetch_cfg["max_retries"]
    pacing_delay = fetch_cfg["rate_limit_ms"] / tc["ms_per_second"]
   
    while True:
        ohlcv = None
        for attempt in range(1, max_retries + 1):
            try:
                ohlcv = ex.fetch_ohlcv(symbol, timeframe=tf, limit=max_limit, since=since)
                break
            except Exception as e:
                logger.warning(f"Connection retry hook intercept [{attempt}/{max_retries}] for {symbol}: {e}")
                time.sleep(pacing_delay * 2 * attempt)
        if not ohlcv or len(ohlcv) == 0:
            break
        all_ohlcv.extend(ohlcv)
        last_returned_ts = ohlcv[-1][0]
        since = last_returned_ts + 1
        time.sleep(pacing_delay)
        if len(ohlcv) < max_limit:
            break
    if len(all_ohlcv) > 0:
        new_df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        if is_resume and os.path.exists(filepath):
            historical_df = pd.read_parquet(filepath) if db_format == "parquet" else pd.read_csv(filepath)
            combined_df = pd.concat([historical_df, new_df])
        else:
            combined_df = new_df
        combined_df.drop_duplicates(subset=['timestamp'], keep='last', inplace=True)
        combined_df.sort_values('timestamp', inplace=True)
        combined_df.reset_index(drop=True, inplace=True)
        validate_no_gaps(combined_df, symbol, timeframe_ms, logger)
        if db_format == "parquet":
            combined_df.to_parquet(filepath, compression='snappy', index=False)
        else:
            combined_df.to_csv(filepath, index=False)
        logger.info(f"✅ Data Synchronized: {symbol} Shard Array Length → {len(combined_df)} records.")
        return combined_df
    return None

def fetch_all_symbols_data() -> None:
    cfg = get_sovereign_config()
    logger, _ = setup_sovereign_logger(cfg)
    ind_cfg = cfg["individual_mode"]
    if not ind_cfg["enabled"]:
        logger.critical("🛑 [ABLATION INTERCEPT] Individual Mode is disabled inside config. Halting execution pipeline.")
        sys.exit(0)
    fetch_cfg = cfg["data_fetch"]
    exchange_name = fetch_cfg["exchange"]
    if not hasattr(ccxt, exchange_name):
        logger.critical(f"Execution Target Error: CCXT driver does not contain initialization maps for: {exchange_name}")
        sys.exit(1)
    exchange_class = getattr(ccxt, exchange_name)
    exchange_opts = fetch_cfg["exchange_options"]
    exchange_client = exchange_class({'enableRateLimit': True, 'options': exchange_opts})
    proj_cfg = cfg["project"]
    symbols = discover_symbols(exchange_client, cfg, logger)
    logger.info(f"Synchronizing history across {len(symbols)} tracked targets...")
    for sym in symbols:
        fetch_full_history(sym, exchange_client, logger, cfg)
    # Ablation injection point for global_prior_mode (controlled via params)

if __name__ == "__main__":
    fetch_all_symbols_data()