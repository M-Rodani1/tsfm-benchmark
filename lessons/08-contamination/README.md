# Lesson 08: Contamination and how our test works

⏱ **60 minutes** · Open `lesson.ipynb`, run top to bottom, answer each 🤔 first.

**You'll be able to:** explain memorisation risk, build clean / possibly-seen windows,
compute and read Δ, and state what the placebo and synthetic control can and cannot do.

**You need:** Lessons 05 and 07. Read `docs/PRETRAINING-DATA.md` section 4 alongside.

**Stuck on the checkpoint?** `solution.py`, but try for 10 minutes first.

## Common errors

| You see | Why | Fix |
|---|---|---|
| Everything labelled `gap` | Dates are strings, not timestamps | `pd.to_datetime(...)` first |
| Δ has the wrong sign | Computed seen − clean | Δ = ln R_clean − ln R_seen |
| Δ is `nan` / `flag = insufficient_data` | Fewer than 5 origins in a window | Normal for short windows; report it, do not invent |
| `KeyError: 'chronos_bolt_tiny'` | Used a config without that model | Use `configs/default.yaml` |

**Next:** Lesson 09 (reading and critiquing our results).
