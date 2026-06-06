
import pandas as pd
from pathlib import Path
import sys
from pathlib import Path as Path2
sys.path.insert(0, str(Path2(__file__).parent.absolute()))
from sovereign_entrypoint import get_sovereign_config
from load_sovereign_config import get_storage_path
# Utility uses cfg["utilities"] for ticker naming (see params); storage from cfg
cfg = get_sovereign_config()
raw_shards_dir = get_storage_path(cfg, "raw_shards_dir")
tf = cfg["project"]["timeframe"]
utils = cfg["utilities"]
example_prefix = utils["example_ticker_prefix"]
example_suffix = utils["example_ticker_suffix"]
file_path = Path(raw_shards_dir) / f"{example_prefix}{tf}{example_suffix}"
if file_path.exists():
    df = pd.read_parquet(file_path)
    print('File exists:', file_path)
    print('Shape:', df.shape)
    print('Start date:', df['timestamp'].min())
    print('End date:', df['timestamp'].max())
    print('Columns:', df.columns.tolist())
    print(df.head(3))
else:
    print('File not found:', file_path)
    print('Available shards:')
    for p in Path(raw_shards_dir).glob('*.parquet'):
        print(p.name)
