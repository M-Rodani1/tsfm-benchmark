---
id: "10"
title: "Writing it up as a short paper"
minutes: 90
objectives:
  - lay out a 4–6 page empirical paper and know what goes where;
  - write every result sentence with effect size, CI, *corrected* p-value and verdict;
  - generate those sentences from stored tables instead of typing numbers;
  - match each claim to the evidence that supports it (or not).
prerequisites: ["09"]
you_need: "Lesson 09."
code_to_read: ["paper_template.md (this lesson)", "reports/RESULTS.md", "docs/PREREGISTRATION.md"]
mounts: ["results:smoke"]
browser_note: "In the browser, the stored results in this lesson come from the JSON that `make publish-results` exported from the Parquet files (precomputed; the same numbers, checked by `tests/test_publish.py`). The notebook version reads the Parquet files directly."
assets: ["paper_template.md"]
next: null
---

## The shape of the paper

Two rules make it honest. **Methods before results, written as pre-registered**, with every
amendment reported and dated. **Results in the order of the pre-registration**: primary
family first, whatever it says.

```python
import pandas as pd

from tsfm_rc.learn import stats_table
from tsfm_rc.reports.fmt import ci, fp

dm_all = stats_table("smoke", "dm_all")
dm_primary = stats_table("smoke", "dm_primary")
print(open("paper_template.md", encoding="utf-8").read()[:1200])
```

## One sentence per result, generated

A result sentence needs the comparison, the effect size with its CI, the corrected p-value
and a verdict.

```predict
question: "For `garch` vs `har` (rv, h = 5, full period) the point estimate says GARCH's loss is clearly lower. Will the verdict be \"model better\"?"
options:
  - "Yes: its loss is lower"
  - "No: no detectable difference"
answer: 1
explain: "Look at the printed sentence: the 95% CI of the relative loss includes 1 and the Holm-adjusted p is far above 0.05. A large-looking effect that the data cannot separate from luck."
```

```python
def sentence(r) -> str:
    verdict = ("model better" if r.mean_diff < 0 else "model worse") if r.reject_holm else "no detectable difference"
    return (f"{r.model} vs {r.reference} ({r.target}, h={r.horizon}): relative loss "
            f"{ci(r.rel_loss, r.rel_loss_lo, r.rel_loss_hi)}, Holm p = {fp(r.p_holm)}: {verdict}.")

row = dm_all.query("period == 'full' and window == 'expanding' and model == 'garch' and target == 'rv' and horizon == 5").iloc[0]
print(sentence(row))
```

Because the text is produced from the table, a re-run can never leave a stale number in your
paper.

## Absent results get a sentence too

```predict
question: "What should the paper say about the TSFMs in *this* (synthetic, offline) run?"
options:
  - "TSFMs did not beat the baselines"
  - "The TSFMs could not be evaluated, with the reason"
answer: 1
explain: "Without model outputs there is no evidence either way; the paper must say the tests could not be run, and why."
```

```python
n_unavail = (dm_primary["status"] == "UNAVAILABLE").sum()
print(f"{n_unavail} of {len(dm_primary)} primary tests could not be run (model weights unavailable).")
```

## Claims vs evidence

For each draft claim, find the row that supports it. If there is none, delete the claim.

```python
claims = {
    "GARCH beats HAR for 5-day volatility (full period)": ("rv", 5, "garch"),
    "Seasonal naive is worse than HAR for volume at h=20": ("volume", 20, "seasonal_naive"),
}
fam = dm_all.query("period == 'full' and window == 'expanding'")
for claim, (target, horizon, model) in claims.items():
    r = fam[(fam.target == target) & (fam.horizon == horizon) & (fam.model == model)].iloc[0]
    print(f"{'SUPPORTED  ' if r.reject_holm else 'UNSUPPORTED'} | {claim} | Holm p = {fp(r.p_holm)}")
```

Before you submit: the data section says real or synthetic, the period, the universe *and* its
survivorship bias; every model that could not run is named, with the reason; every p-value in
the abstract is a corrected one; related work you cite, you have read.

## Checkpoint

Write `my_sentence(r)` that returns exactly the same text as `sentence(r)` above, for any
row of `dm_all` (use `ci` and `fp`).

```checkpoint
```
