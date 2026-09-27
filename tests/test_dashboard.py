"""Static dashboard: self-contained, faithful to stored tables, valid JavaScript, renders."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from tsfm_rc.paths import RESULTS_DIR
from tsfm_rc.reports.dashboard import build_dashboard

CHROME = next((p for p in [Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome"), shutil.which("chromium")] if p and Path(p).exists()), None)
needs_results = pytest.mark.skipif(not (RESULTS_DIR / "smoke" / "stats").exists(), reason="run `make smoke` first")


@pytest.fixture(scope="module")
def page(tmp_path_factory) -> tuple[Path, str]:
    out = tmp_path_factory.mktemp("dash") / "index.html"
    build_dashboard(RESULTS_DIR, out)
    return out, out.read_text(encoding="utf-8")


def _payload(html: str) -> dict:
    m = re.search(r'<script type="application/json" id="tsfm-data">(.*?)</script>', html, re.S)
    return json.loads(m.group(1).replace("<\\/", "</"))


@needs_results
def test_self_contained_no_external_resources(page):
    _, html = page
    assert not re.search(r"<script[^>]+src=", html)
    assert not re.search(r"<link[^>]+href=", html)
    assert "@import" not in html and not re.search(r"url\(\s*['\"]?https?:", html)
    assert not re.search(r"\bfetch\(|XMLHttpRequest|import\(", html)  # no network calls from the page


@needs_results
def test_payload_matches_stored_tables(page):
    _, html = page
    data = _payload(html)
    runs = {r["run"]: r for r in data["runs"]}
    assert "smoke" in runs
    dm = pd.read_parquet(RESULTS_DIR / "smoke" / "stats" / "dm_all.parquet")
    assert len(runs["smoke"]["dm"]) == len(dm)
    for rec, row in zip(runs["smoke"]["dm"], dm.itertuples(index=False), strict=True):
        assert rec["model"] == row.model and rec["horizon"] == row.horizon
        assert rec["rel_loss"] == pytest.approx(row.rel_loss, rel=1e-5)
        assert rec["p_holm"] == pytest.approx(row.p_holm, rel=1e-5, abs=1e-12)
    series = pd.read_parquet(RESULTS_DIR / "smoke" / "stats" / "loss_diff_series.parquet")
    k0, d0 = runs["smoke"]["series"]["keys"][0], runs["smoke"]["series"]["data"][0]
    s = series[(series.target == k0["target"]) & (series.horizon == k0["horizon"]) & (series.window == k0["window"])
               & (series.model == k0["model"]) & (series.ticker == k0["ticker"])].sort_values("origin")
    assert d0["y"] == pytest.approx(s["cum_diff"].tolist(), rel=1e-4, abs=1e-9)  # precomputed, not recomputed


@needs_results
def test_javascript_parses(page, tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    _, html = page
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    assert len(scripts) == 1
    js = tmp_path / "app.js"
    js.write_text(scripts[0], encoding="utf-8")
    res = subprocess.run([node, "--check", str(js)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


@needs_results
@pytest.mark.slow
@pytest.mark.skipif(CHROME is None, reason="no headless Chromium available")
def test_renders_in_headless_browser(page):
    path, _ = page
    res = subprocess.run(
        [str(CHROME), "--headless=new", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=8000", "--dump-dom", path.as_uri()],
        capture_output=True, text=True, timeout=120,
    )
    dom = res.stdout
    assert '<path d="M' in dom  # the time-series chart was drawn from the embedded data
    assert 'class="cell c-' in dom  # the DM/MCS matrix was drawn
    assert "Synthetic fixture data" in dom
