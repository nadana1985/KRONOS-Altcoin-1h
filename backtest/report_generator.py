"""
KRONOS V1-ALT — Comparison Report Generator

Generates structured markdown reports comparing legacy vs override performance.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("kronos.backtest.report")


def generate_comparison_report(
    results: Dict[str, Any],
    output_path: Optional[str] = None,
) -> str:
    """
    Generate a comprehensive comparison report from A/B test results.

    Parameters
    ----------
    results : dict
        Output of run_ab_comparison().
    output_path : str, optional
        Path to write the markdown report.

    Returns
    -------
    str
        The full markdown report text.
    """
    agg_legacy = results.get("aggregate_legacy", {})
    agg_override = results.get("aggregate_override", {})
    per_sym_legacy = results.get("per_symbol_legacy", [])
    per_sym_override = results.get("per_symbol_override", [])
    n_symbols = results.get("n_symbols", 0)
    seed = results.get("seed", 0)

    lines = []
    lines.append("# KRONOS V1-ALT — Bias Override Impact Analysis Report")
    lines.append(f"\n**Generated:** Backtest run with seed={seed}")
    lines.append(f"**Symbols Tested:** {n_symbols}")
    lines.append(f"**Mode:** Legacy (overrides OFF) vs Override (overrides ON)")
    lines.append("")

    # ── Executive Summary ──
    lines.append("## Executive Summary")
    lines.append("")

    key_metrics = [
        ("total_return_mean", "Total Return"),
        ("cagr_mean", "CAGR"),
        ("sharpe_mean", "Sharpe Ratio"),
        ("sortino_mean", "Sortino Ratio"),
        ("max_drawdown_mean", "Max Drawdown"),
        ("calmar_mean", "Calmar Ratio"),
        ("var_mean", "Value at Risk (95%)"),
        ("expected_shortfall_mean", "Expected Shortfall"),
        ("profit_factor_mean", "Profit Factor"),
        ("win_rate_mean", "Win Rate"),
    ]

    lines.append("| Metric | Legacy | Override | Delta | Direction |")
    lines.append("|--------|--------|----------|-------|-----------|")

    improvements = []
    degradations = []

    for key, label in key_metrics:
        v_legacy = agg_legacy.get(key, 0.0)
        v_override = agg_override.get(key, 0.0)
        delta = v_override - v_legacy

        # Determine if improvement (higher is better for most, except max_drawdown/var)
        if key in ("max_drawdown_mean", "var_mean", "expected_shortfall_mean"):
            is_improvement = delta > 0  # less negative = better for drawdown
        else:
            is_improvement = delta > 0

        direction = "✅" if is_improvement else "⚠️"
        if is_improvement:
            improvements.append(label)
        else:
            degradations.append(label)

        lines.append(f"| {label} | {v_legacy:.4f} | {v_override:.4f} | {delta:+.4f} | {direction} |")

    lines.append("")

    # ── Improvement Summary ──
    lines.append("### Improvements (Override Mode)")
    if improvements:
        for imp in improvements:
            lines.append(f"- ✅ **{imp}** improved")
    else:
        lines.append("- No significant improvements detected")
    lines.append("")

    lines.append("### Degradations (Override Mode)")
    if degradations:
        for deg in degradations:
            lines.append(f"- ⚠️ **{deg}** degraded")
    else:
        lines.append("- No significant degradations detected")
    lines.append("")

    # ── Per-Symbol Breakdown ──
    lines.append("## Per-Symbol Breakdown")
    lines.append("")
    lines.append("| Symbol | Conf_Legacy | Conf_Override | Ret_Legacy | Ret_Override | Sharpe_L | Sharpe_O | MDD_L | MDD_O |")
    lines.append("|--------|-------------|---------------|------------|--------------|----------|----------|-------|-------|")

    for i in range(min(len(per_sym_legacy), len(per_sym_override))):
        leg = per_sym_legacy[i]
        ovr = per_sym_override[i]
        sym = leg.get("symbol", f"SYM_{i}")
        lm = leg.get("metrics", {})
        om = ovr.get("metrics", {})
        lines.append(
            f"| {sym} | {leg.get('confidence', 0):.3f} | {ovr.get('confidence', 0):.3f} | "
            f"{lm.get('total_return', 0):.4f} | {om.get('total_return', 0):.4f} | "
            f"{lm.get('sharpe', 0):.2f} | {om.get('sharpe', 0):.2f} | "
            f"{lm.get('max_drawdown', 0):.4f} | {om.get('max_drawdown', 0):.4f} |"
        )

    lines.append("")

    # ── Regime-Wise Performance Breakdown ──
    lines.append("## Regime-Wise Performance Breakdown")
    lines.append("")

    # Collect regime_stats from per-symbol results
    regime_metrics_legacy: Dict[str, Dict[str, List[float]]] = {}
    regime_metrics_override: Dict[str, Dict[str, List[float]]] = {}

    for leg, ovr in zip(per_sym_legacy, per_sym_override):
        for mode_label, sym_result, regime_dict in [
            ("legacy", leg, regime_metrics_legacy),
            ("override", ovr, regime_metrics_override),
        ]:
            rs = sym_result.get("metrics", {}).get("regime_stats", {})
            if not rs:
                continue
            for regime_name, regime_data in rs.items():
                if regime_name not in regime_dict:
                    regime_dict[regime_name] = {"returns": [], "count": []}
                regime_dict[regime_name]["returns"].extend(
                    [regime_data.get("mean_return", 0.0)]
                )
                regime_dict[regime_name]["count"].append(
                    regime_data.get("count", 0)
                )

    all_regimes = sorted(set(list(regime_metrics_legacy.keys()) + list(regime_metrics_override.keys())))
    if all_regimes:
        lines.append("| Regime | Ret_Legacy | Ret_Override | Delta | Bars (avg) |")
        lines.append("|--------|------------|--------------|-------|------------|")
        for regime in all_regimes:
            leg_r = np.mean(regime_metrics_legacy.get(regime, {}).get("returns", [0.0]))
            ovr_r = np.mean(regime_metrics_override.get(regime, {}).get("returns", [0.0]))
            delta = ovr_r - leg_r
            avg_bars = int(np.mean(regime_metrics_legacy.get(regime, {}).get("count", [0])))
            arrow = "✅" if delta > 0 else "⚠️"
            lines.append(f"| {regime} | {leg_r:.6f} | {ovr_r:.6f} | {delta:+.6f} {arrow} | {avg_bars} |")
    else:
        lines.append("*No regime-level data available (regime classifier did not run or data was synthetic).*")

    lines.append("")

    # ── Bias Reduction Evidence ──
    lines.append("## Bias Reduction Evidence")
    lines.append("")

    # Tail risk comparison
    leg_tail = agg_legacy.get("tail_ratio_mean", 0.0)
    ovr_tail = agg_override.get("tail_ratio_mean", 0.0)
    lines.append("### Tail Risk Handling")
    if ovr_tail > leg_tail:
        lines.append(f"- ✅ Tail ratio improved: {leg_tail:.3f} → {ovr_tail:.3f} (better tail risk capture)")
    else:
        lines.append(f"- ⚠️ Tail ratio: {leg_tail:.3f} → {ovr_tail:.3f}")

    leg_skew = agg_legacy.get("skewness_mean", 0.0)
    ovr_skew = agg_override.get("skewness_mean", 0.0)
    if abs(ovr_skew) < abs(leg_skew):
        lines.append(f"- ✅ Skewness reduced: {leg_skew:.3f} → {ovr_skew:.3f} (less distributional bias)")
    else:
        lines.append(f"- ⚠️ Skewness: {leg_skew:.3f} → {ovr_skew:.3f}")

    leg_kurt = agg_legacy.get("kurtosis_mean", 0.0)
    ovr_kurt = agg_override.get("kurtosis_mean", 0.0)
    if abs(ovr_kurt) < abs(leg_kurt):
        lines.append(f"- ✅ Kurtosis reduced: {leg_kurt:.3f} → {ovr_kurt:.3f} (less fat-tail sensitivity)")
    else:
        lines.append(f"- ⚠️ Kurtosis: {leg_kurt:.3f} → {ovr_kurt:.3f}")

    # Sharpe stability
    leg_stab = agg_legacy.get("sharpe_stability_mean", 0.0)
    ovr_stab = agg_override.get("sharpe_stability_mean", 0.0)
    if ovr_stab < leg_stab:
        lines.append(f"- ✅ Sharpe stability improved: {leg_stab:.3f} → {ovr_stab:.3f} (more consistent performance)")
    else:
        lines.append(f"- ⚠️ Sharpe stability: {leg_stab:.3f} → {ovr_stab:.3f}")

    lines.append("")

    # ── Robustness Analysis ──
    lines.append("## Robustness Analysis")
    lines.append("")
    leg_pos = agg_legacy.get("positive_months_pct_mean", 0.0)
    ovr_pos = agg_override.get("positive_months_pct_mean", 0.0)
    lines.append(f"- Positive return bars: Legacy={leg_pos:.1%} Override={ovr_pos:.1%}")

    leg_pf = agg_legacy.get("profit_factor_mean", 0.0)
    ovr_pf = agg_override.get("profit_factor_mean", 0.0)
    lines.append(f"- Profit factor: Legacy={leg_pf:.2f} Override={ovr_pf:.2f}")

    lines.append("")

    # ── Recommendations ──
    lines.append("## Recommendations")
    lines.append("")

    n_improved = len(improvements)
    n_degraded = len(degradations)
    if n_improved > n_degraded:
        lines.append("1. **Override mode shows net positive impact** — recommend keeping all activated points enabled.")
    elif n_improved < n_degraded:
        lines.append("1. **Override mode shows mixed results** — consider reviewing points that cause degradation.")
    else:
        lines.append("1. **Override mode shows neutral impact** — further tuning may be needed.")

    # max_drawdown is a negative float; override > legacy means override has SMALLER (less severe) drawdown
    ovr_mdd = agg_override.get("max_drawdown_mean", 0.0)
    leg_mdd = agg_legacy.get("max_drawdown_mean", 0.0)
    if ovr_mdd > leg_mdd:  # override drawdown is less negative = smaller drawdown = better
        lines.append(f"2. **Max Drawdown improved** — override reduced drawdown: {leg_mdd:.4f} → {ovr_mdd:.4f} "
                     "(vol-adjusted sizing is working).")
    else:
        lines.append(f"2. **Max Drawdown still larger in override mode**: {leg_mdd:.4f} → {ovr_mdd:.4f}. "
                     "Consider lowering `position_max_size` or `position_target_vol` in params_yaml.txt.")

    if agg_override.get("sharpe_mean", 0) > agg_legacy.get("sharpe_mean", 0):
        lines.append("3. **Risk-adjusted returns improved** — Sharpe enhancement validates override approach.")

    ovr_calmar = agg_override.get("calmar_mean", 0.0)
    leg_calmar = agg_legacy.get("calmar_mean", 0.0)
    if ovr_calmar > leg_calmar:
        lines.append(f"4. **Calmar Ratio improved**: {leg_calmar:.3f} → {ovr_calmar:.3f} — "
                     "CAGR-to-drawdown ratio confirms override risk control is effective.")
    else:
        lines.append(f"4. **Calmar Ratio check**: Legacy={leg_calmar:.3f} Override={ovr_calmar:.3f} — "
                     "tune `position_target_vol` if override Calmar remains inferior.")

    lines.append("")
    lines.append("---")
    lines.append(f"*Report generated by KRONOS V1-ALT Backtest Framework | seed={seed}*")

    report_text = "\n".join(lines)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        logger.info("[REPORT] Written to %s", output_path)

    return report_text
