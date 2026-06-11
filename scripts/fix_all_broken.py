"""Fix all remaining broken point_XX.py files that have syntax errors."""
import py_compile
from pathlib import Path

overrides_dir = Path(__file__).parent.parent / "kronos" / "quant_spec" / "overrides"

# Find broken files
broken = []
for py_file in sorted(overrides_dir.glob("point_*.py")):
    try:
        py_compile.compile(str(py_file), doraise=True)
    except py_compile.PyCompileError:
        broken.append(py_file)

print(f"Found {len(broken)} broken files")

# Fix each broken file
for py_file in broken:
    content = py_file.read_text(encoding="utf-8")
    original = content
    lines = content.split('\n')
    fixed_lines = []
    changed = False
    
    # Fix 1: Multi-line f-string where first line ends with """) (extra paren)
    # Fix 2: Missing closing on final line
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Fix: line ends with """) that should just be "
        if stripped.endswith('"")') and i + 1 < len(lines):
            next_line = lines[i+1].strip()
            if next_line.startswith('f"') or next_line.startswith('          f"'):
                line = line.rstrip()[:-1] + '"'
                changed = True
        
        # Fix: line ends with :.1f} without closing )
        if stripped.endswith(':.1f}') and i + 1 < len(lines):
            next_line = lines[i+1].strip()
            if next_line.startswith('          ') and not next_line.startswith('          f"'):
                # This likely needs a closing )
                line = line.rstrip() + ')'
                # Also close the f-string if the next line isn't a continuation
                if not next_line.startswith('          f"'):
                    # Check if line has unclosed f-string
                    open_quotes = line.count('f"')
                    close_quotes = line.count('")')
                    if open_quotes > close_quotes:
                        line = line.rstrip() + '")'
                changed = True
        
        fixed_lines.append(line)
        i += 1
    
    content = '\n'.join(fixed_lines)
    
    # Fix 3: Duplicated function blocks from batch script (find and remove)
    # Check for duplicate def lines
    defs = [i for i, l in enumerate(lines) if l.strip().startswith('def ') or l.strip().startswith('if __name__')]
    seen_defs = set()
    duplicated_ranges = []
    for d in defs:
        name = lines[d].strip()
        if name in seen_defs:
            # Find where this duplicate starts and ends
            for prev_d in defs:
                if lines[prev_d].strip() == name and prev_d != d:
                    # This is a duplicate - mark range from d to next def or end
                    end = d + 1
                    while end < len(lines) and not lines[end].strip().startswith('def ') and not lines[end].strip().startswith('if __name__'):
                        end += 1
                    duplicated_ranges.append((d, end))
        else:
            seen_defs.add(name)
    
    # Remove duplicated ranges (in reverse order)
    if duplicated_ranges:
        changed = True
        for start, end in reversed(duplicated_ranges):
            content_lines = content.split('\n')
            content = '\n'.join(content_lines[:start] + content_lines[end:])
    
    if changed:
        py_file.write_text(content, encoding="utf-8")
    
    # Verify
    try:
        py_compile.compile(str(py_file), doraise=True)
        print(f"  FIXED OK: {py_file.name}")
    except py_compile.PyCompileError as e:
        msg = str(e)
        line_no = ""
        for part in msg.split():
            if part.isdigit():
                line_no = f"(line {part})"
                break
        print(f"  STILL BROKEN: {py_file.name} {line_no}")

print("\nDone")