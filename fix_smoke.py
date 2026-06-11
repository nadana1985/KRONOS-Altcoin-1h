import glob

files = glob.glob(r'f:\kronos_v1_alt\kronos\quant_spec\overrides\point_*.py')
for file in files:
    with open(file, 'r') as f:
        content = f.read()
    if 'print("Smoke done."' in content and 'print("Smoke done.")' not in content:
        print(f'Fixing {file}')
        content = content.replace('print("Smoke done."\n', 'print("Smoke done.")\n')
        with open(file, 'w') as f:
            f.write(content)
