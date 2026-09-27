"""Test-only TSFM helpers. NOTHING here is ever used to produce reported results.

``ToyBackend`` is a deterministic function of the context (a damped mean-reversion rule),
used to test the TSFM plumbing (caching, batching, conversion, leakage) without weights.
The random-initialisation factories build tiny *untrained* instances of the real library
models, only to check that our adapters call the real APIs correctly.
"""

from __future__ import annotations

import datetime as dt

import numpy as np

from tsfm_rc.config import TSFMSpec
from tsfm_rc.models.tsfm import DECILES, BackendInfo, TSFMBackend


class ToyBackend(TSFMBackend):
    def __init__(self, name: str = "toy"):
        self.info = BackendInfo(name, "toy", "test/toy", "main", resolved_revision="deadbeef", package="none", package_version="0")
        self.calls = 0
        self.n_series = 0

    def predict_batch(self, contexts, steps, seed=0):
        self.calls += 1
        self.n_series += len(contexts)
        med, dec = [], []
        z = np.array([-1.2816, -0.8416, -0.5244, -0.2533, 0.0, 0.2533, 0.5244, 0.8416, 1.2816])
        for c in contexts:
            c = np.asarray(c, dtype=float)
            mu, last, sd = c[-60:].mean(), c[-1], c[-60:].std() + 1e-6
            path = mu + (last - mu) * 0.8 ** np.arange(1, steps + 1)
            med.append(path)
            dec.append(path[:, None] + sd * z[None, :])
        return np.array(med), np.array(dec)


def spec(name: str, family: str, **kw) -> TSFMSpec:
    return TSFMSpec(name=name, family=family, hf_id="test/none", release_date=dt.date(2024, 11, 26), **kw)


def random_chronos_pipeline():
    import torch
    from chronos.chronos_bolt import ChronosBoltModelForForecasting, ChronosBoltPipeline
    from transformers import T5Config

    torch.manual_seed(0)
    cfg = T5Config(d_model=32, d_ff=64, num_layers=1, num_decoder_layers=1, num_heads=2, d_kv=16,
                   vocab_size=2, pad_token_id=0, eos_token_id=1, decoder_start_token_id=0)
    cfg.chronos_config = dict(context_length=512, input_patch_size=16, input_patch_stride=16,
                              prediction_length=64, quantiles=list(DECILES), use_reg_token=True)
    cfg.chronos_pipeline_class = "ChronosBoltPipeline"
    return ChronosBoltPipeline(model=ChronosBoltModelForForecasting(cfg).eval())


def random_moirai_module():
    import torch
    from uni2ts.distribution import (
        LogNormalOutput,
        MixtureOutput,
        NegativeBinomialOutput,
        NormalFixedScaleOutput,
        StudentTOutput,
    )
    from uni2ts.model.moirai import MoiraiModule

    torch.manual_seed(0)
    return MoiraiModule(
        distr_output=MixtureOutput([StudentTOutput(), NormalFixedScaleOutput(), NegativeBinomialOutput(), LogNormalOutput()]),
        d_model=64, num_layers=1, patch_sizes=(8, 16, 32, 64, 128), max_seq_len=512,
        attn_dropout_p=0.0, dropout_p=0.0, scaling=True,
    )
