"""
Point 35: Overlapping Label Autocorrelation Smearing - Causal Purged and Embargoed Cross-Validation
(Scikit-Learn Compliant Implementation)

Eliminates lookahead contamination and post-test serial correlation dependencies.
Executes mathematically strict purging of overlapping multi-bar forward labels and explicit 
post-test chronological embargo logic to generate mathematically pure out-of-sample training folds natively.
"""

from __future__ import annotations

import logging
from typing import Generator, Iterable, Optional, Tuple, Any, Union, Dict

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

_logger = logging.getLogger("kronos.bias_override.point_35")

_DEFAULT_CONFIG = {
    "fallback_purge_ratio": 0.15,
}


class PurgedEmbargoedTimeSeriesSplit:
    """
    Scikit-Learn compliant generator natively enforcing strict out-of-sample temporal cross-validation.
    
    MATHEMATICAL SPECIFICATION:
    1. Extracts explicit [test_start, test_end] block sequence organically.
    2. Purging: Drops training indices matching [test_start - h, test_end].
    3. Embargoing: Drops post-test training indices matching [test_end + 1, test_end + v].
    4. Output: Safe training mask guarantees mathematically pure out-of-sample evaluation constraints natively.
    """
    
    def __init__(self, n_splits: int = 5, h: int = 4, v: int = 24):
        """
        Parameters
        ----------
        n_splits : int
            Total number of temporal splits organically extracting bounds.
        h : int
            Look-forward label horizon length (Purging range).
        v : int
            Post-test chronological lock window length (Embargo range).
        """
        self.n_splits = n_splits
        self.h = h
        self.v = v

    def split(
        self, 
        X: Union[pd.DataFrame, np.ndarray], 
        y: Any = None, 
        groups: Any = None
    ) -> Iterable[Tuple[np.ndarray, np.ndarray]]:
        """
        Generates purged and embargoed training and validation index sequences natively.
        
        Returns
        -------
        Iterable[Tuple[np.ndarray, np.ndarray]]
            Yields safe_train_idx, test_idx seamlessly fitting standard SKLearn pipelines organically.
        """
        N = len(X)
        
        # Standard Scikit-Learn TimeSeriesSplit logic fundamentally isolates chronological fold blocks cleanly
        tscv = TimeSeriesSplit(n_splits=self.n_splits)
        
        for train_idx, test_idx in tscv.split(X):
            if len(test_idx) == 0:
                continue
                
            test_start = test_idx[0]
            test_end = test_idx[-1]
            
            # 1. Purging Evaluation natively
            # Eliminates training samples perfectly where the forward label calculation physically 
            # leaks directly into the validation test set sequence.
            purge_start = test_start - self.h
            
            # 2. Embargo Evaluation natively
            # Eliminates training samples chronologically immediately following the validation test set
            # destroying any lingering persistent autocorrelation states organically.
            embargo_end = test_end + self.v
            
            # Construct strict training set mathematical boundaries cleanly utilizing boolean masks natively
            train_mask = np.ones_like(train_idx, dtype=bool)
            
            # Vectorized logical boundaries securely mapping exact sequence isolation states
            mask_purge = (train_idx >= purge_start) & (train_idx <= test_end)
            mask_embargo = (train_idx > test_end) & (train_idx <= embargo_end)
            
            train_mask = train_mask & ~mask_purge & ~mask_embargo
            
            safe_train_idx = train_idx[train_mask]
            
            yield safe_train_idx, test_idx

    def get_n_splits(self, X: Any = None, y: Any = None, groups: Any = None) -> int:
        return self.n_splits


def compute_purged_embargoed_mask(
    total_length: int,
    test_start: int,
    test_end: int,
    h: int = 4,
    v: int = 24
) -> np.ndarray:
    """
    Computes a raw boolean mask extracting mathematically pure training bounds explicitly.
    Useful for isolated localized matrix filtering operations natively beyond SkLearn objects.
    """
    mask = np.ones(total_length, dtype=bool)
    
    # 1. Remove strict validation sequences organically
    mask[test_start:test_end + 1] = False
    
    # 2. Purging explicitly isolating label-leak vectors locally
    purge_start = max(0, test_start - h)
    mask[purge_start:test_start] = False
    
    # 3. Embargoing natively stripping structural post-test correlations naturally
    embargo_end = min(total_length, test_end + v + 1)
    mask[test_end + 1:embargo_end] = False
    
    return mask


def _load_point_35_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_35", engine)
    return cfg if cfg else _DEFAULT_CONFIG


def compute_point_35_override(
    raw_train_size: int,
    event_index: int,
    horizon: int = 4,
    df: Optional[pd.DataFrame] = None,
    symbol: str = '',
    engine: Optional[BiasOverrideEngine] = None
) -> int:
    """
    Adapter for KRONOS V1-ALT BiasOverrideEngine.
    """
    try:
        cfg = _load_point_35_config(engine)
        override_val = int(raw_train_size * (1 - cfg.get("fallback_purge_ratio", 0.15)))
        if engine:
            return engine.apply_override(
                point_id="35",
                raw_value=raw_train_size,
                override_value=override_val,
                df=df,
                symbol=symbol
            )
        return override_val
    except Exception as e:
        _logger.debug(f"[POINT_35] Error: {e}")
        return raw_train_size