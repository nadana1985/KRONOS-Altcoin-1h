"""
KRONOS V1-ALT — Evaluation Harness (Phase 2B)

Wires Points 79 (CPCV), 80 (Deflated Sharpe), and 90 (Monte Carlo DSR)
into a coherent model evaluation framework.

This module provides:
  - Purged cross-validation path generation (Point 79)
  - Deflated Sharpe Ratio for model selection (Point 80)
  - Monte Carlo DSR for robust performance evaluation (Point 90)

All functions respect the BiasOverrideEngine, master switch, and liquidity tiers.
Fallbacks are provided for all operations — the system degrades gracefully.

Usage:
    from kronos.quant_spec.evaluation import EvaluationHarness
    harness = EvaluationHarness(engine=engine)
    results = harness.evaluate_model(returns, sharpe, n_trials=100)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine, is_overrides_enabled

# Performance: Pre-import point modules at module level (not inside methods)
from kronos.quant_spec.overrides.point_79 import (
    generate_cpcv_paths_for_data,
    _load_point_79_config,
)
from kronos.quant_spec.overrides.point_35 import (
    apply_combinatorial_purging_embargo,
    _load_point_35_config,
)
from kronos.quant_spec.overrides.point_80 import (
    compute_deflated_sharpe,
    _load_point_80_config,
)
from kronos.quant_spec.overrides.point_82 import (
    apply_causal_cross_sectional,
    _load_point_82_config,
)
from kronos.quant_spec.overrides.point_90 import (
    run_monte_carlo_dsr_evaluation,
    _load_point_90_config,
)
from kronos.quant_spec.overrides.point_26 import compute_cauchy_proximity_kernel
from kronos.quant_spec.overrides.point_76 import compute_mutual_information_distance
from kronos.quant_spec.overrides.point_77 import compute_pca_distance_projections
from kronos.quant_spec.overrides.point_83 import compute_information_weighted_loss
from kronos.quant_spec.overrides.point_84 import compute_mahalanobis_distance
from kronos.quant_spec.overrides.point_85 import compute_bma_weights
from kronos.quant_spec.overrides.point_86 import compute_mrmr_scores
from kronos.quant_spec.overrides.point_87 import compute_loess_prediction
from kronos.quant_spec.overrides.point_88 import compute_linex_loss
from kronos.quant_spec.overrides.point_89 import compute_gmm_soft_membership

logger = logging.getLogger("kronos.evaluation")

_DEFAULT_HARNESS: Optional["EvaluationHarness"] = None


class EvaluationHarness:
    """
    Unified evaluation framework for KRONOS V1-ALT.

    Wires Points 79, 80, 90 through the BiasOverrideEngine with
    proper fallbacks and master switch support.
    """

    def __init__(self, engine: Optional[BiasOverrideEngine] = None):
        self.engine = engine or BiasOverrideEngine()
        self._overrides_wired = True

    def _check_overrides(self) -> bool:
        """Check if overrides are active."""
        return self._overrides_wired and is_overrides_enabled()

    def generate_cpcv_paths(
        self,
        n_blocks: int = 6,
        k_test: int = 2,
        df: Optional[pd.DataFrame] = None,
        symbol: str = "UNKNOWN",
    ) -> List[Tuple[List[int], List[int]]]:
        """
        Generate CPCV paths (Point 79).

        Returns list of (train_blocks, test_blocks) tuples.
        Falls back to walk-forward if overrides are disabled.
        """
        if not self._check_overrides():
            # Fallback: single walk-forward split
            logger.info("[EVAL] overrides disabled — using walk-forward fallback")
            train = list(range(n_blocks - 1))
            test = [n_blocks - 1]
            return [(train, test)]

        try:
            cfg = _load_point_79_config(self.engine)
            n_b = int(cfg.get("n_blocks", n_blocks))
            k_t = int(cfg.get("k_test", k_test))
            paths = generate_cpcv_paths_for_data(n_b, k_t, config=cfg)
            logger.info(
                "[EVAL] CPCV paths | n_blocks=%d k_test=%d -> %d paths",
                n_b, k_t, len(paths),
            )
            return paths
        except Exception as e:
            logger.warning("[EVAL] CPCV path generation failed: %s — using fallback", e)
            train = list(range(n_blocks - 1))
            test = [n_blocks - 1]
            return [(train, test)]

    def compute_purged_train_size(
        self,
        raw_train_size: int,
        n_test_blocks: int = 6,
        horizon: int = 10,
        embargo: int = 5,
        df: Optional[pd.DataFrame] = None,
        symbol: str = "UNKNOWN",
    ) -> int:
        """
        Compute effective training size after purging (Point 35).

        Returns the number of training samples that survive purging + embargo.
        """
        if not self._check_overrides():
            # Conservative fallback: lose 20% of training data
            return max(1, int(raw_train_size * 0.8))

        try:
            cfg = _load_point_35_config(self.engine)
            emb = int(cfg.get("embargo_window", embargo))
            effective = apply_combinatorial_purging_embargo(
                n_train_samples=raw_train_size,
                n_test_blocks=n_test_blocks,
                horizon=horizon,
                embargo=emb,
                config=cfg,
            )
            logger.info(
                "[EVAL] Purging | raw=%d effective=%d (purge_ratio=%.2f)",
                raw_train_size, effective,
                1.0 - effective / max(raw_train_size, 1),
            )
            return effective
        except Exception as e:
            logger.warning("[EVAL] Purging failed: %s — using conservative fallback", e)
            return max(1, int(raw_train_size * 0.8))

    def compute_deflated_sharpe(
        self,
        sharpe: float,
        n_trials: int = 100,
        n_observations: int = 200,
        skew: float = 0.0,
        kurt: float = 3.0,
        df: Optional[pd.DataFrame] = None,
        symbol: str = "UNKNOWN",
    ) -> float:
        """
        Compute Deflated Sharpe Ratio (Point 80).

        Adjusts the observed Sharpe for multiple testing.
        """
        if not self._check_overrides():
            return sharpe  # no adjustment

        try:
            cfg = _load_point_80_config(self.engine)
            dsr = compute_deflated_sharpe(
                sharpe, n_trials, n_observations, skew, kurt, config=cfg,
            )
            logger.info(
                "[EVAL] DSR | raw_sharpe=%.3f trials=%d T=%d -> dsr=%.4f",
                sharpe, n_trials, n_observations, dsr,
            )
            return dsr
        except Exception as e:
            logger.warning("[EVAL] DSR computation failed: %s — returning raw Sharpe", e)
            return sharpe

    def run_monte_carlo_dsr(
        self,
        returns: pd.Series,
        n_mc_paths: int = 1000,
        n_trials: int = 100,
        df: Optional[pd.DataFrame] = None,
        symbol: str = "UNKNOWN",
    ) -> Dict[str, float]:
        """
        Run Monte Carlo DSR evaluation (Point 90).

        Returns dict with:
          - dsr_mean: mean DSR across paths
          - dsr_std: standard deviation
          - prob_positive: fraction of paths with positive DSR
        """
        if not self._check_overrides():
            return {
                "dsr_mean": 0.0,
                "dsr_std": 0.0,
                "prob_positive": 0.5,
                "n_paths": 0,
            }

        try:
            cfg = _load_point_90_config(self.engine)
            # Override n_mc_paths if specified
            cfg["n_mc_paths"] = n_mc_paths
            stats = run_monte_carlo_dsr_evaluation(returns, config=cfg)
            stats["n_paths"] = n_mc_paths
            logger.info(
                "[EVAL] MC-DSR | paths=%d -> mean=%.4f prob_pos=%.3f",
                n_mc_paths, stats["dsr_mean"], stats["prob_positive"],
            )
            return stats
        except Exception as e:
            logger.warning("[EVAL] MC-DSR failed: %s — returning fallback", e)
            return {
                "dsr_mean": 0.0,
                "dsr_std": 0.0,
                "prob_positive": 0.5,
                "n_paths": 0,
            }

    def evaluate_model(
        self,
        returns: pd.Series,
        raw_sharpe: float,
        n_trials: int = 100,
        n_observations: int = 200,
        n_mc_paths: int = 1000,
        df: Optional[pd.DataFrame] = None,
        symbol: str = "UNKNOWN",
    ) -> Dict[str, Any]:
        """
        Full model evaluation combining Points 79, 80, 90.

        Returns comprehensive evaluation dict with:
          - cpcv_paths: number of CPCV paths
          - purged_train_pct: percentage of training data surviving purging
          - raw_sharpe: input Sharpe
          - dsr: deflated Sharpe ratio
          - mc_dsr: Monte Carlo DSR statistics
          - evaluation_passed: overall pass/fail based on DSR > 0
        """
        # 1. CPCV paths
        cpcv_paths = self.generate_cpcv_paths(
            df=df, symbol=symbol,
        )

        # 2. Purging estimate (assume 80/20 train/test split)
        n_test_blocks = len(cpcv_paths[0][1]) if cpcv_paths else 2
        n_total_blocks = n_test_blocks + len(cpcv_paths[0][0]) if cpcv_paths else 6
        effective_train = self.compute_purged_train_size(
            raw_train_size=800,
            n_test_blocks=n_total_blocks,
            df=df, symbol=symbol,
        )
        purged_pct = effective_train / 800.0 if 800 > 0 else 0.8

        # 3. Deflated Sharpe
        dsr = self.compute_deflated_sharpe(
            raw_sharpe, n_trials, n_observations,
            df=df, symbol=symbol,
        )

        # 4. Monte Carlo DSR
        mc_dsr = self.run_monte_carlo_dsr(
            returns, n_mc_paths, n_trials,
            df=df, symbol=symbol,
        )

        # 5. Overall evaluation
        evaluation_passed = dsr > 0 and mc_dsr.get("prob_positive", 0) > 0.5

        results = {
            "symbol": symbol,
            "cpcv_paths": len(cpcv_paths),
            "purged_train_pct": round(purged_pct, 3),
            "raw_sharpe": round(raw_sharpe, 4),
            "dsr": round(dsr, 4),
            "mc_dsr_mean": round(mc_dsr.get("dsr_mean", 0), 4),
            "mc_dsr_std": round(mc_dsr.get("dsr_std", 0), 4),
            "mc_prob_positive": round(mc_dsr.get("prob_positive", 0), 4),
            "evaluation_passed": evaluation_passed,
        }

        logger.info(
            "[EVAL] %s | paths=%d purged=%.1f%% raw_sharpe=%.3f dsr=%.4f mc_dsr=%.4f pass=%s",
            symbol, results["cpcv_paths"], results["purged_train_pct"] * 100,
            raw_sharpe, dsr, mc_dsr.get("dsr_mean", 0), evaluation_passed,
        )

        return results

    def validate_causal_lag(
        self,
        local_feature: pd.Series,
        cross_sectional_df: pd.DataFrame,
        lag: int = 1,
        df: Optional[pd.DataFrame] = None,
        symbol: str = "UNKNOWN",
    ) -> Dict[str, Any]:
        """
        Validate cross-sectional feature causality (Point 82).

        Ensures all cross-sectional features are strictly lagged.
        Returns dict with:
          - is_causal: whether the lagging was applied
          - lag_used: the lag applied
          - n_features: number of cross-sectional features
          - result: the causally lagged DataFrame
        """
        if not self._check_overrides():
            # Fallback: return local-only (most conservative)
            logger.info("[EVAL] overrides disabled — returning local-only for %s", symbol)
            return {
                "is_causal": False,
                "lag_used": 1,
                "n_features": 0,
                "result": pd.DataFrame({"local": local_feature}),
            }

        try:
            cfg = _load_point_82_config(self.engine)
            lag_val = int(cfg.get("global_lag", lag))
            lagged = apply_causal_cross_sectional(
                local_feature, cross_sectional_df, lag_val, config=cfg,
            )
            cs_cols = [c for c in lagged.columns if c != "local"]
            logger.info(
                "[EVAL] Causal lag | %s lag=%d features=%d",
                symbol, lag_val, len(cs_cols),
            )
            return {
                "is_causal": True,
                "lag_used": lag_val,
                "n_features": len(cs_cols),
                "result": lagged,
            }
        except Exception as e:
            logger.warning("[EVAL] Causal lag failed: %s — returning local-only", e)
            return {
                "is_causal": False,
                "lag_used": 1,
                "n_features": 0,
                "result": pd.DataFrame({"local": local_feature}),
            }


    # ── Phase 3 Group B: ML & Clustering Utilities ─────────────────────

    def compute_feature_quality_metrics(
        self,
        features: pd.DataFrame,
        target: pd.Series,
        df: Optional[pd.DataFrame] = None,
        symbol: str = "UNKNOWN",
    ) -> Dict[str, Any]:
        """
        Compute feature quality metrics using Points 76 (MI weights), 77 (PCA),
        84 (Mahalanobis), 86 (mRMR).

        Returns dict with:
          - mi_weights: mutual information feature weights
          - pca_variance_explained: PCA variance explained ratio
          - mahalanobis_distance: pairwise Mahalanobis distance
          - mrmr_selected: mRMR-selected features
        """
        results = {}

        # Point 76: MI distance scaling
        try:
            from kronos.quant_spec.overrides.point_76 import compute_mi_weights
            results["mi_weights"] = compute_mi_weights(features, target)
        except Exception:
            results["mi_weights"] = pd.Series(1.0, index=features.columns)

        # Point 77: PCA projections
        try:
            from kronos.quant_spec.overrides.point_77 import compute_pca_projection
            pca = compute_pca_projection(features)
            results["pca_variance_explained"] = pca.get("variance_explained", [1.0])
        except Exception:
            results["pca_variance_explained"] = [1.0]

        # Point 84: Mahalanobis distance
        try:
            from kronos.quant_spec.overrides.point_84 import compute_mahalanobis_cluster_distance
            results["mahalanobis_distance"] = compute_mahalanobis_cluster_distance(features)
        except Exception:
            results["mahalanobis_distance"] = 0.0

        # Point 86: mRMR feature selection
        try:
            from kronos.quant_spec.overrides.point_86 import compute_mrmr_feature_selection
            results["mrmr_selected"] = compute_mrmr_feature_selection(features, target)
        except Exception:
            results["mrmr_selected"] = []

        return results

    def compute_training_loss_metrics(
        self,
        predictions: np.ndarray,
        actuals: np.ndarray,
        information_density: np.ndarray = None,
        df: Optional[pd.DataFrame] = None,
        symbol: str = "UNKNOWN",
    ) -> Dict[str, float]:
        """
        Compute training loss metrics using Points 83 (info-weighted loss)
        and 88 (Linex asymmetric loss).

        Returns dict with:
          - info_weighted_loss: information-weighted MSE
          - linex_loss: asymmetric Linex loss
          - linex_asymmetry: asymmetry parameter used
        """
        results = {}

        # Point 83: Information-weighted loss
        try:
            from kronos.quant_spec.overrides.point_83 import compute_info_weighted_loss
            results["info_weighted_loss"] = compute_info_weighted_loss(
                predictions, actuals, information_density)
        except Exception:
            results["info_weighted_loss"] = 0.0

        # Point 88: Linex asymmetric loss
        try:
            from kronos.quant_spec.overrides.point_88 import compute_asymmetric_loss
            errors = actuals[:len(predictions)] - predictions
            results["linex_loss"] = compute_asymmetric_loss(errors)
        except Exception:
            results["linex_loss"] = 0.0

        return results

    def compute_ensemble_state_metrics(
        self,
        model_likelihoods: List[float] = None,
        features: pd.DataFrame = None,
        df: Optional[pd.DataFrame] = None,
        symbol: str = "UNKNOWN",
    ) -> Dict[str, Any]:
        """
        Compute ensemble and state metrics using Points 78 (barrier labels),
        81 (MST pruning), 85 (BMA), 89 (GMM soft membership).

        Returns dict with:
          - barrier_label: dynamic barrier label
          - mst_edges: MST network edge count
          - bma_weights: BMA ensemble weights
          - gmm_max_membership: GMM soft state membership
        """
        results = {}

        # Point 78: Dynamic barrier labels
        try:
            from kronos.quant_spec.overrides.point_78 import compute_dynamic_barrier_label
            c = pd.to_numeric(df.get("close") if df is not None else pd.Series(), errors="coerce")
            rets = np.log((c / c.shift(1)).clip(lower=1e-12))
            barrier = compute_dynamic_barrier_label(rets)
            results["barrier_label"] = barrier.get("label", 0)
        except Exception:
            results["barrier_label"] = 0

        # Point 81: MST pruning (requires multi-asset returns)
        results["mst_edges"] = 0  # placeholder, computed when multi-asset data available

        # Point 85: BMA ensemble weights
        try:
            from kronos.quant_spec.overrides.point_85 import compute_bma_ensemble_weights
            if model_likelihoods and len(model_likelihoods) > 1:
                results["bma_weights"] = compute_bma_ensemble_weights(model_likelihoods)
            else:
                results["bma_weights"] = []
        except Exception:
            results["bma_weights"] = []

        # Point 89: GMM soft membership
        try:
            from kronos.quant_spec.overrides.point_89 import compute_soft_state_membership
            if features is not None and features.shape[1] >= 1:
                gmm = compute_soft_state_membership(features)
                results["gmm_max_membership"] = float(
                    np.max(gmm["memberships"][-1])) if gmm["memberships"].size > 0 else 0.5
            else:
                results["gmm_max_membership"] = 0.5
        except Exception:
            results["gmm_max_membership"] = 0.5

        # Point 87: LOESS prediction (requires x/y series)
        results["loess_available"] = features is not None

        return results


def quick_evaluate(
    returns: pd.Series,
    sharpe: float,
    engine: Optional[BiasOverrideEngine] = None,
    symbol: str = "QUICK",
) -> Dict[str, Any]:
    """
    Convenience function for quick model evaluation.

    Combines DSR + MC-DSR in a single call.
    """
    harness = EvaluationHarness(engine=engine) if engine is not None else get_default_harness()
    return harness.evaluate_model(
        returns=returns,
        raw_sharpe=sharpe,
        symbol=symbol,
    )


def get_default_harness() -> EvaluationHarness:
    """Return a process-wide EvaluationHarness for hot paths."""
    global _DEFAULT_HARNESS
    if _DEFAULT_HARNESS is None:
        _DEFAULT_HARNESS = EvaluationHarness()
    return _DEFAULT_HARNESS


if __name__ == "__main__":
    import numpy as np
    print("=== Evaluation Harness Smoke Test ===")

    # Synthetic returns
    rng = np.random.default_rng(42)
    n = 300
    rets = rng.normal(0.0005, 0.01, n)
    returns = pd.Series(rets)

    # Sharpe
    sharpe = float(rets.mean() / (rets.std() + 1e-12) * np.sqrt(252 * 24))
    print(f"Raw Sharpe: {sharpe:.3f}")

    # Full evaluation
    results = quick_evaluate(returns, sharpe)
    for k, v in results.items():
        if k != "mc_dsr_std":
            print(f"  {k}: {v}")

    # Causal lag validation
    harness = EvaluationHarness()
    local = pd.Series(rng.normal(0, 1, 100), name="local")
    xsec = pd.DataFrame({
        "mkt1": rng.normal(0, 1, 100),
        "mkt2": rng.normal(0, 1, 100),
    })
    lag_result = harness.validate_causal_lag(local, xsec, symbol="TEST")
    print(f"  Causal lag: is_causal={lag_result['is_causal']} features={lag_result['n_features']}")

    print("=== Smoke test complete ===")
