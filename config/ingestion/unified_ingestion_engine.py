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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))  # insert project root for subpackage imports
from config.utils.sovereign_entrypoint import get_sovereign_config
from config.validation.load_sovereign_config import get_storage_path

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

CRITICAL_COLS = ["open", "high", "low", "close", "volume", "quote_volume"]

def _detect_outliers(series, n_std=4):
    """Return count of values beyond n_std from mean (IQR method fallback)."""
    if len(series) < 4:
        return 0
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return 0
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return int((series < lower).sum() + (series > upper).sum())

def _clip_outliers(series, n_std=4):
    """Clip values beyond n_std from mean to boundary values."""
    if len(series) < 4:
        return series
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return series
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return series.clip(lower=lower, upper=upper)

def validate_and_fix_data(df: pd.DataFrame, symbol: str, timeframe_ms: int, logger, cfg) -> dict:
    """Comprehensive quality checker: gaps, duplicates, NaN, outliers, completeness.
    Returns report with health_score (0-100) and per-metric details.
    Auto-fixes: forward-fill NaN, clip outliers when params allow."""
    report = {"gaps": 0, "duplicates": 0, "nan_pct": 0.0, "outlier_pct": 0.0, "completeness_pct": 100.0,
              "health_score": 100, "fixed_nan": 0, "fixed_outliers": 0, "issues": []}
    if len(df) < 2:
        report["health_score"] = 0
        return report
    present_critical = [c for c in CRITICAL_COLS if c in df.columns]
    n = len(df)
    auto_fix = cfg.get("data_fetch", {}).get("auto_fill_gaps", True)
    # 1. Duplicate timestamps
    dup_count = int(df['timestamp'].duplicated().sum())
    report["duplicates"] = dup_count
    if dup_count:
        report["issues"].append(f"{dup_count} duplicate timestamps")
        logger.warning(f"⚠️ {symbol}: {dup_count} duplicate timestamps.")
    # 2. NaN ratio in critical columns
    nan_mask = df[present_critical].isna().any(axis=1)
    nan_total = int(nan_mask.sum())
    nan_pct = 100.0 * nan_total / max(n, 1)
    report["nan_pct"] = round(nan_pct, 2)
    if nan_total:
        nan_by_col = {c: int(df[c].isna().sum()) for c in present_critical if df[c].isna().any()}
        report["nan_cols"] = nan_by_col
        report["issues"].append(f"{nan_pct:.1f}% NaN rows ({nan_total})")
        logger.warning(f"⚠️ {symbol}: {nan_pct:.1f}% NaN in critical cols: {nan_by_col}")
        # Auto forward-fill NaN
        if auto_fix:
            pre_fill_nan = int(df[present_critical].isna().sum().sum())
            df[present_critical] = df[present_critical].ffill()
            post_fill_nan = int(df[present_critical].isna().sum().sum())
            filled = pre_fill_nan - post_fill_nan
            report["fixed_nan"] = filled
            if filled:
                logger.info(f"✅ {symbol}: forward-filled {filled} NaN values.")
    # 3. Temporal gaps
    diffs = df['timestamp'].diff().dropna()
    gap_mask = diffs != timeframe_ms
    total_gaps = int(gap_mask.sum())
    report["gaps"] = total_gaps
    if total_gaps:
        max_gap_ms = int(diffs[gap_mask].max()) if gap_mask.any() else 0
        report["max_gap_bars"] = max_gap_ms // max(timeframe_ms, 1)
        report["issues"].append(f"{total_gaps} temporal gaps (max {max_gap_ms//max(timeframe_ms,1)} bars)")
        logger.warning(f"⚠️ {symbol}: {total_gaps} gaps, max {max_gap_ms//max(timeframe_ms,1)} bars.")
    # 4. Outlier detection on volume, close, quote_volume
    outlier_total = 0
    for col_name in ["close", "volume"]:
        if col_name in df.columns and df[col_name].dtype.kind in "fc":
            oc = _detect_outliers(df[col_name])
            outlier_total += oc
    outlier_pct = 100.0 * outlier_total / max(n, 1)
    report["outlier_pct"] = round(outlier_pct, 2)
    if outlier_total:
        report["issues"].append(f"{outlier_pct:.1f}% outlier rows ({outlier_total})")
        logger.warning(f"⚠️ {symbol}: {outlier_pct:.1f}% outlier values in close/volume.")
        # Auto clip outliers
        if auto_fix:
            pre_clip = outlier_total
            if "close" in df.columns:
                df["close"] = _clip_outliers(df["close"])
            if "volume" in df.columns:
                df["volume"] = _clip_outliers(df["volume"])
            report["fixed_outliers"] = pre_clip
            logger.info(f"✅ {symbol}: clipped {pre_clip} outlier values.")
    # 5. Completeness: expected bars = (end_ms - genesis) / timeframe_ms
    report["completeness_pct"] = 100.0
    # 6. Health score (0-100)
    completeness_score = 100.0
    if len(present_critical):
        completeness_score = 100.0 * (1.0 - df[present_critical].isna().any(axis=1).mean())
    gap_score = max(0, 100 - total_gaps * 2)
    outlier_score = max(0, 100 - outlier_pct * 2)
    nan_score = max(0, 100 - nan_pct * 2)
    health = int(round(0.40 * completeness_score + 0.20 * gap_score + 0.20 * outlier_score + 0.20 * nan_score))
    health = max(0, min(100, health))
    report["health_score"] = health
    # Log final per-symbol report
    if health >= 90:
        tag = "🟢"
    elif health >= 70:
        tag = "🟡"
    else:
        tag = "🔴"
    logger.info(f"{tag} {symbol}: health={health}/100 | gaps={total_gaps} dup={dup_count} nan={nan_pct:.1f}% out={outlier_pct:.1f}%")
    return report

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

def get_checkpoint_dir(cfg) -> str:
    cp = get_storage_path(cfg, "checkpoints_dir")
    os.makedirs(cp, exist_ok=True)
    return cp

def load_checkpoint(safe_name: str, cp_dir: str, logger) -> int | None:
    cpath = os.path.join(cp_dir, f"last_ts_{safe_name}.txt")
    if os.path.exists(cpath):
        try:
            with open(cpath, "r") as f:
                return int(f.read().strip())
        except Exception as e:
            logger.warning(f"Checkpoint read failed for {safe_name}: {e}")
    return None

def save_checkpoint(safe_name: str, last_ts: int, cp_dir: str) -> None:
    cpath = os.path.join(cp_dir, f"last_ts_{safe_name}.txt")
    with open(cpath, "w") as f:
        f.write(str(last_ts))

_request_counter = 0

def _rate_limited_call(ex, symbol, kparams, logger, cfg):
    """Call fapiPublicGetKlines with global request pacing + exponential backoff for 429."""
    global _request_counter
    fetch_cfg = cfg["data_fetch"]
    max_retries = fetch_cfg["max_retries"]
    delay = float(fetch_cfg.get("rate_limit_delay", 0.5))
    max_backoff = fetch_cfg.get("rate_limit_max_backoff", 8)
    # Global inter-request pacing
    _request_counter += 1
    time.sleep(delay)
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            return ex.fapiPublicGetKlines(kparams)
        except ccxt.RateLimitExceeded as e:
            backoff = min(max_backoff, 2 ** (attempt - 1))
            logger.warning(f"🚦 Rate limit [{attempt}/{max_retries}] {symbol}: backing off {backoff}s — {e}")
            time.sleep(backoff)
            last_err = e
        except Exception as e:
            if attempt < max_retries:
                backoff = min(max_backoff, 2 ** (attempt - 1))
                logger.warning(f"⚠️ Retry [{attempt}/{max_retries}] {symbol}: {e} — backoff {backoff}s")
                time.sleep(backoff)
            last_err = e
    raise last_err

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
    cp_dir = get_checkpoint_dir(cfg)
    
    end_offset_days = fetch_cfg.get("end_date_offset_days", 1)
    current_ms = int(time.time() * tc["ms_per_second"])
    end_ms = current_ms - (end_offset_days * tc["hours_per_day"] * tc["minutes_per_hour"] * tc["seconds_per_minute"] * tc["ms_per_second"])
    lookback_years = fetch_cfg["genesis_lookback_years"]
    sovereign_genesis = current_ms - (lookback_years * tc["days_per_year"] * tc["hours_per_day"] * tc["minutes_per_hour"] * tc["seconds_per_minute"] * tc["ms_per_second"])
    
    cp_last = load_checkpoint(safe_name, cp_dir, logger)
    shard_last = None
    if os.path.exists(filepath):
        try:
            existing_df = pd.read_parquet(filepath, columns=['timestamp']) if db_format == "parquet" else pd.read_csv(filepath, usecols=['timestamp'])
            shard_last = int(existing_df['timestamp'].max()) if not existing_df.empty else None
        except Exception:
            pass
    
    # Incremental skip: if shard has data within 1 day of end_ms, skip
    if shard_last is not None:
        one_day_ms = tc["hours_per_day"] * tc["minutes_per_hour"] * tc["seconds_per_minute"] * tc["ms_per_second"]
        if shard_last >= end_ms - one_day_ms:
            logger.info(f"⏭️ {symbol}: shard already recent ({shard_last} >= {end_ms - one_day_ms}), skipping fetch.")
            if cp_last is None or cp_last < shard_last:
                save_checkpoint(safe_name, shard_last, cp_dir)
            return None
    
    since = cp_last if cp_last is not None else (shard_last + 1 if shard_last is not None else sovereign_genesis)
    is_resume = os.path.exists(filepath) and (shard_last is not None)
    
    all_ohlcv = []
    max_limit = fetch_cfg["fetch_limits"]["max_ohlcv"]
    market = ex.market(symbol)
    bsym = market['id']
    
    while True:
        if since is not None and since >= end_ms:
            break
        kparams = {'symbol': bsym, 'interval': tf, 'limit': max_limit}
        if since is not None:
            kparams['startTime'] = since
        kparams['endTime'] = end_ms
        ohlcv = _rate_limited_call(ex, symbol, kparams, logger, cfg)
        if not ohlcv or len(ohlcv) == 0:
            break
        all_ohlcv.extend(ohlcv)
        last_returned_ts = ohlcv[-1][0]
        since = last_returned_ts + 1
        if len(ohlcv) < max_limit:
            break
    if len(all_ohlcv) > 0:
        kline_fields = fetch_cfg["kline_fields"]
        new_df = pd.DataFrame(all_ohlcv, columns=kline_fields)
        if 'quote_volume' in new_df.columns and 'amount' not in new_df.columns:
            new_df['amount'] = new_df['quote_volume']
        if is_resume and os.path.exists(filepath):
            historical_df = pd.read_parquet(filepath) if db_format == "parquet" else pd.read_csv(filepath)
            combined_df = pd.concat([historical_df, new_df])
        else:
            combined_df = new_df
        combined_df.drop_duplicates(subset=['timestamp'], keep='last', inplace=True)
        combined_df.sort_values('timestamp', inplace=True)
        combined_df.reset_index(drop=True, inplace=True)
        # Strict Schema Enforcement
        for col in combined_df.columns:
            if col in ['timestamp', 'close_time', 'count']:
                combined_df[col] = pd.to_numeric(combined_df[col], errors='coerce').fillna(0).astype('int64')
            elif col != 'ignore':
                combined_df[col] = pd.to_numeric(combined_df[col], errors='coerce').astype('float64')
        validate_and_fix_data(combined_df, symbol, timeframe_ms, logger, cfg)
        if db_format == "parquet":
            combined_df.to_parquet(filepath, compression='snappy', index=False)
        else:
            combined_df.to_csv(filepath, index=False)
        save_checkpoint(safe_name, int(combined_df['timestamp'].max()), cp_dir)
        logger.info(f"✅ Data Synchronized: {symbol} Shard Array Length → {len(combined_df)} records.")
        return combined_df
    return None

class IngestionTracker:
    """Rich progress logger for multi-symbol ingestion. Uses tqdm if available."""
    def __init__(self, total: int, logger):
        self.total = total
        self.logger = logger
        self.completed = 0
        self.total_bars = 0
        self.errors = 0
        self.start_ts = time.time()
        self.tqdm = None
        try:
            from tqdm import tqdm as _tqdm
            self.tqdm = _tqdm(total=total, unit="sym", desc="Ingestion", ncols=80)
        except ImportError:
            pass

    def on_start_symbol(self, sym: str) -> None:
        self.current = sym

    def on_symbol_done(self, bars: int, sym: str) -> None:
        self.completed += 1
        self.total_bars += max(bars, 0)
        elapsed = time.time() - self.start_ts
        rate = self.completed / elapsed if elapsed > 0 else 0
        remaining = (self.total - self.completed) / rate if rate > 0 else 0
        if self.tqdm is not None:
            self.tqdm.set_postfix(bars=self.total_bars, err=self.errors, eta=f"{remaining:.0f}s")
            self.tqdm.set_description(f"Ingesting {sym}")
            self.tqdm.update(1)
        else:
            if self.completed % 10 == 0 or self.completed == self.total:
                line = (f"[{self.completed}/{self.total}] sym={sym} bars={self.total_bars} "
                        f"err={self.errors} eta={remaining:.0f}s elapsed={elapsed:.0f}s")
                print(line)
                self.logger.info(line)

    def on_error(self, sym: str) -> None:
        self.errors += 1
        self.logger.error(f"Error on {sym} (total errors: {self.errors})")

    def close(self) -> None:
        elapsed = time.time() - self.start_ts
        line = (f"✅ Ingestion done: {self.completed}/{self.total} symbols, "
                f"{self.total_bars} total bars, {self.errors} errors, {elapsed:.0f}s elapsed")
        print(line)
        self.logger.info(line)
        if self.tqdm is not None:
            self.tqdm.close()

def _get_failed_path(cfg) -> str:
    return os.path.join(get_storage_path(cfg, "checkpoints_dir"), "failed_symbols_recovery.txt")

def _load_failed_symbols(cfg) -> list[dict]:
    """Load failed symbols with reason+timestamp. Returns list of {symbol, reason, ts}."""
    fp = _get_failed_path(cfg)
    records = []
    if os.path.exists(fp):
        with open(fp, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("|")
                rec = {"symbol": parts[0].strip()}
                if len(parts) > 1:
                    rec["reason"] = parts[1].strip()
                else:
                    rec["reason"] = "Unknown"
                if len(parts) > 2:
                    rec["ts"] = parts[2].strip()
                else:
                    rec["ts"] = ""
                records.append(rec)
    return records

def _save_failed_symbols(records: list[dict], cfg) -> None:
    """Save list of {symbol, reason, ts} to failed_symbols_recovery.txt."""
    fp = _get_failed_path(cfg)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "w") as f:
        for rec in sorted(records, key=lambda r: r["symbol"]):
            f.write(f"{rec['symbol']} | {rec['reason']} | {rec['ts']}\n")

def _classify_error(e: Exception) -> str:
    msg = str(e).lower()
    if "rate" in msg and ("limit" in msg or "429" in msg):
        return "RateLimit"
    if "timeout" in msg or "timed out" in msg:
        return "Timeout"
    if "no data" in msg or "empty" in msg:
        return "NoData"
    if "api" in msg or "http" in msg or "connection" in msg:
        return "APIError"
    return "APIError"

def _print_error_recovery_dashboard(records: list[dict], logger) -> None:
    """Print and log formatted Error Recovery Dashboard."""
    if not records:
        return
    from collections import Counter
    total = len(records)
    reasons = Counter(r["reason"] for r in records if r.get("reason"))
    sep = "=" * 60
    dash = "-" * 60
    lines = [
        sep,
        "  KRONOS V1-ALT — Error Recovery Dashboard",
        sep,
        f"  Total failed symbols  : {total}",
        dash,
        "  Error Type Breakdown:",
    ]
    for err_type, count in reasons.most_common():
        pct = 100.0 * count / total
        lines.append(f"    {err_type:15s} : {count:4d} ({pct:5.1f}%)")
    lines.append(dash)
    lines.append("  Sample (up to 5):")
    for r in records[:5]:
        lines.append(f"    {r['symbol']:20s} | {r.get('reason',''):12s} | {r.get('ts',''):s}")
    lines.append(dash)
    lines.append(sep)
    for l in lines:
        print(l)
        if hasattr(logger, 'info'):
            logger.info(l)

def _safe_name(symbol: str) -> str:
    return symbol.replace('/', '_').replace(':', '_').replace('-', '_')

def _detect_delisted(cfg, active_symbols: set, logger) -> int:
    """Archive raw_shards + signatures for symbols no longer in active list. Returns count archived."""
    import glob, shutil
    raw_dir = get_storage_path(cfg, "raw_shards_dir")
    sig_dir = get_storage_path(cfg, "signatures_individual_dir")
    archive_dir = get_storage_path(cfg, "archive_dir")
    os.makedirs(archive_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    active_safe = {_safe_name(s) for s in active_symbols}
    tf = cfg["project"]["timeframe"]
    suffix_replace = f"_{tf}.parquet"
    for sp in glob.glob(os.path.join(raw_dir, "*.parquet")):
        base = os.path.basename(sp).replace(suffix_replace, "").replace(".parquet", "")
        if base not in active_safe:
            dest = os.path.join(archive_dir, f"{base}_{ts}.parquet")
            shutil.move(sp, dest)
            for sig in glob.glob(os.path.join(sig_dir, f"{base}_*")):
                sig_dest = os.path.join(archive_dir, f"{os.path.basename(sig).replace('.parquet','')}_{ts}.parquet")
                shutil.move(sig, sig_dest)
            archived += 1
            logger.info(f"📦 Archived delisted: {base} → {dest}")
    return archived

def _fetch_one(sym: str, ex, logger, cfg) -> tuple[str, int]:
    """Wrapper for ThreadPoolExecutor: returns (symbol, bar_count)."""
    df = fetch_full_history(sym, ex, logger, cfg)
    return (sym, len(df) if df is not None else 0)

def fetch_all_symbols_data(symbols_override: list | None = None) -> None:
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
    all_symbols = symbols_override if symbols_override is not None else discover_symbols(exchange_client, cfg, logger)
    # New listings & delistings sync
    sym_cfg = cfg["symbols"]
    if sym_cfg.get("refresh_discovery", True):
        active_set = set(all_symbols)
        # Compare with on-disk shards to detect new listings
        raw_dir = get_storage_path(cfg, "raw_shards_dir")
        on_disk = set()
        tf_sh = proj_cfg["timeframe"]
        suffix_replace = f"_{tf_sh}.parquet"
        for sp in glob.glob(os.path.join(raw_dir, "*.parquet")):
            base = os.path.basename(sp).replace(suffix_replace, "").replace(".parquet", "")
            # Reverse safe_name: normalise for comparison — both are in safe_name format
            on_disk.add(base)
        # Derive on-disk in real format (split safe_name back)
        tf = proj_cfg["timeframe"]
        on_disk_reals = set()
        for d in on_disk:
            parts = d.rsplit(f"_{tf}", 1)
            on_disk_reals.add(parts[0].replace("_", "/") if "_" in parts[0] else parts[0])
        new_listings = [s for s in all_symbols if _safe_name(s) not in on_disk]
        if new_listings:
            logger.info(f"🆕 New listings detected: {len(new_listings)} symbols — {new_listings[:3]}...")
        # Delisted: in on_disk but not in active API list
        delisted_count = _detect_delisted(cfg, set(all_symbols), logger)
        if delisted_count:
            logger.info(f"🗑️ Delisted & cleaned: {delisted_count} symbols.")
    # Load previously failed symbols (with reasons), intersect with current symbol set
    failed_recs = _load_failed_symbols(cfg)
    failed_syms = {r["symbol"] for r in failed_recs} & set(all_symbols)
    if failed_syms:
        logger.info(f"Retrying {len(failed_syms)} previously failed symbols: {sorted(failed_syms)[:5]}...")
        _print_error_recovery_dashboard([r for r in failed_recs if r["symbol"] in failed_syms], logger)
    symbols = sorted(failed_syms | set(all_symbols)) if failed_syms else all_symbols
    # Remove already-recent from retry set — fetch_full_history handles incremental skip internally
    total = len(symbols)
    tracker = IngestionTracker(total, logger)
    max_workers = int(fetch_cfg.get("max_workers", 4))
    logger.info(f"Synchronizing history across {total} tracked targets with {max_workers} workers...")
    from concurrent.futures import ThreadPoolExecutor, as_completed
    new_failed_recs = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {pool.submit(_fetch_one, sym, exchange_client, logger, cfg): sym for sym in symbols}
        for fut in as_completed(futs):
            sym = futs[fut]
            try:
                _, bars = fut.result()
                tracker.on_symbol_done(bars, sym)
            except Exception as e:
                tracker.on_error(sym)
                reason = _classify_error(e)
                new_failed_recs.append({"symbol": sym, "reason": reason, "ts": datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')})
                logger.error(f"Failed {sym}: [{reason}] {e}")
    _save_failed_symbols(new_failed_recs, cfg)
    if new_failed_recs:
        logger.warning(f"❌ {len(new_failed_recs)} symbols failed. Saved to failed_symbols_recovery.txt for retry.")
        _print_error_recovery_dashboard(new_failed_recs, logger)
    tracker.close()
    generate_metrics_summary(cfg, tracker)
    # Ablation injection point for global_prior_mode (controlled via params)

def generate_metrics_summary(cfg, tracker) -> None:
    """Scan raw_shards and print/save formatted metrics dashboard."""
    import glob
    raw_dir = get_storage_path(cfg, "raw_shards_dir")
    shards = sorted(glob.glob(os.path.join(raw_dir, "*.parquet")))
    total_shards = len(shards)
    total_bytes = sum(os.path.getsize(f) for f in shards)
    total_bars = 0
    missing_quote_vol = 0
    missing_taker = 0
    bar_counts = []
    tf = cfg["project"]["timeframe"]
    suffix_replace = f"_{tf}.parquet"
    for sp in shards:
        sym = os.path.basename(sp).replace(suffix_replace, "").replace(".parquet", "")
        df = pd.read_parquet(sp)
        n = len(df)
        total_bars += n
        bar_counts.append(n)
        if "quote_volume" not in df.columns:
            missing_quote_vol += 1
        if "taker_buy_base_volume" not in df.columns:
            missing_taker += 1
    avg_bars = total_bars / max(total_shards, 1)
    avg_size_mb = (total_bytes / max(total_shards, 1)) / (1024 * 1024)
    total_mb = total_bytes / (1024 * 1024)
    sep = "=" * 60
    dash = "-" * 60
    lines = [
        sep,
        "  KRONOS V1-ALT — Ingestion Metrics Dashboard",
        sep,
        f"  Timeframe          : {cfg['project']['timeframe']}",
        f"  Exchange           : {cfg['data_fetch']['exchange']}",
        f"  Target symbols     : {cfg['symbols']['target_count']}",
        f"  Workers            : {cfg['data_fetch'].get('max_workers', 4)}",
        dash,
        f"  Symbols discovered : {tracker.total if hasattr(tracker, 'total') else len(shards)}",
        f"  Symbols completed  : {tracker.completed if hasattr(tracker, 'completed') else total_shards}",
        f"  Symbols failed     : {tracker.errors if hasattr(tracker, 'errors') else 0}",
        f"  Shards on disk     : {total_shards}",
        dash,
        f"  Total bars         : {total_bars:,}",
        f"  Avg bars/symbol    : {avg_bars:,.0f}",
        f"  Min bars/symbol    : {min(bar_counts) if bar_counts else 0:,}",
        f"  Max bars/symbol    : {max(bar_counts) if bar_counts else 0:,}",
        dash,
        f"  Total size         : {total_mb:.2f} MB",
        f"  Avg size/symbol    : {avg_size_mb:.2f} MB",
        dash,
        f"  Missing quote_volume         : {missing_quote_vol}",
        f"  Missing taker_buy_base_volume: {missing_taker}",
        dash,
        f"  Elapsed            : {time.time() - tracker.start_ts:.0f}s",
        f"  Completed at       : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        sep,
    ]
    # Filter empty lines from conditional
    lines = [l for l in lines if l]
    for l in lines:
        print(l)
        tracker.logger.info(l)
    metrics_path = os.path.join(get_storage_path(cfg, "logs_dir"), "metrics_summary.txt")
    with open(metrics_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    tracker.logger.info(f"Metrics saved to {metrics_path}")
    generate_html_summary(cfg, tracker)

def generate_html_summary(cfg, tracker) -> None:
    """Generate HTML ingestion dashboard with health scores table, top/bottom symbols."""
    import glob, base64
    raw_dir = get_storage_path(cfg, "raw_shards_dir")
    shards = sorted(glob.glob(os.path.join(raw_dir, "*.parquet")))
    total_shards = len(shards)
    total_bytes = sum(os.path.getsize(f) for f in shards)
    total_bars = 0
    missing_qv = 0
    missing_taker = 0
    bar_counts = []
    health_rows = []
    tf = cfg["project"]["timeframe"]
    suffix_replace = f"_{tf}.parquet"
    timeframe_ms = parse_timeframe_to_ms(tf, cfg["time_constants"])
    for sp in shards:
        sym = os.path.basename(sp).replace(suffix_replace, "").replace(".parquet", "")
        df = pd.read_parquet(sp)
        n = len(df)
        total_bars += n
        bar_counts.append(n)
        if "quote_volume" not in df.columns: missing_qv += 1
        if "taker_buy_base_volume" not in df.columns: missing_taker += 1
        # Health compute (inline simplified)
        present = [c for c in CRITICAL_COLS if c in df.columns]
        completeness = 100.0 * (1.0 - df[present].isna().any(axis=1).mean()) if present else 100.0
        gap_count = int((df['timestamp'].diff().dropna() != timeframe_ms).sum()) if len(df) > 1 else 0
        nan_pct = 100.0 * int(df[present].isna().any(axis=1).sum()) / max(n, 1) if present else 0.0
        outlier_count = sum(_detect_outliers(df[c]) for c in ["close","volume"] if c in df.columns and df[c].dtype.kind in "fc")
        outlier_pct = 100.0 * outlier_count / max(n, 1)
        gap_score = max(0, 100 - gap_count * 2)
        outlier_score = max(0, 100 - outlier_pct * 2)
        nan_score = max(0, 100 - nan_pct * 2)
        health = int(round(0.40 * completeness + 0.20 * gap_score + 0.20 * outlier_score + 0.20 * nan_score))
        health = max(0, min(100, health))
        color = "#4CAF50" if health >= 90 else "#FF9800" if health >= 70 else "#F44336"
        health_rows.append((sym, n, health, color, gap_count, nan_pct, outlier_pct))
    health_rows.sort(key=lambda r: r[2], reverse=True)
    top10 = health_rows[:10]
    bottom10 = health_rows[-10:] if len(health_rows) >= 10 else health_rows
    bottom10.reverse()
    avg_bars = total_bars / max(total_shards, 1)
    total_mb = total_bytes / (1048576)
    now_ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    tf = cfg['project']['timeframe']
    exchange = cfg['data_fetch']['exchange']
    target = cfg['symbols']['target_count']
    workers = cfg['data_fetch'].get('max_workers', 4)
    completed = tracker.completed if hasattr(tracker, 'completed') else total_shards
    failed = tracker.errors if hasattr(tracker, 'errors') else 0
    def _tr(s, n, h, c, g, np, op):
        return f"<tr><td>{s}</td><td>{n:,}</td><td style='color:{c}'><b>{h}</b></td><td>{g}</td><td>{np:.1f}%</td><td>{op:.1f}%</td></tr>"
    top_rows = "\n".join(_tr(s,n,h,c,g,np,op) for s,n,h,c,g,np,op in top10)
    bot_rows = "\n".join(_tr(s,n,h,c,g,np,op) for s,n,h,c,g,np,op in bottom10)
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>KRONOS V1-ALT — Ingestion Summary</title>
<style>
body{{font-family:system-ui,-apple-system,sans-serif;margin:20px;background:#f5f7fa;color:#333}}
h1{{color:#1a237e;border-bottom:3px solid #1a237e;padding-bottom:8px}}
h2{{color:#283593}}
.dashboard{{max-width:1100px;margin:0 auto}}
.card{{background:#fff;border-radius:8px;padding:16px;margin:16px 0;box-shadow:0 1px 4px rgba(0,0,0,.1)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px}}
.metric{{text-align:center;padding:12px;background:#e8eaf6;border-radius:6px}}
.metric .val{{font-size:1.6em;font-weight:700;color:#1a237e}}
.metric .lbl{{font-size:.8em;color:#5c6bc0}}
table{{width:100%;border-collapse:collapse;font-size:.9em}}
th{{background:#1a237e;color:#fff;padding:8px 6px;text-align:left}}
td{{padding:6px;border-bottom:1px solid #e0e0e0}}
tr:hover{{background:#f5f5f5}}
.green{{color:#4CAF50;font-weight:700}}
.orange{{color:#FF9800;font-weight:700}}
.red{{color:#F44336;font-weight:700}}
</style></head><body><div class="dashboard">
<h1>📊 KRONOS V1-ALT — Ingestion Summary</h1>
<div class="card"><div class="grid">
<div class="metric"><div class="val">{total_shards}</div><div class="lbl">Shards</div></div>
<div class="metric"><div class="val">{total_bars:,}</div><div class="lbl">Total Bars</div></div>
<div class="metric"><div class="val">{avg_bars:,.0f}</div><div class="lbl">Avg Bars/Sym</div></div>
<div class="metric"><div class="val">{total_mb:.1f}</div><div class="lbl">Total MB</div></div>
<div class="metric"><div class="val">{completed}</div><div class="lbl">Completed</div></div>
<div class="metric"><div class="val">{failed}</div><div class="lbl">Failed</div></div>
<div class="metric"><div class="val">{missing_qv}</div><div class="lbl">Missing qVol</div></div>
<div class="metric"><div class="val">{missing_taker}</div><div class="lbl">Missing Taker</div></div>
</div></div>
<div class="card"><h2>🏆 Top 10 Healthiest Symbols</h2><table><tr><th>Symbol</th><th>Bars</th><th>Health</th><th>Gaps</th><th>NaN%</th><th>Outlier%</th></tr>{top_rows}</table></div>
<div class="card"><h2>⚠️ Bottom 10 Symbols (lowest health)</h2><table><tr><th>Symbol</th><th>Bars</th><th>Health</th><th>Gaps</th><th>NaN%</th><th>Outlier%</th></tr>{bot_rows}</table></div>
<div class="card" style="text-align:center;color:#666;font-size:.85em">
<p>{exchange} | {tf} | target={target} | workers={workers} | {now_ts}</p>
</div></div></body></html>"""
    html_path = os.path.join(get_storage_path(cfg, "logs_dir"), "ingestion_summary.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"📊 HTML Dashboard saved: {html_path}")
    tracker.logger.info(f"HTML Dashboard saved to {html_path}")

def clean_ingest(target_count: int | None = None) -> None:
    """Delete old raw_shards/*.parquet and re-fetch full history for target_count symbols."""
    cfg = get_sovereign_config()
    logger, _ = setup_sovereign_logger(cfg)
    raw_dir = get_storage_path(cfg, "raw_shards_dir")
    import glob, shutil
    for f in glob.glob(os.path.join(raw_dir, "*.parquet")):
        os.remove(f)
        logger.info(f"Removed old shard: {os.path.basename(f)}")
    logger.info("Clean sweep complete. Starting full re-ingestion.")
    fetch_cfg = cfg["data_fetch"]
    if target_count is not None:
        cfg["symbols"]["target_count"] = target_count
    fetch_all_symbols_data()
    logger.info(f"Full ingestion done for {cfg['symbols']['target_count']} symbols.")

def inspect_missing_fields() -> dict:
    """Scan all raw shards and report which ones lack taker_buy_base_volume / quote_volume."""
    cfg = get_sovereign_config()
    logger, _ = setup_sovereign_logger(cfg)
    raw_dir = get_storage_path(cfg, "raw_shards_dir")
    import glob
    shards = sorted(glob.glob(os.path.join(raw_dir, "*.parquet")))
    report = {"total_shards": len(shards), "missing_quote_volume": [], "missing_taker_buy_base_volume": [], "missing_both": []}
    tf = cfg["project"]["timeframe"]
    suffix_replace = f"_{tf}.parquet"
    for sp in shards:
        sym = os.path.basename(sp).replace(suffix_replace, "").replace(".parquet", "")
        df = pd.read_parquet(sp)
        missing_qv = "quote_volume" not in df.columns
        missing_tbv = "taker_buy_base_volume" not in df.columns
        if missing_qv:
            report["missing_quote_volume"].append(sym)
        if missing_tbv:
            report["missing_taker_buy_base_volume"].append(sym)
        if missing_qv and missing_tbv:
            report["missing_both"].append(sym)
    report_path = os.path.join(get_storage_path(cfg, "logs_dir"), "missing_fields_summary.txt")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write(f"Missing Fields Inspection Report — {datetime.now(timezone.utc).isoformat()}\n")
        f.write(f"Total shards: {report['total_shards']}\n")
        f.write(f"Symbols missing quote_volume: {len(report['missing_quote_volume'])}\n")
        f.write(f"Symbols missing taker_buy_base_volume: {len(report['missing_taker_buy_base_volume'])}\n")
        f.write(f"Both missing: {len(report['missing_both'])}\n\n")
        if report["missing_quote_volume"]:
            f.write("Missing quote_volume:\n" + "\n".join(report["missing_quote_volume"]) + "\n\n")
        if report["missing_taker_buy_base_volume"]:
            f.write("Missing taker_buy_base_volume:\n" + "\n".join(report["missing_taker_buy_base_volume"]) + "\n\n")
    logger.info(f"Inspection report saved to {report_path}")
    print(f"\nReport: {len(report['missing_quote_volume'])} symbols missing quote_volume, "
          f"{len(report['missing_taker_buy_base_volume'])} missing taker_buy_base_volume, "
          f"{len(report['missing_both'])} missing both.")
    return report

def _compute_health_summary(cfg, logger) -> dict:
    """Scan shards, compute health scores, return summary stats."""
    import glob
    raw_dir = get_storage_path(cfg, "raw_shards_dir")
    shards = sorted(glob.glob(os.path.join(raw_dir, "*.parquet")))
    scores = []
    tf = cfg["project"]["timeframe"]
    suffix_replace = f"_{tf}.parquet"
    timeframe_ms = parse_timeframe_to_ms(tf, cfg["time_constants"])
    for sp in shards:
        sym = os.path.basename(sp).replace(suffix_replace, "").replace(".parquet", "")
        df = pd.read_parquet(sp)
        n = len(df)
        present = [c for c in CRITICAL_COLS if c in df.columns]
        completeness = 100.0 * (1.0 - df[present].isna().any(axis=1).mean()) if present else 100.0
        gap_count = int((df['timestamp'].diff().dropna() != timeframe_ms).sum()) if len(df) > 1 else 0
        nan_pct = 100.0 * int(df[present].isna().any(axis=1).sum()) / max(n, 1) if present else 0.0
        outlier_count = sum(_detect_outliers(df[c]) for c in ["close","volume"] if c in df.columns and df[c].dtype.kind in "fc")
        outlier_pct = 100.0 * outlier_count / max(n, 1)
        gap_score = max(0, 100 - gap_count * 2)
        outlier_score = max(0, 100 - outlier_pct * 2)
        nan_score = max(0, 100 - nan_pct * 2)
        health = int(round(0.40 * completeness + 0.20 * gap_score + 0.20 * outlier_score + 0.20 * nan_score))
        health = max(0, min(100, health))
        scores.append((sym, health, n, gap_count, nan_pct, outlier_pct))
    scores.sort(key=lambda r: r[1], reverse=True)
    avg_health = round(sum(s[1] for s in scores) / max(len(scores), 1), 1)
    return {"avg_health": avg_health, "total": len(scores), "all": scores}

def _print_health_summary(summary: dict, logger, new_count: int = 0, delisted_count: int = 0) -> None:
    """Print formatted health summary to console + log."""
    sep = "=" * 60
    dash = "-" * 60
    lines = [sep, "  KRONOS V1-ALT — Final Health Score Summary", sep]
    lines.append(f"  Total symbols        : {summary['total']}")
    lines.append(f"  Average health score : {summary['avg_health']}/100")
    if new_count or delisted_count:
        lines.append(f"  New listings         : {new_count}")
        lines.append(f"  Delisted & archived  : {delisted_count}")
    lines.append(dash)
    lines.append("  🏆 Top 10 Healthiest:")
    for r in summary['all'][:10]:
        tag = "🟢" if r[1] >= 90 else "🟡" if r[1] >= 70 else "🔴"
        lines.append(f"    {tag} {r[0]:20s} health={r[1]:3d} bars={r[2]:>6,} gaps={r[3]} nan={r[4]:.1f}% out={r[5]:.1f}%")
    lines.append(dash)
    lines.append("  ⚠️  Worst 10:")
    for r in summary['all'][-10:]:
        tag = "🟢" if r[1] >= 90 else "🟡" if r[1] >= 70 else "🔴"
        lines.append(f"    {tag} {r[0]:20s} health={r[1]:3d} bars={r[2]:>6,} gaps={r[3]} nan={r[4]:.1f}% out={r[5]:.1f}%")
    lines.append(sep)
    for l in lines:
        print(l)
        logger.info(l)

BANNER_TOP = "=" * 60
BANNER_BOT = "=" * 60

def full_run(clean_first: bool = False, run_miner: bool = False, target_count: int | None = None, dummy: bool = False) -> None:
    """Full ingestion pipeline: optional clean → ingest → health summary → optional mine."""
    cfg = get_sovereign_config()
    logger, _ = setup_sovereign_logger(cfg)
    if target_count is not None:
        cfg["symbols"]["target_count"] = target_count
    if dummy:
        cfg["symbols"]["target_count"] = 20
    target = cfg["symbols"]["target_count"]
    mode_tag = " (DUMMY MODE — 20 symbols)" if dummy else ""
    print(f"\n{BANNER_TOP}")
    print(f"  🚀 KRONOS V1-ALT Full Ingestion Run{mode_tag}")
    print(f"  Target: {target} symbols  |  Clean: {clean_first}  |  Mine: {run_miner}")
    print(f"{BANNER_TOP}\n")
    logger.info(f"KRONOS V1-ALT Full Ingestion Run — target={target} clean={clean_first} mine={run_miner}")
    if clean_first:
        raw_dir = get_storage_path(cfg, "raw_shards_dir")
        import glob
        for f in glob.glob(os.path.join(raw_dir, "*.parquet")):
            os.remove(f)
            logger.info(f"Removed old shard: {os.path.basename(f)}")
        logger.info("Clean sweep complete. Starting full re-ingestion.")
    fetch_all_symbols_data()
    summary = _compute_health_summary(cfg, logger)
    new_count = 0
    delisted_count = 0
    _print_health_summary(summary, logger, new_count, delisted_count)
    print(f"\n{BANNER_TOP}")
    print(f"  ✅ Full ingestion completed. Average health score: {summary['avg_health']}/100")
    print(f"{BANNER_BOT}\n")
    logger.info(f"Full ingestion completed. Average health score: {summary['avg_health']}/100")
    if run_miner:
        from config.mining.reversal_signature_miner_sovereign import mine_all_shards
        print(f"\n{BANNER_TOP}")
        print(f"  ⛏️  Running reversal miner on all shards...")
        print(f"{BANNER_BOT}\n")
        logger.info("Running reversal miner on all shards...")
        mine_all_shards()
        print(f"\n{BANNER_TOP}")
        print(f"  ✅ Full ingestion + mining completed successfully")
        print(f"{BANNER_BOT}\n")
        logger.info("Full ingestion + mining completed successfully")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true", help="Delete old raw_shards before fetching")
    parser.add_argument("--target", type=int, default=None, help="Override target_count (default from params)")
    parser.add_argument("--inspect", action="store_true", help="Run field inspection on existing shards")
    parser.add_argument("--mine", action="store_true", help="Run reversal miner after ingestion")
    parser.add_argument("--dummy", action="store_true", help="Limit to 20 symbols for testing")
    args = parser.parse_args()
    if args.inspect:
        inspect_missing_fields()
    elif args.clean:
        full_run(clean_first=True, run_miner=args.mine, target_count=args.target, dummy=args.dummy)
    elif args.mine:
        full_run(clean_first=False, run_miner=True, target_count=args.target, dummy=args.dummy)
    else:
        full_run(clean_first=False, run_miner=False, target_count=args.target, dummy=args.dummy)
