# Diff Summary — New Listings & Delistings Sync

## Files Changed

### 1. `params_yaml.txt`
**Added** 1 line under `symbols:`
```yaml
  refresh_discovery: true
```

### 2. `config/unified_ingestion_engine.py`

**Added `_safe_name(symbol: str) -> str` helper** — normalises `BTC/USDT` → `BTC_USDT` for file/path comparison.

**Added `_detect_delisted(cfg, active_symbols: set, logger) -> int`** — scans `raw_shards/*.parquet`, deletes any whose safe_name is not in the active set. Also cleans matching `signatures/individual/{base}_*` files. Returns count removed.

**Modified `fetch_all_symbols_data()`** — added new listings & delistings block after `discover_symbols`:

```python
sym_cfg = cfg["symbols"]
if sym_cfg.get("refresh_discovery", True):
    # Compare API result vs on-disk shards
    on_disk = {basename stripped of _1h.parquet}
    new_listings = [s for s in all_symbols if _safe_name(s) not in on_disk]
    if new_listings:
        logger.info(f"🆕 New listings detected: {len(new_listings)} symbols — ...")
    delisted_count = _detect_delisted(cfg, set(all_symbols), logger)
    if delisted_count:
        logger.info(f"🗑️ Delisted & cleaned: {delisted_count} symbols.")
```

**Behaviour:**
- Every run fetches current USDT perpetuals from Binance API
- New symbols (not on disk) are identified and ingested as part of the normal loop
- Delisted symbols (on disk but not in API response) have their raw_shards + signatures deleted
- All existing checkpointing, incremental skip, rate limiting, parallel fetch — preserved

**Log output examples:**
```
🆕 New listings detected: 5 symbols — ['SUI/USDT', 'TAO/USDT', 'WIF/USDT']...
🗑️ Delisted: removed LUNA_USDT
🗑️ Delisted & cleaned: 2 symbols.
```

## Zero Changes To

- `reversal_signature_miner_sovereign.py` — untouched
- `clean_ingest`, `inspect_missing_fields`, `bridge_mine_after_ingest` — untouched
- Dual-mode, Option B E2E, sovereign_ctx wiring — preserved