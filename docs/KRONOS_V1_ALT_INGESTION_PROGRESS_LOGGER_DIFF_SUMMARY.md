# Diff Summary — Rich Progress Logger for Ingestion

## File Changed

### `config/unified_ingestion_engine.py`

**Added class `IngestionTracker`** before `fetch_all_symbols_data`:

```python
class IngestionTracker:
    def __init__(self, total: int, logger):
        - total, logger, completed=0, total_bars=0, errors=0, start_ts=now
        - tries `from tqdm import tqdm` → if available uses tqdm progress bar
        - falls back to formatted print every 10 symbols

    def on_start_symbol(self, sym: str) -> None    # sets self.current
    def on_symbol_done(self, bars: int, sym: str) -> None
        - increments completed, total_bars
        - computes elapsed, rate, remaining ETA
        - tqdm mode: set_postfix(bars, err, eta) + update(1)
        - fallback mode: print every 10th or last symbol:
          `[{completed}/{total}] sym={sym} bars={total_bars} err={errors} eta={remaining:.0f}s elapsed={elapsed:.0f}s`

    def on_error(self, sym: str) -> None
        - increments errors counter, logs error

    def close(self) -> None
        - prints + logs final summary line:
          `✅ Ingestion done: {completed}/{total} symbols, {total_bars} total bars, {errors} errors, {elapsed:.0f}s elapsed`
        - closes tqdm if active
```

**Modified `fetch_all_symbols_data()` loop:**

```python
# Before: bare for-loop
for sym in symbols:
    fetch_full_history(sym, exchange_client, logger, cfg)

# After: wrapped with IngestionTracker
tracker = IngestionTracker(total, logger)
for sym in symbols:
    tracker.on_start_symbol(sym)
    try:
        df = fetch_full_history(sym, exchange_client, logger, cfg)
        tracker.on_symbol_done(len(df) if df is not None else 0, sym)
    except Exception as e:
        tracker.on_error(sym)
        logger.error(f"Failed {sym}: {e}")
tracker.close()
```

**Live display (tqdm):**
```
Ingesting BTC/USDT: 100%|████████████| 530/530 [42:15<00:00, bars=1234567 err=0 eta=0s]
```

**Live display (fallback, every 10):**
```
[10/530] sym=ETH/USDT bars=123456 err=0 eta=3780s elapsed=420s
[20/530] sym=XRP/USDT bars=246912 err=1 eta=3402s elapsed=840s
...
```

## Zero Changes To

- Checkpointing, incremental skip, end_date logic — untouched
- `fetch_full_history`, `clean_ingest`, `inspect_missing_fields`, `bridge_mine_after_ingest` — untouched
- `params_yaml.txt` — untouched
- `reversal_signature_miner_sovereign.py` — untouched
- Dual-mode, Option B E2E, sovereign_ctx wiring — preserved