"""
Fix 4 remaining broken files with multi-line f-string issues.
The character sequence ``"")`` at end of a continuation line needs to be just ``"``.
"""
import py_compile
from pathlib import Path

overrides_dir = Path(__file__).parent.parent / "kronos" / "quant_spec" / "overrides"

for fname in ['point_93.py', 'point_94.py', 'point_95.py', 'point_100.py']:
    path = overrides_dir / fname
    content = path.read_text(encoding="utf-8")
    lines = content.split('\n')
    
    fixed = []
    for i, line in enumerate(lines):
        stripped = line.rstrip()
        # Check if line ends with "") and is followed by f-string continuation
        if stripped.endswith('"")'):
            # Look ahead to see if this is a multi-line f-string
            if i + 1 < len(lines) and ('f"' in lines[i+1] or lines[i+1].startswith('          f"')):
                # Remove the trailing ) - it was added by the fix script erroneously
                line = stripped[:-1] + '"'
        fixed.append(line)
    
    new_content = '\n'.join(fixed)
    if new_content != content:
        path.write_text(new_content, encoding="utf-8")
    
    # Verify
    try:
        py_compile.compile(str(path), doraise=True)
        print(f"OK: {fname}")
    except py_compile.PyCompileError as e:
        print(f"FAIL: {fname}: {str(e).split(chr(10))[0][:150]}")

print("Done")