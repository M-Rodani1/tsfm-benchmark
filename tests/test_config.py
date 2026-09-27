"""Config loading/validation and hashing."""

from __future__ import annotations

import copy

import pytest
import yaml
from pydantic import ValidationError

from tsfm_rc.config import RunConfig, config_hash, load_config
from tsfm_rc.paths import CONFIG_DIR


@pytest.mark.parametrize("name", ["smoke", "default", "full"])
def test_shipped_configs_validate(name):
    cfg = load_config(CONFIG_DIR / f"{name}.yaml")
    assert cfg.name == name
    assert cfg.targets.horizons == [1, 5, 20]
    assert len(config_hash(cfg)) == 64


def _raw(name="smoke"):
    with open(CONFIG_DIR / f"{name}.yaml") as fh:
        return yaml.safe_load(fh)


def test_hash_ignores_operational_fields_but_not_science():
    raw = _raw()
    a = RunConfig.model_validate(raw)
    b = RunConfig.model_validate({**raw, "n_jobs": 7, "output_dir": "elsewhere"})
    assert config_hash(a) == config_hash(b)
    raw2 = copy.deepcopy(raw)
    raw2["evaluation"]["stride"] = 3
    assert config_hash(RunConfig.model_validate(raw2)) != config_hash(a)


def test_default_preregistered_design():
    cfg = load_config(CONFIG_DIR / "default.yaml")
    assert cfg.models.context_length == 512
    assert cfg.evaluation.stride == 5
    assert cfg.evaluation.primary_window == "expanding"
    assert cfg.models.reference == {"returns": "zero", "rv": "har", "volume": "har"}
    assert {t.name for t in cfg.models.tsfms} == {
        "chronos_bolt_tiny",
        "timesfm_2p5_200m",
        "moirai_1p1_small",
    }
    assert len(cfg.data.tickers) == 26


@pytest.mark.parametrize(
    "mutate, msg",
    [
        (lambda r: r.update(unknown_key=1), "Extra inputs"),
        (lambda r: r["data"].update(end="2000-01-01"), "after data.start"),
        (lambda r: r["targets"].update(horizons=[1, 1]), "duplicate horizons"),
        (lambda r: r["targets"].update(horizons=[1, 100]), "out of scope"),
        (lambda r: r["evaluation"].update(stride=0), "greater than 0"),
        (lambda r: r["evaluation"].update(test_start="2030-01-01"), "test_start"),
        (lambda r: r.setdefault("models", {}).update(baselines={"returns": ["garch"], "rv": ["har"], "volume": ["har"]}), "not defined"),
        (lambda r: r["economic"].update(asset="NOPE"), "economic.asset"),
        (lambda r: r["data"].update(tickers=["A", "A"]), "duplicate tickers"),
    ],
)
def test_invalid_configs_rejected(mutate, msg):
    raw = copy.deepcopy(_raw())
    mutate(raw)
    with pytest.raises(ValidationError, match=msg):
        RunConfig.model_validate(raw)
