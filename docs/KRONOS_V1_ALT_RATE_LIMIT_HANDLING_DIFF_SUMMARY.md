# Diff Summary — Rate Limit Handling + Exponential Backoff

## Files Changed

### 1. `params_yaml.txt`
**Added** 1 line under `data_fetch`:
```yaml
  rate_limit_delay: 0.5     # Inter-request delay in seconds
```

### 2. `config/unified_ingestion_engine.py`

**Added module-level `_request_counter` + `_rate_limited_call()` function** (before `fetch_full_history`):

```python
_request_counter = 0

def _rate_limited_call(ex, symbol, kparams, logger, cfg):
    global _request_counter
    delay = float(fetch_cfg.get("rate_limit_delay", 0.5))      # from params
    max_backoff = fetch_cfg.get("rate_limit_max_backoff", 8)   # max 8s
    _request_counter += 1
    time.sleep(delay)  # global pacing between every call
    for attempt in range(1, max_retries + 1):
        try:
            return ex.fapiPublicGetKlines(kparams)
        except ccxt.RateLimitExceeded as e:
            backoff = min(max_backoff, 2 ** (attempt - 1))     # 1s, 2s, 4s, 8s
            logger.warning(f"🚦 Rate limit [{attempt}/{max_retries}] {symbol}: backing off {backoff}s")
            time.sleep(backoff)
        except Exception as e:
            if attempt < max_retries:
                backoff = min(max_backoff, 2 ** (attempt - 1)) # same exp backoff
                logger.warning(f"⚠️ Retry [{attempt}/{max_retries}] {symbol}: {e} — backoff {backoff}s")
                time.sleep(backoff)
    raise last_err
```

**Modified `fetch_full_history()`** — inner retry loop replaced with single `_rate_limited_call()`:
- Before: nested retry loop with `pacing_delay * 2 * attempt` inside each page fetch
- After: `_rate_limited_call()` handles per-request pacing + 429 detection + exponential backoff
- `market = ex.market(symbol)` and `bsym = market['id']` hoisted outside the while-loop (one call per symbol instead of per page)
- `time.sleep(pacing_delay)` after each page removed (replaced by `_rate_limited_call`'s global pacing)

## Behaviors

| Scenario | Before | After |
|----------|--------|-------|
| Normal request | `pacing_delay * 2 * attempt` per retry attempt | `rate_limit_delay` (0.5s) global delay every call |
| 429 rate limit | generic retry with `pacing_delay * 2 * attempt` | `ccxt.RateLimitExceeded` caught → exp backoff 1s, 2s, 4s, 8s |
| Other API errors | same as retry | same exp backoff 1s, 2s, 4s, 8s |
| Request counting | none | `_request_counter` increments globally |

## Zero Changes To

- Checkpointing, incremental skip, end_date logic — untouched
- `IngestionTracker`, `fetch_all_symbols_data`, `clean_ingest`, `inspect_missing_fields`, `bridge_mine_after_ingest` — untouched
- `reversal_signature_miner_sovereign.py` — untouched
- Dual-mode, Option B E2E, sovereign_ctx wiring — preserved