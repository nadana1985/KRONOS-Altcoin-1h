"""
KRONOS V1-ALT — Bias Override Point 91: "OS-Dependent Directory Path Configurations"

Manual description:
  "Hardcoding fixed, platform-specific directory paths (base_path: 'f:/kronos_v1_alt')
   causes execution failures on different operating systems."

Quant replacement:
  "OS-Agnostic Environment Path Resolution. Resolve paths dynamically at runtime
   using platform-neutral functions: Base_Path = Resolve_POSIX_Path(Env['KRONOS_ROOT'])."

Uses shared resolve_os_agnostic_path from utils.

This provides cross-platform deployment by resolving paths through environment
variables with POSIX normalization and intelligent fallbacks.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from kronos.quant_spec.bias_override_engine import BiasOverrideEngine
from kronos.quant_spec.overrides.utils import resolve_os_agnostic_path
from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback

logger = logging.getLogger("kronos.bias_override.point_91")



_DEFAULT_POINT_91_CONFIG = {
            "env_var": "KRONOS_ROOT",
            "fallback_path": ".",
            "subdirs": ["data", "logs", "output"],
            "min_data_density": 0,
        }


def resolve_project_paths(
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Resolve all critical project paths in an OS-agnostic manner.
    Returns a dict of named paths (root, data, logs, output, etc.).
    """
    cfg = config or {}
    env_var = cfg.get("env_var", "KRONOS_ROOT")
    fallback = cfg.get("fallback_path", ".")
    subdirs = cfg.get("subdirs", ["data", "logs", "output"])

    paths = {}
    # Use Path(__file__) fallback when env var is unset and fallback is relative
    resolved_root = resolve_os_agnostic_path(env_var, fallback)
    if not Path(resolved_root).is_absolute():
        # Resolve relative to this file's project root
        project_root = str(Path(__file__).resolve().parents[2])
        resolved_root = str(Path(project_root) / resolved_root.lstrip("./"))
    paths["root"] = resolved_root

    for subdir in subdirs:
        paths[subdir] = resolve_os_agnostic_path(
            env_var, fallback, relative_segments=[subdir]
        )

    logger.info(
        "[POINT_91] resolved paths | root=%s subdirs=%s",
        paths["root"],
        list(paths.keys()),
    )
    return paths


def compute_point_91_override(
    raw_path: str,
    df: pd.DataFrame,
    symbol: str,
    engine: Optional[BiasOverrideEngine] = None,
    **kwargs,
) -> str:
    """
    Wrapper for Point 91.
    raw_path: the legacy hardcoded path.
    Returns the resolved OS-agnostic path.
    """
    if engine is None:
        engine = BiasOverrideEngine()
    cfg = _load_point_91_config(engine)

    env_var = cfg.get("env_var", "KRONOS_ROOT")
    fallback = cfg.get("fallback_path", ".")

    new_val = resolve_os_agnostic_path(env_var, fallback)
    raw_val = str(raw_path) if raw_path else fallback

    final = engine.apply_override(
        point_id="91",
        raw_value=raw_val,
        override_value=new_val,
        df=df,
        symbol=symbol,
        **kwargs,
    )
    logger.debug("[POINT_91] decision | %s raw=%s final=%s", symbol, raw_val, final)
    return str(final)


def validate_path_permissions(paths: Dict[str, str]) -> Dict[str, Any]:
    """
    Validate that resolved paths are accessible (readable/writable).
    Returns a diagnostic dict.
    """
    import os
    diagnostics = {}
    for name, path in paths.items():
        exists = os.path.exists(path)
        readable = os.access(path, os.R_OK) if exists else False
        writable = os.access(path, os.W_OK) if exists else False
        diagnostics[name] = {
            "path": path,
            "exists": exists,
            "readable": readable,
            "writable": writable,
        }
    return diagnostics


if __name__ == "__main__":
    import numpy as np
    import pandas as pd
    from kronos.quant_spec.bias_override_engine import BiasOverrideEngine

    print("=== Point 91 OS-Agnostic Path Resolution Smoke ===")
    engine = BiasOverrideEngine()
    n = 20
    df = pd.DataFrame({"close": np.random.randn(n) + 100})

    raw = "f:/kronos_v1_alt"
    final = compute_point_91_override(raw, df, "TEST91", engine=engine)
    print(f"raw={raw} -> final={final}")

    paths = resolve_project_paths()
    print(f"Resolved paths: {paths}")

    diags = validate_path_permissions(paths)
    for name, info in diags.items():
        print(f"  {name}: exists={info['exists']}")

def _load_point_91_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_91", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_91_CONFIG







