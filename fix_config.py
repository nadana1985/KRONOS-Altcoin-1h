import glob
import re

files = glob.glob(r'f:\kronos_v1_alt\kronos\quant_spec\overrides\point_*.py')
for file in files:
    with open(file, 'r') as f:
        content = f.read()
    
    # We want to replace:
    # return get_cached_point_config_with_engine_fallback("point_XX", engine, _DEFAULT_CONFIG)
    # with:
    # cfg = get_cached_point_config_with_engine_fallback("point_XX", engine)
    # return cfg if cfg else _DEFAULT_CONFIG
    
    pattern = re.compile(r'return get_cached_point_config_with_engine_fallback\("([^"]+)", engine, _DEFAULT_CONFIG\)')
    if pattern.search(content):
        print(f"Fixing {file}")
        new_content = pattern.sub(r'cfg = get_cached_point_config_with_engine_fallback("\1", engine)\n    return cfg if cfg else _DEFAULT_CONFIG', content)
        with open(file, 'w') as f:
            f.write(new_content)
