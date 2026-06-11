"""
Fix truncated print(f" lines in point modules.
The batch_update script accidentally removed closing ") from print(f"...") lines.
Simply adds the missing closing quote+paren to each affected line.
Target: only lines ending with an unclosed f-string.
"""
from pathlib import Path

overrides_dir = Path(__file__).parent.parent / "kronos" / "quant_spec" / "overrides"

# Files that the miner actually imports (need to compile)
target_files = [
    'point_01', 'point_02', 'point_17', 'point_21', 'point_25', 'point_26',
    'point_35', 'point_46', 'point_47', 'point_48', 'point_49', 'point_50',
    'point_51', 'point_52', 'point_57', 'point_61', 'point_64', 'point_66',
    'point_71', 'point_74', 'point_97', 'point_98',
]

for name in target_files:
    path = overrides_dir / f"{name}.py"
    if not path.exists():
        continue
    content = path.read_text(encoding="utf-8")
    lines = content.split('\n')
    fixed = []
    changed = False
    for i, line in enumerate(lines):
        # Check if line has print(f" and is missing closing ")
        stripped = line.strip()
        if 'print(f"' in stripped and not stripped.endswith('")'):
            # Count unclosed f-strings
            has_open = stripped.count('print(f"')
            has_close = stripped.count('")')
            if has_open > has_close:
                # The line was truncated - add closing
                fixed.append(line + '")')
                changed = True
                continue
        fixed.append(line)
    if changed:
        path.write_text('\n'.join(fixed), encoding="utf-8")
        print(f"Fixed: {name}.py")
    else:
        print(f"OK:   {name}.py")

# Also check for indentation errors
print("\nChecking point_35 for indentation issues...")
p35 = overrides_dir / "point_35.py"
if p35.exists():
    content = p35.read_text(encoding="utf-8")
    # Fix: the batch script added a const line before _load function but may have broken indent
    lines = content.split('\n')
    fixed = []
    for line in lines:
        if line.startswith("_DEFAULT_POINT_35_CONFIG"):
            # Ensure it has proper indentation
            fixed.append(line)
        elif line.startswith("def _load_point_35_config"):
            # Make sure it's not indented
            fixed.append(line)
        else:
            fixed.append(line)
    p35.write_text('\n'.join(fixed), encoding="utf-8")
    print("Checked point_35.py")