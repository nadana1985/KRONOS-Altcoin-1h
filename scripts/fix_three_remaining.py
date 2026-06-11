"""Fix 3 remaining files with multi-line f-string issues."""
import py_compile
from pathlib import Path

overrides_dir = Path(__file__).parent.parent / "kronos" / "quant_spec" / "overrides"

fixes = {
    "point_94.py": [
        # Line: print(f"  order=${order_usd:>6.0f} vol=${vol_usd:.0e} -> "" )
        # Should be: print(f"  order=${order_usd:>6.0f} vol=${vol_usd:.0e} -> "
        (' -> """\n              f"cost=', ' -> "\n              f"cost='),
        # Line: f"(fee={res['base_fee_bps']:.1f} + spread={res['spread_cost_bps']:.1f} + impact={res['impact_bps']:.1f}
        # Should end with :.1f}"
        (":.1f}\n\ndef _load", ":.1f})\n\n\ndef _load"),
    ],
    "point_95.py": [
    ],
    "point_100.py": [
    ],
}

for fname, f in fixes.items():
    path = overrides_dir / fname
    content = path.read_text(encoding="utf-8")
    for old, new in f:
        if old in content:
            content = content.replace(old, new)
    path.write_text(content, encoding="utf-8")
    try:
        py_compile.compile(str(path), doraise=True)
        print(f"OK: {fname}")
    except py_compile.PyCompileError as e:
        print(f"FAIL: {fname}: {str(e).split(chr(10))[0][:150]}")