# Diff Summary — Parallel Ingestion with ThreadPoolExecutor

## Files Changed

### 1. `params_yaml.txt`
**Added** 1 line under `data_fetch`:
```yaml
  max_workers: 4            # Parallel ingestion threads
```

### 2. `config/unified_ingestion_engine.py`

**Added helper `_fetch_one(sym, ex, logger, cfg) -> tuple[str, int]`** — wraps `fetch_full_history`, returns `(symbol, bar_count)` for thread-safe result collection.

**Modified `fetch_all_symbols_data()`** — serial `for sym in symbols:` loop replaced with `ThreadPoolExecutor`:

```python
max_workers = int(fetch_cfg.get("max_workers", 4))          # from params
from concurrent.futures import ThreadPoolExecutor, as_completed
with ThreadPoolExecutor(max_workers=max_workers) as pool:
    futs = {pool.submit(_fetch_one, sym, exchange_client, logger, cfg): sym for sym in symbols}
    for fut in as_completed(futs):
        sym = futs[fut]
        try:
            _, bars = fut.result()
            tracker.on_symbol_done(bars, sym)
        except Exception as e:
            tracker.on_error(sym)
            logger.error(f"Failed {sym}: {e}")
```

- `ThreadPoolExecutor` with `max_workers` from params (default 4)
- `_fetch_one` preserves per-thread `fetch_full_history` call chain (checkpointing, incremental skip, rate limiting all intact)
- `as_completed` feeds `IngestionTracker` as each symbol finishes (thread-safe since tracker only touched in main thread via `fut.result()`)
- Exceptions caught per-future, routed to `tracker.on_error`
- `pool` context manager ensures clean shutdown on completion or exception

## Thread Safety

- `exchange_client` (ccxt) is the only shared mutable resource — ccxt exchanges are thread-safe for separate requests (each request is a new HTTP call)
- `_request_counter` in `_rate_limited_call` uses atomic increment (Python int, GIL-protected)
- `IngestionTracker` updated only from main thread in `as_completed` loop — no locks needed
- Parquet writes per-symbol go to separate files — no file conflicts

## Zero Changes To

- `fetch_full_history` — untouched (checkpointing, incremental skip, end_date, rate limiting, 12-field klines)
- `_rate_limited_call` — untouched
- `IngestionTracker`, `clean_ingest`, `inspect_missing_fields`, `bridge_mine_after_ingest` — untouched
- `reversal_signature_miner_sovereign.py` — untouched
- Dual-mode, Option B E2E, sovereign_ctx wiring — preserved