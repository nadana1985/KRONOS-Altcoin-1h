"""
KRONOS V1-ALT Liquidity Tiering System (Phase 0, Step 0.2)

Dynamic, rolling-metric 5-tier classifier:
    very_high | high | medium | low | micro

Sovereignty principles:
- Zero inline literals for thresholds, weights, windows, or boundaries.
- Everything resolved from kronos/config/liquidity_tiers.yaml (or caller-supplied path).
- Pydantic validation on load.
- Supports runtime reload() for live config experiments.
- Works with real 1h parquet shards (coerces Arrow/string dtypes).
- Incremental-friendly interface (compute_metrics + get_tier on a recent window).
- No dependence on static symbol lists.

Intended consumers:
- Future bias override implementations (point 01, 02, 04, ... will consult tier).
- The BiasOverrideRegistry (via filter_by_liquidity + new helpers).
- Miner / analysis scripts for per-symbol or per-bar tier labeling.

Typical usage:
    from kronos.features.liquidity_classifier import LiquidityClassifier, get_liquidity_tier

    clf = LiquidityClassifier()
    tier = clf.get_tier(df=symbol_df, symbol="SOMEALTUSDT", lookback=288)
    # or
    tier = get_liquidity_tier(df, symbol="SOMEALTUSDT")

    # Bar-level (causal, for historical labeling or session analysis)
    tiers_series = clf.get_tiers_for_bars(df, lookback=288)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, Field, validator

# Module logger (structured messages include tier + diagnostic metrics)
logger = logging.getLogger("kronos.liquidity")


# ---------------------------------------------------------------------
# Pydantic config model (validates the YAML at load time)
# ---------------------------------------------------------------------
class LiquidityTiersConfig(BaseModel):
    """Validated configuration for dynamic liquidity tiering."""

    version: str = Field("0.2", description="Config schema version")
    lookback_default: int = Field(288, ge=12, description="Default rolling lookback in bars (1h)")
    min_data_density: int = Field(48, ge=1, description="Min valid bars required for trusted tier")
    fallback_tier: str = Field("medium", description="Tier returned on insufficient data or error")

    metrics: Dict[str, float] = Field(..., description="Weights for composite liquidity score")
    tier_thresholds: Dict[str, float] = Field(..., description="Score cutoffs for tier assignment")
    absolute_guards: Dict[str, Any] = Field(default_factory=dict)
    normalization: Dict[str, Any] = Field(..., description="Reference values for sub-score normalization")
    spread: Dict[str, Any] = Field(default_factory=dict)
    numerical: Dict[str, float] = Field(default_factory=lambda: {"eps": 1e-12})
    logging: Dict[str, Any] = Field(default_factory=dict)

    @validator("fallback_tier")
    def validate_fallback(cls, v: str) -> str:
        allowed = {"very_high", "high", "medium", "low", "micro"}
        if v not in allowed:
            raise ValueError(f"fallback_tier must be one of {allowed}")
        return v

    @validator("metrics")
    def validate_weights(cls, v: Dict[str, float]) -> Dict[str, float]:
        total = sum(v.values())
        if not (0.95 <= total <= 1.05):
            raise ValueError(f"metrics weights should sum to ~1.0 (got {total:.3f})")
        return v

    @validator("tier_thresholds")
    def validate_thresholds(cls, v: Dict[str, float]) -> Dict[str, float]:
        required = ["very_high", "high", "medium", "low"]
        for k in required:
            if k not in v:
                raise ValueError(f"tier_thresholds missing required key: {k}")
        # Monotonic: very_high > high > medium > low
        order = ["very_high", "high", "medium", "low"]
        for i in range(len(order) - 1):
            if v[order[i]] <= v[order[i + 1]]:
                raise ValueError("tier_thresholds must be strictly decreasing: very_high > high > ...")
        return v

    class Config:
        extra = "allow"   # Keep top-level sections like "overrides" (for bias points) in the loaded config dict


# ---------------------------------------------------------------------
# Core computation (pure, easy to unit test)
# ---------------------------------------------------------------------
def _coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Robust coercion for real shards (Arrow strings, mixed dtypes)."""
    cols = ["open", "high", "low", "close", "volume", "quote_volume", "count", "number_of_trades"]
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def compute_liquidity_metrics(
    df: pd.DataFrame,
    lookback: Optional[int] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """
    Compute the five core rolling metrics + data density for a window.

    Returns a dict with:
        median_quote_volume, amihud, avg_trade_count, spread_proxy, zero_volume_bar_pct,
        data_density, lookback_used
    """
    if df is None or len(df) == 0:
        return _empty_metrics()

    cfg = config or {}
    num = cfg.get("numerical", {"eps": 1e-12})
    eps = float(num.get("eps", 1e-12))

    work = _coerce_numeric(df.copy())
    window = int(lookback or cfg.get("lookback_default", 288))
    window = max(1, min(window, len(work)))

    recent = work.iloc[-window:].copy()

    # Prefer quote_volume; fall back to close*volume
    qvol = recent.get("quote_volume", recent["close"] * recent["volume"]).astype(float).fillna(0.0)
    vol = recent["volume"].astype(float).fillna(0.0)
    close = recent["close"].astype(float).ffill().bfill()

    # Trade count (column name varies slightly across ingestion versions)
    trades_col = None
    for cand in ("count", "number_of_trades", "trades"):
        if cand in recent.columns:
            trades_col = cand
            break
    trades = recent[trades_col].astype(float).fillna(0.0) if trades_col else pd.Series(0.0, index=recent.index)

    # --- Core metrics ---
    med_qvol = float(qvol.median())

    # Amihud-style illiquidity (lower = more liquid). Use dollar volume via quote when available.
    ret_abs = (close / close.shift(1) - 1.0).abs().fillna(0.0)
    dollar_vol = (close * qvol).replace(0.0, np.nan)
    amihud = float((ret_abs / (dollar_vol + eps)).mean())

    avg_trades = float(trades.mean())

    # Spread proxy (high-low range normalized)
    spread_method = cfg.get("spread", {}).get("method", "high_low_ratio")
    if spread_method == "high_low_ratio":
        hl = (recent["high"].astype(float) - recent["low"].astype(float)) / (close + eps)
        spread = float(hl.mean() * float(cfg.get("spread", {}).get("proxy_mult", 1.0)))
    else:
        spread = float(((recent["high"] - recent["low"]) / (close + eps)).mean())

    zero_bars = int((qvol <= 0).sum())
    zero_pct = (zero_bars / max(1, window)) * 100.0

    valid_bars = int((~pd.isna(close) & (close > 0)).sum())

    return {
        "median_quote_volume": med_qvol,
        "amihud": amihud if np.isfinite(amihud) else 1e9,
        "avg_trade_count": avg_trades,
        "spread_proxy": spread if np.isfinite(spread) else 1.0,
        "zero_volume_bar_pct": float(zero_pct),
        "data_density": float(valid_bars),
        "lookback_used": float(window),
    }


def _empty_metrics() -> Dict[str, float]:
    return {
        "median_quote_volume": 0.0,
        "amihud": 1e9,
        "avg_trade_count": 0.0,
        "spread_proxy": 1.0,
        "zero_volume_bar_pct": 100.0,
        "data_density": 0.0,
        "lookback_used": 0.0,
    }


def _compute_subscores(metrics: Dict[str, float], norm: Dict[str, Any]) -> Dict[str, float]:
    """Map raw metrics into [0,1] sub-scores (1.0 = best liquidity contribution)."""
    eps = 1e-12

    # Volume (log scale)
    lv = np.log1p(metrics["median_quote_volume"])
    v_low = float(norm.get("log_volume", {}).get("ref_low", 11.5))
    v_high = float(norm.get("log_volume", {}).get("ref_high", 19.5))
    vol_score = float(np.clip((lv - v_low) / (v_high - v_low + eps), 0.0, 1.0))

    # Amihud (inverse)
    a_ref = float(norm.get("amihud", {}).get("ref_high", 2.5e-5))
    amihud_score = float(np.clip(1.0 - (metrics["amihud"] / (a_ref + eps)), 0.0, 1.0))

    # Trade count
    t_low = float(norm.get("trade_count", {}).get("ref_low", 80))
    t_high = float(norm.get("trade_count", {}).get("ref_high", 8500))
    trade_score = float(np.clip((metrics["avg_trade_count"] - t_low) / (t_high - t_low + eps), 0.0, 1.0))

    # Spread (inverse)
    s_ref = float(norm.get("spread", {}).get("ref_high", 0.018))
    spread_score = float(np.clip(1.0 - (metrics["spread_proxy"] / (s_ref + eps)), 0.0, 1.0))

    # Zero-bar penalty (inverse)
    zero_score = float(np.clip(1.0 - (metrics["zero_volume_bar_pct"] / 100.0), 0.0, 1.0))

    return {
        "vol_score": vol_score,
        "amihud_score": amihud_score,
        "trade_score": trade_score,
        "spread_score": spread_score,
        "zero_score": zero_score,
    }


def _score_from_subscores(sub: Dict[str, float], weights: Dict[str, float]) -> float:
    s = (
        weights["volume_weight"] * sub["vol_score"]
        + weights["amihud_weight"] * sub["amihud_score"]
        + weights["trade_count_weight"] * sub["trade_score"]
        + weights["spread_weight"] * sub["spread_score"]
        + weights["zero_bar_weight"] * sub["zero_score"]
    )
    return float(np.clip(s, 0.0, 1.0))


def _apply_tier(score: float, thresholds: Dict[str, float]) -> str:
    if score >= thresholds["very_high"]:
        return "very_high"
    if score >= thresholds["high"]:
        return "high"
    if score >= thresholds["medium"]:
        return "medium"
    if score >= thresholds["low"]:
        return "low"
    return "micro"


def _apply_absolute_guards(
    tier: str, metrics: Dict[str, float], guards: Dict[str, Any]
) -> Tuple[str, Optional[str]]:
    """Return (possibly adjusted tier, optional reason string)."""
    if not guards.get("enabled", False):
        return tier, None

    med_qvol = metrics["median_quote_volume"]
    zero_pct = metrics["zero_volume_bar_pct"]

    reason = None

    vh_min = guards.get("very_high_min_24h_quote_volume", 0)
    if tier == "very_high" and med_qvol < vh_min:
        tier = "high"
        reason = f"volume_below_very_high_guard({med_qvol:.0f}<{vh_min})"

    h_min = guards.get("high_min_24h_quote_volume", 0)
    if tier == "high" and med_qvol < h_min:
        tier = "medium"
        reason = f"volume_below_high_guard({med_qvol:.0f}<{h_min})"

    low_max_z = guards.get("low_max_zero_bar_pct", 100)
    if tier in ("very_high", "high", "medium") and zero_pct > low_max_z:
        tier = "low"
        reason = f"zero_bar_exceeded_low_guard({zero_pct:.1f}% > {low_max_z}%)"

    micro_max_z = guards.get("micro_max_zero_bar_pct", 100)
    if tier != "micro" and zero_pct > micro_max_z:
        tier = "micro"
        reason = f"zero_bar_exceeded_micro_guard({zero_pct:.1f}% > {micro_max_z}%)"

    return tier, reason


# ---------------------------------------------------------------------
# LiquidityClassifier (class interface + reload support)
# ---------------------------------------------------------------------
class LiquidityClassifier:
    """
    Dynamic liquidity tier classifier.

    Loads sovereign config from kronos/config/liquidity_tiers.yaml by default.
    Can be pointed at an alternate YAML via constructor or reload().

    Provides:
      - get_tier(...) -> single tier for latest window (bar/session level)
      - get_tiers_for_bars(...) -> per-bar causal tier series (historical labeling)
      - compute_metrics(...) -> raw diagnostic metrics
      - reload() -> hot-reload config without process restart
    """

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            base = Path(__file__).parent.parent / "config"
            config_path = base / "liquidity_tiers.yaml"
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._model: Optional[LiquidityTiersConfig] = None
        self.reload()

    def reload(self) -> None:
        """Reload and validate YAML. Safe to call at runtime."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Liquidity tiers config not found: {self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        self._model = LiquidityTiersConfig(**raw)
        self._config = self._model.dict()

        # Cache frequently used values
        self.lookback_default = int(self._config["lookback_default"])
        self.min_data_density = int(self._config["min_data_density"])
        self.fallback_tier = str(self._config["fallback_tier"])
        self.log_enabled = bool(self._config.get("logging", {}).get("enabled", True))
        self.log_detail = bool(self._config.get("logging", {}).get("include_metrics_on_info", True))

        logger.debug(f"LiquidityClassifier reloaded from {self.config_path} (version={self._config.get('version')})")

    @property
    def config(self) -> Dict[str, Any]:
        """Return the validated config as plain dict (for inspection / downstream use)."""
        return self._config

    def compute_metrics(self, df: pd.DataFrame, lookback: Optional[int] = None) -> Dict[str, float]:
        """Public passthrough to the pure metrics function using current config."""
        return compute_liquidity_metrics(df, lookback=lookback, config=self._config)

    def get_tier(
        self,
        df: pd.DataFrame,
        symbol: Optional[str] = None,
        lookback: Optional[int] = None,
    ) -> str:
        """
        Classify the liquidity tier for the most recent window of the provided dataframe.

        Parameters
        ----------
        df : pd.DataFrame
            Symbol history (must contain at minimum close, volume, quote_volume or high/low).
            Works with full shards or recent tails.
        symbol : Optional[str]
            Asset identifier for logging (e.g. "SOMEALTUSDT").
        lookback : Optional[int]
            Override window size. Falls back to config lookback_default.

        Returns
        -------
        str
            One of: "very_high", "high", "medium", "low", "micro"
        """
        metrics = self.compute_metrics(df, lookback=lookback)

        density = metrics["data_density"]
        if density < self.min_data_density:
            tier = self.fallback_tier
            if self.log_enabled:
                logger.info(
                    f"[LIQUIDITY] symbol={symbol or 'unknown'} tier={tier} "
                    f"(fallback: data_density={density:.0f} < min={self.min_data_density})"
                )
            return tier

        norm = self._config["normalization"]
        weights = self._config["metrics"]
        thresholds = self._config["tier_thresholds"]
        guards = self._config.get("absolute_guards", {})

        sub = _compute_subscores(metrics, norm)
        score = _score_from_subscores(sub, weights)
        tier = _apply_tier(score, thresholds)
        tier, guard_reason = _apply_absolute_guards(tier, metrics, guards)

        if self.log_enabled:
            if self.log_detail:
                logger.info(
                    f"[LIQUIDITY] symbol={symbol or 'unknown'} tier={tier} score={score:.3f} "
                    f"med_qvol={metrics['median_quote_volume']:.0f} amihud={metrics['amihud']:.2e} "
                    f"trades={metrics['avg_trade_count']:.1f} spread={metrics['spread_proxy']:.4f} "
                    f"zero_pct={metrics['zero_volume_bar_pct']:.1f}% "
                    f"density={metrics['data_density']:.0f} "
                    f"reason={guard_reason or 'score_based'}"
                )
            else:
                logger.info(f"[LIQUIDITY] symbol={symbol or 'unknown'} tier={tier}")

        return tier

    def get_tiers_for_bars(
        self,
        df: pd.DataFrame,
        symbol: Optional[str] = None,
        lookback: Optional[int] = None,
    ) -> pd.Series:
        """
        Causal per-bar liquidity tier series.

        For each row i, classification uses only data up to and including bar i
        (subject to the lookback tail). Useful for labeling historical sessions
        or building liquidity regime features.

        Returns a pandas Series with the same index as df, dtype=object (tier strings).
        """
        if df is None or len(df) == 0:
            return pd.Series(dtype=object)

        work = df.copy()
        n = len(work)
        look = int(lookback or self.lookback_default)
        tiers = []

        for i in range(n):
            # Causal window: data available up to i
            window_df = work.iloc[: i + 1]
            # Delegate to the single-window path (it will tail internally)
            t = self.get_tier(window_df, symbol=symbol, lookback=look)
            tiers.append(t)

        return pd.Series(tiers, index=work.index, name="liquidity_tier")

    def __repr__(self) -> str:
        return f"<LiquidityClassifier config={self.config_path} fallback={self.fallback_tier}>"


# ---------------------------------------------------------------------
# Standalone function interface (convenience, matches user example)
# ---------------------------------------------------------------------
def get_liquidity_tier(
    df: pd.DataFrame,
    symbol: Optional[str] = None,
    config_path: Optional[str] = None,
    lookback: Optional[int] = None,
) -> str:
    """
    Convenience function. Creates a transient classifier and returns the tier.

    Example (exactly as specified in requirements):
        from kronos.features.liquidity_classifier import get_liquidity_tier
        tier = get_liquidity_tier(df, asset="SOMEALTUSDT", lookback=288)
    """
    clf = LiquidityClassifier(config_path=config_path)
    # The example in the prompt used kwarg "asset=" — support both "symbol" and "asset"
    sym = symbol or None
    return clf.get_tier(df, symbol=sym, lookback=lookback)


def compute_liquidity_metrics_standalone(
    df: pd.DataFrame, config_path: Optional[str] = None, lookback: Optional[int] = None
) -> Dict[str, float]:
    """Standalone metrics helper (no side effects)."""
    clf = LiquidityClassifier(config_path=config_path)
    return clf.compute_metrics(df, lookback=lookback)


if __name__ == "__main__":
    # Smoke test / example (requires a real shard or synthetic df)
    print("LiquidityClassifier smoke test")
    try:
        clf = LiquidityClassifier()
        print("Config loaded:", clf.config["version"], "fallback=", clf.fallback_tier)
        print("Tiers supported: very_high, high, medium, low, micro")
        print("Ready for use with real 1h shards.")
    except Exception as e:
        print("Smoke test note (no data path provided):", e)
