"""
KRONOS V1-ALT — Global Override Config Cache (Performance Optimization)

Loads liquidity_tiers.yaml ONCE at module import time and caches it
so that individual point modules do NOT re-parse the YAML file
on every call. Eliminates ~2100 redundant YAML parses (42 points × 50 symbols).

Usage in any point module:

    from kronos.quant_spec.override_config_cache import get_point_config

    cfg = get_point_config("point_51")
    # cfg is a dict with that point's parameters

All point modules' _load_point_XX_config() should fallback to this cache
when the engine (BiasOverrideEngine.override_config) is not available or empty.
This ensures zero YAML file I/O after initialization.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger("kronos.override_config_cache")

# Module-level lock for thread-safe lazy loading
_lock = threading.Lock()
_config: Optional[Dict[str, Any]] = None
_override_config: Optional[Dict[str, Any]] = None


def _load_config(force_reload: bool = False) -> Dict[str, Any]:
    """Load liquidity_tiers.yaml once. Thread-safe."""
    global _config, _override_config
    if _config is not None and not force_reload:
        return _config

    with _lock:
        # Double-check after acquiring lock
        if _config is not None and not force_reload:
            return _config

        try:
            import yaml
            from pathlib import Path

            # Resolve path relative to this module
            base = Path(__file__).parent.parent / "config"
            yaml_path = base / "liquidity_tiers.yaml"

            if not yaml_path.exists():
                logger.warning(
                    "Config not found at %s — using empty config", yaml_path
                )
                _config = {}
                _override_config = {}
                return _config

            with open(yaml_path, "r", encoding="utf-8") as f:
                _config = yaml.safe_load(f) or {}

            _override_config = _config.get("overrides", {})

            n_points = len(_override_config)
            logger.info(
                "Override config cache loaded: %d point configs from %s",
                n_points,
                yaml_path,
            )
            return _config

        except Exception as e:
            logger.warning("Failed to load config cache: %s — using empty", e)
            _config = {}
            _override_config = {}
            return _config


def _normalize_point_key(point_id: str) -> str:
    """Accept either '51' or 'point_51' and return the YAML key."""
    key = str(point_id)
    if key.startswith("point_"):
        return key
    return f"point_{key.zfill(2)}"


def get_point_config(point_id: str) -> Dict[str, Any]:
    """
    Return the config dict for a specific override point.

    Parameter
    ---------
    point_id : str
        Zero-padded point ID (e.g. "51", "46", "01").

    Returns
    -------
    dict
        The point's config from liquidity_tiers.yaml, or {} if not found.
    """
    _load_config()
    return _override_config.get(_normalize_point_key(point_id), {}) if _override_config else {}


def get_all_override_config() -> Dict[str, Any]:
    """
    Return the full 'overrides' section from liquidity_tiers.yaml.
    Useful for diagnostics or batch operations.
    """
    _load_config()
    return _override_config or {}


def get_full_config() -> Dict[str, Any]:
    """Return the entire liquidity_tiers.yaml parsed content."""
    _load_config()
    return _config or {}


def reload_config() -> None:
    """Force reload the config cache at runtime (useful for hot-reload scenarios)."""
    _load_config(force_reload=True)
    logger.info("Override config cache reloaded")


def warm_config_cache() -> Dict[str, Any]:
    """Eagerly load the config cache during miner startup."""
    return get_all_override_config()


def get_cached_point_config_with_engine_fallback(
    point_id: str, engine: Any = None
) -> Dict[str, Any]:
    """
    Preference-ordered config resolution:
    1. BiasOverrideEngine.override_config (if engine is provided and has data)
    2. Global config cache (loaded once at import)

    This is the recommended pattern for all point modules.
    """
    # Try engine first (most authoritative)
    if engine is not None:
        try:
            cfg = engine.override_config.get(point_id, {})
            if cfg:
                return cfg
        except Exception:
            pass

    # Fallback to global cache (loaded once, no YAML I/O)
    return get_point_config(point_id)
