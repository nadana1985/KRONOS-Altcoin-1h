"""Fix the ablation early-return checks inserted in wrong places."""
import os
import re

OVERRIDE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             "kronos", "quant_spec", "overrides")

# Points to fix
POINT_IDS = [1, 2, 3, 6, 11, 15, 19, 23, 24, 25, 28, 29, 35, 36, 44,
             46, 47, 48, 52, 56, 57, 64, 66, 69, 72, 82]


def fix_ablation_check(filepath: str, point_id: int) -> bool:
    """Fix the ablation check placement in a point module."""
    with open(filepath, "r") as f:
        content = f.read()

    func_name = f"compute_point_{point_id:02d}_override"
    point_str = f"{point_id:02d}"

    # Find the broken code pattern: ablation check mixed into function signature
    # Pattern: "def compute_point_XX_override(\n            return raw_value\n        if not is_point_enabled"
    broken_pattern = rf"(def {func_name}\(\s*\n\s+return raw_value\s*\n\s+if not is_point_enabled\(\"{point_str}\"\):\s*\n\s+from config\.ablation_bootstrap import is_point_enabled\s*\n\s+# When this point is disabled via config-driven ablation, return raw_value immediately\.\s*\n\s+# ── Ablation early-return ──)"
    
    if re.search(broken_pattern, content):
        # Remove the broken ablation code from the function signature
        content = re.sub(broken_pattern, f"def {func_name}(", content)
        
    # Now find where to insert properly: after docstring, before first computation line
    # Find the function definition
    func_start = re.search(rf"def {func_name}\(.*?\)\s*->\s*\w+:|def {func_name}\(.*?\):", content, re.DOTALL)
    
    if not func_start:
        print(f"  [ERROR] Could not find function {func_name} in {filepath}")
        return False
    
    # Find the first line of the function body (after docstring)
    body_start = func_start.end()
    lines_after = content[body_start:].split("\n")
    
    # Skip docstring
    i = 0
    while i < len(lines_after):
        stripped = lines_after[i].strip()
        if stripped in ('"""', "'''") or stripped.startswith('"""') or stripped.startswith("'''"):
            if stripped in ('"""', "'''"):
                i += 1
                while i < len(lines_after) and lines_after[i].strip() not in ('"""', "'''"):
                    i += 1
                i += 1
                continue
            elif stripped.endswith('"""') or stripped.endswith("'''"):
                i += 1
                break
            else:
                i += 1
                break
        elif stripped == "" or stripped.startswith("#"):
            i += 1
            continue
        else:
            break
    
    # Get the indent level of the first line
    if i < len(lines_after) and lines_after[i].strip():
        first_line = lines_after[i]
        indent = len(first_line) - len(first_line.lstrip())
    else:
        indent = 4
    
    ablation_code = f"""    # ── Ablation early-return ──
    # When this point is disabled via config-driven ablation, return raw_value immediately.
    from config.ablation_bootstrap import is_point_enabled
    if not is_point_enabled("{point_str}"):
        return raw_value

"""
    
    # Construct the fixed content
    # Insert ablation code before the line at index i (after docstring)
    lines_before = content[:body_start].split("\n")
    after_lines = content[body_start:].split("\n")
    
    # Build new content
    new_lines = lines_before + [""]
    for codeline in ablation_code.strip().split("\n"):
        new_lines.append(" " * indent + codeline)
    new_lines.append("")
    new_lines += after_lines
    
    new_content = "\n".join(new_lines)
    
    with open(filepath, "w") as f:
        f.write(new_content)
    
    return True


def process_all():
    print("=" * 60)
    print("Fixing ablation checks in override point modules")
    print("=" * 60)
    
    for pid in POINT_IDS:
        filepath = os.path.join(OVERRIDE_DIR, f"point_{pid:02d}.py")
        if not os.path.exists(filepath):
            print(f"  [SKIP] point_{pid:02d}.py not found")
            continue
        
        try:
            if fix_ablation_check(filepath, pid):
                print(f"  [FIXED] point_{pid:02d}.py")
            else:
                print(f"  [OK] point_{pid:02d}.py - no issues")
        except Exception as e:
            print(f"  [ERROR] point_{pid:02d}.py: {e}")
    
    print("\nDone.")


if __name__ == "__main__":
    process_all()