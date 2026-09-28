# Helper module loaded into the browser's Python (Pyodide) by the lesson runner.
# Keeps one namespace per lesson, returns results as plain dicts, captures matplotlib figures
# as PNG, and reports errors with the line number inside the learner's cell.
import base64
import contextlib
import importlib
import io
import os
import sys
import traceback

LESSON_DIR = "/home/pyodide/lesson"
NS = {"__name__": "__main__"}


def reset():
    global NS
    NS = {"__name__": "__main__"}
    os.makedirs(LESSON_DIR, exist_ok=True)
    os.chdir(LESSON_DIR)
    if LESSON_DIR not in sys.path:
        sys.path.insert(0, LESSON_DIR)
    sys.modules.pop("checker", None)
    importlib.invalidate_caches()
    _figures()


def _figures():
    plt = sys.modules.get("matplotlib.pyplot")
    if plt is None:
        return []
    out = []
    for num in plt.get_fignums():
        buf = io.BytesIO()
        plt.figure(num).savefig(buf, format="png", dpi=90, bbox_inches="tight")
        out.append(base64.b64encode(buf.getvalue()).decode("ascii"))
    plt.close("all")
    return out


def _error(e, filename):
    line = None
    if isinstance(e, SyntaxError) and e.filename == filename:
        line = e.lineno
    frames = [f for f in traceback.extract_tb(e.__traceback__) if f.filename == filename]
    if frames:
        line = frames[-1].lineno
    tb = traceback.format_exception(type(e), e, e.__traceback__)
    keep = [t for t in tb if "/lib/python" not in t or "tsfm_rc" in t or "checker" in t]
    msg = str(e)
    return {"type": type(e).__name__, "message": msg, "line": line, "traceback": "".join(keep)[-5000:]}


def _repr(v):
    try:
        import pandas as pd

        if isinstance(v, (pd.DataFrame, pd.Series)):
            return v.to_string(max_rows=60, max_cols=20)
    except Exception:
        pass
    r = repr(v)
    return r if len(r) < 20000 else r[:20000] + " …"


async def run(code, filename):
    from pyodide.code import eval_code_async

    try:
        value = await eval_code_async(code, NS, filename=filename)
        return {"ok": True, "value": None if value is None else _repr(value), "figures": _figures()}
    except BaseException as e:  # noqa: BLE001 - everything is reported to the learner
        return {"ok": False, "error": _error(e, filename), "figures": _figures()}


async def check(code, fn_name, checker_src):
    res = await run(code, "<checkpoint>")
    if not res["ok"]:
        return {**res, "passed": False}
    fn = NS.get(fn_name)
    if fn is None:
        err = {"type": "NameError", "message": f"name '{fn_name}' is not defined (keep the function name `{fn_name}`)",
               "line": None, "traceback": ""}
        return {"ok": False, "passed": False, "error": err, "figures": []}
    with open(os.path.join(LESSON_DIR, "checker.py"), "w", encoding="utf-8") as fh:
        fh.write(checker_src)
    sys.modules.pop("checker", None)
    importlib.invalidate_caches()
    buf = io.StringIO()
    try:
        import checker

        with contextlib.redirect_stdout(buf):
            checker.check(fn)
        out = buf.getvalue()
        return {"ok": True, "passed": "✅" in out, "output": out, "figures": _figures()}
    except BaseException as e:  # noqa: BLE001
        return {"ok": False, "passed": False, "output": buf.getvalue(), "error": _error(e, "<checkpoint>"), "figures": _figures()}
