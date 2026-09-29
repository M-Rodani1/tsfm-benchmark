# Screenshots of the study console

Taken with Playwright (Chromium) from the production build, by `node scripts/screenshots.mjs`
(run it from `site/` after `npm run build`). Names are `<state>-<width>-<theme>.png`: widths
1440×900, 1024×768 and 390×844, light and dark (`prefers-color-scheme`). Each shows the first
screen, as a visitor sees it without scrolling. The predict states are scrolled to the chart.
The progress in each state is imported through the site's own import (fixtures in the script).
The rules they show are in `site/DESIGN.md`.

| State | Files | What it shows |
|---|---|---|
| Home, fresh | `home-fresh-*` | After the tour: next is lesson 00, nothing started |
| Home, study running | `home-study-running-*` | Lessons 00–02 done, the laptop set up, `make reproduce` started 14:05 (self-reported), 4 cards due |
| Your path open at 390 | `home-study-running-rail-open-390-*` | The rail as a disclosure, opened |
| "It has finished" | `home-finished-dialog-*` | The paste check in a dialog |
| Home, results published | `home-published-SIMULATED-*` | **Simulated.** See below |
| Home, all done | `home-all-done-SIMULATED-*` | **Simulated.** See below |
| Lesson 02, chart question | `lesson-predict-1-before-*` (top of the step), `-1-before-scrolled-*`, `-2-selected-*`, `-3-correct-*`, `-4-incorrect-*` | Before a prediction, an option chosen (drawn dashed), after the check when right and when wrong (what happened drawn solid) |
| Your path | `your-path-*` | The whole route with the study running |
| Results | `results-*` | The committed synthetic fixture run |

**SIMULATED.** No real run of the study exists yet, so the *published* and *all done* states
of Home cannot occur on this site today. `node scripts/screenshots.mjs --simulated` builds a
copy of the site into a temporary folder, with a fake real `default` run added to its
build-time status ("SIMULATED for screenshots"). It then removes the folder, and the committed
data and the site are not changed. These screenshots show layout only. Their numbers (run
finished 13:10, 26 tickers, 3/3 models) are the fixture's, not results.
