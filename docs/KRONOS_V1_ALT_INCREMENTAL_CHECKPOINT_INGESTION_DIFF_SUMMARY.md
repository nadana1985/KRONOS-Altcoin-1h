# Diff Summary — Incremental Checkpoint Ingestion

## Files Changed

### 1. `params_yaml.txt`
**Added** `end_date_offset_days: 1` under `data_fetch`:
```yaml
data_fetch:
  ...
  end_date_offset_days: 1     # Fetch up to yesterday (1 = exclude today)
```

### 2. `config/unified_ingestion_engine.py`
**Added 3 helper functions:**

```python
def get_checkpoint_dir(cfg) -> str           # Returns checkpoints_dir (from params), creates if missing
def load_checkpoint(safe_name, cp_dir, logger) -> int | None   # Reads last_ts_{symbol}.txt, returns timestamp or None
def save_checkpoint(safe_name, last_ts, cp_dir) -> None         # Writes last_ts_{symbol}.txt
```

**Modified `fetch_full_history(symbol, ex, logger, cfg)`:**

1. **End date cap** — computes `end_ms = now - (end_offset_days * 1d)` from `params["data_fetch"]["end_date_offset_days"]`. Passes `endTime` in every kline API call. Loop breaks when `since >= end_ms`.

2. **Per-symbol checkpointing** — loads `last_ts_{safe_name}.txt` from checkpoints dir. If checkpoint exists, uses it as `since` instead of reading shard max. Saves checkpoint after successful fetch.

3. **Incremental skip** — if shard exists and `shard_last >= end_ms - 1day`, logs `⏭️ {symbol}: shard already recent` and returns `None` without fetching. Also syncs checkpoint if stale.

4. **12-field kline + amount alias** — uses `kline_fields` from params. `quote_volume` is aliased to `amount` column.

**`fetch_all_symbols_data()`** unchanged — still iterates via `discover_symbols` which reads `params["symbols"]["target_count"]` (530).

## Zero Changes To

- `config/reversal_signature_miner_sovereign.py` — untouched
- Dual-mode, Option B E2E, sovereign_ctx wiring — preserved
- All existing argparse flags (`--clean`, `--mine`, `--inspect`, `--target`) — unchanged

## Usage

```powershell
$env:KRONOS_PARAMS_PATH="F:\kronos_v1_alt\params_yaml.txt"
python config/unified_ingestion_engine.py             # Full run (end_date capped, checkpointed)
python config/unified_ingestion_engine.py              # Second run (incremental skip for recent shards)
python config/unified_ingestion_engine.py --clean      # Delete shards + re-fetch with checkpointing
python config/unified_ingestion_engine.py --inspect    # Inspect only