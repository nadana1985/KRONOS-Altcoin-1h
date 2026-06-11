"""
Fix import blocks in point_93, 94, 95, 100.
The batch script inserted 'from kronos.quant_spec.override_config_cache import ...' inside 
multi-line import blocks, breaking them.
"""
import py_compile
from pathlib import Path

overrides_dir = Path(__file__).parent.parent / "kronos" / "quant_spec" / "overrides"

for fname in ['point_93.py', 'point_94.py', 'point_95.py', 'point_100.py']:
    path = overrides_dir / fname
    content = path.read_text(encoding="utf-8")
    
    # Fix: move 'from kronos.quant_spec.override_config_cache' line outside the import block
    # Pattern: 
    #   from kronos.quant_spec.overrides.utils import (
    #   from kronos.quant_spec.override_config_cache import ...
    #       symbol_name,
    #   )
    # Should become:
    #   from kronos.quant_spec.overrides.utils import (
    #       symbol_name,
    #   )
    #   from kronos.quant_spec.override_config_cache import ...
    
    old_block = 'from kronos.quant_spec.overrides.utils import (\nfrom kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback\n    '
    new_block = 'from kronos.quant_spec.overrides.utils import (\n    '
    content = content.replace(old_block, new_block)
    
    # Add the import after the closing parenthesis of the overrides.utils import
    # Find 'from kronos.quant_spec.overrides.utils import (' and add after the ')'
    import re
    # Find the closing paren of the utils import block
    def fix_imports(text):
        lines = text.split('\n')
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]
            result.append(line)
            # Check if we just passed a single-line import from kronos.overrides.utils
            if line.strip() == ')' and i > 0 and 'from kronos.quant_spec.overrides.utils import (' in lines[i-1]:
                # Check if there's NOT already an override_config_cache import
                k = i + 1
                found_cache = False
                while k < len(lines) and not lines[k].strip().startswith('from') and not lines[k].strip().startswith('#') and lines[k].strip():
                    if 'override_config_cache' in lines[k]:
                        found_cache = True
                    k += 1
                if not found_cache:
                    # Check next line isn't already the import
                    if i + 1 < len(lines) and 'override_config_cache' not in lines[i+1]:
                        result.append('from kronos.quant_spec.override_config_cache import get_cached_point_config_with_engine_fallback')
            i += 1
        return '\n'.join(result)
    
    content = fix_imports(content)
    path.write_text(content, encoding="utf-8")
    
    # Verify
    try:
        py_compile.compile(str(path), doraise=True)
        print(f"OK: {fname}")
    except py_compile.PyCompileError as e:
        # Show the line and context
        msg = str(e)
        print(f"FAIL: {fname}: {msg.split(chr(10))[0][:200]}")

print("Done")