# Diff Summary — Health Score Validation

## File Changed

### `config/unified_ingestion_engine.py`

**Added 2 helper functions + rewrote `validate_and_fix_data`:**

```python
def _detect_outliers(series, n_std=4):
    """IQR-based outlier count. Returns number of values outside 1.5*IQR from Q1/Q3."""

def _clip_outliers(series, n_std=4):
    """Clips values to [Q1 - 1.5*IQR, Q3 + 1.5*IQR] boundaries."""
```

**Enhanced `validate_and_fix_data(df, symbol, timeframe_ms, logger, cfg) -> dict`:**

**Checks performed per symbol:**
| Metric | Method | Weight in health |
|--------|--------|------------------|
| Duplicate timestamps | `df['timestamp'].duplicated().sum()` | (informing only) |
| NaN ratio | % of rows with NaN in critical cols | 20% (nan_score) |
| Temporal gaps | `df['timestamp'].diff() != timeframe_ms` | 20% (gap_score) |
| Outliers (IQR) | close/volume outside 1.5x IQR | 20% (outlier_score) |
| Completeness | 1 - NaN row fraction | 40% (completeness_score) |

**Health score computation:**
```python
health = int(round(0.40 * completeness_score + 0.20 * gap_score + 0.20 * outlier_score + 0.20 * nan_score))
health = max(0, min(100, health))
```

**Auto-fixes (when `auto_fill_gaps: True` from params):**
- Forward-fill NaN values in critical columns
- Clip close/volume outliers to IQR boundaries

**Per-symbol log output with color tag:**
```
🟢 BTC/USDT: health=96/100 | gaps=0 dup=0 nan=0.0% out=0.2%
🟡 ETH/USDT: health=78/100 | gaps=3 dup=1 nan=2.1% out=0.5%
🔴 XRP/USDT: health=45/100 | gaps=12 dup=5 nan=8.3% out=3.1%
```

**Report dict returned:**
```python
{
  "gaps": int,
  "duplicates": int,
  "nan_pct": float,
  "outlier_pct": float,
  "completeness_pct": float,
  "health_score": int,        # 0-100
  "fixed_nan": int,
  "fixed_outliers": int,
  "issues": [str]             # list of detected issues
}
```

## Zero Changes To

- `params_yaml.txt` — untouched
- All ingestion logic (checkpointing, incremental, rate limiting, parallel, failed symbols, metrics dashboard) — untouched
- `reversal_signature_miner_sovereign.py` — untouched
- Dual-mode, Option B E2E, sovereign_ctx wiring — preserved