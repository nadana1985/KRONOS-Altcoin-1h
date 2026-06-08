# KRONOS V1-ALT — Slot Reference Manual Updated to Current Implementation

**Update:** Refreshed `slot_reference_manual.md` to accurately document the *actual* code in `structural_engine.py` (compute_slots_sovereign) and `reversal_signature_miner_sovereign.py` (dna_vector construction after neural_conv, plus post-hoc phylum).

**Changes made (targeted, minimal diffs):**
- Layer Overview table: Updated to reflect current implemented slots and notes (structural now lists 00,04,07,08,09,10,11,15; neural noted as single conviction proxy; aux/metadata as simple proxies + HDBSCAN phylum).
- Structural layer intro: Clarified that only 8 structural slots are populated, full 12-field kline is used (via .get for quote_volume/taker_buy_base_volume), and all scaling from neural_slots.
- Added concise "**Current Implementation**" subsections after the ideal formulas for Slot_00, Slot_04, Slot_07, Slot_08, Slot_09, Slot_15 (and notes for 10/11 via the pattern).
- Neural 16–23 section: Added note that all 8 are currently the single `neural_conv` (L_p from compute_neural_conviction on causal slice + sovereign_ctx model load).
- Aux 24–27: Updated Slot_24/25/26/27 with the exact simple calculations from the dna_vector code (vol_delta, mfe_proxy = slot15*(factor + vol_spike*variation), etc.).
- Metadata 28–31: Updated each with current proxies (phylum is 0 in dna_vector but overlaid post-loop by HDBSCAN; recovery/mfe/neural proxies using neural expressions).
- New section at end: "## Current DNA Vector Construction (in reversal_signature_miner_sovereign.py)" with the exact code block that builds the 32-slot dict (after neural_conv, using dict(slots) + loops/proxies for 16-31) and includes it in the signature return (thus in every Parquet).

All updates are descriptive only. No code changes. No new inline literals in the spirit of the project (slot numbers are identifiers, as already present in the manual and code). References the actual use of full kline, neural_slots for params, slot_15 veto (enforced in miner before dna_vector), and the recent dna_vector + HDBSCAN additions.

**Result:** The manual now truthfully reflects the current (proxy-based but fully wired and causal) 32-slot DNA implementation instead of purely aspirational HYBRID-V5 formulas. Ideal formulas are preserved for reference.

**Validation (suggested):**
- `git diff slot_reference_manual.md` (or the generated diff.txt from the session).
- Re-run miner + inspect a signature: `python -c "import pandas as pd,glob; df=pd.read_parquet(glob.glob('data/signatures/individual/*_signature.parquet')[0]); print('dna_vector len:', len(df['dna_vector'].iloc[0]) if 'dna_vector' in df.columns else 0); print('has slot_00-31 + phylum overlay in parquet'); ..."`
- Cross-check against code in structural_engine.py:149 (return keys) and miner:69 (dna_vector build).

The slot reference manual is now synchronized with the live implementation (full kline in structural, explicit 32-slot dna_vector in signatures, post-hoc phylum, all from neural_slots/ctx, slot_15 absolute first).

**File:** This summary + the updated `slot_reference_manual.md`.

Task complete. (Smallest targeted doc updates only.)