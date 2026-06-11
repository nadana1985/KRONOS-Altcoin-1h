import pandas as pd
import os
import sys
import glob
from pathlib import Path

# Robust bootstrap (zero literals, from params)
params_path = os.getenv("KRONOS_PARAMS_PATH")
if params_path:
    project_root = os.path.dirname(os.path.abspath(params_path))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)  # insert root so from config.xxx works for subdirs

from config.utils.sovereign_entrypoint import get_sovereign_config, get_storage_path

cfg = get_sovereign_config()
shards_dir = get_storage_path(cfg, "raw_shards_dir")
logs_dir = get_storage_path(cfg, "logs_dir")
os.makedirs(logs_dir, exist_ok=True)

print("=== RAW SHARDS INSPECTION (taker/quote/trades) ===\n")

tf = cfg["project"]["timeframe"]
suffix_replace = f"_{tf}.parquet"
files = sorted(glob.glob(os.path.join(shards_dir, f"*{suffix_replace}")))
print("Files found:")
for f in files:
    print(f"  {os.path.basename(f)}  ({os.path.getsize(f)/1024/1024:.2f} MB)")

print("\n" + "="*70)

report_lines = []
total_symbols = 0
full_taker_count = 0
missing_taker_ratios = []

for path in files:
    fname = os.path.basename(path)
    sym = fname.replace(suffix_replace, "")
    df = pd.read_parquet(path)
    total_rows = len(df)
    cols = df.columns.tolist()
    has_taker_buy = "taker_buy_base_volume" in cols
    has_quote_volume = "quote_volume" in cols
    has_trades = "number_of_trades" in cols
    if has_taker_buy and total_rows > 0:
        missing_ratio = df["taker_buy_base_volume"].isna().sum() / total_rows
    else:
        missing_ratio = 1.0
    total_symbols += 1
    if has_taker_buy and missing_ratio < 1e-6:
        full_taker_count += 1
    missing_taker_ratios.append(missing_ratio)
    line = f"{sym}: has_taker_buy={has_taker_buy}, has_quote_volume={has_quote_volume}, has_trades={has_trades}, total_rows={total_rows}, missing_ratio={missing_ratio:.4f}"
    print(line)
    report_lines.append(line)

print("\n" + "="*70)

avg_missing = sum(missing_taker_ratios) / len(missing_taker_ratios) if missing_taker_ratios else 0.0
pct_full = (full_taker_count / total_symbols * 100) if total_symbols > 0 else 0.0
reversal_window_min = cfg["thresholds"]["reversal_window_min"]
reversal_hash_mod = cfg["thresholds"]["reversal_hash_mod"]
bvc_required = avg_missing > (reversal_window_min / (reversal_hash_mod / 10))
bvc_str = f"BVC Required: {'Yes' if bvc_required else 'No'} ({avg_missing*100:.1f}% missing)"
print(bvc_str)
report_lines.append(bvc_str)

summary = f"% symbols with full taker_buy data: {pct_full:.1f}%"
print(summary)
report_lines.append(summary)

report_path = os.path.join(logs_dir, "shard_inspection_report.txt")
with open(report_path, "w") as f:
    f.write("\n".join(report_lines) + "\n")
print(f"Report saved to {report_path}")
