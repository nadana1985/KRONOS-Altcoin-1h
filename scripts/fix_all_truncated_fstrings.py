"""
Fix ALL truncated f-string print statements in ALL point_*.py files.
The batch_update script accidentally removed closing ") from print(f"...") lines.
This script finds every file that fails compilation and fixes it.
"""
import py_compile
import re
from pathlib import Path

overrides_dir = Path(__file__).parent.parent / "kronos" / "quant_spec" / "overrides"

# First pass: find all files that fail to compile
failed = []
for py_file in sorted(overrides_dir.glob("point_*.py")):
    try:
        py_compile.compile(str(py_file), doraise=True)
    except py_compile.PyCompileError as e:
        failed.append(py_file)
        print(f"FAIL: {py_file.name}: {e}")

print(f"\n{len(failed)} files with syntax errors. Fixing...")

# Fix them: add missing ") after any print(f" line that lacks it
fixed_count = 0
for py_file in failed:
    content = py_file.read_text(encoding="utf-8")
    lines = content.split('\n')
    new_lines = []
    changed = False
    
    for line in lines:
        stripped = line.strip()
        # Check if this is a print(f" line missing closing
        if 'print(f"' in stripped:
            # Count occurrences of opening print(f" vs closing ")
            opens = stripped.count('print(f"') + stripped.count("print(f'")
            closes = stripped.count('")') + stripped.count("')")
            if opens > closes:
                # Line is truncated - add closing "
                # But be careful: if the line already has content after the f-string
                # we need to add just the closing "
                line = line.rstrip() + '")'
                changed = True
        new_lines.append(line)
    
    if changed:
        py_file.write_text('\n'.join(new_lines), encoding="utf-8")
        fixed_count += 1
        # Verify fix
        try:
            py_compile.compile(str(py_file), doraise=True)
            print(f"  ✓ Fixed: {py_file.name}")
        except py_compile.PyCompileError as e:
            print(f"  ✗ Still broken: {py_file.name}: {e}")

print(f"\n{fixed_count} files fixed. Remaining broken: {len(failed) - fixed_count}")