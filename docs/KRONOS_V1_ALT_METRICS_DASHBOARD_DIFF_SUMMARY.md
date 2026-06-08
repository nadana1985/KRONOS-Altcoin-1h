# Diff Summary — Final Metrics Dashboard

## File Changed

### `config/unified_ingestion_engine.py`

**Added `generate_metrics_summary(cfg, tracker) -> None`** function — called after `tracker.close()` in `fetch_all_symbols_data`:

```python
def generate_metrics_summary(cfg, tracker) -> None:
    """Scan raw_shards and print/save formatted metrics dashboard."""
```

**Output example:**
```
============================================================
  KRONOS V1-ALT — Ingestion Metrics Dashboard
============================================================
  Timeframe          : 1h
  Exchange           : binance
  Target symbols     : 530
  Workers            : 4
------------------------------------------------------------
  Symbols discovered : 530
  Symbols completed  : 528
  Symbols failed     : 2
  Shards on disk     : 528
------------------------------------------------------------
  Total bars         : 3,456,789
  Avg bars/symbol    : 6,546
  Min bars/symbol    : 120
  Max bars/symbol    : 52,560
------------------------------------------------------------
  Total size         : 1,234.56 MB
  Avg size/symbol    : 2.34 MB
------------------------------------------------------------
  Missing quote_volume         : 0
  Missing taker_buy_base_volume: 0
------------------------------------------------------------
  Elapsed            : 4,567s
  Completed at       : 2026-06-07 18:59:59 UTC
============================================================
```

**Dashboard fields:**
- Timeframe, exchange, target symbols, workers — from params
- Symbols discovered/completed/failed — from tracker
- Shards on disk — glob count of `*.parquet` in raw_shards dir
- Total bars, avg/min/max per symbol — scanned from all parquet files
- Total size, avg size per symbol — from file sizes
- Missing quote_volume / taker_buy_base_volume — field presence scan
- Elapsed time, completion timestamp

**Output destinations:**
1. Printed to console
2. Logged via `tracker.logger.info()`
3. Saved to `<logs_dir>/metrics_summary.txt`

**Call site** — single line added after `tracker.close()`:
```python
generate_metrics_summary(cfg, tracker)
```

## Zero Changes To

- `params_yaml.txt` — untouched
- All ingestion logic (checkpointing, incremental, rate limiting, parallel, validation, failed symbols) — untouched
- `reversal_signature_miner_sovereign.py` — untouched
- Dual-mode, Option B E2E, sovereign_ctx wiring — preserved