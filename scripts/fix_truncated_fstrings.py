"""
Fix truncated f-string print statements in point modules.
The batch_update script accidentally truncated lines ending with f-string patterns.
"""
import re
from pathlib import Path

overrides_dir = Path(__file__).parent.parent / "kronos" / "quant_spec" / "overrides"
fixes_applied = 0

for py_file in sorted(overrides_dir.glob("point_*.py")):
    content = py_file.read_text(encoding="utf-8")
    original = content
    
    # Fix 1: Unclosed f-string: print(f"...text {var}" with missing closing )
    # Pattern: unclosed f-string at end of line (no closing } or " after {
    # Find lines that start with print(f" and end without closing parenthesis
    
    # Fix pattern: "  {something}\n"  => add closing parenthesis and/or brace
    content = re.sub(
        r'print\(f"([^"]*)\{([^}]*)\}\n$',
        r'print(f"\1{\2}")\n',
        content,
        flags=re.MULTILINE
    )
    
    # Fix "  {something}.4f}\n" pattern (unclosed after f-string expression)
    content = re.sub(
        r'        print\(f"([^"]*):\{([^}]*)\}\n',
        r'        print(f"\1:{\2}")\n',
        content,
        flags=re.MULTILINE
    )
    
    # Fix unclosed f-strings that end with a segment without closing quotes
    # e.g. print(f"  text {var}    \n     => print(f"  text {var}    ")
    content = re.sub(
        r'print\(f"([^"]*)\n$',
        r'print(f"\1")\n',
        content,
        flags=re.MULTILINE
    )
    
    # Fix: raw_weight=0.250 -> final={final:.4f}\n with missing ")
    content = re.sub(
        r'(print\(f"[^"]*\{[^}]*)\n$',
        r'\1")\n',
        content,
        flags=re.MULTILINE
    )

    # Fix specific common patterns from batch update damage
    # "fdoi_latest: {result['fdoi_latest']:.4f}\n  (missing closing quote + paren)
    content = re.sub(
        r'\{result\[\'([^\']+)\'\]\}\n$',
        r"{result['\1']}")\n',
        content,
        flags=re.MULTILINE
    )
    
    # Fix: f"n_price_levels: {len(result['price_levels'])}\n"
    content = re.sub(
        r"\{len\(result\['([^']+)'\]\)\}\n$",
        r"{len(result['\1'])}")\n',
        content,
        flags=re.MULTILINE
    )
    
    # Fix: unclosed at end of __main__ blocks
    # Common: "... text ..."   then newline then code
    # If we have a line that ends with an unclosed f-string, close it
    lines = content.split('\n')
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if this line has an unclosed f-string print
        if 'print(f"' in line and not line.rstrip().endswith('")') and not line.rstrip().endswith("')"):
            # Count quotes - if odd number of double quotes, it's unclosed
            open_paren = line.count('print(f"')
            close_paren = line.strip().count('")')
            if open_paren > 0 and close_paren < open_paren:
                line = line.rstrip() + '")'
        fixed_lines.append(line)
        i += 1
    
    content = '\n'.join(fixed_lines)
    
    if content != original:
        py_file.write_text(content, encoding="utf-8")
        fixes_applied += 1
        print(f"Fixed: {py_file.name}")

print(f"\nTotal files fixed: {fixes_applied}")