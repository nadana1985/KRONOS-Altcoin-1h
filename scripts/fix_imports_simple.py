"""
Fix the import blocks in point_93,94,95,100.py.
The config cache import was inserted inside multi-line import parentheses.
"""
import py_compile
from pathlib import Path

overrides_dir = Path(__file__).parent.parent / "kronos" / "quant_spec" / "overrides"

files_to_fix = {
    "point_93.py": {
        "old": "from kronos.quant_spec.bias_override_engine import BiasOverrideEngine\nfrom kronos.quant_spec.overrides.utils import (\nfrom kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback\n    compute_latency_slippage_modifier,\n    compute_close_to_close_vol,\n)",
        "new": "from kronos.quant_spec.bias_override_engine import BiasOverrideEngine\nfrom kronos.quant_spec.overrides.utils import (\n    compute_latency_slippage_modifier,\n    compute_close_to_close_vol,\n)\nfrom kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback"
    },
    "point_94.py": {
        "old": "from kronos.quant_spec.overrides.utils import (\nfrom kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback\n    compute_dynamic_execution_cost,\n    compute_corwin_schultz_spread,\n)",
        "new": "from kronos.quant_spec.overrides.utils import (\n    compute_dynamic_execution_cost,\n    compute_corwin_schultz_spread,\n)\nfrom kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback"
    },
    "point_95.py": {
        "old": "from kronos.quant_spec.overrides.utils import (\nfrom kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback\n    compute_twap_execution_price,\n    compute_corwin_schultz_spread,\n)",
        "new": "from kronos.quant_spec.overrides.utils import (\n    compute_twap_execution_price,\n    compute_corwin_schultz_spread,\n)\nfrom kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback"
    },
    "point_100.py": {
        "old": "from kronos.quant_spec.overrides.utils import (\nfrom kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback\n    compute_impact_aware_position_size,\n    compute_close_to_close_vol,\n    compute_corwin_schultz_spread,\n)",
        "new": "from kronos.quant_spec.overrides.utils import (\n    compute_impact_aware_position_size,\n    compute_close_to_close_vol,\n    compute_corwin_schultz_spread,\n)\nfrom kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback"
    },
}

for fname, fix in files_to_fix.items():
    path = overrides_dir / fname
    content = path.read_text(encoding="utf-8")
    if fix["old"] in content:
        content = content.replace(fix["old"], fix["new"])
        path.write_text(content, encoding="utf-8")
        print(f"Fixed imports: {fname}")
    else:
        print(f"Pattern not found in {fname}")
    
    # Verify
    try:
        py_compile.compile(str(path), doraise=True)
        print(f"  OK: {fname}")
    except py_compile.PyCompileError as e:
        print(f"  FAIL: {fname}: {str(e).split(chr(10))[0][:150]}")

print("Done")