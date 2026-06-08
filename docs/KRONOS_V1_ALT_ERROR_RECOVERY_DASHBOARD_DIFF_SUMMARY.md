# Diff Summary — Error Recovery Dashboard for Failed Symbols

## File Changed

### `config/unified_ingestion_engine.py`

**Refactored failed-symbols system** — from bare set to structured records with error classification:

**`_get_failed_path(cfg)`** — changed file to `failed_symbols_recovery.txt` (clearer name)

**`_load_failed_symbols(cfg) -> list[dict]`** — now returns `[{symbol, reason, ts}]` parsing pipe-delimited format:
```
BTC/USDT | RateLimit | 2026-06-07T21:00:00Z
```

**`_save_failed_symbols(records: list[dict], cfg)`** — saves structured format with `symbol | reason | ts`

**`_classify_error(e: Exception) -> str`** — classifies exceptions into 4 buckets:
| Classifier | Returns |
|-----------|---------|
| "rate" + ("limit"/"429") in error msg | `RateLimit` |
| "timeout" / "timed out" in msg | `Timeout` |
| "no data" / "empty" in msg | `NoData` |
| "api" / "http" / "connection" in msg | `APIError` |
| fallback | `APIError` |

**`_print_error_recovery_dashboard(records: list[dict], logger)`** — prints formatted dashboard:

```
============================================================
  KRONOS V1-ALT — Error Recovery Dashboard
============================================================
  Total failed symbols  : 7
------------------------------------------------------------
  Error Type Breakdown:
    RateLimit      :    3 (42.9%)
    Timeout        :    2 (28.6%)
    APIError       :    2 (28.6%)
------------------------------------------------------------
  Sample (up to 5):
    BTC/USDT              | RateLimit     | 2026-06-07T21:00:00Z
    ETH/USDT              | Timeout       | 2026-06-07T21:00:05Z
    SOL/USDT              | APIError      | 2026-06-07T21:00:10Z
    XRP/USDT              | RateLimit     | 2026-06-07T21:00:15Z
    ADA/USDT              | RateLimit     | 2026-06-07T21:00:20Z
------------------------------------------------------------
============================================================
```

**Modified `fetch_all_symbols_data()`:**
- On start: loads records, extracts failed symbol set, shows dashboard for retry set
- On exception: `_classify_error(e)` + appends structured record with ISO timestamp
- On end: saves structured records, shows dashboard for this run's failures
- Logs `[Reason]` tag in error messages: `Failed BTC/USDT: [RateLimit] ...`

## File Format

```
symbol           | reason     | timestamp
BTC/USDT         | RateLimit  | 2026-06-07T21:00:00Z
```

## Zero Changes To

- `params_yaml.txt` — untouched
- All ingestion logic (checkpointing, incremental, rate limiting, parallel, health score, listings/delistings, archive) — untouched
- `reversal_signature_miner_sovereign.py` — untouched
- Dual-mode, Option B E2E, sovereign_ctx wiring — preserved