// The "Paste the output" checks, tested on real captured output of the project's commands
// (tests/fixtures/cli, see its README for how each file was captured).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import contentJson from "../src/generated/content.json";
import { checkPublish, checkSetup, checkStudy, checkTests, parseDoctor, parseFetch, parsePipeline, parsePublish, parsePytest, pythonError } from "../src/lib/cliparse";
import type { ContentBundle } from "../src/lib/types";

const errors = (contentJson as unknown as ContentBundle).errors;
const cap = (name: string) => readFileSync(join(__dirname, "fixtures", "cli", name), "utf8");

describe("make doctor ONLINE=1 (Phase 1)", () => {
  it("parses every check line and its → fix", () => {
    const d = parseDoctor(cap("doctor_offline.txt"));
    expect(d.checks).toHaveLength(24); // Python, uv, 10 packages, lock, fixtures, cache, 4 TSFM packages, 3 weights, results, lessons
    expect(d.checks[0]).toEqual({ status: "OK", name: "Python", detail: "3.11.15 (/home/user/tsfm-benchmark/.venv/bin/python3)" });
    expect(d.checks.find((c) => c.name === "installed = locked")?.detail).toBe("core numeric packages match uv.lock");
    const cache = d.checks.find((c) => c.name === "real-data cache")!;
    expect(cache.status).toBe("WARN");
    expect(cache.fix).toMatch(/^Only needed for the real study/);
    expect(d.summary).toBe("warnings-only");
    expect(d.online).toBe(false);
  });

  it("accepts the success case: no ✗, weights present, only the real-data cache still empty", () => {
    const r = checkSetup(cap("doctor_ok_staged_weights.txt"), errors);
    expect(r.verdict).toBe("success");
    expect(r.problems).toEqual([]);
    expect(r.detail).toBe("24 checks: 23 ✓, 1 !, 0 ✗");
    // pasted from a Windows terminal (CRLF) or with colour codes: same result
    expect(checkSetup(cap("doctor_ok_staged_weights.txt").replace(/\n/g, "\r\n")).verdict).toBe("success");
    const esc = String.fromCharCode(27);
    const coloured = cap("doctor_ok_staged_weights.txt").replace(/ (OK|WARN) /g, ` ${esc}[32m$1${esc}[0m `);
    expect(coloured).not.toBe(cap("doctor_ok_staged_weights.txt"));
    expect(checkSetup(coloured).verdict).toBe("success");
  });

  it("rejects the doctor without ONLINE=1: weights not downloaded", () => {
    const r = checkSetup(cap("doctor_offline.txt"), errors);
    expect(r.verdict).toBe("failure");
    expect(r.summary).toMatch(/run `make doctor ONLINE=1`/);
    expect(r.problems.map((p) => p.title)).toEqual(["! weights chronos_bolt_tiny", "! weights timesfm_2p5_200m", "! weights moirai_1p1_small"]);
  });

  it("rejects failed weight downloads and shows the doctor's own fix", () => {
    const r = checkSetup(cap("doctor_online_blocked.txt"), errors);
    expect(r.verdict).toBe("failure");
    expect(r.summary).toMatch(/3 problem\(s\)/);
    expect(r.problems).toHaveLength(3);
    expect(r.problems[0].title).toBe("✗ weights chronos_bolt_tiny");
    expect(r.problems[0].fix).toBe("Check your internet connection/proxy; the model will be reported UNAVAILABLE until this works.");
    expect(parseDoctor(cap("doctor_online_blocked.txt")).online).toBe(true);
  });

  it("explains shell-level failures: uv missing, wrong folder", () => {
    const noUv = checkSetup(cap("doctor_no_uv.txt"), errors);
    expect(noUv.verdict).toBe("failure");
    expect(noUv.problems[0].title).toMatch(/uv is not installed/);
    const folder = checkSetup(cap("doctor_not_in_repo.txt"), errors);
    expect(folder.verdict).toBe("failure");
    expect(folder.problems[0].fix).toMatch(/cd tsfm-benchmark/);
  });

  it("does not mark anything done on unrelated text", () => {
    expect(checkSetup("hello world").verdict).toBe("unrecognised");
    expect(checkSetup(cap("make_test_ok.txt")).verdict).toBe("unrecognised");
  });
});

describe("make fetch-data / make reproduce (Phase 2)", () => {
  it("recognises a complete pipeline run, but not of another config", () => {
    const text = cap("reproduce_fixtures_ok.txt");
    const p = parsePipeline(text);
    expect(p).toMatchObject({ config: "configs/default_fixtures.yaml", run: "default_fixtures", provider: "fixture", tickersLoaded: 5,
      tickersUnavailable: 0, evaluated: true, reported: true, dashboard: true, noData: false });
    expect(p.models.map((m) => [m.name, m.available])).toEqual([["chronos_bolt_tiny", false], ["timesfm_2p5_200m", false], ["moirai_1p1_small", false]]);
    const r = checkStudy(text, errors);
    expect(r.verdict).toBe("failure");
    expect(r.summary).toMatch(/not of the real study/);
  });

  it("accepts the real study (`default`), and warns about UNAVAILABLE models", () => {
    // Derived from the real capture: only the run name differs (the real study cannot run here).
    const text = cap("reproduce_fixtures_ok.txt").replace(/default_fixtures/g, "default");
    const r = checkStudy(text, errors);
    expect(r.verdict).toBe("success");
    expect(r.summary).toMatch(/3 foundation model\(s\) were UNAVAILABLE/);
    expect(r.problems).toHaveLength(3);
    // ... and with every model available (derived: the three [tsfm] status lines changed)
    const ok = text.replace(/^\[tsfm\] (\w+): UNAVAILABLE: .*$/gm, "[tsfm] $1: AVAILABLE");
    const r2 = checkStudy(ok, errors);
    expect([r2.verdict, r2.problems]).toEqual(["success", []]);
    expect(r2.detail).toBe("run default: 5 tickers, 3/3 models available");
  });

  it("rejects a run without market data, and a failed download", () => {
    const r = checkStudy(cap("reproduce_blocked.txt"), errors);
    expect(r.verdict).toBe("failure");
    expect(r.summary).toMatch(/No market data/);
    const f = parseFetch(cap("fetch_data_blocked.txt"));
    expect([f.ok.length, f.failed.length, f.summaryFailed]).toEqual([0, 26, 26]);
    expect(f.failed[0].ticker).toBe("SPY");
    expect(f.failed[0].reason).toMatch(/^SPY: yfinance download failed: ConnectionError: .*CONNECT tunnel failed, response 403/);
    expect(f.failed[25]).toEqual({ ticker: "SHW", reason: "SHW: yfinance download failed: YFTzMissingError: $SHW: possibly delisted; no timezone found" });
    const r2 = checkStudy(cap("fetch_data_blocked.txt"), errors);
    expect(r2.verdict).toBe("failure");
    expect(r2.summary).toBe("26 ticker(s) failed to download (all of them).");
    expect(r2.problems[0].fix).toMatch(/offline or Yahoo is blocking/);
  });

  it("a successful download alone is progress, not the finished study", () => {
    // Built from cli.py's own format string f"{t:6s} {s}" (no real download is possible here).
    const text = "uv run tsfm-rc fetch configs/default.yaml\nSPY    ok 2014-01-02..2026-09-25 (3203 rows, sha256 0123456789ab)\nQQQ    ok 2014-01-02..2026-09-25 (3203 rows, sha256 ba9876543210)\n";
    const r = checkStudy(text, errors);
    expect(r.verdict).toBe("partial");
    expect(r.summary).toMatch(/Now start the study: `make reproduce`/);
  });

  it("an unfinished run is progress, not success", () => {
    const text = cap("reproduce_fixtures_ok.txt").replace(/default_fixtures/g, "default").split("[evaluate]")[0];
    expect(checkStudy(text, errors).verdict).toBe("partial");
  });
});

describe("make publish-results (Phase 5)", () => {
  it("synthetic-only exports do not count", () => {
    const text = cap("publish_synthetic_only.txt");
    expect(parsePublish(text)).toEqual({ noRealRun: true, runs: [
      { run: "default_fixtures", version: "ee685506f0c0", real: false }, { run: "smoke", version: "ba09b3b967ba", real: false }] });
    const r = checkPublish(text, errors);
    expect(r.verdict).toBe("failure");
    expect(r.summary).toMatch(/Only synthetic runs/);
  });

  it("a real export says to push; the step completes only when the site shows it", () => {
    // Derived: the label of a real run, exactly as cli.py prints it (`e["label"] or "real data"`).
    const text = cap("publish_synthetic_only.txt")
      .replace("[publish] default_fixtures: version ee685506f0c0 (SYNTHETIC — not research results)", "[publish] default: version 0123456789ab (real data)")
      .replace(/^\[publish\] no real-data run published yet.*\n/m, "");
    const r = checkPublish(text, errors);
    expect(r.verdict).toBe("partial");
    expect(r.summary).toMatch(/commit and push/);
  });
});

describe("make test (Phase 7)", () => {
  it("accepts a green suite and rejects a red one", () => {
    const ok = parsePytest(cap("make_test_ok.txt"));
    expect([ok.found, ok.passed, ok.failed]).toEqual([true, 302, 0]);
    expect(checkTests(cap("make_test_ok.txt")).verdict).toBe("success");
    const bad = parsePytest(cap("pytest_failed.txt"));
    expect([bad.passed, bad.failed, bad.failedTests]).toEqual([2, 1, ["tests/test_doctor_flashcards.py::test_doctor_runs_and_reports_fixes"]]);
    const r = checkTests(cap("pytest_failed.txt"));
    expect(r.verdict).toBe("failure");
    expect(r.problems[0].title).toBe("tests/test_doctor_flashcards.py::test_doctor_runs_and_reports_fixes");
    expect(checkTests(cap("doctor_offline.txt")).verdict).toBe("unrecognised");
  });
});

describe("Python errors are explained with site/content/errors.yaml", () => {
  it("uses the lesson runner's explanation for the last exception of a traceback", () => {
    // Constructed: the shape of any Python traceback (no real one is among the captures).
    const tb = "Traceback (most recent call last):\n  File \"x.py\", line 1, in <module>\n    import torch\nModuleNotFoundError: No module named 'torch'\n";
    const p = pythonError(tb, errors)!;
    expect(p.title).toBe("Python stopped with an error: ModuleNotFoundError: No module named 'torch'");
    expect(p.fix).toMatch(/make install-all/);
  });
});
