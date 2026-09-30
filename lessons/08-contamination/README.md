<!-- GENERATED from site/content/lessons/08-contamination by `make lessons`: edit the source, not this file. -->
# Lesson 08: Contamination, and how our test works

⏱ **60 minutes** · Best on the website (Lessons → 08); offline: open `lesson.ipynb`, run top to bottom, answer each 🤔 first.

**You'll be able to:** explain why a model that saw the test period during pretraining can look too good; build "possibly seen" and "clean" windows from release dates; compute the contamination statistic Δ and read its CI; say what the placebo and the synthetic control add, and what they cannot fix.

**You need:** Lessons 05 and 07. (Prerequisites: Lesson 05, Lesson 07.)

**Stuck on the checkpoint?** Hints, in order:

1. First compute each window's ratio of *total* losses: R = sum(model) / sum(reference).
2. Δ is the clean log-ratio minus the seen log-ratio.
3. `np.log(np.sum(m_clean) / np.sum(ref_clean)) - np.log(np.sum(m_seen) / np.sum(ref_seen))`

The full solution is `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| Everything labelled `gap` | Dates are strings, not timestamps. | `pd.to_datetime(...)` first. |
| Checker: "Sign flipped" | Computed seen − clean. | Δ = ln R_clean − ln R_seen. |
| Checker: "ratio of SUMS" | Averaged per-day ratios. | Use total losses: `np.sum(m) / np.sum(ref)`. |
| `KeyError: 'chronos_bolt_tiny'` | Used a config without that model. | Use `configs/default.yaml`. |

**Next:** Lesson 09 (Reading, and critiquing, our own results).
