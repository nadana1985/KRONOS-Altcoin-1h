"""
Fix all remaining syntax errors in point modules after batch update.
The batch_update script caused two types of damage:
1. Multi-line f-strings got extra closing ") on first line
2. Import lines got merged into earlier import blocks
"""
import py_compile
from pathlib import Path

overrides_dir = Path(__file__).parent.parent / "kronos" / "quant_spec" / "overrides"

# Find ALL broken files
broken = []
for py_file in sorted(overrides_dir.glob("point_*.py")):
    try:
        py_compile.compile(str(py_file), doraise=True)
    except py_compile.PyCompileError:
        broken.append(py_file)

print(f"Found {len(broken)} broken files")

import re

for py_file in broken:
    content = py_file.read_text(encoding="utf-8")
    lines = content.split('\n')
    fixed_lines = []
    
    # Track state for multi-line f-strings
    for line in lines:
        # Fix 1: Lines ending with "") that are part of a multi-line f-string
        # These had ") incorrectly concatenated to the first line
        # e.g. print(f"... {var} "") should be print(f"... {var} "
        if '""' in line and 'f(' in line:
            stripped = line.strip()
            if stripped.endswith(', "")') or stripped.endswith('"")'):
                line = line.replace('"")', '"')
                line = line.replace(', ""', ', "')
        
        fixed_lines.append(line)
    
    content = '\n'.join(fixed_lines)
    py_file.write_text(content, encoding="utf-8")
    
    # Verify
    try:
        py_compile.compile(str(py_file), doraise=True)
        print(f"  Fixed: {py_file.name}")
    except py_compile.PyCompileError as e:
        msg = str(e)
        # If it's still broken but only in a __main__ block, print details
        if '__main__' in msg or 'line' in msg:
            line_num = 0
            for part in msg.split():
                if part.isdigit():
                    line_num = int(part)
                    break
            context_lines = '\n'.join([f'{i+1}: {l}' for i,l in enumerate(content.split('\n')) if abs(i+1 - line_num) < 3])
            print(f"  Still broken: {py_file.name} (line {line_num})")
            print(f"    {context_lines[:200]}")
        else:
            print(f"  Still broken: {py_file.name}: {msg[:100]}")