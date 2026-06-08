# KRONOS V1-ALT — Diff Files Folder + Move Summary

**Phase:** Identify folder for transient diff artifacts polluting root (current_diff.txt, diff*.txt, reorg_*.txt, struct_*.txt, manual_diff.txt, miner_diff.txt, final_diff.txt, inspect_diff.txt, structure_md_diff.txt etc.) and execute the move. Smallest supporting changes only.

**Scope (strict):** 
- Identified + moved only diff txt artifacts (no code, no params, no sovereign logic).
- ONLY edited .gitignore + README.md (smallest inserts for tree + ignore rule).
- No changes to any .py (config/, kronos_module/, scripts/, test_end_to_end.py), no import/path updates, no cfg, neural_slots, dual-mode, Option B, reversal miner, sovereign_ctx, slot_15 veto, dna_vector, HDBSCAN, 12-field kline, or compute paths.
- All prior sovereign constraints preserved exactly.

**Chosen folder (from root):** docs/diffs/

**Rationale (fits documented structure):**
- All KRONOS_V1_ALT_*_SUMMARY.md (reaudit, full kline, structural 00-15, HDBSCAN, 32-slot DNA, 10M bars, miner logging/validation, shard inspection, reorg, essential files, etc.) + slot_reference_manual.md live under docs/ after reorg.
- Transient precise diffs (the "output only precise diffs" + reorg response hunks, ~16 files) belong grouped with their accompanying summary MDs for traceability, not in root.
- Root stays pristine: only params_yaml.txt, README, .gitignore, requirements.txt, .env.example, test_end_to_end.py, config/, kronos_module/ (unchanged), scripts/, data/logs (ignored).
- Matches the note already present in docs/KRONOS_V1_ALT_GITIGNORE_README_STRUCTURE_SUMMARY.md ("suggest moving to docs/diffs/").
- .gitignore now covers docs/diffs/*.txt (under existing AI/refactoring session data pattern) so future emitted diffs won't re-pollute root. The dir itself can stay for organization.
- Prior KRONOS_V1_ALT_DIFF_FILES_FOLDER_SUGGESTION.md also moved into docs/diffs/ for completeness (was the record of the suggestion).

**Moved files (16 diff txts + 1 prior suggestion MD = 17 total in docs/diffs/):**
current_diff.txt
diff.txt
diff_ineff.txt
diff_miner.txt
diff_output.txt
diff_structural_miner.txt
final_diff.txt
inspect_diff.txt
manual_diff.txt
miner_diff.txt
reorg_diff.txt
reorg_essentials_diff.txt
reorg_names.txt
struct_diff.txt
structure_diff.txt
structure_md_diff.txt
KRONOS_V1_ALT_DIFF_FILES_FOLDER_SUGGESTION.md

(Validation post-move: root diff*.txt count = 0; docs/diffs/ count = 17.)

**Precise diffs (only .gitignore + README.md touched):**

```diff
diff --git a/.gitignore b/.gitignore
index 71bec0e..9b99cc5 100644
--- a/.gitignore
+++ b/.gitignore
@@ -45,0 +46,3 @@ __pycache__/
+# Surgical session diff artifacts (precise unified diffs from reorg/audit/slots/DNA/miner steps; co-located in docs/diffs/ with *_SUMMARY.md)
+docs/diffs/*.txt
+
```

```diff
diff --git a/README.md b/README.md
index 328fa72..edfec73 100644
--- a/README.md
+++ b/README.md
@@ -46,0 +47 @@ kronos_v1_alt/
+│   ├── diffs/                # precise diff txts from surgical steps (see .gitignore; reference with summaries)
```

(The full captured diff was also written to docs/diffs/structure_md_diff.txt during this step for the record.)

**Updated structure tree (README.md excerpt):**
```
├── docs/
│   ├── slot_reference_manual.md
│   ├── KRONOS_V1_ALT_*_SUMMARY.md
│   ├── diffs/                # precise diff txts from surgical steps (see .gitignore; reference with summaries)
│   └── ...
```

**.gitignore addition (excerpt):**
```
# AI / Refactoring session data (local only, not for version control)
.refact/

# Surgical session diff artifacts (precise unified diffs from reorg/audit/slots/DNA/miner steps; co-located in docs/diffs/ with *_SUMMARY.md)
docs/diffs/*.txt
```

**Validation (executed in session):**
- cd F:\kronos_v1_alt; New-Item ... docs/diffs/
- Move-Item of the 16 named diff txts → docs/diffs/
- Move of prior suggestion MD → docs/diffs/
- git diff --no-color -U0 -- .gitignore README.md | Out-File docs/diffs/structure_md_diff.txt
- Post-move: (Get-ChildItem -File -Name | Where diff*.txt).Count == 0
- docs/diffs/ ls count == 17
- No Python files touched → imports, E2E, miner, ingestion, structural slots, neural conviction, dna_vector, sovereign_ctx, Option B (discover from shards), slot_15 structural veto, etc. all unchanged and still functional.
- Root now contains only: params_yaml.txt, README.md, .gitignore, requirements.txt, .env.example, test_end_to_end.py, the 2 remaining phase MDs (REORG + ESSENTIAL — historical, not diff artifacts), plus runtime reports (full_shard_report.txt etc. — separate concern).
- All values continue to derive from params_yaml.txt via cfg/neural_slots/ctx. Zero new literals introduced.

**Notes:**
- The 16 diff txts are the exact "precise diffs" previously emitted as part of surgical responses (reorg, 10M vectorize, slots, DNA, miner logging, etc.) plus supporting structure/inspect diffs.
- If you want the historical diff hunks version-controlled alongside the summaries, `git add docs/diffs/` (they will be tracked even though *.txt rule exists — adjust .gitignore to `docs/diffs/` if you prefer never track contents).
- Future "give precise diffs" outputs should target docs/diffs/ directly or be moved post-generation.
- The three root KRONOS summary MDs from late phases can be moved to docs/ in a follow-up hygiene pass if desired (not part of this "diff files" request).

**File written:** `docs/KRONOS_V1_ALT_DIFF_FILES_MOVED_TO_DOCS_DIFFS_SUMMARY.md` (this document).

Task complete per strict rules. (ONLY .gitignore + README.md edited with smallest diffs; diff files moved to docs/diffs/ from root; no sovereign code or wiring touched; give summary md file as requested.)

**Sovereignty preserved:** dual-mode (individual primary + ablatable global prior), Option B real-shards-only, reversal miner with absolute slot_15 veto first, full 32-slot causal dna_vector, HDBSCAN phylum post-processing, 12-field kline via params kline_fields, neural L_p conviction, compute_slots_sovereign + miner, KronosPredictor(sovereign_ctx=...), E2E real asserts, all cfg-driven from params_yaml.txt v3.1, zero inline literals. Root hygiene only.