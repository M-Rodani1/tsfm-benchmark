---
id: "09"
title: "Reading, and critiquing, our own results"
minutes: 60
objectives:
  - trace any number in the report back to the stored table it came from;
  - tell a *surviving* finding from one that only looked significant before correction;
  - tell an *absent* result from a *null* result;
  - run a critique checklist on any forecasting study, starting with this one.
prerequisites: ["06", "07", "08"]
you_need: "Lessons 06–08."
code_to_read: ["reports/RESULTS.md", "results/smoke/stats/*.parquet", "the Results page of this site"]
mounts: ["results:smoke"]
browser_note: "In the browser the tables come from the JSON that `make publish-results` exported from the stored Parquet files (the same numbers, checked by `tests/test_publish.py`)."
next: "10"
---

## The report and its tables

The report is *rendered* from stored tables, never typed. We load three of them for the
`smoke` run and print the top of its report.

```python
import pandas as pd

from tsfm_rc.learn import report_text, stats_table

dm_all = stats_table("smoke", "dm_all")
dm_primary = stats_table("smoke", "dm_primary")
mcs = stats_table("smoke", "mcs")
print(report_text("smoke")[:900])
```

The banner matters most: these are **synthetic** fixtures. Nothing here is about markets.

## Trace a number

The report lists `garch` vs `har` for rv. Find the same row in the stored table.

```predict
question: "If you edit a number in RESULTS.md by hand and re-render, what happens?"
options:
  - "Your edit stays"
  - "It is overwritten by the stored table's value"
answer: 1
explain: "The report is a pure function of the stored tables; a test even checks that re-rendering gives an identical file."
```

```python
row = dm_all.query("period == 'full' and window == 'expanding' and target == 'rv' and model == 'garch' and horizon == 5")
print(row[["rel_loss", "rel_loss_lo", "rel_loss_hi", "dm_stat", "p_value", "p_holm", "T"]].round(3).to_string(index=False))
```

## Raw vs corrected

```predict
question: "Of the tests with a raw p < 0.05, will all of them survive the Holm correction?"
options:
  - "Yes"
  - "No, some drop out"
answer: 1
explain: "Holm raises the bar for all but the very smallest p-values; borderline ones drop out."
```

```python
fam = dm_all.query("period == 'full' and window == 'expanding'")
raw = fam["p_value"] < 0.05
print(f"{raw.sum()} raw-significant, {fam['reject_holm'].sum()} survive Holm")
print(fam.loc[raw & ~fam["reject_holm"], ["target", "horizon", "model", "p_value", "p_holm"]].round(3).to_string(index=False))
```

Those rows are what a less careful study would have published.

## Absent is not null

```predict
question: "What does the primary table say about the foundation models in this run?"
options:
  - "They did not beat the baselines"
  - "They could not be evaluated (UNAVAILABLE)"
  - "They beat the baselines"
answer: 1
explain: "No weights could be loaded, so there is no evidence either way. Writing 'TSFMs did not beat the baselines' would be false."
```

```python
print(dm_primary["status"].value_counts())
```

## The MCS view

Instead of "who beat the reference?", the Model Confidence Set asks "who cannot be ruled out
as best?".

```python
print(mcs.query("period == 'full' and ticker == 'POOLED' and target == 'rv'")
      [["horizon", "model", "mean_loss", "mcs_pvalue", "in_mcs"]].round(3).to_string(index=False))
```

## A critique checklist

Ask these of *any* forecasting result, including ours: real or synthetic data, and which
period? Could any input come from after the origin? How many origins (T), any `small_sample`
flags? How many tests, and was the claim corrected? Is the CI narrow enough to matter? Could
the model have seen the test period? Does it hold with a rolling window?

```predict
question: "A paper reports one model beating 10 others at p = 0.03 and does not mention the other 9 comparisons. Which checklist item fails first?"
options:
  - "Leakage"
  - "Multiplicity"
  - "Contamination"
answer: 1
explain: "Ten comparisons were run, but the claim was not corrected for them."
```

The Results page of this site shows the same tables interactively.

## Checkpoint

Write `verdict(mean_diff, p_holm, alpha=0.05)` returning exactly the report's wording:
`"model better"`, `"model worse"`, or `"no detectable difference"`.

```checkpoint
```
