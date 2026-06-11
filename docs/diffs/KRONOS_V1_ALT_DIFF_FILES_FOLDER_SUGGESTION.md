# KRONOS V1-ALT — Suggested Folder for Root Diff Files

**Suggestion:** Move diff artifacts from root (current_diff.txt, diff*.txt, reorg_*.txt, struct_diff.txt, manual_diff.txt, miner_diff.txt, ~14 files from audits, reorgs, inefficiency fixes, etc.) to **docs/diffs/**.

**Rationale (sovereign/clean structure):**
- Fits the documented layout in KRONOS_V1_ALT_GITIGNORE_README_STRUCTURE_SUMMARY.md (docs/ for summaries, slot ref, audit MDs).
- Keeps root clean (only source, params, entry scripts, .gitignore, README).
- Transient audit diffs (not core code) can be .gitignored selectively if desired (e.g. add "docs/diffs/*.txt" or keep for history).
- Aligns with logs/ for reports (but docs/ better for MD/diff artifacts vs runtime logs).
- No impact on cfg, neural_slots, dual-mode, Option B, etc.

**Proposed addition to structure tree (under docs/):**
```
docs/
├── slot_reference_manual.md
├── KRONOS_V1_ALT_*_SUMMARY.md (all audit/reorg summaries)
├── diffs/   <--- suggested for root diff txts (current_diff.txt etc.)
│   └── *.txt
└── ...
```

**Next:** 
- mkdir docs/diffs (if adopting)
- git mv the diff txts (or rm if transient)
- Update .gitignore + this summary MD if needed.
- Re-run any audits to regenerate in new location if wanted.

This suggestion was added to the main structure summary MD via smallest diff.

**File:** KRONOS_V1_ALT_DIFF_FILES_FOLDER_SUGGESTION.md (this document).

(Precise diff for the update to the referenced MD is in structure_md_diff.txt from session.)