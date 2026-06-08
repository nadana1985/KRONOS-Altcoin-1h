# Diff Summary — Full-Run Wrapper + Health Summary

## File Changed

### `config/unified_ingestion_engine.py`

**Added `_compute_health_summary(cfg, logger) -> dict`** — scans all shards, computes per-symbol health scores, returns:
```python
{"avg_health": float, "total": int, "all": [(sym, health, bars, gaps, nan%, out%), ...]}
```

**Added `_print_health_summary(summary, logger, new_count, delisted_count)`** — prints formatted console summary:

```
============================================================
  KRONOS V1-ALT — Final Health Score Summary
============================================================
  Total symbols        : 528
  Average health score : 94.7/100
------------------------------------------------------------
  🏆 Top 10 Healthiest:
    🟢 BTC/USDT              health= 99 bars=52,560 gaps=0 nan=0.0% out=0.0%
    🟢 ETH/USDT              health= 98 bars=52,560 gaps=0 nan=0.0% out=0.1%
    ...
------------------------------------------------------------
  ⚠️  Worst 10:
    🟡 DOGE/USDT             health= 78 bars= 1,234 gaps=3 nan=2.1% out=0.5%
    ...
============================================================
```

**Added `full_run(clean_first=False, run_miner=False, target_count=None)`** — the main pipeline wrapper:
1. Optionally cleans all raw_shards (`--clean` flag)
2. Calls `fetch_all_symbols_data()` (checkpointing, parallel, validation, health score, archive delisted, error recovery — all features)
3. Computes and prints health summary
4. Logs: `✅ Full ingestion completed. Average health score: XX/100`
5. Optionally calls `mine_all_shards()` (`--mine` flag)

**Refactored `__main__` argparse** — all paths route through `full_run`:
| CLI flags | Behaviour |
|-----------|-----------|
| `--clean` | Clean + ingest + health summary |
| `--clean --mine` | Clean + ingest + health summary + mine |
| `--mine` | Ingest + health summary + mine |
| (no flags) | Ingest + health summary |
| `--inspect` | Inspect only (unchanged) |
| `--target N` | Override `params["symbols"]["target_count"]` |

## Zero Changes To

- `params_yaml.txt` — untouched
- All existing functions (`fetch_all_symbols_data`, `generate_metrics_summary`, `generate_html_summary`, `inspect_missing_fields`, etc.) — untouched
- `reversal_signature_miner_sovereign.py` — untouched
- Dual-mode, Option B E2E, sovereign_ctx wiring — preserved