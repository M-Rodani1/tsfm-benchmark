"""Run configuration: YAML files validated with pydantic.

Every experiment is fully described by one YAML file in ``configs/``. The validated
config is hashed (``config_hash``) and that hash is stored next to every result, so a
result can always be traced back to the exact settings that produced it.

The *design* choices encoded in the defaults below are pre-registered in
``docs/PREREGISTRATION.md``. Changing them for the ``default`` config requires a dated
amendment in that file.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator

from tsfm_rc.hashing import sha256_json
from tsfm_rc.paths import resolve

TargetKind = Literal["returns", "rv", "volume"]
TARGET_KINDS: tuple[str, ...] = ("returns", "rv", "volume")

# Which baseline may be used for which target. Kept here (not in the model registry)
# so the config can be validated without importing heavy model code.
BASELINES_BY_TARGET: dict[str, tuple[str, ...]] = {
    "returns": ("zero", "hist_mean", "ar_bic", "lgbm"),
    "rv": ("ewma", "garch", "gjr_garch", "har", "lgbm"),
    "volume": ("seasonal_naive", "ar_bic", "har", "lgbm"),
}
TSFM_FAMILIES = ("chronos", "timesfm", "moirai")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DataConfig(_Strict):
    provider: Literal["fixture", "yfinance", "csv"]
    tickers: list[str] = Field(min_length=1)
    start: dt.date
    end: dt.date
    raw_dir: Path = Path("data/raw")
    fixture_file: Path | None = None
    csv_dir: Path | None = None
    # Largest plausible |daily log return| before a row is flagged as a suspect split.
    split_suspect_threshold: float = 0.35

    @model_validator(mode="after")
    def _check(self) -> DataConfig:
        if self.end <= self.start:
            raise ValueError("data.end must be after data.start")
        if self.provider == "fixture" and self.fixture_file is None:
            raise ValueError("provider 'fixture' requires data.fixture_file")
        if self.provider == "csv" and self.csv_dir is None:
            raise ValueError("provider 'csv' requires data.csv_dir")
        if len(set(self.tickers)) != len(self.tickers):
            raise ValueError("duplicate tickers in data.tickers")
        return self


class TargetConfig(_Strict):
    kinds: list[TargetKind] = Field(default_factory=lambda: list(TARGET_KINDS))
    horizons: list[PositiveInt] = Field(default_factory=lambda: [1, 5, 20])
    rv_estimator: Literal["garman_klass"] = "garman_klass"

    @field_validator("horizons")
    @classmethod
    def _sorted_unique(cls, v: list[int]) -> list[int]:
        if len(set(v)) != len(v):
            raise ValueError("duplicate horizons")
        if max(v) > 64:
            raise ValueError("horizons above 64 trading days are out of scope")
        return sorted(v)


class EvaluationConfig(_Strict):
    test_start: dt.date
    stride: PositiveInt = 5
    min_train_obs: PositiveInt = 1000
    windows: list[Literal["expanding", "rolling"]] = Field(
        default_factory=lambda: ["expanding", "rolling"]
    )
    rolling_length: PositiveInt = 1000
    primary_window: Literal["expanding"] = "expanding"
    # Amendment A4: the primary family and the clean side of the contamination test use
    # origins every `primary_stride` trading days inside each TSFM's clean window.
    primary_stride: PositiveInt = 1

    @model_validator(mode="after")
    def _check(self) -> EvaluationConfig:
        if self.primary_window not in self.windows:
            raise ValueError("primary_window must be one of evaluation.windows")
        return self


class TSFMSpec(_Strict):
    name: str
    family: Literal["chronos", "timesfm", "moirai"]
    hf_id: str
    revision: str = "main"
    # Public release date of this checkpoint (see docs/PRETRAINING-DATA.md).
    release_date: dt.date
    # Latest date of any documented pretraining data. None = not documented.
    documented_data_cutoff: dt.date | None = None
    enabled: bool = True
    batch_size: PositiveInt = 64
    num_samples: PositiveInt = 100  # only used by sample-based models (Moirai 1.x)


class LGBMParams(_Strict):
    n_estimators: PositiveInt = 200
    learning_rate: float = 0.05
    num_leaves: PositiveInt = 15
    min_child_samples: PositiveInt = 50
    subsample: float = 0.8
    subsample_freq: int = 1
    colsample_bytree: float = 0.8
    reg_lambda: float = 1.0


class ModelsConfig(_Strict):
    baselines: dict[TargetKind, list[str]] = Field(
        default_factory=lambda: {k: list(v) for k, v in BASELINES_BY_TARGET.items()}
    )
    # Pre-registered reference baseline per target (primary comparisons).
    reference: dict[TargetKind, str] = Field(
        default_factory=lambda: {"returns": "zero", "rv": "har", "volume": "har"}
    )
    # Naive model used for the out-of-sample R^2 (Campbell-Thompson style).
    r2_benchmark: dict[TargetKind, str] = Field(
        default_factory=lambda: {"returns": "hist_mean", "rv": "ewma", "volume": "seasonal_naive"}
    )
    tsfms: list[TSFMSpec] = Field(default_factory=list)
    context_length: PositiveInt = 512
    # Re-fit schedule in units of forecast origins (1 = re-fit at every origin).
    refit_every: dict[str, PositiveInt] = Field(
        default_factory=lambda: {"garch": 4, "gjr_garch": 4, "lgbm": 50}
    )
    ar_max_lag: PositiveInt = 10
    ewma_lambda: float = 0.94
    lgbm: LGBMParams = Field(default_factory=LGBMParams)

    @model_validator(mode="after")
    def _check(self) -> ModelsConfig:
        for kind, names in self.baselines.items():
            allowed = BASELINES_BY_TARGET[kind]
            for n in names:
                if n not in allowed:
                    raise ValueError(f"baseline '{n}' is not defined for target '{kind}'")
        for kind, ref in self.reference.items():
            if ref not in self.baselines.get(kind, []):
                raise ValueError(f"reference '{ref}' for '{kind}' must be in baselines[{kind}]")
        for kind, ref in self.r2_benchmark.items():
            if ref not in self.baselines.get(kind, []):
                raise ValueError(f"r2_benchmark '{ref}' for '{kind}' must be in baselines[{kind}]")
        names = [t.name for t in self.tsfms]
        if len(set(names)) != len(names):
            raise ValueError("duplicate TSFM names")
        if not 0.0 < self.ewma_lambda < 1.0:
            raise ValueError("ewma_lambda must be in (0, 1)")
        return self


class StatsConfig(_Strict):
    alpha: float = 0.05
    mcs_alpha: float = 0.10
    n_bootstrap: PositiveInt = 1000
    quantile_levels: list[float] = Field(
        default_factory=lambda: [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    )
    mcs_statistic: Literal["Tmax", "TR"] = "Tmax"

    @field_validator("quantile_levels")
    @classmethod
    def _q(cls, v: list[float]) -> list[float]:
        if any(not 0 < q < 1 for q in v):
            raise ValueError("quantile levels must be in (0, 1)")
        return sorted(v)


class ContaminationConfig(_Strict):
    enabled: bool = True
    # Calendar days after the release date before the "clean" window starts.
    buffer_days: int = 30
    # Baseline pairs used as placebo (they cannot have memorised anything).
    placebo_pairs: dict[TargetKind, list[str]] = Field(
        default_factory=lambda: {"returns": ["ar_bic"], "rv": ["garch"], "volume": ["ar_bic"]}
    )


class EconomicConfig(_Strict):
    enabled: bool = True
    asset: str = "SPY"
    horizon: PositiveInt = 5
    target_vol_annual: float = 0.10
    max_leverage: float = 2.0
    cost_bps: float = 5.0


class SyntheticControlConfig(_Strict):
    enabled: bool = True
    n_series: PositiveInt = 10
    n_days: PositiveInt = 3000
    test_days: PositiveInt = 1000
    intraday_steps: PositiveInt = 390
    horizons: list[PositiveInt] = Field(default_factory=lambda: [1, 5, 20])


class RunConfig(_Strict):
    name: str
    description: str = ""
    seed: int = 20260927
    n_jobs: int = 1
    output_dir: Path = Path("results")
    cache_dir: Path = Path("cache")
    data: DataConfig
    targets: TargetConfig = Field(default_factory=TargetConfig)
    evaluation: EvaluationConfig
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    stats: StatsConfig = Field(default_factory=StatsConfig)
    contamination: ContaminationConfig = Field(default_factory=ContaminationConfig)
    economic: EconomicConfig = Field(default_factory=EconomicConfig)
    synthetic: SyntheticControlConfig = Field(default_factory=SyntheticControlConfig)

    @model_validator(mode="after")
    def _check(self) -> RunConfig:
        if not (self.data.start < self.evaluation.test_start < self.data.end):
            raise ValueError("evaluation.test_start must lie strictly inside [data.start, data.end]")
        if self.economic.enabled and self.economic.asset not in self.data.tickers:
            raise ValueError(f"economic.asset '{self.economic.asset}' is not in data.tickers")
        if self.economic.enabled and self.economic.horizon not in self.targets.horizons:
            raise ValueError("economic.horizon must be one of targets.horizons")
        for kind in self.targets.kinds:
            if kind not in self.models.baselines:
                raise ValueError(f"no baselines configured for target '{kind}'")
        return self

    # ------------------------------------------------------------------ helpers
    @property
    def run_dir(self) -> Path:
        return resolve(self.output_dir) / self.name

    def enabled_tsfms(self) -> list[TSFMSpec]:
        return [t for t in self.models.tsfms if t.enabled]

    def as_dict(self) -> dict:
        return self.model_dump(mode="json")


def load_config(path: str | Path, **overrides: object) -> RunConfig:
    """Load and validate a YAML config. ``overrides`` replace top-level keys."""
    p = resolve(path)
    with open(p, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ValueError(f"config {p} is not a mapping")
    raw.update(overrides)
    return RunConfig.model_validate(raw)


# Operational fields that cannot change any number (parallelism, where files go).
_NON_SCIENTIFIC_FIELDS = ("n_jobs", "output_dir", "cache_dir", "description")


def config_hash(cfg: RunConfig) -> str:
    """SHA-256 of the canonical JSON form of the validated config.

    Operational fields (``n_jobs``, output locations, free-text description) are
    excluded so the hash identifies the *scientific* content of the run.
    """
    d = cfg.as_dict()
    for k in _NON_SCIENTIFIC_FIELDS:
        d.pop(k, None)
    return sha256_json(d)
