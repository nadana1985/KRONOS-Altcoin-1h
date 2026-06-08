# Diff Summary — Data Validation After Fetch

## Files Changed

### 1. `params_yaml.txt`
**Added** 1 line under `data_fetch`:
```yaml
  auto_fill_gaps: true        # Forward-fill NaNs in critical columns
```

### 2. `config/unified_ingestion_engine.py`

**Replaced** `validate_no_gaps(df, symbol, timeframe_ms, logger) -> bool` with:

```python
CRITICAL_COLS = ["open", "high", "low", "close", "volume", "quote_volume"]

def validate_and_fix_data(df, symbol, timeframe_ms, logger, cfg) -> dict:
    """Returns report: {gaps, duplicates, nan_any, nan_cols, fixed_gaps}"""
```

**Validation checks per symbol:**
1. **Duplicate timestamps** — `df['timestamp'].duplicated().sum()` → warns if > 0
2. **NaN in critical columns** — checks open/high/low/close/volume/quote_volume → warns per-column counts
3. **Temporal gaps > 1h** — `df['timestamp'].diff() != timeframe_ms` → warns with max gap in bars
4. **Auto-fix** — if `cfg["data_fetch"]["auto_fill_gaps"]` is True (from params), forward-fills NaNs in critical columns → logs how many filled

**Call site updated** in `fetch_full_history`:
```python
# Before:
validate_no_gaps(combined_df, symbol, timeframe_ms, logger)

# After:
validate_and_fix_data(combined_df, symbol, timeframe_ms, logger, cfg)
```

**Example log output:**
```
WARNING  ⚠️ ETH/USDT: 3 duplicate timestamps found.
WARNING  ⚠️ XRP/USDT: 12 rows with NaN in critical columns: {'volume': 12, 'quote_volume': 12}
WARNING  ⚠️ BTC/USDT: 1 temporal gaps detected (max gap: 7200000ms ≈ 2 bars).
INFO     ✅ ADA/USDT: forward-filled 5 NaN values.
```

## Zero Changes To

- Checkpointing, incremental skip, end_date — untouched
- `_rate_limited_call`, `_fetch_one`, `IngestionTracker` — untouched
- `reversal_signature_miner_sovereign.py` — untouched
- Dual-mode, Option B E2E, sovereign_ctx wiring — preserved