# Diff Summary — Archive Instead of Delete for Delisted Symbols

## Files Changed

### 1. `params_yaml.txt`
**Added** 1 line under `storage`:
```yaml
  archive_dir: !join [*base_path, "/data/archive/delisted"]
```

### 2. `config/unified_ingestion_engine.py`

**Modified `_detect_delisted()`** — changed from `os.remove()` to `shutil.move()`:

```python
def _detect_delisted(cfg, active_symbols: set, logger) -> int:
    archive_dir = get_storage_path(cfg, "archive_dir")      # from params
    os.makedirs(archive_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    active_safe = {_safe_name(s) for s in active_symbols}
    for sp in glob.glob(os.path.join(raw_dir, "*.parquet")):
        base = os.path.basename(sp).replace("_1h.parquet", "").replace(".parquet", "")
        if base not in active_safe:
            dest = os.path.join(archive_dir, f"{base}_{ts}.parquet")   # timestamped
            shutil.move(sp, dest)
            for sig in glob.glob(os.path.join(sig_dir, f"{base}_*")):
                sig_dest = os.path.join(archive_dir, f"{os.path.basename(sig).replace('.parquet','')}_{ts}.parquet")
                shutil.move(sig, sig_dest)                              # archive signatures too
            logger.info(f"📦 Archived delisted: {base} → {dest}")
```

**Behaviour changes:**
| Before | After |
|--------|-------|
| `os.remove(sp)` — permanent delete | `shutil.move(sp, archive_dir/{base}_{ts}.parquet)` — timestamped archive |
| `os.remove(sig)` — delete signatures | `shutil.move(sig, archive_dir/{base}_{ts}.parquet)` — archive signatures |
| No archive path needed | Uses `params["storage"]["archive_dir"]` resolved via `get_storage_path` |

**Archive file naming:** `{safe_name}_{YYYYMMDD_HHMMSS}.parquet` — full timestamp prevents name collision across multiple delisting events.

**Log output:**
```
📦 Archived delisted: LUNA_USDT → f:/kronos_v1_alt/data/archive/delisted/LUNA_USDT_20260607_210000.parquet
```

## Zero Changes To

- `refresh_discovery`, new listings detection — untouched
- All ingestion logic (checkpointing, incremental, rate limiting, parallel, failed symbols, health score, metrics dashboard) — untouched
- `reversal_signature_miner_sovereign.py` — untouched
- Dual-mode, Option B E2E, sovereign_ctx wiring — preserved