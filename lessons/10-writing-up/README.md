<!-- GENERATED from site/content/lessons/10-writing-up by `make lessons`: edit the source, not this file. -->
# Lesson 10: Writing it up as a short paper

⏱ **90 minutes** · Best on the website (Lessons → 10); offline: open `lesson.ipynb`, run top to bottom, answer each 🤔 first.

**You'll be able to:** lay out a 4–6 page empirical paper and know what goes where; write every result sentence with effect size, CI, *corrected* p-value and verdict; generate those sentences from stored tables instead of typing numbers; match each claim to the evidence that supports it (or not).

**You need:** Lesson 09. (Prerequisites: Lesson 09.)

**Stuck on the checkpoint?** Hints, in order:

1. Start with the verdict: `reject_holm` decides whether there is a finding, the sign of `mean_diff` its direction.
2. The rest is one f-string: model, reference, target, horizon, then `ci(r.rel_loss, r.rel_loss_lo, r.rel_loss_hi)` and `fp(r.p_holm)`.
3. Copy the pattern of `sentence` character by character, including `: ` before the verdict and the final full stop.

The full solution is `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| Checker shows a one-character difference | Spacing or punctuation differs. | Copy the f-string pattern exactly, including the final full stop. |
| `NameError: name 'ci' is not defined` | The helper was not imported in this session. | Run the lesson's first code cell. |
| Your claim is "UNSUPPORTED" | The evidence is not there. | Delete or weaken the claim; don't hunt for another test. |

**Next:** run the real study (`make reproduce`) and draft your paper.
