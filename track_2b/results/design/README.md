# Design measurements

One-off measurements that decided how the spec was implemented. They are evidence for
`docs/decisions.md`, not part of the pipeline.

| File | What it is |
| --- | --- |
| `spec_measurements.py`, `.log` | Run on 2026-10-10 against an earlier revision of `src/` (the view then also carried the lowest valid slot over all modulations, and blocks were listed at the path's best modulation only). Seed 11, loads 150/270/390, teacher-driven, requests 300-999. Shows: our path-level BM-LS-KSP matched ONG's in 2,100 of 2,100 decisions; with best-modulation-only blocks the teacher's slot was off the list in 16-18 % of accepts; ONG's load-balancing heuristic picks a most-free-slots path 50-59 % of the time and a first-fit slot 74-79 %; how often each intent's admissible set is empty and how often it changes the decision. The script no longer runs as is; the log is its unedited output. |
| `teacher_variants.py`, `.json` | Closed-loop blocking (protocol window, loads 240 and 390, seeds 1-3) of ONG's BM-LS-KSP against two versions restricted to what the prompt lists: `strict` (blocks valid at the path's most efficient modulation) and `same` (blocks valid at any modulation needing the same number of slots). `same` was adopted: it differs from ONG in 0.05-0.2 % of decisions with the same blocking; `strict` differs in 11-15 % and blocks more. Run it with `PYTHONPATH=src uv run python results/design/teacher_variants.py out.json` (it still runs; `strict` is computed inside the script). |
