# TSFM Reality Check — common commands. Run `make help` for a list.
# Every command goes through `uv run`, so the locked environment (uv.lock) is always used.

UV      ?= uv
RUN     := $(UV) run
CONFIG  ?= configs/default.yaml

.PHONY: help install install-tsfm install-all test test-fast test-notebooks lint format \
        validate fixtures smoke fetch-data run report dashboard reproduce reproduce-fixtures \
        doctor flashcards lessons publish-results site site-test clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install core + dev dependencies from the lockfile (no PyTorch)
	$(UV) sync --frozen

install-tsfm:  ## Also install the foundation-model packages (PyTorch, ~6 GB)
	$(UV) sync --frozen --extra tsfm

install-all:  ## Core + TSFM + JupyterLab for the lessons
	$(UV) sync --frozen --extra tsfm --group learn

test:  ## Run the full test suite
	$(RUN) pytest

test-fast:  ## Skip slow tests and notebook execution
	$(RUN) pytest -m "not slow and not notebooks"

test-notebooks:  ## Execute every lesson notebook
	$(RUN) pytest -m notebooks

lint:  ## Static checks
	$(RUN) ruff check src tests lessons

format:  ## Auto-format
	$(RUN) ruff check --fix src tests lessons
	$(RUN) ruff format src tests

validate:  ## Validate all configs
	$(RUN) tsfm-rc validate configs/*.yaml

fixtures:  ## Regenerate the committed synthetic fixtures (deterministic)
	$(RUN) tsfm-rc fixtures

smoke:  ## End-to-end pipeline on committed synthetic fixtures (minutes, CPU)
	$(RUN) tsfm-rc all configs/smoke.yaml
	$(RUN) tsfm-rc all configs/smoke_real.yaml --skip-if-no-data

fetch-data:  ## Download raw data for CONFIG into the immutable cache (network)
	$(RUN) tsfm-rc fetch $(CONFIG)

run:  ## Run forecasts + statistics for CONFIG (uses cached data)
	$(RUN) tsfm-rc run $(CONFIG)

report:  ## Build reports/RESULTS.md and figures from stored results of CONFIG
	$(RUN) tsfm-rc report $(CONFIG)

dashboard:  ## Build the static dashboard from stored results of CONFIG
	$(RUN) tsfm-rc dashboard $(CONFIG)

reproduce:  ## Reproduce every result of the default study from raw data (network on first run)
	$(RUN) tsfm-rc all configs/default.yaml --fetch

reproduce-fixtures:  ## Same full default design, but on fixtures (verifies `reproduce` offline)
	$(RUN) tsfm-rc all configs/default_fixtures.yaml

doctor:  ## Check environment, data cache and model availability (ONLINE=1 also fetches weights)
	$(RUN) tsfm-rc doctor $(if $(ONLINE),--online,)

flashcards:  ## Export all lesson flashcards to an Anki-importable CSV
	$(RUN) tsfm-rc flashcards

lessons:  ## Regenerate lessons/ (notebooks, checkers, flashcards), site/content/doctor_fixes.json and lesson figures
	$(RUN) python lessons/_tools/build_notebooks.py
	$(RUN) python -c "from tsfm_rc.pipeline.doctor import write_fix_catalog; print('wrote', write_fix_catalog())"
	$(RUN) python -c "from tsfm_rc.learn import write_predict_figures; print('wrote', *write_predict_figures())"

publish-results:  ## Export stored statistics to versioned JSON for the website (then commit + push)
	$(RUN) tsfm-rc publish-results

site:  ## Build the website into site/dist (needs Node 22 + npm)
	cd site && npm ci && npm run build

site-test:  ## Website lint, unit tests and browser tests
	cd site && npm run lint && npm test && npm run e2e

clean:  ## Remove caches and results (NOT data/raw, NOT committed fixtures)
	rm -rf .pytest_cache .ruff_cache results/*/tmp
