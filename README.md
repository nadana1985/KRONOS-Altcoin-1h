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
│   ├── diffs/                # precise diff txts from surgical steps (see .gitignore; reference with summaries)
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

## Installation
- Clone repo.
- Set KRONOS_PARAMS_PATH to point to params_yaml.txt (via cfg).
- pip install -r requirements.txt (pandas, numpy, torch, hdbscan, ccxt, pyyaml from cfg-driven deps).
- (Optional) GPU: ensure torch with CUDA for compute_neural_conviction.

## Usage
- python -m config.ingestion.unified_ingestion_engine (or via sovereign_entrypoint).
- python -m config.mining.reversal_signature_miner_sovereign (Option B shards from cfg["storage"]["raw_shards_dir"]).
- python scripts/inspect_shards.py (for 12-field kline checks).
- python test_end_to_end.py (E2E with neural_slots, slot_15 veto, dna_vector).
- All paths/cfg from get_sovereign_config() + get_storage_path (no hardcodes).

## Architecture (V1-ALT Delivered Reality)

**KRONOS V1-ALT** is a robust, fully sovereign, **real-shards-only** (Option B), cfg-driven reversal signature mining engine. It features an absolute structural veto (`slot_15` first) and dual-mode operation (individual primary + ablatable global prior).

### Delivered 32-Slot Causal DNA
- **8 structural microstructure proxies** (slots 00, 04, 07-11, 15) computed via `compute_slots_sovereign` in `kronos_module/model/structural_engine.py`.
- **1 neural conviction signal** (slots 16-23): single L2 norm of tokenizer embedding layer on recent normalized tail (replicated 8×; full Kronos model forward stubbed).
- **16+ derived/auxiliary slots**: vol_delta, MFE proxies, residuals, and zero-expressions — all built from the same cfg-driven variables.
- **HDBSCAN phylum**: post-hoc on structural 8 slots only.
- **Core gating**: Hard `slot_15` veto before DNA vector construction or neural amplification.

This delivers a **high-throughput, configurable heuristic microstructure scoring system** that is E2E-passing and production-operable at 530+ altcoin scale. It prioritizes pragmatism, vectorization, and causality over full deep-model per-bar computation.

**See** `docs/slot_reference_manual.md` (especially "Current Implementation" subsections) for precise delivered behavior vs. aspirational formulas.  
**Reality Audit**: `docs/KRONOS_V1_ALT_32_SLOT_CAUSAL_DNA_REALITY_AUDIT_SUMMARY.md`

All values remain strictly cfg-driven via `params_yaml.txt` (no inline literals introduced).