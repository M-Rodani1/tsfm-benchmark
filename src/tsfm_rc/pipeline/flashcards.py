"""``make flashcards``: export every lesson's flashcards to one Anki-importable CSV.

Source: ``site/content/lessons/*/flashcards.yaml`` (the single source of the lessons; the
website adds the same cards to its review queue). Format: UTF-8 CSV, three columns ``front,back,tags`` (no header row, which is what Anki's
"Import File" expects by default). Tags are space-separated: ``tsfm_rc lesson_NN <slug>``.
In Anki: File → Import → choose the file → Type "Basic", Field separator "Comma",
map columns 1→Front, 2→Back, 3→Tags.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import yaml

from tsfm_rc.paths import ROOT

CONTENT_LESSONS = ROOT / "site" / "content" / "lessons"


def collect(lessons_dir: Path = CONTENT_LESSONS) -> list[tuple[str, str, str]]:
    cards = []
    for d in sorted(p for p in lessons_dir.iterdir() if p.is_dir() and re.match(r"^\d\d-", p.name)):
        f = d / "flashcards.yaml"
        if not f.exists():
            continue
        num, slug = d.name[:2], d.name[3:]
        for c in yaml.safe_load(f.read_text(encoding="utf-8")) or []:
            cards.append((str(c["q"]).strip(), str(c["a"]).strip(), f"tsfm_rc lesson_{num} {slug}"))
    return cards


def export(out: Path = ROOT / "flashcards.csv") -> Path:
    cards = collect()
    with open(out, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        w.writerows(cards)
    return out


def main() -> int:
    p = export()
    n = sum(1 for _ in open(p, encoding="utf-8"))
    print(f"wrote {n} flashcards to {p}")
    print("Anki: File → Import → flashcards.csv · Type: Basic · Separator: Comma · columns: Front, Back, Tags")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
