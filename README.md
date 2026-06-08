# KRONOS V1-ALT

Sovereign reversal signature mining engine for 1h altcoin USDT perps. All config from params_yaml.txt. Zero literals. Dual-mode (individual + ablatable global prior). Option B real shards. Full 32-slot causal DNA.

## Repo Structure (final after reorganization)

```
kronos_v1_alt/
├── .gitignore
├── README.md
├── params_yaml.txt
├── config/
│   ├── ingestion/
│   │   ├── unified_ingestion_engine.py
│   │   └── real_api_bridge_sovereign.py
│   ├── mining/
│   │   └── reversal_signature_miner_sovereign.py
│   ├── validation/
│   │   ├── validate_sovereignty.py
│   │   └── load_sovereign_config.py
│   ├── utils/
│   │   ├── sovereign_entrypoint.py
│   │   ├── symbol_discovery_sovereign.py
│   │   ├── global_prior_sovereign.py
│   │   ├── symbol_map_sovereign.py
│   │   ├── ablation_test_sovereign.py
│   │   ├── kronos_pipeline_sovereign.py
│   │   ├── kronos_master_controller.py
│   │   ├── shard_validator_sovereign.py
│   │   ├── check_date.py
│   │   ├── fix_sovereign_imports.py
│   │   ├── organize_sovereign_structure.py
│   │   ├── real_data_injection_sovereign.py
│   │   ├── real_data_readiness_sovereign.py
│   │   └── ...
│   └── ...
├── kronos_module/ (unchanged)
│   ├── model/
│   │   ├── structural_engine.py
│   │   ├── kronos.py
│   │   └── ...
│   ├── models/ (gitignored)
│   └── orchestrator_engine.py
├── docs/
│   ├── slot_reference_manual.md
│   ├── KRONOS_V1_ALT_*_SUMMARY.md
│   └── ...
├── scripts/
│   └── inspect_shards.py
├── test_end_to_end.py
├── data/ (gitignored)
├── logs/ (gitignored)
├── attachments/ (gitignored)
├── __pycache__/ (gitignored)
└── *.py (other entries)
```

**Notes on structure:**
- Core logic in config/ subfolders + kronos_module/ (unchanged)
- All values from params_yaml.txt via get_sovereign_config()
- data/, logs/, models/, attachments/, __pycache__ ignored
- Reorganized per documented proposal; imports/paths updated.

## Usage
- Set KRONOS_PARAMS_PATH
- python config/unified_ingestion_engine.py
- python config/reversal_signature_miner_sovereign.py
- python inspect_shards.py

See slot_reference_manual.md for 32-slot DNA.