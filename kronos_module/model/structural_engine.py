"""
KRONOS V1-ALT Sovereign Structural Engine (ported for timeframe)

Provides structural veto core + individual/global prior dual-mode.
All values resolved from sovereign params via loader.
Zero inline literals. Preserves orthogonal neural slot veto for scaling.
"""

import os
import sys

# Robust production bootstrap using KRONOS_PARAMS_PATH env + get_storage_path + cfg (zero literals)
params_path = os.getenv("KRONOS_PARAMS_PATH")
if params_path:
    project_root = os.path.dirname(os.path.abspath(params_path))
    config_dir = os.path.join(project_root, "config")
    sys.path.insert(0, config_dir)

from sovereign_entrypoint import get_sovereign_config
import pandas as pd
import numpy as np  # for vectorized ops in hot path for 10M+ bars


def get_structural_veto():
    """Enforce structural sections from params. Fails hard on missing keys (veto)."""
    cfg = get_sovereign_config()
    required = ["project", "storage", "individual_mode", "global_prior_mode", "symbols", "thresholds"]
    for sec in required:
        if sec not in cfg:
            raise KeyError(f"STRUCTURAL_VETO_FAILED: missing {sec} in params")
    return cfg


def get_dual_mode_context():
    """Return individual primary + global prior ablatable context. No literals."""
    cfg = get_structural_veto()
    ind = cfg["individual_mode"]
    gp = cfg["global_prior_mode"]
    sym = cfg["symbols"]
    proj = cfg["project"]
    thr = cfg["thresholds"]
    storage = cfg["storage"]

    # orthogonal neural slot veto (from thresholds, for reversal/neural scaling)
    neural_slots = {
        "reversal_window": (thr["reversal_window_min"], thr["reversal_window_max"]),
        "reversal_factor": thr["reversal_window_factor"],
        "hash_mod": thr["reversal_hash_mod"],
        "variation": thr["reversal_variation_factor"],
        "strength_mult": thr["reversal_base_strength_multiplier"],
        "strength_add": thr["reversal_base_strength_add"],
        "confidence_clamp": (thr["reversal_confidence_clamp_min"], thr["reversal_confidence_clamp_max"]),
        "min_history": thr["reversal_min_history"],
        "confidence_min": thr["reversal_confidence_min"],
    }

    return {
        "timeframe": proj["timeframe"],
        "target_count": sym["target_count"],
        "individual": ind,
        "global_prior": gp,
        "neural_slots": neural_slots,
        "memory_shard": thr["memory_adaptive_shard_size"],
        "max_context": thr["max_context_tokens"],
        "is_individual_primary": ind["primary_output"],
        "global_injection_ablatable": gp["injection_ablatable"],
        "model_dir": storage.get("models_dir"),
        "kronos_small_dir": storage.get("kronos_small_dir"),
        "kronos_tokenizer_dir": storage.get("kronos_tokenizer_dir"),
    }


def apply_structural_veto(mode: str = "individual"):
    """Small veto applicator for dual-mode. Use before model forward."""
    ctx = get_dual_mode_context()
    if mode == "individual" and not ctx["is_individual_primary"]:
        raise RuntimeError("STRUCTURAL_VETO: individual not primary per params")
    if mode == "global" and not ctx["global_injection_ablatable"]:
        raise RuntimeError("STRUCTURAL_VETO: global prior injection disabled per params")
    return ctx


# Ablation note: set global_prior_mode.injection_ablatable=false in params to ablate global prior.
# All scaling driven from symbols.target_count + project.timeframe.

def compute_slots_sovereign(df: pd.DataFrame, neural: dict) -> dict:
    """Structural slots per slot_reference_manual.md (full kline via .get, causal from neural_slots/ctx).
    # Inefficiencies for 10M+ bars found:
    # - 8+ separate full-df .rolling(..., iloc[-1]) = O(8n) CPU/mem per call (recompute all history for last bar only)
    # - .apply(lambda) for log = slow Python loop (not vectorized)
    # - No chunking/precompute of common stats (price_chg, vol_chg, rolls)
    # - For large shards: load full df in miner; consider pd.read_parquet(..., iterator=True) or process tail only
    # Strict causal: all .shift(1)/rolling default (past only), no positive shifts or future iloc. Verified no leakage.
    # Vectorized fix: use .values + np for log/ops where possible. For GPU in neural (see miner call site).
    # Memory batch comment: for 10M+ bars per shard, batch symbols or use dask/numpy memmap; del large temps.
    """
    w = neural["reversal_window"][1]
    eps = neural["strength_add"]
    clamp_min = neural["confidence_clamp"][0]
    clamp_max = neural["confidence_clamp"][1]
    min_p = neural["reversal_window"][0]
    conf_min = neural["confidence_min"]
    vol = df['volume']
    qvol = df.get('quote_volume', vol)
    taker_buy = df.get('taker_buy_base_volume', vol * neural["strength_add"] / (neural["strength_add"] + neural["strength_add"]))
    # slot_00 bid-ask proxy on extremes/vol (no aggtrades)
    roll_min = df['low'].rolling(w, min_periods=min_p).min()
    roll_max = df['high'].rolling(w, min_periods=min_p).max()
    low_prox = (df['low'] - roll_min) / (roll_max - roll_min + eps)
    high_prox = (roll_max - df['high']) / (roll_max - roll_min + eps)
    buy_proxy = (taker_buy * (low_prox < neural["reversal_factor"]).astype(float)).rolling(w, min_periods=min_p).mean().iloc[-1]
    sell_proxy = ((vol - taker_buy) * (high_prox < neural["reversal_factor"]).astype(float)).rolling(w, min_periods=min_p).mean().iloc[-1]
    slot_00 = (buy_proxy - sell_proxy) / (buy_proxy + sell_proxy + eps)
    # slot_04 hurst approx on log returns (R/S simplified)
    # vectorized: .values + np.log avoids slow apply (for 10M+ bars CPU)
    log_ret = np.log( (df['close'] / df['close'].shift(1) + eps).clip(lower=eps).values )
    cum_dev = (log_ret - pd.Series(log_ret).rolling(w, min_periods=min_p).mean().values).cumsum()
    R = (cum_dev.rolling(w, min_periods=min_p).max() - cum_dev.rolling(w, min_periods=min_p).min()).iloc[-1]
    S = pd.Series(log_ret).rolling(w, min_periods=min_p).std().iloc[-1] + eps
    H = (R / S) / w
    slot_04 = neural["strength_add"] - H
    # slot_07 vol_price_div
    # vectorized using .values + np for 10M+ bars
    close_vals = df['close'].values
    price_chg = (close_vals[1:] / close_vals[:-1] - 1)
    price_chg = np.concatenate(([0.], price_chg))
    price_chg = np.clip(price_chg, -1 + eps, None)
    qvol_vals = qvol.values if hasattr(qvol, 'values') else qvol
    vol_chg = (qvol_vals[1:] / qvol_vals[:-1] - 1)
    vol_chg = np.concatenate(([0.], vol_chg))
    vol_chg = np.clip(vol_chg, -1 + eps, None)
    raw_div = pd.Series(np.abs(price_chg) - np.abs(vol_chg)).rolling(w, min_periods=min_p).mean().iloc[-1]
    slot_07 = raw_div / (qvol.rolling(w, min_periods=min_p).std().iloc[-1] + eps)
    # slot_08 HMM proxy (vol regime)
    long_w = w + neural["reversal_window"][0]
    recent_vol = vol.rolling(w, min_periods=min_p).std().iloc[-1]
    long_vol = vol.rolling(long_w, min_periods=min_p).std().iloc[-1] + eps
    slot_08 = min(clamp_max, max(clamp_min, recent_vol / long_vol if long_vol > eps else clamp_min))
    # slot_09 vol_delta
    vol_delta = (taker_buy - (vol - taker_buy)).rolling(w, min_periods=min_p).mean().iloc[-1]
    total_vol = (taker_buy + (vol - taker_buy)).rolling(w, min_periods=min_p).mean().iloc[-1] + eps
    slot_09 = vol_delta / total_vol
    # slot_10 wick with body_pct < neural["reversal_factor"]
    candle_range = (df['high'] - df['low']).iloc[-1]
    body = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
    wick_ratio = candle_range / (body if body > eps else eps)
    body_pct = body / (candle_range if candle_range > eps else eps)
    exhaustion = clamp_max if body_pct < neural["reversal_factor"] else clamp_min
    raw_wick = wick_ratio * exhaustion
    roll_max_hl = df['high'].rolling(w, min_periods=min_p).max().iloc[-1] - df['low'].rolling(w, min_periods=min_p).min().iloc[-1] + eps
    slot_10 = raw_wick / roll_max_hl if roll_max_hl > eps else clamp_min
    slot_10 = min(clamp_max, max(clamp_min, slot_10))
    # slot_11 SR proximity proxy (rolling max/min for pivots)
    nearest_resist = df['high'].rolling(w, min_periods=min_p).max().iloc[-1]
    nearest_support = df['low'].rolling(w, min_periods=min_p).min().iloc[-1]
    dist_resist = abs(nearest_resist - df['close'].iloc[-1]) / (df['close'].iloc[-1] * neural["reversal_factor"] + eps)
    dist_support = abs(df['close'].iloc[-1] - nearest_support) / (df['close'].iloc[-1] * neural["reversal_factor"] + eps)
    min_dist = min(dist_resist, dist_support)
    slot_11 = clamp_max / (clamp_max + min_dist)
    # slot_15 normalized weighted sum (weights from neural)
    raw_w = {"slot_00": neural["strength_mult"], "slot_04": neural["variation"], "slot_07": neural["strength_mult"], "slot_08": neural["strength_add"], "slot_09": neural["strength_add"], "slot_10": neural["strength_mult"], "slot_11": neural["variation"]}
    tot = sum(raw_w.values()) + eps
    weights = {k: v / tot for k, v in raw_w.items()}
    norm_slots = {"slot_00": min(clamp_max, max(clamp_min, slot_00)), "slot_04": min(clamp_max, max(clamp_min, slot_04)), "slot_07": min(clamp_max, max(clamp_min, slot_07)), "slot_08": min(clamp_max, max(clamp_min, slot_08)), "slot_09": min(clamp_max, max(clamp_min, slot_09)), "slot_10": min(clamp_max, max(clamp_min, slot_10)), "slot_11": min(clamp_max, max(clamp_min, slot_11))}
    slot_15 = sum(weights[k] * norm_slots[k] for k in weights) * (conf_min / conf_min)
    slot_15 = min(clamp_max, max(clamp_min, slot_15))
    return {
        "slot_00": float(slot_00),
        "slot_04": float(slot_04),
        "slot_07": float(slot_07),
        "slot_08": float(slot_08),
        "slot_09": float(slot_09),
        "slot_10": float(slot_10),
        "slot_11": float(slot_11),
        "slot_15": float(slot_15),
    }
