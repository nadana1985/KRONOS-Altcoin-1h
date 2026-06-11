# KRONOS V1-ALT — Backtesting & Impact Analysis Framework Summary

## Overview

Implemented a comprehensive A/B backtesting framework to measure the performance impact of ~45 activated bias override points across Batches 1–5. The framework compares **Legacy mode** (overrides disabled) vs **Override-enabled mode** (all active points enabled) using real on-disk shards or synthetic data.

## Files Created

| File | Purpose |
|------|---------|
| `backtest/__init__.py` | Package initialization |
| `backtest/regime_classifier.py` | Market regime detection (high/low vol × trending/ranging) |
| `backtest/metrics_engine.py` | Comprehensive metrics (return, risk, trade, robustness) |
| `backtest/backtest_runner.py` | A/B comparison runner with confidence-weighted position sizing |
| `backtest/report_generator.py` | Markdown report generation with regime-wise breakdown |
| `backtest/run_backtest.py` | CLI entry point with argparse |

## Architecture

### Modes
- **Legacy mode** (`overrides_enabled=False`): Static heuristics, no bias override points active
- **Override mode** (`overrides_enabled=True`): Full 45-point bias override pipeline active

### Key Components

1. **Regime Classifier** — Detects 4 market regimes using rolling volatility percentile and ADX-based trend strength:
   - Low volatility trending
   - High volatility trending
   - Low volatility ranging
   - High volatility ranging

2. **Metrics Engine** — Computes 20+ metrics across 4 categories:
   - Return: Total Return, CAGR, Profit Factor, Expectancy, Win Rate
   - Risk: Sharpe, Sortino, Calmar, Max Drawdown, VaR, Expected Shortfall
   - Trade: Round-trip count, Duration, Win Rate, Avg PnL
   - Robustness: Sharpe stability, Skewness, Kurtosis, Tail ratio

3. **Backtest Runner** — Runs the full miner pipeline in both modes with:
   - Confidence-weighted position sizing (higher confidence = larger position)
   - E2E / research isolation via `set_overrides_enabled()` with try/finally cleanup
   - Regime classification per symbol

4. **Report Generator** — Produces structured markdown with:
   - Executive summary table (Legacy vs Override vs Delta)
   - Per-symbol breakdown
   - Regime-wise performance comparison
   - Bias reduction evidence (tail risk, skewness, kurtosis, Sharpe stability)
   - Recommendations

## Usage

```bash
# Synthetic data (fast, ~2 minutes)
python backtest/run_backtest.py --symbols 10 --bars 2000

# Real shards (requires ingested data)
python backtest/run_backtest.py --real --symbols 20

# Custom seed for reproducibility
python backtest/run_backtest.py --real --seed 123 --output docs/MY_REPORT.md
```

## Config (params_yaml.txt)

All backtest parameters loaded from sovereign config:
```yaml
backtest:
  risk_free_rate: 0.0
  annualization_factor: 8760
  var_confidence: 0.95
  regime_vol_window: 100
  regime_vol_percentile_high: 75
  regime_vol_percentile_low: 25
  regime_adx_threshold: 25
```

## Sovereignty Compliance

- ✅ All parameters from config (zero inline literals in logic)
- ✅ E2E / research isolation via `set_overrides_enabled()` with cleanup
- ✅ Deterministic seed control
- ✅ Engine threading consistency
- ✅ `try/except` fallback on all override imports

## Integration Points

- **Miner**: `mine_reversal_signature()` called in both override modes
- **Structural Engine**: `compute_slots_sovereign()` computes all 32+ slots with active overrides
- **Bias Override Engine**: `set_overrides_enabled(False/True)` toggles the global gate
- **Regime Classifier**: Feeds regime labels into per-symbol regime_stats for report breakdown

## Verification

- ✅ All 6 module imports pass
- ✅ All 5 files parse without syntax errors
- ✅ Code reviewer approved (duplicate removed, config cached, regime breakdown added)
