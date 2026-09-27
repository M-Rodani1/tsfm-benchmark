# Pretraining data and release dates of the evaluated TSFMs

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
| Training volume | "nearly 100 billion time series observations" | [S] https://huggingface.co/amazon/chronos-bolt-tiny |
| Training corpus composition | Not enumerated in any source I could read | [UNVERIFIED] |
| Related: original Chronos corpus | Datasets used in pretraining that are also evaluated "in-domain": electricity_15min, electricity hourly/weekly, KDD Cup 2018, **M4 daily/hourly/monthly/weekly**, pedestrian counts, taxi_30min, Uber TLC hourly/daily, rideshare, temperature-rain, London smart meters; plus synthetic TSMixup and KernelSynth series | [V-code] `scripts/evaluation/configs/in-domain.yaml`, `scripts/README.md` in the GitHub repo; the equivalence "in-domain = in pretraining" is from the paper [M] (Ansari et al., TMLR 2024, arXiv:2403.07815) |
| Held out from original Chronos | Includes `exchange_rate`, `monash_fred_md`, M1/M3, tourism, M4 quarterly/yearly | [V-code] `scripts/evaluation/configs/zero-shot.yaml` |
| Financial exposure | Via M4 (the M4 competition includes a "Finance" domain of anonymised series) — **possible**; no US equity/ETF daily price series named in any readable source | [M] for M4 domains; [UNVERIFIED] for Bolt's corpus |
| Documented data cutoff | None found | — |

**Assessment.** Contamination with the specific assets studied here cannot be ruled out
(M4 finance series are anonymised and could include US stocks), nor confirmed.

## 2. TimesFM 2.5 (200M) — `google/timesfm-2.5-200m-pytorch`

| Item | Value | Tag / source |
|---|---|---|
| Release | **2025-09-15** ("TimesFM 2.5 is out!") | [V-repo] https://github.com/google-research/timesfm README, "Update - Sept. 15, 2025" |
| Size / context | 200M parameters, up to 16k context, optional 30M quantile head | [V-repo] same README; [V-code] `timesfm/timesfm_2p5/timesfm_2p5_base.py` (`context_limit = 16384`) |
| Training data (2.5 model card) | Wikimedia pageviews (cutoff Nov 2023), Google Trends top queries (cutoff end of 2022), synthetic and augmented data; "details in the paper" | [S] https://huggingface.co/google/timesfm-2.5-200m-pytorch |
| Training data (2.0 model card) | TimesFM 1.0 pretraining set plus a subset of LOTSA | [S] https://huggingface.co/google/timesfm-2.0-500m-pytorch |
| Training data (1.0 paper) | Google Trends, Wikipedia pageviews, synthetic series, and public datasets (M4, electricity, traffic, weather, Favorita sales, LibCity) | [M] Das et al., ICML 2024, arXiv:2310.10688 |
| Whether 2.5 includes LOTSA / M4 | Not stated in any source I could read | [UNVERIFIED] |
| Financial exposure | Possible via M4 and/or LOTSA (see §3) if included | [UNVERIFIED] |
| Documented data cutoff | Partial: Trends 2022, Wiki Nov 2023; not for all components | [S] |

**Assessment.** The partial cutoffs are *before* our clean window, but because the full
corpus is undocumented we use the release date, not the partial cutoffs.

## 3. Moirai 1.1-R (small) — `Salesforce/moirai-1.1-R-small`

| Item | Value | Tag / source |
|---|---|---|
| Release | **June 2024** ("Released Moirai-1.1-R model weights in small, base, and large"); exact day not given, so **2024-06-30** is used (latest possible day) | [V-repo] https://github.com/SalesforceAIResearch/uni2ts README, "What's New" |
| Size | ~14M parameters (Moirai-small) | [M] Woo et al., ICML 2024, arXiv:2402.02592 |
| Training data | LOTSA (Large-scale Open Time Series Archive), released together with Moirai 1.0-R | [V-repo] uni2ts README ("Release of Uni2TS library, along with Moirai Paper, Moirai-1.0-R Models, and LOTSA Data") |
| Is 1.1-R trained on the same LOTSA? | Not stated in the README | [UNVERIFIED] |
| LOTSA v1 contents | Builders for: Monash/GluonTS repository datasets (incl. **M1, M3, M4**, tourism, NN5, traffic, electricity, **`bitcoin`**, **`fred_md`**, CIF 2016, ...), BuildingsBench, CloudOps, CMIP6, ERA5, LargeST, LibCity, ProEnFo, SubseasonalClimateUSA and "others" (Favorita, KDD 2022, GoDaddy, air quality, ...) | [V-code] `uni2ts/data/builder/lotsa_v1/*.py` in uni2ts 2.0.0 |
| Individual US equity / ETF price series | None found by searching the builder code for stock, exchange, nasdaq, sp500, finance | [V-code] (absence of evidence in the builder code; M4's anonymised finance series remain possible) |
| Financial exposure | `bitcoin` (daily crypto metrics), `fred_md` (monthly US macro), M-competition finance/macro series | [V-code] names; [M] for M4 domains |
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
