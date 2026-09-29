# Captured terminal output

Real output of the project's commands, used by `site/tests/cliparse.test.ts` to test the
checker behind the site's “Paste the output” boxes (`site/src/lib/cliparse.ts`), and by the
Playwright test that pastes a doctor success into the Phase 1 page.

All were captured on 2026-09-29 in the build container (Linux, Python 3.11.15, uv 0.8.17)
with `make <target> > file 2>&1`, from a clean checkout of `main`. That container cannot reach
Yahoo Finance or Hugging Face (egress policy), which is why several files show those failures.

| File | Command | What it shows |
|---|---|---|
| `doctor_offline.txt` | `make doctor` | everything installed; model weights not downloaded (`!`), real-data cache empty (`!`) |
| `doctor_online_blocked.txt` | `make doctor ONLINE=1` | the three weight downloads fail (`✗`, Hugging Face blocked), exit code 2 |
| `doctor_ok_staged_weights.txt` | `HF_HUB_CACHE=<staged> make doctor` | **the Phase 1 success case**: every check ✓ except the real-data cache, which Phase 2 fills |
| `doctor_no_uv.txt` | `env PATH=/usr/bin:/bin make doctor` | uv not on PATH: `make: uv: No such file or directory`, Error 127 |
| `doctor_not_in_repo.txt` | `make doctor` run in `/tmp` | `No rule to make target 'doctor'` |
| `fetch_data_blocked.txt` | `make fetch-data CONFIG=configs/default.yaml` | all 26 tickers `FAILED` (Yahoo blocked) |
| `reproduce_blocked.txt` | `make reproduce` | no market data: `[data] no data available; stopping.` |
| `reproduce_fixtures_ok.txt` | `make reproduce-fixtures` | a complete, successful pipeline run (the `default_fixtures` run: same code path as `make reproduce`) |
| `publish_synthetic_only.txt` | `make publish-results` | only synthetic runs exported |
| `make_test_ok.txt` | `make test` | `302 passed` |
| `pytest_failed.txt` | `uv run pytest tests/test_doctor_flashcards.py` with one fixture file altered | `1 failed, 2 passed` |

**Staged, not downloaded:** `doctor_ok_staged_weights.txt` is the real doctor's output, but
Hugging Face is unreachable here, so the three model repositories were placed in a temporary
Hugging Face cache (`HF_HUB_CACHE`) as empty stand-ins. The doctor only checks that they are
in the cache, which is what `make doctor ONLINE=1` leaves behind on a connected laptop.

**Derived in the tests, not captured:** the real study (`make reproduce`, run `default`) and a
real `make publish-results` cannot run here. The tests derive those cases from the captures
above by changing only the run name (`default_fixtures` → `default`), the `[tsfm] …` status
lines, or the publish label. The tests say so where they do it.
