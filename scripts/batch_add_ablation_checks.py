"""
Batch script to add `is_point_enabled()` checks to all override point modules.
Adds an early-return guard at the top of each compute_point_XX_override function.

Usage:
    python scripts/batch_add_ablation_checks.py
"""
import os
import re
import sys

OVERRIDE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "kronos", "quant_spec", "overrides")

# Points that have param_yaml.txt point_XX_enabled flags (the 26 active ones)
ACTIVE_POINTS = [1, 2, 3, 6, 11, 15, 19, 23, 24, 25, 28, 29, 35, 36, 44, 46, 47, 48, 52, 56, 57, 64, 66, 69, 72, 82]


def get_point_id_from_filename(filename: str) -> int | None:
    """Extract point ID from filename like point_01.py -> 1"""
    m = re.match(r"point_(\d+)\.py", filename)
    if m:
        return int(m.group(1))
    return None


def get_override_function_name(point_id: int) -> str:
    """Get the override function name for this point."""
    return f"compute_point_{point_id:02d}_override"


def process_file(filepath: str, point_id: int) -> bool:
    """Add is_point_enabled check to the compute function. Returns True if modified."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    func_name = get_override_function_name(point_id)

    # Construct the check code
    check_code = f"""    # ── Ablation early-return ──
    # When this point is disabled via config-driven ablation, return raw_value immediately.
    from config.ablation_bootstrap import is_point_enabled
    if not is_point_enabled("{point_id:02d}"):
        return raw_value

"""
    # Find the function definition
    # Pattern: "def compute_point_XX_override(" with its arguments
    func_pattern = rf"(def {func_name}\(.*?{re.escape(') ->')}|def {func_name}\(.*?\):)"
    
    # We need to find the signature and insert after the docstring or the first line
    lines = content.split("\n")
    new_lines = []
    inserted = False
    
    for i, line in enumerate(lines):
        new_lines.append(line)
        
        if not inserted and line.strip().startswith(f"def {func_name}("):
            # This is the function def — next non-comment/blank line after docstring
            # Look ahead for where to insert
            insert_at = i + 1
            # Skip the docstring if present
            while insert_at < len(lines):
                stripped = lines[insert_at].strip()
                if stripped in ('"""', "'''") or stripped.startswith('"""') or stripped.startswith("'''"):
                    # Find end of docstring
                    if stripped in ('"""', "'''"):
                        insert_at += 1
                        while insert_at < len(lines) and lines[insert_at].strip() not in ('"""', "'''"):
                            insert_at += 1
                        insert_at += 1
                        continue
                    elif stripped.endswith('"""') or stripped.endswith("'''"):
                        insert_at += 1
                        break
                    else:
                        insert_at += 1
                        break
                elif stripped == "" or stripped.startswith("#"):
                    insert_at += 1
                    continue
                else:
                    break
            
            # Insert check code before the first real line of the function body
            indent = "    " if line[0] != ' ' else line[:len(line) - len(line.lstrip())] + "    "
            check_lines = check_code.split("\n")
            for cl in reversed(check_lines):
                if cl.strip():
                    new_lines.insert(len(new_lines), indent + cl if cl.strip() else "")
            
            inserted = True

    new_content = "\n".join(new_lines)
    
    if new_content != content:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        return True
    
    return False


def process_all_files():
    """Process all override point files."""
    modified = []
    skipped = []
    errors = []
    
    print("=" * 60)
    print("Batch adding ablation checks to override point modules")
    print("=" * 60)
    
    for filename in sorted(os.listdir(OVERRIDE_DIR)):
        if not filename.endswith(".py") or not filename.startswith("point_"):
            continue
        
        filepath = os.path.join(OVERRIDE_DIR, filename)
        point_id = get_point_id_from_filename(filename)
        
        if point_id is None:
            skipped.append(f"{filename} (no point ID)")
            continue
        
        if point_id not in ACTIVE_POINTS:
            skipped.append(f"{filename} (point {point_id} not in active set)")
            continue
        
        try:
            if process_file(filepath, point_id):
                modified.append(f"point_{point_id:02d}.py")
                print(f"  [MODIFIED] {filename}")
            else:
                skipped.append(f"{filename} (no changes needed)")
                print(f"  [SKIP] {filename} - no changes needed")
        except Exception as e:
            errors.append(f"{filename}: {e}")
            print(f"  [ERROR] {filename}: {e}")
    
    print("\n" + "=" * 60)
    print(f"Results: {len(modified)} modified, {len(skipped)} skipped, {len(errors)} errors")
    print("=" * 60)
    
    if modified:
        print("\nModified files:")
        for m in modified:
            print(f"  - {m}")
    
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  - {e}")


if __name__ == "__main__":
    process_all_files()