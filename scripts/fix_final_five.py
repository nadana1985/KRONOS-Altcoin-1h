"""
Fix the 5 remaining broken files (point_92-95, 100).
These have issues from the batch script mangling imports and multi-line f-strings.
"""
from pathlib import Path

overrides_dir = Path(__file__).parent.parent / "kronos" / "quant_spec" / "overrides"

fixes = {
    "point_92.py": [
        # Fix mangled import block
        ('from kronos.quant_spec.overrides.utils import (\nfrom kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback\n    compute_system_memory_available_gb,\n    compute_adaptive_shard_size,\n)',
         'from kronos.quant_spec.overrides.utils import (\n    compute_system_memory_available_gb,\n    compute_adaptive_shard_size,\n)\nfrom kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback'),
        # Fix multi-line f-string with extra ")
        ('print(f"Memory: avail={resources[\'memory_available_gb\']:.1f}GB, "")\n          f"used={resources[\'memory_used_by_shards_gb\']:.1f}GB, "',
         'print(f"Memory: avail={resources[\'memory_available_gb\']:.1f}GB, "\n          f"used={resources[\'memory_used_by_shards_gb\']:.1f}GB, "'),
    ],
    "point_93.py": [
        ('print(f"signal_price={raw:.4f} -> executed={res[\'engine_final_price\']:.4f} "")\n          f"slippage={res[\'slippage_bps\']:.1f}bps")',
         'print(f"signal_price={raw:.4f} -> executed={res[\'engine_final_price\']:.4f} "\n          f"slippage={res[\'slippage_bps\']:.1f}bps")'),
    ],
    "point_94.py": [
        ('print(f"  order=${order_usd:>6.0f} vol=${vol_usd:.0e} -> "")\n              f"cost={res[\'engine_final_cost_bps\']:.1f}bps "',
         'print(f"  order=${order_usd:>6.0f} vol=${vol_usd:.0e} -> "\n              f"cost={res[\'engine_final_cost_bps\']:.1f}bps "'),
    ],
    "point_95.py": [
        ('print(f"raw_close={raw_close:.4f} -> twap={res[\'engine_final_price\']:.4f} "")\n          f"vs_close={res.get(\'vs_close\', 0):.4f}")',
         'print(f"raw_close={raw_close:.4f} -> twap={res[\'engine_final_price\']:.4f} "\n          f"vs_close={res.get(\'vs_close\', 0):.4f}")'),
    ],
    "point_100.py": [
        ('print(f"  {label:10s} -> size=${res[\'engine_final_size\']:.0f} "")\n              f"(impact_adj={res[\'impact_adjustment\']:.3f}, vol={res[\'volatility\']:.4f}")',
         'print(f"  {label:10s} -> size=${res[\'engine_final_size\']:.0f} "\n              f"(impact_adj={res[\'impact_adjustment\']:.3f}, vol={res[\'volatility\']:.4f})"'),
    ],
}

fixed = 0
for filename, replacements in fixes.items():
    path = overrides_dir / filename
    if not path.exists():
        print(f"NOT FOUND: {filename}")
        continue
    content = path.read_text(encoding="utf-8")
    original = content
    for old, new in replacements:
        content = content.replace(old, new)
    if content != original:
        path.write_text(content, encoding="utf-8")
        fixed += 1
        print(f"FIXED: {filename}")
    else:
        print(f"UNCHANGED: {filename}")

# Verify all 5
import py_compile
for filename in ["point_92.py", "point_93.py", "point_94.py", "point_95.py", "point_100.py"]:
    path = overrides_dir / filename
    try:
        py_compile.compile(str(path), doraise=True)
        print(f"  OK: {filename}")
    except py_compile.PyCompileError as e:
        print(f"  STILL BROKEN: {filename}: {str(e).split(chr(10))[0]}")

print(f"\n{fixed} files fixed")