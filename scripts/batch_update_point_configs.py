"""
Batch-update all point_XX.py modules to use the global config cache
instead of loading YAML per call.
"""
import os
import re
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
overrides_dir = project_root / "kronos" / "quant_spec" / "overrides"

# Pattern: find _load_point_XX_config functions that load YAML directly
# Replace with cache-based loading
config_cache_import = "from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback\n"

yaml_load_pattern = re.compile(
    r"def _load_point_\d+_config\(engine: Optional\[BiasOverrideEngine\] = None\) -> Dict\[str, Any\]:\s*"
    r"(?:    if engine is not None:\s*)"
    r"(?:        cfg = engine\.override_config\.get\(\"point_\d+\", \{\}\)\s*)"
    r"(?:        if cfg:\s*)"
    r"(?:            return cfg\s*)"
    r"    try:\s*"
    r"        import yaml\s*"
    r"        from pathlib import Path\s*"
    r"        base = Path\(__file__\)\.parent\.parent\.parent / \"config\"\s*"
    r"        with open\(base / \"liquidity_tiers\.yaml\", \"r\", encoding=\"utf-8\"\) as f:\s*"
    r"            full = yaml\.safe_load\(f\) or \{\}\s*"
    r"        return full\.get\(\"overrides\", \{\}\)\.get\(\"point_\d+\", \{\}\)\s*"
    r"    except Exception as e:\s*"
    r"        logger\.warning\(\"Could not load config for point_\d+: %s\", e\)\s*"
    r"        return \{[^}]*\}([\s\S]*?)(?=\ndef|\nif __name__|\Z)",
    re.DOTALL
)

updated_count = 0
for py_file in sorted(overrides_dir.glob("point_*.py")):
    if py_file.name in ("point_51.py", "point_46.py"):
        # Already updated
        continue
    
    content = py_file.read_text(encoding="utf-8")
    
    # Check if it has the old YAML-loading pattern
    if "import yaml" in content and "_load_point_" in content and "liquidity_tiers.yaml" in content:
        # Extract the point_id
        point_id_match = re.search(r"_load_point_(\d+)_config", content)
        if not point_id_match:
            continue
        point_id = point_id_match.group(1)
        
        # Add import for config cache (after the existing imports block)
        if "override_config_cache" not in content:
            # Find the last import from kronos
            import_lines = re.findall(r"^(from kronos\..*)$", content, re.MULTILINE)
            if import_lines:
                last_kronos_import = import_lines[-1]
                content = content.replace(
                    last_kronos_import,
                    last_kronos_import + "\n" + config_cache_import.rstrip()
                )
        
        # Find default config dict to use as fallback
        default_match = re.search(r"return \{[^}]+\}", content)
        default_config = default_match.group(0) if default_match else "{}"
        
        # Extract point-specific default config
        fallback_start = content.find("logger.warning(\"Could not load config for")
        if fallback_start > 0:
            fallback_block_end = content.find("\n", content.find("return {", fallback_start))
            if fallback_block_end > 0:
                # Find the return statement
                return_match = re.search(r"return \{.*\}", content[fallback_start:], re.DOTALL)
                if return_match:
                    default_config = return_match.group(0)
        
        # Build the new _load function
        new_load_func = f"""
def _load_point_{point_id}_config(engine: Optional[BiasOverrideEngine] = None) -> Dict[str, Any]:
    cfg = get_cached_point_config_with_engine_fallback("point_{point_id}", engine)
    if cfg:
        return cfg
    return _DEFAULT_POINT_{point_id}_CONFIG
"""
        
        # Replace old _load function
        old_func_start = content.find(f"def _load_point_{point_id}_config(engine")
        if old_func_start < 0:
            continue
        
        # Find end of the old function - look for next def or __name__
        old_func_end_search = re.search(
            r"\n(?=def |if __name__)",
            content[old_func_start + 1:]
        )
        old_func_end = old_func_start + 1 + old_func_end_search.start() if old_func_end_search else len(content)
        old_func = content[old_func_start:old_func_end]
        
        content = content.replace(old_func, new_load_func)
        
        # Add DEFAULT_CONFIG constant right before the function
        default_const = f"\n_DEFAULT_POINT_{point_id}_CONFIG = {default_config[7:] if default_config.startswith('return ') else default_config}\n"
        content = content.replace(
            f"\ndef _load_point_{point_id}_config",
            default_const + f"\ndef _load_point_{point_id}_config"
        )
        
        # Also fix the function signature s/import yaml/ etc
        py_file.write_text(content, encoding="utf-8")
        updated_count += 1
        print(f"Updated: {py_file.name}")

print(f"\nTotal updated: {updated_count} files")