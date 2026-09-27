"""Time-series foundation models behind the shared Forecaster interface.

Three backends, written against the package APIs verified at build time (see
docs/DECISIONS.md D-029):

- Chronos-Bolt  ``chronos.BaseChronosPipeline.from_pretrained(...).predict_quantiles``
                (chronos-forecasting 2.3.x); deterministic; 9 quantiles.
- TimesFM 2.5   ``timesfm.TimesFM_2p5_200M_torch.from_pretrained(...)`` + ``compile`` +
                ``forecast`` (timesfm 3.0.x); deterministic; output channel 0 = mean,
                1..9 = deciles 0.1..0.9 (channel 5 = median = point forecast).
- Moirai 1.1    ``uni2ts.model.moirai.MoiraiForecast`` with ``MoiraiModule.from_pretrained``
                (uni2ts 2.0.x); 100 sample paths -> empirical deciles; seeded per batch.

Weights are fetched with ``huggingface_hub.snapshot_download`` so the exact commit hash is
known and recorded. Any failure (package missing, no network, repository gone) raises
:class:`TSFMUnavailable` with a plain-English reason, and the model is reported as
UNAVAILABLE everywhere. No output of a model is ever invented.

Conversion to the target scale (PREREGISTRATION.md section 5.2), identical for all TSFMs:

- returns: input r_t;          h-step forecast = sum of per-step medians
- rv:      input ln(GK_t);     per step exp(m + s^2/2), s = (q0.9 - q0.1)/2.5631; mean over h
- volume:  input ln(V_t);      mean of per-step medians
"""

from __future__ import annotations

import abc
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from tsfm_rc.config import TSFMSpec
from tsfm_rc.data.targets import INPUT_COL
from tsfm_rc.models.base import Forecast, Forecaster, PointForecast, QuantileForecast

log = logging.getLogger(__name__)

DECILES = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
Z90 = 1.2815515655446004  # standard normal 0.9 quantile; 2*Z90 = 2.5631


class TSFMUnavailable(RuntimeError):
    """The model cannot be used here; the message says why in plain English."""


@dataclass
class BackendInfo:
    name: str
    family: str
    hf_id: str
    requested_revision: str
    resolved_revision: str = "unknown"
    weights_commit_date: str | None = None  # last commit touching the weight files
    package: str = ""
    package_version: str = "unknown"
    extra: dict = field(default_factory=dict)


class TSFMBackend(abc.ABC):
    """Maps a batch of 1-D contexts to per-step medians (B, S) and deciles (B, S, 9)."""

    info: BackendInfo

    @abc.abstractmethod
    def predict_batch(self, contexts: Sequence[np.ndarray], steps: int, seed: int = 0) -> tuple[np.ndarray, np.ndarray]: ...

    def context_length(self, base: int, max_horizon: int) -> int:
        """How many past observations this backend is given (see D-030 for Moirai)."""
        return base


# --------------------------------------------------------------- weight download


def _package_version(dist: str) -> str:
    from importlib import metadata

    try:
        return metadata.version(dist)
    except metadata.PackageNotFoundError as e:
        raise TSFMUnavailable(f"python package '{dist}' is not installed (run `make install-tsfm`)") from e


def fetch_weights(hf_id: str, revision: str) -> tuple[Path, str, str | None]:
    """Download (or find in the local HF cache) a model snapshot.

    Returns (local path, resolved commit hash, last commit date of the weight files or None).
    """
    try:
        from huggingface_hub import HfApi, snapshot_download
    except ImportError as e:  # pragma: no cover - huggingface_hub comes with the tsfm extra
        raise TSFMUnavailable("huggingface_hub is not installed (run `make install-tsfm`)") from e
    try:
        path = Path(snapshot_download(hf_id, revision=revision))
    except Exception as e:
        raise TSFMUnavailable(
            f"could not download '{hf_id}' from Hugging Face ({type(e).__name__}: {str(e)[:200]}). "
            "Check your internet connection / proxy, or pre-download with "
            f"`huggingface-cli download {hf_id}`."
        ) from e
    resolved = path.name  # snapshots/<commit sha>
    weights_date = None
    try:  # best effort: when did the weight files last change? (D-015 / amendment A1)
        files = HfApi().list_repo_tree(hf_id, revision=resolved, expand=True)
        dates = [
            f.last_commit.date
            for f in files
            if getattr(f, "last_commit", None) and str(f.path).endswith((".safetensors", ".bin", ".pt"))
        ]
        if dates:
            weights_date = max(dates).date().isoformat()
    except Exception as e:
        log.warning("%s: could not read weight commit dates (%s); using the release date", hf_id, e)
    return path, resolved, weights_date


# --------------------------------------------------------------- backends


class ChronosBoltBackend(TSFMBackend):
    def __init__(self, spec: TSFMSpec, pipeline=None):
        self.info = BackendInfo(spec.name, "chronos", spec.hf_id, spec.revision, package="chronos-forecasting")
        self.info.package_version = _package_version("chronos-forecasting")
        if pipeline is None:
            try:
                import torch
                from chronos import BaseChronosPipeline
            except ImportError as e:
                raise TSFMUnavailable(f"cannot import chronos/torch: {e}") from e
            path, self.info.resolved_revision, self.info.weights_commit_date = fetch_weights(spec.hf_id, spec.revision)
            pipeline = BaseChronosPipeline.from_pretrained(str(path), device_map="cpu", dtype=torch.float32)
        self.pipeline = pipeline

    def predict_batch(self, contexts, steps, seed=0):
        import torch

        q, _mean = self.pipeline.predict_quantiles(
            inputs=[torch.tensor(np.asarray(c, dtype=np.float32)) for c in contexts],
            prediction_length=steps,
            quantile_levels=list(DECILES),
        )
        q = q.detach().cpu().numpy().astype(float)  # (B, S, 9)
        return q[..., DECILES.index(0.5)], q


class TimesFMBackend(TSFMBackend):
    def __init__(self, spec: TSFMSpec, context_length: int, max_horizon: int, model=None):
        self.info = BackendInfo(spec.name, "timesfm", spec.hf_id, spec.revision, package="timesfm")
        self.info.package_version = _package_version("timesfm")
        try:
            import timesfm
        except ImportError as e:
            raise TSFMUnavailable(f"cannot import timesfm: {e}") from e
        if model is None:
            if not hasattr(timesfm, "TimesFM_2p5_200M_torch"):
                raise TSFMUnavailable("installed timesfm has no TimesFM_2p5_200M_torch (needs timesfm[torch] >= 2)")
            path, self.info.resolved_revision, self.info.weights_commit_date = fetch_weights(spec.hf_id, spec.revision)
            model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(str(path), torch_compile=False)
        max_ctx = int(np.ceil(context_length / 32) * 32)
        model.compile(
            timesfm.ForecastConfig(
                max_context=max_ctx,
                max_horizon=max(128, int(np.ceil(max_horizon / 128) * 128)),
                normalize_inputs=True,
                use_continuous_quantile_head=True,
                force_flip_invariance=True,
                infer_is_positive=True,
                fix_quantile_crossing=True,
                per_core_batch_size=spec.batch_size,
            )
        )
        self.model = model

    def predict_batch(self, contexts, steps, seed=0):
        point, full = self.model.forecast(horizon=steps, inputs=[np.asarray(c, dtype=float) for c in contexts])
        full = np.asarray(full, dtype=float)  # (B, S, 10): 0 = mean, 1..9 = deciles
        q = full[..., 1:10]
        return q[..., 4], q


class MoiraiBackend(TSFMBackend):
    def __init__(self, spec: TSFMSpec, context_length: int, max_horizon: int, module=None):
        self.info = BackendInfo(spec.name, "moirai", spec.hf_id, spec.revision, package="uni2ts")
        self.info.package_version = _package_version("uni2ts")
        try:
            from uni2ts.model.moirai import MoiraiForecast, MoiraiModule
        except ImportError as e:
            raise TSFMUnavailable(f"cannot import uni2ts: {e}") from e
        if module is None:
            path, self.info.resolved_revision, self.info.weights_commit_date = fetch_weights(spec.hf_id, spec.revision)
            module = MoiraiModule.from_pretrained(str(path))
        self.num_samples = spec.num_samples
        self.base_context = context_length
        self.max_horizon = max_horizon
        self.model = MoiraiForecast(
            module=module,
            prediction_length=max_horizon,
            context_length=context_length,
            patch_size="auto",
            num_samples=spec.num_samples,
            target_dim=1,
            feat_dynamic_real_dim=0,
            past_feat_dynamic_real_dim=0,
        ).eval()

    def context_length(self, base, max_horizon):
        # patch_size="auto" selects the patch size by validation loss on the last
        # `prediction_length` points, so the model is given base + max_horizon points (D-030)
        return base + max_horizon

    def predict_batch(self, contexts, steps, seed=0):
        import torch

        L = self.base_context + self.max_horizon
        B = len(contexts)
        target = np.zeros((B, L), dtype=np.float32)
        observed = np.zeros((B, L), dtype=bool)
        is_pad = np.ones((B, L), dtype=bool)
        for i, c in enumerate(contexts):
            c = np.asarray(c, dtype=np.float32)[-L:]
            target[i, L - len(c) :] = c
            observed[i, L - len(c) :] = True
            is_pad[i, L - len(c) :] = False
        torch.manual_seed(seed)
        with torch.no_grad():
            samples = self.model(
                past_target=torch.from_numpy(target)[..., None],
                past_observed_target=torch.from_numpy(observed)[..., None],
                past_is_pad=torch.from_numpy(is_pad),
            )
        s = samples.detach().cpu().numpy().astype(float)[:, :, :steps]  # (B, samples, S)
        q = np.moveaxis(np.quantile(s, DECILES, axis=1), 0, -1)  # (B, S, 9)
        return q[..., DECILES.index(0.5)], q


def load_backend(spec: TSFMSpec, context_length: int, max_horizon: int) -> TSFMBackend:
    """Instantiate a backend or raise TSFMUnavailable with the reason."""
    try:
        if spec.family == "chronos":
            return ChronosBoltBackend(spec)
        if spec.family == "timesfm":
            return TimesFMBackend(spec, context_length, max_horizon)
        if spec.family == "moirai":
            return MoiraiBackend(spec, context_length, max_horizon)
    except TSFMUnavailable:
        raise
    except Exception as e:  # anything unexpected while loading is also "unavailable", with reason
        raise TSFMUnavailable(f"failed to load {spec.hf_id}: {type(e).__name__}: {str(e)[:300]}") from e
    raise TSFMUnavailable(f"unknown TSFM family {spec.family}")


# --------------------------------------------------------------- conversion


def make_context(history: pd.DataFrame, kind: str, n: int) -> np.ndarray:
    """Last n values of the model-input series (causal forward-fill, leading NaNs dropped)."""
    x = history[INPUT_COL[kind]].to_numpy(dtype=float)
    first = np.flatnonzero(np.isfinite(x))
    if len(first) == 0:
        raise ValueError("empty context")
    x = pd.Series(x[first[0] :]).ffill().to_numpy()
    return x[-n:]


def to_target_scale(
    kind: str, median: np.ndarray, deciles: np.ndarray, horizons: Sequence[int]
) -> tuple[dict[int, float], np.ndarray]:
    """Convert per-step outputs (S,), (S, 9) to h-step point forecasts and h=1 deciles."""
    median = np.asarray(median, dtype=float)
    deciles = np.asarray(deciles, dtype=float)
    if kind == "returns":
        pts = {h: float(median[:h].sum()) for h in horizons}
        q1 = deciles[0]
    elif kind == "rv":
        s = (deciles[:, -1] - deciles[:, 0]) / (2.0 * Z90)
        per_step = np.exp(median + 0.5 * s**2)
        pts = {h: float(per_step[:h].mean()) for h in horizons}
        q1 = np.exp(deciles[0])  # quantiles are equivariant under the monotone exp
    elif kind == "volume":
        pts = {h: float(median[:h].mean()) for h in horizons}
        q1 = deciles[0]
    else:
        raise ValueError(kind)
    return pts, q1


class TSFMForecaster(Forecaster):
    """A TSFM behind the Forecaster interface (zero-shot: ``fit`` does nothing)."""

    kinds = ("returns", "rv", "volume")
    is_tsfm = True

    def __init__(self, kind: str, backend: TSFMBackend, context_length: int, seed: int = 0):
        super().__init__(kind, seed)
        self.backend = backend
        self.name = backend.info.name
        self.n_ctx = context_length

    def fit(self, history):
        self.fitted = True  # zero-shot

    def predict(self, history, horizons, quantile_levels=None):
        ctx = make_context(history, self.kind, self.n_ctx)
        med, dec = self.backend.predict_batch([ctx], max(horizons), seed=self.seed)
        pts, q1 = to_target_scale(self.kind, med[0], dec[0], horizons)
        qf = QuantileForecast(DECILES, {1: q1}) if quantile_levels and 1 in horizons else None
        return Forecast(PointForecast(pts), qf)
