# Diff Summary — Enhanced Full-Run Entrypoint

## File Changed

### `config/unified_ingestion_engine.py`

**Refactored `full_run()`** — upgraded to main entrypoint with all CLI features:

**New `--dummy` flag** — sets `cfg["symbols"]["target_count"] = 20` for quick testing, displays `(DUMMY MODE — 20 symbols)` in banner.

**New `BANNER_TOP` / `BANNER_BOT` constants** — clean `====` separators for console output.

**Enhanced `full_run()` signature:**
```python
def full_run(clean_first=False, run_miner=False, target_count=None, dummy=False)
```

**Start banner printed to console:**
```
============================================================
  🚀 KRONOS V1-ALT Full Ingestion Run
  Target: 530 symbols  |  Clean: True  |  Mine: True
============================================================
```

**Completion banners:**
```
============================================================
  ✅ Full ingestion completed. Average health score: 94.7/100
============================================================
```
```
============================================================
  ⛏️  Running reversal miner on all shards...
============================================================
```
```
============================================================
  ✅ Full ingestion + mining completed successfully
============================================================
```

**Updated `__main__` argparse:**
| CLI | Behaviour |
|-----|-----------|
| `--clean` | Clean + full ingest + health summary |
| `--clean --mine` | Clean + full ingest + health summary + mine |
| `--mine` | Full ingest + health summary + mine |
| `--dummy` | Same as above but 20 symbols only |
| `--target N` | Override target count |
| `--inspect` | Inspect only (unchanged) |
| (no flags) | Full ingest + health summary |

**Log output:**
- `🚀 KRONOS V1-ALT Full Ingestion Run — target=530 clean=True mine=True`
- `✅ Full ingestion completed. Average health score: 94.7/100`
- `✅ Full ingestion + mining completed successfully`

## Zero Changes To

- `params_yaml.txt` — untouched
- All existing pipeline features (checkpointing, incremental skip, end_date, parallel, rate limit, health score, validation, archive delisted, error recovery, HTML dashboard) — untouched
- `reversal_signature_miner_sovereign.py` — untouched
- Dual-mode, Option B E2E, sovereign_ctx wiring — preserved