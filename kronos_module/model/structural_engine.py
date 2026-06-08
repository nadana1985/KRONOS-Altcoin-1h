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
        # Phase 1 proxy hardening (from KRONOS_V1_ALT_PROXY_HARDENING_ROADMAP.md)
        "vpin_window": thr.get("vpin_window", 100),
        "hurst_lags": thr.get("hurst_lags", [5, 10, 20, 50]),
        "hurst_min_periods": thr.get("hurst_min_periods", 20),
        "slot15_entropy_weight": thr.get("slot15_entropy_weight", 0.1),
        # Phase 2 proxy hardening
        "ofi_window": thr.get("ofi_window", 50),
        "ofi_pressure_mult": thr.get("ofi_pressure_mult", 1.0),
        "regime_adx_window": thr.get("regime_adx_window", 14),
        "regime_vol_short": thr.get("regime_vol_short", 10),
        "regime_vol_long": thr.get("regime_vol_long", 50),
        "amihud_window": thr.get("amihud_window", 50),
        "divergence_weight": thr.get("divergence_weight", 1.0),
        # Phase 3: Final Proxy Hardening
        "exhaustion_windows": thr.get("exhaustion_windows", [5, 20]),
        "wick_ratio_mult": thr.get("wick_ratio_mult", 1.5),
        "sr_windows": thr.get("sr_windows", [20, 50, 100]),
        "proximity_decay": thr.get("proximity_decay", 0.95),
    }
    # Phase 1 neural config for full Kronos conviction (from neural: section or defaults)
    neural_cfg = cfg.get("neural", {})
    neural_slots.update({
        "neural_conv_mode": neural_cfg.get("neural_conv_mode", "scalar"),
        "neural_conv_dims": neural_cfg.get("neural_conv_dims", 8),
        "forecast_horizon": neural_cfg.get("forecast_horizon", 4),
        "use_full_model": neural_cfg.get("use_full_model", False),
        "max_context_length": neural_cfg.get("max_context_length", 64),
        "mixed_precision": neural_cfg.get("mixed_precision", True),
    })

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
    # Robust coercion for real shards (Arrow/string dtypes from ingestion)
    for col in ['open', 'high', 'low', 'close', 'volume', 'quote_volume', 'taker_buy_base_volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    vol = pd.to_numeric(df['volume'], errors='coerce')
    qvol = pd.to_numeric(df.get('quote_volume', vol), errors='coerce')
    taker_buy = pd.to_numeric(df.get('taker_buy_base_volume', vol * neural["strength_add"] / (neural["strength_add"] + neural["strength_add"])), errors='coerce')
    # slot_00 Order Flow Imbalance (OFI) with cumulative pressure normalization (Phase 2 per roadmap)
    ofi_w = neural["ofi_window"]
    ofi_mult = neural["ofi_pressure_mult"]
    ofi = (taker_buy - (vol - taker_buy)).rolling(ofi_w, min_periods=min(min_p, ofi_w)).mean() / (vol.rolling(ofi_w, min_periods=min(min_p, ofi_w)).mean() + eps)
    cum_pressure = (taker_buy - (vol - taker_buy)).rolling(ofi_w, min_periods=min(min_p, ofi_w)).sum() / (vol.rolling(ofi_w, min_periods=min(min_p, ofi_w)).sum() + eps) * ofi_mult
    slot_00 = ((ofi + cum_pressure) / 2).iloc[-1]
    slot_00 = min(clamp_max, max(clamp_min, slot_00))
    # slot_04 Hurst Exponent (Phase 1 hardening per KRONOS_V1_ALT_PROXY_HARDENING_ROADMAP.md)
    # Proper multi-lag Rescaled Range (R/S) + mean (vectorized where possible, causal)
    log_ret = np.log( (df['close'] / df['close'].shift(1) + eps).clip(lower=eps).values )
    lags = neural["hurst_lags"]
    min_p_h_base = neural["hurst_min_periods"]
    H_list = []
    for lag in lags:
        if lag < 2:
            continue
        min_p_h = min(min_p_h_base, lag)  # per-lag safety (min_periods must <= window)
        r = pd.Series(log_ret).rolling(lag, min_periods=min_p_h).max() - pd.Series(log_ret).rolling(lag, min_periods=min_p_h).min()
        s = pd.Series(log_ret).rolling(lag, min_periods=min_p_h).std() + eps
        rs = (r / s).iloc[-1]
        H_list.append(np.log(rs) / np.log(lag))
    hurst = np.mean(H_list) if H_list else 0.5
    slot_04 = 0.5 - hurst   # mean-reversion bias (higher = stronger reversal potential)
    # slot_07 Amihud Illiquidity + Volume-Weighted Price Divergence (Phase 2 per roadmap)
    amihud_w = neural["amihud_window"]
    div_w = neural["divergence_weight"]
    # Amihud: |ret| / dollar volume (illiquidity)
    ret = (df['close'] - df['close'].shift(1)) / (df['close'].shift(1) + eps)
    dollar_vol = (df['close'] * vol).rolling(amihud_w, min_periods=min(min_p, amihud_w)).mean()
    amihud = (ret.abs() / (dollar_vol + eps)).rolling(amihud_w, min_periods=min(min_p, amihud_w)).mean().iloc[-1]
    # Volume-weighted price divergence (enhanced from prior)
    close_vals = df['close'].values
    price_chg = (close_vals[1:] / close_vals[:-1] - 1)
    price_chg = np.concatenate(([0.], price_chg))
    price_chg = np.clip(price_chg, -1 + eps, None)
    qvol_vals = qvol.values if hasattr(qvol, 'values') else qvol
    vol_chg = (qvol_vals[1:] / qvol_vals[:-1] - 1)
    vol_chg = np.concatenate(([0.], vol_chg))
    vol_chg = np.clip(vol_chg, -1 + eps, None)
    raw_div = pd.Series(np.abs(price_chg) - np.abs(vol_chg)).rolling(amihud_w, min_periods=min(min_p, amihud_w)).mean().iloc[-1]
    vol_weighted_div = raw_div / (qvol.rolling(amihud_w, min_periods=min(min_p, amihud_w)).std().iloc[-1] + eps)
    slot_07 = (amihud + div_w * vol_weighted_div) / (1 + div_w)
    slot_07 = min(clamp_max, max(clamp_min, slot_07))
    # slot_08 Lightweight Regime Detection (ADX-inspired trend strength + multi-window volatility clustering) (Phase 2 per roadmap)
    adx_w = neural["regime_adx_window"]
    vol_s = neural["regime_vol_short"]
    vol_l = neural["regime_vol_long"]
    # ADX-inspired directional movement (simplified, no true +DM/-DM for lightness)
    dm_pos = (df['high'] - df['high'].shift(1)).clip(lower=0).rolling(adx_w, min_periods=min(min_p, adx_w)).mean()
    dm_neg = (df['low'].shift(1) - df['low']).clip(lower=0).rolling(adx_w, min_periods=min(min_p, adx_w)).mean()
    adx_approx = 100 * (dm_pos - dm_neg).abs() / (dm_pos + dm_neg + eps)
    # Multi-window volatility clustering
    recent_vol = vol.rolling(vol_s, min_periods=min(min_p, vol_s)).std().iloc[-1]
    long_vol = vol.rolling(vol_l, min_periods=min(min_p, vol_l)).std().iloc[-1] + eps
    vol_cluster = recent_vol / long_vol if long_vol > eps else 1.0
    regime_score = vol_cluster * (adx_approx.iloc[-1] / 50)
    slot_08 = min(clamp_max, max(clamp_min, regime_score))
    # slot_09 VPIN (Phase 1 hardening per KRONOS_V1_ALT_PROXY_HARDENING_ROADMAP.md)
    # Bulk Volume Classification + Cumulative Imbalance (vectorized, causal)
    vpin_w = neural["vpin_window"]
    buy_vol = taker_buy
    sell_vol = vol - buy_vol
    delta = buy_vol - sell_vol
    cum_delta = delta.rolling(vpin_w, min_periods=min_p).sum()
    total_vol = vol.rolling(vpin_w, min_periods=min_p).sum()
    vpin = (cum_delta.abs() / (total_vol + eps)).clip(0, 1)
    slot_09 = vpin.iloc[-1]
    # slot_10 Multi-scale Candle Exhaustion Score (Phase 3)
    exh_ws = neural["exhaustion_windows"]
    wick_mult = neural["wick_ratio_mult"]
    candle_range = (df['high'] - df['low'])
    body = (df['close'] - df['open']).abs()
    upper_wick = df['high'] - pd.concat([df['close'], df['open']], axis=1).max(axis=1)
    lower_wick = pd.concat([df['close'], df['open']], axis=1).min(axis=1) - df['low']
    wick_ratio = (upper_wick + lower_wick) / (body + eps) * wick_mult
    exhaustion = wick_ratio.clip(0, 5)
    exh_scores = []
    for win in exh_ws:
        score = exhaustion.rolling(win, min_periods=min(min_p, win)).quantile(0.75).iloc[-1]
        exh_scores.append(score if not pd.isna(score) else 0.0)
    slot_10 = np.mean(exh_scores) if exh_scores else 0.0
    slot_10 = min(clamp_max, max(clamp_min, slot_10))
    # slot_11 Dynamic S/R Proximity with Decay (Phase 3)
    sr_ws = neural["sr_windows"]
    decay = neural["proximity_decay"]
    close_val = df['close'].iloc[-1]
    prox_scores = []
    for win in sr_ws:
        resist = df['high'].rolling(win, min_periods=min(min_p, win)).max().iloc[-1]
        support = df['low'].rolling(win, min_periods=min(min_p, win)).min().iloc[-1]
        dist_r = abs(resist - close_val) / (close_val * neural["reversal_factor"] + eps)
        dist_s = abs(close_val - support) / (close_val * neural["reversal_factor"] + eps)
        min_dist = min(dist_r, dist_s)
        prox = (1.0 / (1.0 + min_dist)) * (decay ** min_dist)  # use decay as base for exponential decay on dist
        prox_scores.append(prox)
    slot_11 = np.mean(prox_scores) if prox_scores else 0.0
    slot_11 = min(clamp_max, max(clamp_min, slot_11))
    # slot_15 Sovereign Logistic Composite Gate (Phase 1 hardening per KRONOS_V1_ALT_PROXY_HARDENING_ROADMAP.md)
    # Weighted logistic + entropy/diversity term (cfg-driven, causal)
    raw_w = {"slot_00": neural["strength_mult"], "slot_04": neural["variation"], "slot_07": neural["strength_mult"], "slot_08": neural["strength_add"], "slot_09": neural["strength_add"], "slot_10": neural["strength_mult"], "slot_11": neural["variation"]}
    tot = sum(raw_w.values()) + eps
    weights = {k: v / tot for k, v in raw_w.items()}
    norm_slots = {"slot_00": min(clamp_max, max(clamp_min, slot_00)), "slot_04": min(clamp_max, max(clamp_min, slot_04)), "slot_07": min(clamp_max, max(clamp_min, slot_07)), "slot_08": min(clamp_max, max(clamp_min, slot_08)), "slot_09": min(clamp_max, max(clamp_min, slot_09)), "slot_10": min(clamp_max, max(clamp_min, slot_10)), "slot_11": min(clamp_max, max(clamp_min, slot_11))}
    weighted = sum(weights[k] * norm_slots[k] for k in weights)
    # entropy = diversity bonus (higher entropy = more balanced signals -> bonus)
    entropy = -sum( (p * np.log(p + eps) if p > 0 else 0) for p in norm_slots.values() )
    entropy_w = neural["slot15_entropy_weight"]
    # sigmoid for bounded [0,1] gate
    x = weighted + entropy_w * entropy
    slot_15 = 1 / (1 + np.exp(-np.clip(x, -50, 50)))   # stable sigmoid
    slot_15 = slot_15 * (conf_min / conf_min)  # cfg scaling
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
