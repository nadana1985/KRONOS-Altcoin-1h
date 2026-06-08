# Diff Summary — Resume from Partial Failure

## File Changed

### `config/unified_ingestion_engine.py`

**Added 3 helper functions:**

```python
def _get_failed_path(cfg) -> str:
    """Returns path: <checkpoints_dir>/failed_symbols.txt"""

def _load_failed_symbols(cfg) -> set:
    """Reads failed_symbols.txt, returns set of symbol strings."""

def _save_failed_symbols(symbols: set, cfg) -> None:
    """Writes sorted failed symbols to failed_symbols.txt."""
```

**Modified `fetch_all_symbols_data()`** — added `symbols_override` parameter + failed-symbol resume logic:

```python
def fetch_all_symbols_data(symbols_override: list | None = None) -> None:
```

**Logic added after symbol discovery:**
1. Load previously failed symbols from `failed_symbols.txt` (in checkpoints dir)
2. Intersect with current symbol set (in case symbol universe changed)
3. Union failed set with discovered set → `symbols = sorted(failed_set | set(all_symbols))`
4. On exception: add symbol to `new_failed` set (instead of just logging)
5. After loop: `_save_failed_symbols(new_failed, cfg)` overwrites file with current failures only

**On next run:**
- `_load_failed_symbols()` reads back the file
- Only previously failed + new API-discovered symbols are processed
- Successfully fetched symbols are not retried (removed from file on next write)
- `fetch_full_history` incremental skip handles already-recent shards for free

**Log output:**
```
INFO     Retrying 3 previously failed symbols: ['BTC/USDT', 'ETH/USDT', 'XRP/USDT']...
...
WARNING  ❌ 1 symbols failed. Saved to failed_symbols.txt for retry.
```

## Zero Changes To

- `params_yaml.txt` — untouched
- Checkpointing, incremental skip, end_date — untouched
- `_rate_limited_call`, `_fetch_one`, `IngestionTracker` — untouched
- `reversal_signature_miner_sovereign.py` — untouched
- Dual-mode, Option B E2E, sovereign_ctx wiring — preserved