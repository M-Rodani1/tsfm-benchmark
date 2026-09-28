# Pretraining data and release dates of the evaluated TSFMs

## Verification checklist (do this before writing up)

Every claim below that was **not** verified against a primary source, i.e. tagged [S]
(search snippet only), [M] (from memory of the paper) or [UNVERIFIED]. Tick each one after
checking it against the paper or model card, and replace its tag in the tables with [V-card] /
[V-paper] plus the exact URL, section and date read. The last column says what changes in
the study if the claim turns out to be wrong.

| ✓ | # | Model | Claim (tag) | Check against | If wrong |
|---|---|---|---|---|---|
| [ ] | C1 | Chronos-Bolt | Trained on "nearly 100 billion time series observations" [S] | Model card https://huggingface.co/amazon/chronos-bolt-tiny | Description only |
| [ ] | C2 | Chronos-Bolt | Composition of the Bolt training corpus is not enumerated anywhere [UNVERIFIED] | Model card; Chronos-Bolt release notes/blog; any Bolt technical report | Contamination assessment (§1) |
| [ ] | C3 | Chronos (original) | "In-domain" benchmark datasets = datasets in the pretraining corpus [M] | Ansari et al., TMLR 2024, arXiv:2403.07815 (benchmark section) | Which public datasets count as seen |
| [ ] | C4 | Chronos, TimesFM, Moirai | The M4 competition includes an anonymised "Finance" domain (daily series among them) [M] | Makridakis, Spiliotis & Assimakopoulos, IJF 2020 (M4 paper); M4 metadata file | Financial-exposure rows of §1–3 |
| [ ] | C5 | Chronos-Bolt | Financial exposure of Bolt's corpus (e.g. via M4) [UNVERIFIED] | Model card / report of C2 | §1 assessment |
| [ ] | T1 | TimesFM 2.5 | Training data: Wikimedia pageviews (cutoff Nov 2023), Google Trends top queries (cutoff end 2022), synthetic and augmented data [S] | Model card https://huggingface.co/google/timesfm-2.5-200m-pytorch | §2; partial cutoffs |
| [ ] | T2 | TimesFM 2.0 | 2.0 = TimesFM 1.0 data plus a subset of LOTSA [S] | Model card https://huggingface.co/google/timesfm-2.0-500m-pytorch | Whether LOTSA (M4, bitcoin, fred_md) is in the lineage |
| [ ] | T3 | TimesFM 1.0 | Trained on Google Trends, Wikipedia pageviews, synthetic series and public datasets incl. M4, electricity, traffic, weather, Favorita, LibCity [M] | Das et al., ICML 2024, arXiv:2310.10688 (data section) | §2 |
| [ ] | T4 | TimesFM 2.5 | Whether 2.5's corpus includes LOTSA and/or M4 [UNVERIFIED] | Model card of 2.5, TimesFM 2.5 release notes | §2 financial exposure |
| [ ] | T5 | TimesFM 2.5 | Financial exposure via M4/LOTSA [UNVERIFIED] | Result of T4 | §2 assessment |
| [ ] | T6 | TimesFM 2.5 | Only partial data cutoffs are documented (Trends 2022, Wiki Nov 2023) [S] | Model card (as T1) | None for the windows: they use the release date, not these cutoffs |
| [ ] | M1 | Moirai small | About 14M parameters [M] | Woo et al., ICML 2024, arXiv:2402.02592; model card https://huggingface.co/Salesforce/moirai-1.1-R-small | Description only |
| [ ] | M2 | Moirai 1.1-R | 1.1-R was trained on the same LOTSA corpus as 1.0-R [UNVERIFIED] | Model card of 1.1-R; uni2ts release notes | §3 corpus rows |
| [ ] | M3 | Moirai 1.1-R | Release day: the README says only "June 2024", so 2024-06-30 (latest possible day) is used | Model card history / first commit of the weights on Hugging Face | Clean-window start; already guarded by amendment A1 (weight-file commit dates) |
| [ ] | R1 | — | "Re(Visiting) Time Series Foundation Models in Finance", arXiv:2511.18578: found by search, **not read** | The paper | Related work (lesson 10) |
| [ ] | R2 | — | "Pretrained Time-Series Foundation Models for Financial Return Forecasting", arXiv:2606.27100: found by search, **not read** | The paper | Related work (lesson 10) |

`tests/test_utils.py::test_pretraining_checklist_covers_every_unverified_tag` fails if a
new [S]/[M]/[UNVERIFIED] claim is added to the tables below without a checklist row.

---

**Why this file exists.** A foundation model may have seen public financial series during
pretraining. If it did, good test scores on those periods could reflect memorisation.
This file records what is *documented* about each model's pretraining data and release,
and how firmly we could verify it. It feeds the clean / possibly-seen windows
(`src/tsfm_rc/contamination/windows.py`, PREREGISTRATION.md section 9 and amendment A1).

**How it was researched (2026-09-27).** In the build environment, `huggingface.co`
(model cards), `arxiv.org`, `openreview.net`, `proceedings.mlr.press` and the vendors'
blogs were blocked by the network policy; GitHub and PyPI were reachable, and a web
search tool returned result snippets. Every claim is therefore tagged:

| Tag | Meaning |
|---|---|
| **[V-code]** | Verified by reading source code or configuration shipped in the package/repository |
| **[V-repo]** | Verified by reading the official GitHub README (URL given, read on 2026-09-27) |
| **[S]** | Seen only as a web-search snippet of the cited page; the page itself was *not* retrieved |
| **[M]** | From the authors' paper as I recall it; **not re-checked** here |
| **[UNVERIFIED]** | Could not be verified at all |

**Rule actually used** (independent of the unverifiable details): data after a model's
public release cannot be in its pretraining set. The *possibly-seen* window contains
targets that ended before the effective release date; the *clean* window starts 30 days
after it. Effective release = max(documented release date, last commit date of the weight
files at the downloaded revision), per amendment A1.

---

## 1. Chronos-Bolt (tiny) — `amazon/chronos-bolt-tiny`

| Item | Value | Tag / source |
|---|---|---|
| Release | **2024-11-26** ("Chronos-Bolt models released on HuggingFace") | [V-repo] https://github.com/amazon-science/chronos-forecasting README, News |
| Size | 9M parameters | [V-repo] same README, model table |
| Architecture | Patch-based T5 encoder-decoder, direct multi-step quantile output (0.1…0.9) | [V-repo] README; [V-code] `chronos/chronos_bolt.py` (chronos-forecasting 2.3.2) |
| Training volume (C1) | "nearly 100 billion time series observations" | [S] https://huggingface.co/amazon/chronos-bolt-tiny |
| Training corpus composition (C2) | Not enumerated in any source I could read | [UNVERIFIED] |
| Related: original Chronos corpus (C3) | Datasets used in pretraining that are also evaluated "in-domain": electricity_15min, electricity hourly/weekly, KDD Cup 2018, **M4 daily/hourly/monthly/weekly**, pedestrian counts, taxi_30min, Uber TLC hourly/daily, rideshare, temperature-rain, London smart meters; plus synthetic TSMixup and KernelSynth series | [V-code] `scripts/evaluation/configs/in-domain.yaml`, `scripts/README.md` in the GitHub repo; the equivalence "in-domain = in pretraining" is from the paper [M] (Ansari et al., TMLR 2024, arXiv:2403.07815) |
| Held out from original Chronos | Includes `exchange_rate`, `monash_fred_md`, M1/M3, tourism, M4 quarterly/yearly | [V-code] `scripts/evaluation/configs/zero-shot.yaml` |
| Financial exposure (C4, C5) | Via M4 (the M4 competition includes a "Finance" domain of anonymised series) — **possible**; no US equity/ETF daily price series named in any readable source | [M] for M4 domains; [UNVERIFIED] for Bolt's corpus |
| Documented data cutoff | None found | — |

**Assessment.** Contamination with the specific assets studied here cannot be ruled out
(M4 finance series are anonymised and could include US stocks), nor confirmed.

## 2. TimesFM 2.5 (200M) — `google/timesfm-2.5-200m-pytorch`

| Item | Value | Tag / source |
|---|---|---|
| Release | **2025-09-15** ("TimesFM 2.5 is out!") | [V-repo] https://github.com/google-research/timesfm README, "Update - Sept. 15, 2025" |
| Size / context | 200M parameters, up to 16k context, optional 30M quantile head | [V-repo] same README; [V-code] `timesfm/timesfm_2p5/timesfm_2p5_base.py` (`context_limit = 16384`) |
| Training data (2.5 model card) (T1) | Wikimedia pageviews (cutoff Nov 2023), Google Trends top queries (cutoff end of 2022), synthetic and augmented data; "details in the paper" | [S] https://huggingface.co/google/timesfm-2.5-200m-pytorch |
| Training data (2.0 model card) (T2) | TimesFM 1.0 pretraining set plus a subset of LOTSA | [S] https://huggingface.co/google/timesfm-2.0-500m-pytorch |
| Training data (1.0 paper) (T3) | Google Trends, Wikipedia pageviews, synthetic series, and public datasets (M4, electricity, traffic, weather, Favorita sales, LibCity) | [M] Das et al., ICML 2024, arXiv:2310.10688 |
| Whether 2.5 includes LOTSA / M4 (T4) | Not stated in any source I could read | [UNVERIFIED] |
| Financial exposure (T5) | Possible via M4 and/or LOTSA (see §3) if included | [UNVERIFIED] |
| Documented data cutoff (T6) | Partial: Trends 2022, Wiki Nov 2023; not for all components | [S] |

**Assessment.** The partial cutoffs are *before* our clean window, but because the full
corpus is undocumented we use the release date, not the partial cutoffs.

## 3. Moirai 1.1-R (small) — `Salesforce/moirai-1.1-R-small`

| Item | Value | Tag / source |
|---|---|---|
| Release (M3) | **June 2024** ("Released Moirai-1.1-R model weights in small, base, and large"); exact day not given, so **2024-06-30** is used (latest possible day) | [V-repo] https://github.com/SalesforceAIResearch/uni2ts README, "What's New" |
| Size (M1) | ~14M parameters (Moirai-small) | [M] Woo et al., ICML 2024, arXiv:2402.02592 |
| Training data | LOTSA (Large-scale Open Time Series Archive), released together with Moirai 1.0-R | [V-repo] uni2ts README ("Release of Uni2TS library, along with Moirai Paper, Moirai-1.0-R Models, and LOTSA Data") |
| Is 1.1-R trained on the same LOTSA? (M2) | Not stated in the README | [UNVERIFIED] |
| LOTSA v1 contents | Builders for: Monash/GluonTS repository datasets (incl. **M1, M3, M4**, tourism, NN5, traffic, electricity, **`bitcoin`**, **`fred_md`**, CIF 2016, ...), BuildingsBench, CloudOps, CMIP6, ERA5, LargeST, LibCity, ProEnFo, SubseasonalClimateUSA and "others" (Favorita, KDD 2022, GoDaddy, air quality, ...) | [V-code] `uni2ts/data/builder/lotsa_v1/*.py` in uni2ts 2.0.0 |
| Individual US equity / ETF price series | None found by searching the builder code for stock, exchange, nasdaq, sp500, finance | [V-code] (absence of evidence in the builder code; M4's anonymised finance series remain possible) |
| Financial exposure (C4) | `bitcoin` (daily crypto metrics), `fred_md` (monthly US macro), M-competition finance/macro series | [V-code] names; [M] for M4 domains |
| Documented data cutoff | None | — |

**Assessment.** LOTSA is the most auditable corpus of the three (this is why the 1.1
checkpoint was preferred over Moirai 2.0, whose corpus includes non-public Salesforce data;
see DECISIONS.md D-005). No named US equity series, but anonymised M4 finance series are
possible.

---

## 4. Summary used by the code

| Model | Release used | Clean window starts | Possibly-seen targets end before |
|---|---|---|---|
| chronos_bolt_tiny | 2024-11-26 | 2024-12-26 | 2024-11-26 |
| timesfm_2p5_200m | 2025-09-15 | 2025-10-15 | 2025-09-15 |
| moirai_1p1_small | 2024-06-30 | 2024-07-30 | 2024-06-30 |
| **Common clean window** (all three) | | **2025-10-15** | |

These dates are in `configs/default.yaml` and are moved later automatically if the
downloaded weight files turn out to have been committed after the release date
(`model_status.json` records the revision and weight commit date of every run).

## 5. What would strengthen this file

- Read the four papers and three model cards directly and replace every [S]/[M] tag.
- Check whether Chronos-Bolt's and TimesFM 2.5's corpora include M4 daily and LOTSA.
- Check the M4 daily finance series' date ranges against our "possibly seen" window.

Related work found by search but **not read** (to read before writing up, lesson 10):
"Re(Visiting) Time Series Foundation Models in Finance" (arXiv:2511.18578) and
"Pretrained Time-Series Foundation Models for Financial Return Forecasting" (arXiv:2606.27100).
