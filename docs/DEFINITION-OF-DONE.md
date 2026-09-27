# Definition of done

The acceptance checklist from the project brief, with the status at hand-off and the
evidence an auditor can check. "Verified" means checked by running code in this repository,
not by reading it.

| # | Criterion | Status | Evidence / how to check |
|---|---|---|---|
| 1 | All eight builds are committed and the test suite passes in CI | **Met** | `git log --oneline` shows `Build 01` … `Build 08`; GitHub Actions workflow `CI` (`.github/workflows/ci.yml`) was green for every build commit (lint, config validation, full pytest suite, `make smoke`). Locally: `make test`. |
| 2 | `make smoke` runs end to end from a clean clone | **Met** | CI runs it on a fresh checkout with only the core environment (no PyTorch). Runtime in the build environment: about 40 s (4 cores). It includes the optional real-data subset only if Yahoo data are cached. |
| 3 | `make reproduce` works on the default config, or (if the network blocks it) has been verified on fixtures with the local command documented | **Met, via the fixture route** | Yahoo Finance and Hugging Face were blocked here. `make reproduce-fixtures` runs the default design unchanged except the data block (`configs/default_fixtures.yaml`, D-037): end to end in about 3 minutes, outputs in `results/default_fixtures/` and `reports/default_fixtures/`. Local command: `make install-tsfm && make fetch-data CONFIG=configs/default.yaml && make reproduce` (README, BUILD-REPORT). |
| 4 | Every number in RESULTS.md and the dashboard can be traced to a stored artifact with provenance | **Met** | Reports are rendered only from `results/<run>/stats/*.parquet` (each with embedded provenance: config hash, data hashes, package versions, git commit); RESULTS.md ends with a Provenance section listing every artifact and its SHA-256. `tests/test_reports.py` requires the committed smoke report to be byte-identical to a re-render of the committed artifacts; `tests/test_dashboard.py` checks the dashboard's embedded data equals the stored tables and that the page loads nothing external. |
| 5 | PREREGISTRATION.md exists, and any amendments are dated and justified | **Met** | `docs/PREREGISTRATION.md`, committed in Build 01 before any forecasting code existed; amendments A1 (effective release date), A2 (HAC kernel for overlapping targets, with the Monte Carlo that motivated it) and A3 (proxy-alignment constant), each dated with its reason and what had been seen at the time. |
| 6 | PRETRAINING-DATA.md is complete, with citations, and anything unverifiable is marked | **Met, with many items marked unverifiable** | `docs/PRETRAINING-DATA.md`: every claim carries a tag ([V-code], [V-repo], [S] search snippet only, [M] from memory, [UNVERIFIED]). Papers and model cards were unreachable from the build environment, so several items remain [S]/[M]/[UNVERIFIED]; section 5 lists what to check. |
| 7 | At least 10 lessons with checkers, flashcards and a common-errors section; `make doctor` and `make flashcards` work | **Met** | 11 lessons (`lessons/00-…` to `lessons/10-…`), each with README (time, "You'll be able to", "You need", common errors, next), notebook built from `lesson.py`, `checker.py`, `solution.py`, 6–9 flashcards. `tests/test_lessons.py` enforces the structure and a ≤ 650-word prose budget, executes every notebook with its solution, and checks every checker rejects the unsolved stub. `make doctor` and `make flashcards` are tested in `tests/test_doctor_flashcards.py`. |

## What "done" does **not** mean here

- No foundation model has been evaluated on real data, or with its real weights at all.
  The primary research question is **unanswered** by the committed results. All TSFM rows
  are marked UNAVAILABLE with the reason.
- The committed numbers are about synthetic fixtures. They show the pipeline works and
  behaves sensibly (e.g. GARCH wins on GARCH-generated series, HAR on HAR-generated ones);
  they are not evidence about markets.
