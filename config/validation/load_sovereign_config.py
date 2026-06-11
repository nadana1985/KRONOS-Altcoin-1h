"""
Sovereign Config Loader for KRONOS V1-ALT.

Single entrypoint for reading the params file (storage.params_file).
Enforces YAML anchor resolution and custom !join tag.
WARNING: Never import values directly from the params file —
          always go through this loader to preserve single-source-of-truth.
"""

import os
import yaml
from typing import Any, Dict


def join_constructor(loader: yaml.SafeLoader, node: yaml.SequenceNode) -> str:
    """Resolves !join [anchor, "/suffix"] into concatenated string."""
    parts = loader.construct_sequence(node)
    return "".join(str(p) for p in parts)


# Register custom !join tag on the SafeLoader
yaml.SafeLoader.add_constructor("!join", join_constructor)


def load_sovereign_config(path: str = None) -> Dict[str, Any]:
    """
    Load the params file and return resolved config dict.

    All YAML anchors and custom tags are resolved at load time.
    The returned dict is a plain Python dict — no YAML objects leak through.
    Phase 0: structural veto + dual-mode bootstrap (individual primary + global ablatable).

    Args:
        path: Path to the params file. If None, uses the env var declared in params (cfg-driven).

    Returns:
        Fully resolved config dictionary.
    """
    if path is None:
        path = os.getenv("KRONOS_PARAMS_PATH")
        if path is None:
            raise ValueError(
                "KRONOS_PARAMS_PATH environment variable must be set to the absolute path of the params file. "
                "See the params file for the declared env var name. "
                "This makes config loading fully cfg-driven."
            )

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Sovereign config not found at {path}. "
            "The params file (storage.params_file in params) is the single source of truth — it must exist."
        )

    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    try:
        cfg: Dict[str, Any] = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise ValueError(
            f"The params file at {path} failed YAML validation. "
            "Run validate_sovereignty.py to diagnose.\n"
            f"Error: {e}"
        )

    if cfg is None:
        raise ValueError("The params file is empty. Must contain at least a `project` key.")

    resolved = _resolve_anchors(cfg)

    return resolved


def _resolve_anchors(cfg: Dict[str, Any], _seen: set = None) -> Dict[str, Any]:
    """
    Post-process: flatten any residual YAML anchor references.
    safe_load already resolves *anchors, but we ensure the output
    contains no YAML-specific types (e.g. Anchor, ScalarNode).
    """
    if _seen is None:
        _seen = set()
    _id = id(cfg)
    if _id in _seen:
        return cfg
    _seen.add(_id)

    result: Dict[str, Any] = {}
    for k, v in cfg.items():
        if isinstance(v, dict):
            result[k] = _resolve_anchors(v, _seen)
        elif isinstance(v, list):
            result[k] = [
                _resolve_anchors(item, _seen) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            result[k] = v
    return result


def get_storage_path(cfg: Dict[str, Any], key: str) -> str:
    """
    Resolve a storage path from config, ensuring the base exists.

    Args:
        cfg: Config dict from load_sovereign_config()
        key: Storage key (e.g. 'raw_shards_dir', 'signatures_individual_dir')

    Returns:
        Resolved path string.

    Raises:
        KeyError: If key missing from config.
    """
    storage = cfg["storage"]
    path = storage[key]
    if path is None:
        raise KeyError(
            f"Storage key '{key}' not found in params['storage']. "
            "Add it to the params file (see storage section) — never hardcode paths."
        )
    return os.path.normpath(str(path))


TIMEFRAME_MS_MAP: Dict[str, int] = {
    "1m": 60 * 1000,
    "3m": 3 * 60 * 1000,
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "30m": 30 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "2h": 2 * 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "6h": 6 * 60 * 60 * 1000,
    "8h": 8 * 60 * 60 * 1000,
    "12h": 12 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
    "3d": 3 * 24 * 60 * 60 * 1000,
    "1w": 7 * 24 * 60 * 60 * 1000,
}


def get_timeframe_ms(timeframe_str: str, cfg: Dict[str, Any] = None) -> int:
    """Resolve timeframe string into milliseconds using project config or default map."""
    if cfg and "time_constants" in cfg:
        tc = cfg["time_constants"]
        unit = timeframe_str[-1]
        try:
            val = int(timeframe_str[:-1])
            multipliers = tc.get("unit_multipliers", {})
            if unit in multipliers:
                return val * multipliers[unit] * tc.get("ms_per_second", 1000)
        except Exception:
            pass
    return TIMEFRAME_MS_MAP.get(timeframe_str, 3600000)


if __name__ == "__main__":
    cfg = load_sovereign_config()
    print("=== Sovereign Config Loaded ===")
    print(f"Project: {cfg['project']['name']}")
    print(f"Storage base: {cfg['storage']['base_path']}")
    print(f"Individual mode enabled: {cfg['individual_mode']['enabled']}")
    print(f"Symbols target: {cfg['symbols']['target_count']}")
    print("================================")